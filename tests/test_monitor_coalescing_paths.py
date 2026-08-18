"""Prompt 3B — domain-wide Monitor active-work coalescing across every
supported producer (direct enqueue, rerun, scheduler).

These tests close the two bypasses identified by the Prompt 3 completion
report: direct ``JobService.enqueue`` of ``monitor_check`` and ``rerun`` of a
historical ``monitor_check`` could each create a second active obligation for
the same Monitor when another was already active. The invariant — at most one
active ``monitor_check`` per Monitor across all supported paths — is now
enforced transactionally inside ``JobService.enqueue`` and
``JobService.rerun``, in addition to the scheduler-level check from Prompt 3.
"""
from __future__ import annotations

import sqlite3
import threading
from typing import Any

import pytest
from fastapi.testclient import TestClient

from newsroom import storage
from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.domain import CoreService, DomainValidation
from newsroom.jobs import JobConflict, JobService, MONITOR_CHECK_JOB_TYPE, SchedulerService
from newsroom.migrations import apply_migrations
from newsroom.monitoring import MonitoringPolicyService, MonitorService


T0 = "2026-08-17T12:00:00Z"
T1 = "2026-08-17T13:00:00Z"


def _policy(db_path) -> dict:
    return MonitoringPolicyService(db_path).create({
        "name": "Coalesce paths policy",
        "allowed_channels": ["rss", "direct_http"],
        "base_cadence_seconds": 60,
        "min_cadence_seconds": 30,
        "max_cadence_seconds": 300,
    })


def _monitor(db_path, *, name_suffix: str = "m", next_check_at: str = T0) -> tuple[dict, dict]:
    core = CoreService(db_path)
    src = core.create_source({
        "name": f"Paths Source {name_suffix}",
        "slug": f"paths-source-{name_suffix}",
    })
    policy = _policy(db_path)
    mon = MonitorService(db_path).create({
        "target_type": "source",
        "target_id": src["id"],
        "policy_id": policy["id"],
        "next_check_at": next_check_at,
    })
    return src, mon


def _active(db_path, monitor_id: str) -> list:
    conn = storage.connect(db_path)
    try:
        return list(conn.execute(
            "SELECT id, status FROM jobs "
            "WHERE monitor_id=? AND job_type=? AND status IN ('queued','running') "
            "ORDER BY created_at, id",
            (monitor_id, MONITOR_CHECK_JOB_TYPE),
        ).fetchall())
    finally:
        conn.close()


def _force_due(db_path, monitor_id: str, next_check_at: str) -> None:
    conn = storage.connect(db_path)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE monitors SET next_check_at=? WHERE id=?",
                (next_check_at, monitor_id),
            )
    finally:
        conn.close()


def _terminate(job_id: str, db_path, *, status: str = "succeeded") -> None:
    queue = JobService(db_path)
    queue.claim(job_id, "worker-a", now=T0)
    queue.complete(job_id, "worker-a", status, now=T0)


# ---------------------------------------------------------------------------
# A. DIRECT ENQUEUE DUPLICATE
# ---------------------------------------------------------------------------


def test_direct_double_enqueue_of_monitor_check_is_rejected(tmp_db):
    """Two ``JobService.enqueue`` calls for the same Monitor cannot both
    create active ``monitor_check`` obligations."""
    apply_migrations(tmp_db)
    _, mon = _monitor(tmp_db)
    queue = JobService(tmp_db)

    first = queue.enqueue(
        MONITOR_CHECK_JOB_TYPE,
        {"monitor_id": mon["id"]},
        monitor_id=mon["id"],
    )
    assert first["status"] == "queued"

    with pytest.raises(JobConflict):
        queue.enqueue(
            MONITOR_CHECK_JOB_TYPE,
            {"monitor_id": mon["id"]},
            monitor_id=mon["id"],
        )

    assert len(_active(tmp_db, mon["id"])) == 1


