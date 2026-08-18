"""Prompt 3 — Scheduler coalescing, concurrency, and stale-backlog prevention.

These tests prove that ``SchedulerService.tick()`` maintains the invariant that
an enabled Monitor has at most ONE active ``monitor_check`` durable execution
obligation at a time, under repeated ticks, worker downtime, retries, lease
recovery, and concurrent scheduler processes.
"""
from __future__ import annotations

import sqlite3
import threading

import pytest

from newsroom import storage
from newsroom.domain import CoreService
from newsroom.jobs import JobService, SchedulerService
from newsroom.migrations import apply_migrations
from newsroom.monitoring import MonitorService
from newsroom.worker import WorkerProcess


T0 = "2026-08-16T12:00:00Z"
T1 = "2026-08-16T12:01:00Z"
T2 = "2026-08-16T12:02:00Z"


def _policy(db_path, **overrides):
    values = {
        "name": "Coalescing policy",
        "allowed_channels": ["rss", "direct_http"],
        "base_cadence_seconds": 60,
        "min_cadence_seconds": 30,
        "max_cadence_seconds": 300,
        "query_budget": 5,
        "local_model_budget": 10,
        "paid_budget_usd": 0.0,
    }
    values.update(overrides)
    from newsroom.monitoring import MonitoringPolicyService

    return MonitoringPolicyService(db_path).create(values)


def _make_monitor(db_path, *, cadence=60, name_suffix="m", next_check_at=T0):
    core = CoreService(db_path)
    source = core.create_source(
        {"name": f"Coalescing Source {name_suffix}", "slug": f"coalescing-source-{name_suffix}"}
    )
    policy = _policy(db_path, base_cadence_seconds=cadence)
    monitor = MonitorService(db_path).create(
        {
            "target_type": "source",
            "target_id": source["id"],
            "policy_id": policy["id"],
            "next_check_at": next_check_at,
        }
    )
    return source, policy, monitor


