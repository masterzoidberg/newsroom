from __future__ import annotations

import pytest

from newsroom import storage
from newsroom.domain import CoreService, DomainValidation
from newsroom.jobs import (
    BudgetService,
    JobConflict,
    JobService,
    SchedulerService,
)
from newsroom.migrations import apply_migrations, migration_status
from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.worker import RetryableJobFailure, WorkerProcess
from fastapi.testclient import TestClient


PASSWORD = "a-long-test-password-12345"
T0 = "2026-08-16T12:00:00Z"
T1 = "2026-08-16T12:00:20Z"
T2 = "2026-08-16T12:01:00Z"


def _policy_and_monitor(db_path, *, target_id="src_1", next_check_at=T0, cadence=60):
    conn = storage.connect(db_path)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO monitoring_policies
                    (id, name, allowed_channels, base_cadence_seconds,
                     min_cadence_seconds, max_cadence_seconds, created_at, updated_at)
                VALUES (?, ?, '[]', ?, ?, ?, ?, ?)
                """,
                ("pol_1", "Test policy", cadence, cadence, cadence * 10, T0, T0),
            )
            conn.execute(
                """
                INSERT INTO monitors
                    (id, target_type, target_id, policy_id, enabled,
                     next_check_at, created_at, updated_at)
                VALUES ('mon_1', 'source', ?, 'pol_1', 1, ?, ?, ?)
                """,
                (target_id, next_check_at, T0, T0),
            )
    finally:
        conn.close()


def test_phase07_migration_adds_budget_and_scheduler_state_idempotently(tmp_db):
    assert apply_migrations(tmp_db).applied_versions == (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)
    assert apply_migrations(tmp_db).applied_versions == ()
    assert migration_status(tmp_db) == (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)

    conn = storage.connect(tmp_db)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {"budget_limits", "budget_reservations", "scheduler_state"} <= tables
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
        assert {"run_id", "cancel_requested_at"} <= columns
    finally:
        conn.close()


def test_enqueue_is_idempotent_and_claim_is_transactional(tmp_db):
    apply_migrations(tmp_db)
    service = JobService(tmp_db, lease_seconds=30)
    first = service.enqueue(
        "source_check",
        {"source_id": "src_1"},
        idempotency_key="monitor:mon_1:2026-08-16T12:00:00Z",
        max_attempts=2,
    )
    duplicate = service.enqueue(
        "source_check",
        {"source_id": "src_1", "different": True},
        idempotency_key="monitor:mon_1:2026-08-16T12:00:00Z",
        max_attempts=5,
    )
    assert duplicate["id"] == first["id"]
    assert duplicate["payload"] == {"source_id": "src_1"}

    claimed = service.claim(first["id"], "worker-a", now=T0)
    assert claimed["status"] == "running"
    assert claimed["attempts"] == 1
    assert service.claim(first["id"], "worker-b", now=T0) is None

    with pytest.raises(JobConflict):
        service.complete(first["id"], "worker-b", "succeeded", now=T0)


def test_expired_lease_is_recovered_and_retry_is_bounded(tmp_db):
    apply_migrations(tmp_db)
    service = JobService(tmp_db, lease_seconds=10, backoff_base_seconds=20)
    job = service.enqueue("flaky", {}, max_attempts=2)
    service.claim(job["id"], "worker-a", now=T0)

    recovered = service.recover_expired(now=T1)
    assert recovered == 1
    state = service.get(job["id"])
    assert state["status"] == "queued"
    assert state["failure_cause"] == "lease_expired"
    assert state["attempts_detail"][0]["error_code"] == "lease_expired"

    assert service.claim(job["id"], "worker-b", now=T1) is None
    claimed = service.claim(job["id"], "worker-b", now=T2)
    assert claimed["attempts"] == 2
    retry = service.complete(
        job["id"], "worker-b", "failed", error_code="fixture_failure", retryable=True, now=T2
    )
    assert retry["status"] == "failed"
    assert retry["failure_cause"] == "fixture_failure"
    assert len(retry["attempts_detail"]) == 2


def test_cancellation_is_terminal_and_rerun_creates_new_idempotent_work(tmp_db):
    apply_migrations(tmp_db)
    service = JobService(tmp_db)
    queued = service.enqueue("queued", {})
    assert service.cancel(queued["id"], reason="user_request")["status"] == "cancelled"

    running = service.enqueue("running", {})
    service.claim(running["id"], "worker-a", now=T0)
    requested = service.cancel(running["id"], reason="user_request")
    assert requested["cancel_requested_at"] is not None
    completed = service.complete(running["id"], "worker-a", "succeeded", now=T0)
    assert completed["status"] == "cancelled"

    rerun = service.rerun(running["id"])
    assert rerun["id"] != running["id"]
    assert rerun["status"] == "queued"
    assert rerun["payload"] == {}


def test_scheduler_tick_advances_due_monitor_once_and_creates_run(tmp_db):
    apply_migrations(tmp_db)
    source = CoreService(tmp_db).create_source({"name": "Scheduled", "slug": "scheduled"})
    _policy_and_monitor(tmp_db, target_id=source["id"])

    scheduler = SchedulerService(tmp_db)
    first = scheduler.tick(now=T0)
    second = scheduler.tick(now=T0)
    assert len(first["job_ids"]) == 1
    assert second["job_ids"] == []
    assert first["run_id"]

    queue = JobService(tmp_db)
    queue.claim(first["job_ids"][0], "worker-a", now=T0)
    queue.complete(first["job_ids"][0], "worker-a", "succeeded", now=T1)
    assert queue.get_run(first["run_id"])["status"] == "success"

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1
        next_check = conn.execute("SELECT next_check_at FROM monitors WHERE id = 'mon_1'").fetchone()[0]
        assert next_check == "2026-08-16T12:01:00Z"
    finally:
        conn.close()


def test_budget_reservation_and_actual_usage_stop_paid_dispatch(tmp_db):
    apply_migrations(tmp_db)
    budgets = BudgetService(tmp_db)
    budgets.set_paid_enabled(True)
    budgets.configure_limit("global", None, "daily", "paid_requests", 1)
    budgets.configure_limit("global", None, "daily", "usd", 0.05)

    service = JobService(tmp_db, budget_service=budgets)
    first = service.enqueue("paid_search", {"budget": {"paid_requests": 1, "usd": 0.04}})
    second = service.enqueue("paid_search", {"budget": {"paid_requests": 1, "usd": 0.04}})
    claimed = service.claim(first["id"], "worker-a", now=T0)
    assert claimed["status"] == "running"
    assert service.claim(second["id"], "worker-b", now=T0) is None
    assert service.get(second["id"])["failure_cause"] == "budget_exhausted"

    budgets.record_usage(
        job_id=first["id"],
        capability="search",
        provider="fixture",
        request_type="paid_search",
        paid_requests=1,
        estimated_cost_usd=0.04,
    )
    service.complete(first["id"], "worker-a", "succeeded", now=T0)

    third = service.enqueue("paid_search", {"budget": {"paid_requests": 1, "usd": 0.04}})
    assert service.claim(third["id"], "worker-c", now=T0) is None
    assert service.get(third["id"])["failure_cause"] == "budget_exhausted"


def test_budget_rejects_unknown_scopes_and_disabled_paid_work(tmp_db):
    apply_migrations(tmp_db)
    budgets = BudgetService(tmp_db)
    with pytest.raises(DomainValidation):
        budgets.configure_limit("unknown", "x", "daily", "usd", 1)
    budgets.set_paid_enabled(False)
    service = JobService(tmp_db, budget_service=budgets)
    job = service.enqueue("paid", {"budget": {"paid_requests": 1, "usd": 0.01}})
    assert service.claim(job["id"], "worker-a", now=T0) is None
    assert service.get(job["id"])["failure_cause"] == "paid_disabled"


def test_worker_process_executes_allowlisted_handler_and_retries(tmp_db):
    apply_migrations(tmp_db)
    queue = JobService(tmp_db, backoff_base_seconds=1)
    job = queue.enqueue("fixture", {})
    calls = []

    def handler(_job):
        calls.append("called")
        if len(calls) == 1:
            raise RetryableJobFailure("temporary fixture failure")

    worker = WorkerProcess(tmp_db, {"fixture": handler}, worker_id="worker-a", queue=queue)
    first = worker.run_once(now=T0)
    assert first["status"] == "queued"
    assert first["failure_cause"] == "retryable_handler_failure"
    second = worker.run_once(now=T1)
    assert second["status"] == "succeeded"
    assert calls == ["called", "called"]


def test_authenticated_jobs_and_budget_api(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    client = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))
    assert client.post("/api/v1/auth/setup", json={"username": "admin", "password": PASSWORD}).status_code == 201
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}).status_code == 200
    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}

    job = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={"job_type": "fixture", "payload": {"safe": True}, "idempotency_key": "api-1"},
    )
    assert job.status_code == 201
    assert client.get(f"/api/v1/jobs/{job.json()['id']}").status_code == 200
    budget = client.put(
        "/api/v1/budgets/limits",
        headers=headers,
        json={"scope_type": "global", "period": "daily", "cap_type": "usd", "cap_value": 1.0},
    )
    assert budget.status_code == 200
    paid = client.put("/api/v1/budgets/paid-enabled", headers=headers, json={"enabled": True})
    assert paid.status_code == 200
    cancelled = client.post(f"/api/v1/jobs/{job.json()['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