def test_direct_enqueue_with_idempotency_key_match_still_returns_existing(tmp_db):
    """Idempotent re-submission of the same key must continue to return the
    existing job even when it is active; the active-work check is only applied
    when a new row would be inserted."""
    apply_migrations(tmp_db)
    _, mon = _monitor(tmp_db)
    queue = JobService(tmp_db)

    key = f"monitor:{mon['id']}:explicit-key"
    first = queue.enqueue(
        MONITOR_CHECK_JOB_TYPE,
        {"monitor_id": mon["id"]},
        idempotency_key=key,
        monitor_id=mon["id"],
    )
    second = queue.enqueue(
        MONITOR_CHECK_JOB_TYPE,
        {"monitor_id": mon["id"], "note": "re-submission"},
        idempotency_key=key,
        monitor_id=mon["id"],
    )
    assert second["id"] == first["id"]
    assert second["payload"] == first["payload"]
    assert len(_active(tmp_db, mon["id"])) == 1


def test_api_post_jobs_monitor_check_returns_409_when_active(tmp_db):
    """``POST /jobs`` for ``monitor_check`` is a supported operator path and
    must surface the conflict as a 409, not silently succeed."""
    config = RuntimeConfig.for_environment("dev", root=tmp_db.parent / "dev")
    client = TestClient(create_app(config=config, frontend_dist=tmp_db.parent / "missing-dist"))
    password = "a-long-test-password-12345"
    assert client.post("/api/v1/auth/setup", json={"username": "admin", "password": password}).status_code == 201
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": password}).status_code == 200
    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}

    # Build a real Monitor.
    db_path = config.database_path
    _, mon = _monitor(db_path)

    first = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "job_type": MONITOR_CHECK_JOB_TYPE,
            "payload": {"monitor_id": mon["id"]},
            "monitor_id": mon["id"],
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={
            "job_type": MONITOR_CHECK_JOB_TYPE,
            "payload": {"monitor_id": mon["id"]},
            "monitor_id": mon["id"],
        },
    )
    assert second.status_code == 409
    body = second.json()
    assert "active monitor_check" in body["error"]["message"].casefold()
    assert body["error"]["code"] == "job_conflict"


# ---------------------------------------------------------------------------
# B. RERUN WHILE SCHEDULED JOB ACTIVE
# ---------------------------------------------------------------------------


def test_rerun_while_scheduled_monitor_check_is_active_is_rejected(tmp_db):
    apply_migrations(tmp_db)
    _, mon = _monitor(tmp_db)
    scheduler = SchedulerService(tmp_db)
    queue = JobService(tmp_db)

    historical = scheduler.tick(now=T0)["job_ids"][0]
    _terminate(historical, tmp_db)
    _force_due(tmp_db, mon["id"], T1)
    scheduled_id = scheduler.tick(now=T1)["job_ids"][0]

    with pytest.raises(JobConflict, match="rerun refused"):
        queue.rerun(historical)

    assert len(_active(tmp_db, mon["id"])) == 1
    assert _active(tmp_db, mon["id"])[0]["id"] == scheduled_id


def test_rerun_after_scheduled_job_terminalizes_is_allowed(tmp_db):
    """Once the active scheduled job terminalizes, a rerun of a historical
    job may create a fresh active obligation again."""
    apply_migrations(tmp_db)
    _, mon = _monitor(tmp_db)
    scheduler = SchedulerService(tmp_db)
    queue = JobService(tmp_db)

    historical = scheduler.tick(now=T0)["job_ids"][0]
    _terminate(historical, tmp_db)
    _force_due(tmp_db, mon["id"], T1)
    scheduled_id = scheduler.tick(now=T1)["job_ids"][0]
    _terminate(scheduled_id, tmp_db)

    rerun = queue.rerun(historical)
    assert rerun["id"] not in {historical, scheduled_id}
    assert rerun["status"] == "queued"
    assert len(_active(tmp_db, mon["id"])) == 1


# ---------------------------------------------------------------------------
# C. SCHEDULER WHILE RERUN JOB ACTIVE
# ---------------------------------------------------------------------------


def test_scheduler_coalesces_when_rerun_created_active_obligation(tmp_db):
    apply_migrations(tmp_db)
    _, mon = _monitor(tmp_db)
    scheduler = SchedulerService(tmp_db)
    queue = JobService(tmp_db)

    historical = scheduler.tick(now=T0)["job_ids"][0]
    _terminate(historical, tmp_db)
    _force_due(tmp_db, mon["id"], T1)

    rerun = queue.rerun(historical)
    result = scheduler.tick(now=T1)
    assert result["enqueued"] == 0
    assert result["coalesced_skipped_active"] == 1
    assert len(_active(tmp_db, mon["id"])) == 1
    assert _active(tmp_db, mon["id"])[0]["id"] == rerun["id"]