def _active_monitor_jobs(conn: sqlite3.Connection, monitor_id: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT id, status, next_attempt_at, idempotency_key
            FROM jobs
            WHERE monitor_id = ? AND job_type = 'monitor_check'
              AND status IN ('queued', 'running')
            ORDER BY created_at, id
            """,
            (monitor_id,),
        ).fetchall()
    )


# ---------------------------------------------------------------------------
# A. WORKER OFFLINE / MULTIPLE TICKS
# ---------------------------------------------------------------------------


def test_worker_offline_multiple_ticks_keep_single_active_obligation(tmp_db):
    """Repeated scheduler ticks while the worker is offline must not accumulate
    duplicate queued monitor_check jobs for the same Monitor."""
    apply_migrations(tmp_db)
    _, _, monitor = _make_monitor(tmp_db, cadence=60)

    scheduler = SchedulerService(tmp_db)
    first = scheduler.tick(now=T0)
    assert first["enqueued"] == 1
    assert first["coalesced_skipped_active"] == 0
    assert first["run_id"] is not None

    # Six ticks (one per hour of worker downtime) — all must coalesce.
    total_coalesced = 0
    for hour in range(1, 7):
        result = scheduler.tick(now=f"2026-08-16T{12 + hour:02d}:00:00Z")
        assert result["enqueued"] == 0
        total_coalesced += result["coalesced_skipped_active"]

    assert total_coalesced == 6

    conn = storage.connect(tmp_db)
    try:
        active = _active_monitor_jobs(conn, monitor["id"])
    finally:
        conn.close()
    assert len(active) == 1
    assert active[0]["status"] == "queued"


def test_coalesced_tick_does_not_advance_next_check_at(tmp_db):
    """When coalescing skips enqueue, ``monitors.next_check_at`` must NOT be
    advanced — the existing active job owns the obligation and adaptive cadence
    is preserved for the eventual ``record_activity``."""
    apply_migrations(tmp_db)
    _, _, monitor = _make_monitor(tmp_db, cadence=60)

    scheduler = SchedulerService(tmp_db)
    scheduler.tick(now=T0)

    conn = storage.connect(tmp_db)
    try:
        before = conn.execute(
            "SELECT next_check_at FROM monitors WHERE id = ?", (monitor["id"],)
        ).fetchone()[0]
    finally:
        conn.close()

    scheduler.tick(now="2026-08-16T13:00:00Z")

    conn = storage.connect(tmp_db)
    try:
        after = conn.execute(
            "SELECT next_check_at FROM monitors WHERE id = ?", (monitor["id"],)
        ).fetchone()[0]
    finally:
        conn.close()
    assert after == before


# ---------------------------------------------------------------------------
# B. ACTIVE QUEUED JOB
# ---------------------------------------------------------------------------


def test_active_queued_job_blocks_re_enqueue(tmp_db):
    apply_migrations(tmp_db)
    _, _, monitor = _make_monitor(tmp_db, cadence=60)

    scheduler = SchedulerService(tmp_db)
    first = scheduler.tick(now=T0)
    assert len(first["job_ids"]) == 1

    # Manually rewind next_check_at so the monitor is "due" again at the same
    # logical tick — the scheduler must still coalesce because the job is queued.
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE monitors SET next_check_at = ? WHERE id = ?",
                (T0, monitor["id"]),
            )
    finally:
        conn.close()

    second = scheduler.tick(now=T0)
    assert second["job_ids"] == []
    assert second["coalesced_skipped_active"] == 1
    assert second["enqueued"] == 0
    assert second["run_id"] is None

    conn = storage.connect(tmp_db)
    try:
        rows = conn.execute(
            "SELECT id FROM jobs WHERE monitor_id = ? AND job_type = 'monitor_check'",
            (monitor["id"],),
        ).fetchall()
    finally:
        conn.close()
    assert {row[0] for row in rows} == set(first["job_ids"])


# ---------------------------------------------------------------------------
# C. ACTIVE LEASED / RUNNING JOB
# ---------------------------------------------------------------------------


def test_active_leased_job_blocks_re_enqueue(tmp_db):
    apply_migrations(tmp_db)
    _, _, monitor = _make_monitor(tmp_db, cadence=60)

    queue = JobService(tmp_db, lease_seconds=120)
    scheduler = SchedulerService(tmp_db)
    first = scheduler.tick(now=T0)
    job_id = first["job_ids"][0]

    claimed = queue.claim(job_id, "worker-a", now=T0)
    assert claimed["status"] == "running"

    # Rewind next_check_at to force another "due" tick while the job is leased.
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE monitors SET next_check_at = ? WHERE id = ?",
                (T0, monitor["id"]),
            )
    finally:
        conn.close()

    second = scheduler.tick(now=T0)
    assert second["job_ids"] == []
    assert second["coalesced_skipped_active"] == 1

    conn = storage.connect(tmp_db)
    try:
        active = _active_monitor_jobs(conn, monitor["id"])
    finally:
        conn.close()
    assert len(active) == 1
    assert active[0]["status"] == "running"


# ---------------------------------------------------------------------------
# D. RETRYABLE FAILURE — job returns to queued/backoff; no second job.
# ---------------------------------------------------------------------------


def test_retryable_failure_does_not_create_second_obligation(tmp_db):
    apply_migrations(tmp_db)
    _, _, monitor = _make_monitor(tmp_db, cadence=60)

    scheduler = SchedulerService(tmp_db)
    first = scheduler.tick(now=T0)
    job_id = first["job_ids"][0]

    queue = JobService(tmp_db, lease_seconds=10, backoff_base_seconds=600)
    queue.claim(job_id, "worker-a", now=T0)
    queue.complete(
        job_id,
        "worker-a",
        "failed",
        error_code="retryable_handler_failure",
        retryable=True,
        now=T0,
    )

    # Job is back to queued with a future next_attempt_at — active.
    state = queue.get(job_id)
    assert state["status"] == "queued"
    assert state["next_attempt_at"] is not None

    # Several ticks while the retry is waiting — must coalesce.
    for offset in range(1, 4):
        scheduler.tick(now=f"2026-08-16T{12 + offset:02d}:00:00Z")

    conn = storage.connect(tmp_db)
    try:
        rows = conn.execute(
            "SELECT id FROM jobs WHERE monitor_id = ? AND job_type = 'monitor_check'",
            (monitor["id"],),
        ).fetchall()
    finally:
        conn.close()
    assert {row[0] for row in rows} == {job_id}


# ---------------------------------------------------------------------------
# E. TERMINAL COMPLETION — succeeded; future cadence may create one new job.
# ---------------------------------------------------------------------------


def test_terminal_completion_releases_obligation_for_next_cadence(tmp_db):
    apply_migrations(tmp_db)
    _, _, monitor = _make_monitor(tmp_db, cadence=60)

    queue = JobService(tmp_db)
    scheduler = SchedulerService(tmp_db)
    first = scheduler.tick(now=T0)
    job_id = first["job_ids"][0]

    queue.claim(job_id, "worker-a", now=T0)
    queue.complete(job_id, "worker-a", "succeeded", now=T0)

    # After terminal completion, the obligation is gone; a future due tick
    # creates exactly one fresh job.
    next_due = f"2026-08-16T12:10:00Z"
    third = scheduler.tick(now=next_due)
    assert third["job_ids"] != first["job_ids"]
    assert len(third["job_ids"]) == 1
    assert third["coalesced_skipped_active"] == 0

    conn = storage.connect(tmp_db)
    try:
        rows = conn.execute(
            "SELECT id, status FROM jobs WHERE monitor_id = ? AND job_type = 'monitor_check'",
            (monitor["id"],),
        ).fetchall()
    finally:
        conn.close()
    statuses = {row[1] for row in rows}
    assert statuses == {"succeeded", "queued"}


# ---------------------------------------------------------------------------
# F. TERMINAL FAILURE — uses record_activity / retirement semantics.
# ---------------------------------------------------------------------------


def test_terminal_failure_recovers_via_record_activity(tmp_db):
    """A terminal monitor job failure records an activity via
    ``record_activity`` (called by the handler). The scheduler must then
    respect the resulting ``next_check_at`` / retirement state and not lock
    the Monitor out permanently."""
    apply_migrations(tmp_db)
    _, _, monitor = _make_monitor(tmp_db, cadence=60)

    scheduler = SchedulerService(tmp_db)
    first = scheduler.tick(now=T0)
    job_id = first["job_ids"][0]

    # Simulate the handler's non-retryable terminal-failure path: record the
    # error activity (which advances next_check_at via adaptive cadence) and
    # terminalize the job so it no longer counts as active.
    queue = JobService(tmp_db)
    queue.claim(job_id, "worker-a", now=T0)
    MonitorService(tmp_db).record_activity(monitor["id"], "error", error_code="timeout", observed_at=T0)
    queue.complete(job_id, "worker-a", "failed", error_code="timeout", retryable=False, now=T0)

    conn = storage.connect(tmp_db)
    try:
        next_check = conn.execute(
            "SELECT next_check_at FROM monitors WHERE id = ?", (monitor["id"],)
        ).fetchone()[0]
    finally:
        conn.close()
    # Backoff: error_multiplier 2.0 -> next_check_at = T0 + 60 (current_interval)*2 = T0+120
    assert next_check == "2026-08-16T12:02:00Z"

    # A later tick at the new due time creates one fresh job (no stale lockout).
    result = scheduler.tick(now="2026-08-16T12:02:00Z")
    assert result["enqueued"] == 1
    assert len(result["job_ids"]) == 1


def test_retired_monitor_stops_creating_work(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Retire Source", "slug": "retire-source"})
    from newsroom.monitoring import MonitoringPolicyService

    policy = MonitoringPolicyService(tmp_db).create({
        "name": "Retire policy",
        "allowed_channels": ["rss"],
        "base_cadence_seconds": 60,
        "min_cadence_seconds": 30,
        "max_cadence_seconds": 300,
        "retirement_criteria": {"max_consecutive_errors": 1},
    })
    monitor = MonitorService(tmp_db).create({
        "target_type": "source",
        "target_id": source["id"],
        "policy_id": policy["id"],
        "next_check_at": T0,
    })

    MonitorService(tmp_db).record_activity(monitor["id"], "error", error_code="x", observed_at=T0)
    assert MonitorService(tmp_db).get(monitor["id"])["enabled"] == 0

    for hour in range(1, 4):
        result = SchedulerService(tmp_db).tick(now=f"2026-08-16T{12 + hour:02d}:00:00Z")
        assert result["enqueued"] == 0
        assert result["job_ids"] == []


# ---------------------------------------------------------------------------
# G. CANCELLATION
# ---------------------------------------------------------------------------


def test_cancelled_monitor_job_does_not_block_future_scheduling(tmp_db):
    apply_migrations(tmp_db)
    _, _, monitor = _make_monitor(tmp_db, cadence=60)

    scheduler = SchedulerService(tmp_db)
    first = scheduler.tick(now=T0)
    job_id = first["job_ids"][0]

    queue = JobService(tmp_db)
    queue.cancel(job_id, reason="operator_request")

    # Cancellation is terminal — next due tick enqueues a fresh obligation.
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE monitors SET next_check_at = ? WHERE id = ?",
                (T1, monitor["id"]),
            )
    finally:
        conn.close()

    result = scheduler.tick(now=T1)
    assert result["coalesced_skipped_active"] == 0
    assert result["enqueued"] == 1
    assert result["job_ids"][0] != job_id


# ---------------------------------------------------------------------------
# H. DISABLED MONITOR
# ---------------------------------------------------------------------------


def test_disabled_monitor_with_queued_job_worker_noops(tmp_db):
    """A Monitor disabled while a job is queued must not perform unexpected
    source acquisition. The worker handler no-ops on a disabled Monitor and
    the job terminalizes without recording monitor activity."""
    apply_migrations(tmp_db)
    _, _, monitor = _make_monitor(tmp_db, cadence=60)

    scheduler = SchedulerService(tmp_db)
    scheduler.tick(now=T0)

    # Operator disables the Monitor after enqueue but before worker claim.
    MonitorService(tmp_db).disable(monitor["id"])

    # Subsequent ticks must not re-enqueue (enabled=0 filter).
    for hour in range(1, 3):
        result = scheduler.tick(now=f"2026-08-16T{12 + hour:02d}:00:00Z")
        assert result["enqueued"] == 0

    # Worker claims the queued job and the handler short-circuits to disabled.
    from newsroom.monitoring import MonitorExecutionService

    queue = JobService(tmp_db)
    worker = WorkerProcess(
        tmp_db,
        MonitorExecutionService(tmp_db).handlers(),
        worker_id="worker-disabled-queued",
        queue=queue,
    )
    finished = worker.run_once(now=T0)
    assert finished["status"] == "succeeded"

    # No monitor activity rows were written by the no-op and last_result is
    # untouched — the disabled Monitor performed no source acquisition.
    activity = MonitorService(tmp_db).activity(monitor["id"])["items"]
    assert activity == []
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] is None
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# I. TWO SCHEDULERS — concurrent tick() calls must produce one active job.
# ---------------------------------------------------------------------------


def test_two_concurrent_schedulers_produce_one_active_job(tmp_db):
    apply_migrations(tmp_db)
    _, _, monitor = _make_monitor(tmp_db, cadence=60)

    barrier = threading.Barrier(2)
    results: dict[str, dict] = {}
    errors: list[BaseException] = []

    def tick(name: str):
        try:
            scheduler = SchedulerService(tmp_db)
            barrier.wait(timeout=5.0)
            results[name] = scheduler.tick(now=T0)
        except BaseException as exc:  # pragma: no cover - failure path
            errors.append(exc)

    t1 = threading.Thread(target=tick, args=("a",))
    t2 = threading.Thread(target=tick, args=("b",))
    t1.start()
    t2.start()
    t1.join(timeout=10.0)
    t2.join(timeout=10.0)

    assert not errors, errors
    enqueued_total = results["a"]["enqueued"] + results["b"]["enqueued"]
    coalesced_total = results["a"]["coalesced_skipped_active"] + results["b"]["coalesced_skipped_active"]
    assert enqueued_total == 1
    # The invariant is "at most one active job". Depending on whether the
    # second scheduler saw the monitor as still due, it either coalesced
    # (coalesced_total == 1) or found it not-due (coalesced_total == 0); both
    # paths leave exactly one active job.
    assert coalesced_total in (0, 1)

    conn = storage.connect(tmp_db)
    try:
        active = _active_monitor_jobs(conn, monitor["id"])
    finally:
        conn.close()
    assert len(active) == 1


def test_two_schedulers_with_two_due_monitors_no_duplicates(tmp_db):
    apply_migrations(tmp_db)
    _, _, monitor_a = _make_monitor(tmp_db, cadence=60, name_suffix="a")
    _, _, monitor_b = _make_monitor(tmp_db, cadence=60, name_suffix="b")

    barrier = threading.Barrier(2)
    results: dict[str, dict] = {}
    errors: list[BaseException] = []

    def tick(name: str):
        try:
            scheduler = SchedulerService(tmp_db)
            barrier.wait(timeout=5.0)
            results[name] = scheduler.tick(now=T0)
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    t1 = threading.Thread(target=tick, args=("a",))
    t2 = threading.Thread(target=tick, args=("b",))
    t1.start()
    t2.start()
    t1.join(timeout=10.0)
    t2.join(timeout=10.0)

    assert not errors, errors
    assert results["a"]["enqueued"] + results["b"]["enqueued"] == 2

    conn = storage.connect(tmp_db)
    try:
        active_a = _active_monitor_jobs(conn, monitor_a["id"])
        active_b = _active_monitor_jobs(conn, monitor_b["id"])
    finally:
        conn.close()
    assert len(active_a) == 1
    assert len(active_b) == 1


# ---------------------------------------------------------------------------
# J. LEASE RECOVERY — claimed job whose lease expires returns to queued.
# ---------------------------------------------------------------------------


def test_lease_recovery_does_not_create_duplicate_obligation(tmp_db):
    apply_migrations(tmp_db)
    _, _, monitor = _make_monitor(tmp_db, cadence=60)

    queue = JobService(tmp_db, lease_seconds=10, backoff_base_seconds=600)
    scheduler = SchedulerService(tmp_db)
    first = scheduler.tick(now=T0)
    job_id = first["job_ids"][0]

    queue.claim(job_id, "worker-a", now=T0)
    # Lease expires and the worker recovers it back to queued with backoff.
    recovered = queue.recover_expired(now=T1)
    assert recovered == 1
    state = queue.get(job_id)
    assert state["status"] == "queued"
    assert state["next_attempt_at"] is not None

    # Several ticks while recovered/retry waits — must coalesce.
    for offset in range(2, 5):
        scheduler.tick(now=f"2026-08-16T{12 + offset:02d}:00:00Z")

    conn = storage.connect(tmp_db)
    try:
        rows = conn.execute(
            "SELECT id FROM jobs WHERE monitor_id = ? AND job_type = 'monitor_check'",
            (monitor["id"],),
        ).fetchall()
    finally:
        conn.close()
    assert {row[0] for row in rows} == {job_id}


# ---------------------------------------------------------------------------
# Idempotency key audit
# ---------------------------------------------------------------------------


def test_idempotency_key_remains_unique_per_cadence_after_terminalization(tmp_db):
    """After a cadence terminalizes (success), a future cadence must use a
    distinct idempotency key so both historical and active rows coexist."""
    apply_migrations(tmp_db)
    _, _, monitor = _make_monitor(tmp_db, cadence=60)

    scheduler = SchedulerService(tmp_db)
    first = scheduler.tick(now=T0)
    JobService(tmp_db).claim(first["job_ids"][0], "worker-a", now=T0)
    JobService(tmp_db).complete(first["job_ids"][0], "worker-a", "succeeded", now=T0)

    # Force next due time, then schedule again.
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE monitors SET next_check_at = ? WHERE id = ?",
                ("2026-08-16T13:00:00Z", monitor["id"]),
            )
    finally:
        conn.close()

    second = scheduler.tick(now="2026-08-16T13:00:00Z")
    assert second["enqueued"] == 1

    conn = storage.connect(tmp_db)
    try:
        keys = [
            row[0]
            for row in conn.execute(
                "SELECT idempotency_key FROM jobs WHERE monitor_id = ? AND job_type = 'monitor_check' ORDER BY created_at",
                (monitor["id"],),
            ).fetchall()
        ]
    finally:
        conn.close()
    assert len(keys) == 2
    assert keys[0] != keys[1]
    assert all(key.startswith(f"monitor:{monitor['id']}:") for key in keys)


# ---------------------------------------------------------------------------
# Tick result counters
# ---------------------------------------------------------------------------


def test_tick_result_exposes_coalescing_counters(tmp_db):
    apply_migrations(tmp_db)
    _, _, monitor_one = _make_monitor(tmp_db, cadence=60, name_suffix="one")
    _, _, monitor_two = _make_monitor(tmp_db, cadence=60, name_suffix="two")

    scheduler = SchedulerService(tmp_db)
    first = scheduler.tick(now=T0)
    assert first["enqueued"] == 2
    assert first["coalesced_skipped_active"] == 0
    assert first["due_count"] == 2
    assert first["eligible_count"] == 2

    # Force both monitors due again with the queued jobs still active.
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE monitors SET next_check_at = ? WHERE id IN (?, ?)",
                (T0, monitor_one["id"], monitor_two["id"]),
            )
    finally:
        conn.close()

    second = scheduler.tick(now=T0)
    assert second["enqueued"] == 0
    assert second["coalesced_skipped_active"] == 2
    assert second["run_id"] is None
    assert second["job_ids"] == []