# ---------------------------------------------------------------------------
# D. CONCURRENT SCHEDULER VS RERUN
# ---------------------------------------------------------------------------


def test_concurrent_scheduler_and_rerun_produce_one_active_job(tmp_db):
    apply_migrations(tmp_db)
    _, mon = _monitor(tmp_db)
    scheduler = SchedulerService(tmp_db)
    queue = JobService(tmp_db)

    historical = scheduler.tick(now=T0)["job_ids"][0]
    _terminate(historical, tmp_db)
    _force_due(tmp_db, mon["id"], T1)

    barrier = threading.Barrier(2)
    results: dict[str, Any] = {}
    errors: list[BaseException] = []

    def do_schedule():
        try:
            barrier.wait(timeout=5.0)
            results["schedule"] = scheduler.tick(now=T1)
        except BaseException as exc:  # pragma: no cover - failure path
            errors.append(exc)

    def do_rerun():
        try:
            barrier.wait(timeout=5.0)
            results["rerun"] = queue.rerun(historical)
        except JobConflict as exc:
            results["rerun_conflict"] = str(exc)
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    t1 = threading.Thread(target=do_schedule)
    t2 = threading.Thread(target=do_rerun)
    t1.start()
    t2.start()
    t1.join(timeout=10.0)
    t2.join(timeout=10.0)

    assert not errors, errors
    active = _active(tmp_db, mon["id"])
    assert len(active) == 1


# ---------------------------------------------------------------------------
# E. CONCURRENT RERUN VS RERUN
# ---------------------------------------------------------------------------


def test_concurrent_double_rerun_keeps_at_most_one_active(tmp_db):
    apply_migrations(tmp_db)
    _, mon = _monitor(tmp_db)
    scheduler = SchedulerService(tmp_db)
    queue = JobService(tmp_db)

    historical = scheduler.tick(now=T0)["job_ids"][0]
    _terminate(historical, tmp_db)

    barrier = threading.Barrier(2)
    results: dict[str, Any] = {"successes": 0, "conflicts": 0}

    def do_rerun():
        barrier.wait(timeout=5.0)
        try:
            results.setdefault("ids", []).append(queue.rerun(historical)["id"])
            results["successes"] += 1
        except JobConflict:
            results["conflicts"] += 1

    t1 = threading.Thread(target=do_rerun)
    t2 = threading.Thread(target=do_rerun)
    t1.start()
    t2.start()
    t1.join(timeout=10.0)
    t2.join(timeout=10.0)

    assert results["successes"] == 1
    assert results["conflicts"] == 1
    assert len(_active(tmp_db, mon["id"])) == 1


def test_concurrent_double_direct_enqueue_keeps_at_most_one_active(tmp_db):
    apply_migrations(tmp_db)
    _, mon = _monitor(tmp_db)
    queue = JobService(tmp_db)

    barrier = threading.Barrier(2)
    results: dict[str, Any] = {"successes": 0, "conflicts": 0}

    def do_enqueue():
        barrier.wait(timeout=5.0)
        try:
            queue.enqueue(MONITOR_CHECK_JOB_TYPE, {"monitor_id": mon["id"]}, monitor_id=mon["id"])
            results["successes"] += 1
        except JobConflict:
            results["conflicts"] += 1

    t1 = threading.Thread(target=do_enqueue)
    t2 = threading.Thread(target=do_enqueue)
    t1.start()
    t2.start()
    t1.join(timeout=10.0)
    t2.join(timeout=10.0)

    assert results["successes"] == 1
    assert results["conflicts"] == 1
    assert len(_active(tmp_db, mon["id"])) == 1


# ---------------------------------------------------------------------------
# F. OWNERSHIP VALIDATION
# ---------------------------------------------------------------------------


def test_payload_monitor_id_mismatch_is_rejected(tmp_db):
    apply_migrations(tmp_db)
    _, mon = _monitor(tmp_db)
    queue = JobService(tmp_db)

    with pytest.raises(DomainValidation, match="payload monitor_id"):
        queue.enqueue(
            MONITOR_CHECK_JOB_TYPE,
            {"monitor_id": "some-other-monitor"},
            monitor_id=mon["id"],
        )

    # No job inserted.
    assert len(_active(tmp_db, mon["id"])) == 0


def test_monitor_check_without_canonical_monitor_id_is_rejected(tmp_db):
    apply_migrations(tmp_db)
    queue = JobService(tmp_db)

    with pytest.raises(DomainValidation, match="canonical monitor_id"):
        queue.enqueue(MONITOR_CHECK_JOB_TYPE, {"monitor_id": "anything"}, monitor_id=None)


def test_rerun_of_monitor_check_with_conflicting_payload_is_rejected(tmp_db):
    """A historical monitor_check row whose payload carries a conflicting
    monitor_id cannot be rerun — the ownership invariant applies to the
    historical row too."""
    apply_migrations(tmp_db)
    _, mon = _monitor(tmp_db)
    scheduler = SchedulerService(tmp_db)
    queue = JobService(tmp_db)

    historical = scheduler.tick(now=T0)["job_ids"][0]
    _terminate(historical, tmp_db)

    # Mutate the historical job's payload to lie about monitor_id.
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE jobs SET payload_json=? WHERE id=?",
                ('{"monitor_id": "forged"}', historical),
            )
    finally:
        conn.close()

    with pytest.raises(DomainValidation, match="conflicting monitor_id"):
        queue.rerun(historical)


# ---------------------------------------------------------------------------
# G. TERMINAL RELEASE — scheduler can enqueue after rerun terminalizes
# ---------------------------------------------------------------------------


def test_scheduler_recovers_cadence_after_rerun_terminates(tmp_db):
    apply_migrations(tmp_db)
    _, mon = _monitor(tmp_db)
    scheduler = SchedulerService(tmp_db)
    queue = JobService(tmp_db)

    historical = scheduler.tick(now=T0)["job_ids"][0]
    _terminate(historical, tmp_db)
    _force_due(tmp_db, mon["id"], T1)
    rerun = queue.rerun(historical)
    _terminate(rerun["id"], tmp_db)

    _force_due(tmp_db, mon["id"], "2026-08-17T14:00:00Z")
    result = scheduler.tick(now="2026-08-17T14:00:00Z")
    assert result["enqueued"] == 1
    assert len(_active(tmp_db, mon["id"])) == 1


# ---------------------------------------------------------------------------
# H. RESEARCH QUESTION REGRESSION — research_question rerun still works.
# ---------------------------------------------------------------------------


def test_research_question_rerun_is_not_affected_by_monitor_guard(tmp_db):
    """The monitor_check guard must not interfere with the research_question
    rerun path implemented in Prompt 1D."""
    from newsroom.research_questions import (
        ResearchQuestionService,
        research_job_completion_hook,
        research_job_recovery_hook,
        research_job_rerun_factory,
    )
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = service.create({
        "question": "monitor guard does not interfere",
        "origin_type": "user",
        "search_attempt_budget": 2,
        "query_budget": 2,
        "local_model_budget": 1,
    })
    queue = JobService(
        tmp_db,
        recovery_hook=research_job_recovery_hook,
        completion_hook=research_job_completion_hook,
        rerun_factory=research_job_rerun_factory,
    )

    original = service.pursue(question["id"], mode="manual", query_units=1)
    job_id = original["id"]
    queue.claim(job_id, "worker-a", now=T0)
    queue.complete(job_id, "worker-a", "succeeded", now=T0)

    rerun = queue.rerun(job_id)
    assert rerun["job_type"] == "research_question"
    assert rerun["status"] == "queued"
    assert rerun["id"] != job_id
    current = service.get(question["id"])
    assert current["attempts"][-1]["job_id"] == rerun["id"]


# ---------------------------------------------------------------------------
# I. PROMPT 3 REGRESSION — scheduler coalescing still works.
# ---------------------------------------------------------------------------


def test_scheduler_multiple_ticks_remain_coalesced(tmp_db):
    """Prompt 3's scheduler coalescing behavior must remain unchanged after
    Prompt 3B's centralization."""
    apply_migrations(tmp_db)
    _, mon = _monitor(tmp_db)
    scheduler = SchedulerService(tmp_db)

    first = scheduler.tick(now=T0)
    assert first["enqueued"] == 1

    for hour in range(1, 4):
        result = scheduler.tick(now=f"2026-08-17T{12 + hour:02d}:00:00Z")
        assert result["enqueued"] == 0
        assert result["coalesced_skipped_active"] == 1

    assert len(_active(tmp_db, mon["id"])) == 1
