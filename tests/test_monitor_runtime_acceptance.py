"""Prompt 4 — Monitor Runtime Integration Acceptance Gate.

These tests prove that the Monitor runtime end-to-end — from a due Monitor,
through the persisted scheduler tick, the durable ``monitor_check`` job, the
production worker handler, the canonical acquisition service, the persisted
Document/DocumentVersion, and the truthful ``monitor_activity`` outcome —
behaves as a single production system.

The tests intentionally compose the same objects the production runtime uses:

    apply_migrations(...)
        ↓
    CoreService.create_source(...)
        ↓
    MonitoringPolicyService.create(...)
        ↓
    MonitorService.create(...)
        ↓
    SchedulerProcess.run_once()
        ↓
    MonitorExecutionService(...).handlers()       (production class & registry)
        ↓
    build_worker_queue(db_path)                   (production queue + hooks)
        ↓
    WorkerProcess(...).run_once()

The HTTP transport is replaced with a deterministic ``CountingTransport``; the
rest of the composition is the production wiring. This is the composition
the runtime entrypoints in ``newsroom/runtime.py`` build at startup.

Acceptance scenarios verified here:

* Primary content lifecycle (A -> A -> B) with exact counts.
* Feed lifecycle (RSS) with no duplicate DocumentVersion on unchanged poll.
* Multi-scheduler concurrency resulting in a single source acquisition.
* Process-like restart / persistence boundary.
* ``no_change`` invariant — acquisition MUST have actually succeeded before a
  Monitor may truthfully report ``no_change``.
* Rerun acceptance via the production API (happy path + 409 conflict).
* Provenance / persistence assertions on canonical acquisition.
"""
from __future__ import annotations

import sqlite3
import threading
from typing import Any, Mapping

import pytest
from fastapi.testclient import TestClient

from newsroom import storage
from newsroom.acquisition import (
    AcquisitionBlocked,
    AcquisitionService,
    AcquisitionTimeout,
    HttpResponse,
)
from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.domain import CoreService
from newsroom.jobs import JobService, MONITOR_CHECK_JOB_TYPE, SchedulerService
from newsroom.migrations import apply_migrations
from newsroom.monitoring import (
    MonitorExecutionService,
    MonitorService,
    MonitoringPolicyService,
)
from newsroom.runtime import build_worker_handlers, build_worker_queue
from newsroom.scheduler import SchedulerProcess
from newsroom.worker import WorkerProcess


T0 = "2026-08-17T12:00:00Z"
T1 = "2026-08-17T12:01:00Z"
T2 = "2026-08-17T12:02:00Z"

PASSWORD = "a-long-test-password-12345"


# ---------------------------------------------------------------------------
# Deterministic test transports
# ---------------------------------------------------------------------------


class CountingTransport:
    """Record every ``get()`` invocation for acquisition-counting assertions."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.get_calls = 0
        self.requests: list[dict[str, Any]] = []

    def get(self, url, *, headers, policy):
        self.get_calls += 1
        self.requests.append({"url": url, "headers": dict(headers)})
        if not self._responses:
            raise AssertionError("CountingTransport exhausted: unexpected acquisition call")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


# ---------------------------------------------------------------------------
# Composition helpers
# ---------------------------------------------------------------------------


def _bootstrap(tmp_db, *, slug: str, homepage: str, feed_url: str | None = None) -> tuple[dict, dict, dict]:
    """Build a Source + MonitoringPolicy + Monitor with the production services."""
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    payload: dict[str, Any] = {"name": f"{slug}-name", "slug": slug, "homepage_url": homepage}
    if feed_url:
        payload["feed_url"] = feed_url
        payload["source_kind"] = "feed"
    source = core.create_source(payload)
    policy = MonitoringPolicyService(tmp_db).create({
        "name": f"{slug}-policy",
        "allowed_channels": ["rss", "direct_http"] if feed_url else ["direct_http"],
        "base_cadence_seconds": 60,
        "min_cadence_seconds": 30,
        "max_cadence_seconds": 300,
    })
    monitor = MonitorService(tmp_db).create({
        "target_type": "source",
        "target_id": source["id"],
        "policy_id": policy["id"],
        "next_check_at": T0,
    })
    return source, policy, monitor


def _build_runtime(tmp_db, transport, *, worker_id: str = "worker-acceptance"):
    """Compose the production handler + queue + worker for a deterministic transport."""
    acquisition = AcquisitionService(tmp_db, transport=transport)
    handlers = MonitorExecutionService(tmp_db, acquisition_service=acquisition).handlers()
    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(tmp_db, handlers, worker_id=worker_id, queue=queue)
    return queue, worker, handlers


def _active_monitor_jobs(tmp_db, monitor_id: str) -> list[sqlite3.Row]:
    conn = storage.connect(tmp_db)
    try:
        return list(conn.execute(
            """
            SELECT id, status FROM jobs
            WHERE monitor_id = ? AND job_type = ?
              AND status IN ('queued', 'running')
            ORDER BY created_at, id
            """,
            (monitor_id, MONITOR_CHECK_JOB_TYPE),
        ).fetchall())
    finally:
        conn.close()


def _force_due(tmp_db, monitor_id: str, at: str = T0) -> None:
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE monitors SET next_check_at = ? WHERE id = ?",
                (at, monitor_id),
            )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Section 3 + 4 — true production-composition lifecycle
# ---------------------------------------------------------------------------


def test_production_composition_source_monitor_lifecycle_aaa_to_b(tmp_db):
    """End-to-end Source Monitor lifecycle through the production wiring.

    T0: Content A -> Monitor records ``changed`` after one real acquisition.
    T1: Content A again (HTTP 304) -> Monitor records ``no_change`` after a
        second real acquisition that confirmed no change. Exactly 1 version.
    T2: Content B -> Monitor records ``changed`` after a third real
        acquisition. Exactly 2 versions with distinct content hashes.
    """
    source, _policy, monitor = _bootstrap(
        tmp_db,
        slug="runtime-aaa-b",
        homepage="https://example.test/runtime-aaa-b",
    )
    transport = CountingTransport([
        HttpResponse(
            200, "https://example.test/runtime-aaa-b",
            {"content-type": "text/html", "etag": '"v1"'},
            b"<html><title>Title A</title><p>Content A</p></html>",
        ),
        HttpResponse(304, "https://example.test/runtime-aaa-b", {"etag": '"v1"'}, b""),
        HttpResponse(
            200, "https://example.test/runtime-aaa-b",
            {"content-type": "text/html", "etag": '"v2"'},
            b"<html><title>Title B</title><p>Content B</p></html>",
        ),
    ])
    _, worker, _ = _build_runtime(tmp_db, transport, worker_id="worker-lifecycle")

    process = SchedulerProcess(tmp_db)

    # T0
    scheduled = process.run_once()
    assert scheduled["enqueued"] == 1
    assert len(_active_monitor_jobs(tmp_db, monitor["id"])) == 1
    finished = worker.run_once(now=T0)
    assert finished["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM monitor_activity").fetchone()[0] == 1
        v1 = conn.execute(
            "SELECT id, content_hash FROM document_versions ORDER BY retrieved_at, id"
        ).fetchone()
    finally:
        conn.close()

    # T1
    _force_due(tmp_db, monitor["id"], T1)
    scheduled = process.run_once()
    assert scheduled["enqueued"] == 1
    finished = worker.run_once(now=T1)
    assert finished["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "no_change"

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM monitor_activity").fetchone()[0] == 2
    finally:
        conn.close()

    # T2
    _force_due(tmp_db, monitor["id"], T2)
    scheduled = process.run_once()
    assert scheduled["enqueued"] == 1
    finished = worker.run_once(now=T2)
    assert finished["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 2
        versions = conn.execute(
            "SELECT id, content_hash FROM document_versions ORDER BY retrieved_at, id"
        ).fetchall()
        assert versions[1]["id"] != v1["id"]
        assert versions[1]["content_hash"] != v1["content_hash"]
        assert conn.execute("SELECT COUNT(*) FROM monitor_activity").fetchone()[0] == 3
        jobs = conn.execute(
            "SELECT status, COUNT(*) FROM jobs WHERE monitor_id = ? GROUP BY status",
            (monitor["id"],),
        ).fetchall()
    finally:
        conn.close()

    statuses = {row[0]: row[1] for row in jobs}
    assert statuses.get("succeeded") == 3
    assert statuses.get("queued", 0) == 0

    # Exactly three successful HTTP acquisitions; no extra / no duplicate calls.
    assert transport.get_calls == 3


# ---------------------------------------------------------------------------
# Section 5 — Feed lifecycle through the production wiring
# ---------------------------------------------------------------------------


FEED_RSS_A = b"""<rss version="2.0"><channel><title>Runtime Feed</title>
<item><title>One</title><link>https://example.test/feed/1</link><description>D1</description></item>
</channel></rss>"""

FEED_RSS_B = b"""<rss version="2.0"><channel><title>Runtime Feed</title>
<item><title>One updated</title><link>https://example.test/feed/1</link><description>D1 changed</description></item>
<item><title>Two</title><link>https://example.test/feed/2</link><description>D2</description></item>
</channel></rss>"""


def test_production_composition_source_monitor_feed_lifecycle(tmp_db):
    source, _policy, monitor = _bootstrap(
        tmp_db,
        slug="runtime-feed",
        homepage="https://example.test/runtime-feed-home",
        feed_url="https://example.test/feed.xml",
    )
    transport = CountingTransport([
        HttpResponse(
            200, "https://example.test/feed.xml",
            {"content-type": "application/rss+xml", "etag": '"f1"'},
            FEED_RSS_A,
        ),
        HttpResponse(304, "https://example.test/feed.xml", {"etag": '"f1"'}, b""),
        HttpResponse(
            200, "https://example.test/feed.xml",
            {"content-type": "application/rss+xml", "etag": '"f2"'},
            FEED_RSS_B,
        ),
    ])
    _, worker, _ = _build_runtime(tmp_db, transport, worker_id="worker-feed")
    process = SchedulerProcess(tmp_db)

    # First poll: 1 new item -> changed
    process.run_once()
    assert worker.run_once(now=T0)["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM documents WHERE source_id = ?", (source["id"],)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 1
    finally:
        conn.close()

    # Second poll: 304 -> no_change, no new version
    _force_due(tmp_db, monitor["id"], T1)
    process.run_once()
    assert worker.run_once(now=T1)["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "no_change"
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM monitor_activity").fetchone()[0] == 2
    finally:
        conn.close()

    # Third poll: 2 items, one new + one changed -> changed, new versions persisted
    _force_due(tmp_db, monitor["id"], T2)
    process.run_once()
    assert worker.run_once(now=T2)["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM documents WHERE source_id = ?", (source["id"],)).fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 3
    finally:
        conn.close()

    assert transport.get_calls == 3


# ---------------------------------------------------------------------------
# Section 12 — multi-scheduler concurrency produces a single acquisition
# ---------------------------------------------------------------------------


def test_concurrent_schedulers_produce_single_acquisition_integration(tmp_db):
    """Two SchedulerProcess instances ticking concurrently must produce
    exactly one source acquisition in the end-to-end pipeline.

    The existing Prompt 3 tests prove the queue invariant (one active job).
    This test proves the stronger end-result invariant that the SOURCE itself
    is only acquired once even under concurrent scheduling pressure.
    """
    source, _policy, monitor = _bootstrap(
        tmp_db,
        slug="concurrent-acq",
        homepage="https://example.test/concurrent-acq",
    )
    transport = CountingTransport([
        HttpResponse(
            200, "https://example.test/concurrent-acq",
            {"content-type": "text/html", "etag": '"v1"'},
            b"<html><title>Once</title><p>content</p></html>",
        ),
    ])
    _, worker, _ = _build_runtime(tmp_db, transport, worker_id="worker-concurrent")

    barrier = threading.Barrier(3)
    errors: list[BaseException] = []

    def tick(name: str) -> None:
        try:
            barrier.wait(timeout=5.0)
            SchedulerProcess(tmp_db).run_once()
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=tick, args=(name,)) for name in ("a", "b", "c")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10.0)
    assert not errors, errors

    # Worker drains the single obligation.
    result = worker.run_once(now=T0)
    assert result["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"

    # CRITICAL: the Source was acquired EXACTLY ONCE despite 3 concurrent
    # scheduler ticks.
    assert transport.get_calls == 1

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM acquisition_events").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM monitor_activity").fetchone()[0] == 1
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Section 14 — restart / persistence boundary
# ---------------------------------------------------------------------------


def test_restart_persistence_recovers_queued_monitor_job(tmp_db):
    """Scheduler enqueues a monitor_check, the runtime objects are discarded,
    and reconstructed production worker + queue must drain the queued job
    correctly against the same database.
    """
    source, _policy, monitor = _bootstrap(
        tmp_db,
        slug="restart-queue",
        homepage="https://example.test/restart-queue",
    )
    transport = CountingTransport([
        HttpResponse(
            200, "https://example.test/restart-queue",
            {"content-type": "text/html"},
            b"<html><title>Post-restart</title><p>content</p></html>",
        ),
    ])

    # --- First "process" creates the queued obligation. ---
    process = SchedulerProcess(tmp_db)
    scheduled = process.run_once()
    job_id = scheduled["job_ids"][0]
    assert job_id

    # Discard runtime objects; reconstruct from the same DB.
    del process
    _, worker, _ = _build_runtime(tmp_db, transport, worker_id="worker-after-restart")

    # Worker drains the persisted queued job.
    finished = worker.run_once(now=T0)
    assert finished["status"] == "succeeded"
    assert finished["id"] == job_id
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"
    assert transport.get_calls == 1


def test_restart_persistence_dedup_after_already_acquired_content(tmp_db):
    """A previously acquired Document must deduplicate after service restart:
    the second acquisition against the same final URL must observe the prior
    DocumentVersion and yield truthful no_change without inserting a duplicate
    DocumentVersion.
    """
    source, _policy, monitor = _bootstrap(
        tmp_db,
        slug="restart-dedup",
        homepage="https://example.test/restart-dedup",
    )

    # First "process" acquires content A.
    transport1 = CountingTransport([
        HttpResponse(
            200, "https://example.test/restart-dedup",
            {"content-type": "text/html", "etag": '"v1"'},
            b"<html><title>A</title><p>content A</p></html>",
        ),
    ])
    _, worker, _ = _build_runtime(tmp_db, transport1, worker_id="worker-restart-1")
    SchedulerProcess(tmp_db).run_once()
    assert worker.run_once(now=T0)["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"

    # Restart: discard services; reconstruct against the same DB.
    del worker
    transport2 = CountingTransport([
        HttpResponse(
            200, "https://example.test/restart-dedup",
            {"content-type": "text/html", "etag": '"v1-fresh"'},
            b"<html><title>A</title><p>content A</p></html>",
        ),
    ])
    _force_due(tmp_db, monitor["id"], T1)
    _, worker2, _ = _build_runtime(tmp_db, transport2, worker_id="worker-restart-2")
    SchedulerProcess(tmp_db).run_once()
    assert worker2.run_once(now=T1)["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "no_change"

    conn = storage.connect(tmp_db)
    try:
        versions = conn.execute(
            "SELECT id, content_hash FROM document_versions ORDER BY retrieved_at, id"
        ).fetchall()
        assert len(versions) == 1
        assert versions[0]["content_hash"]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Section 16 — false-success invariant
# ---------------------------------------------------------------------------


def _no_change_paths_to_cover(tmp_db, source_id: str, monitor_id: str) -> None:
    """Walk every path that COULD set ``last_result = no_change`` and confirm
    that each path is preceded by a successful, evidence-bearing acquisition.
    """
    conn = storage.connect(tmp_db)
    try:
        activity = conn.execute(
            "SELECT outcome, error_code FROM monitor_activity WHERE monitor_id = ? ORDER BY observed_at, id",
            (monitor_id,),
        ).fetchall()
        events = conn.execute(
            "SELECT outcome, status_code, channel, error_code FROM acquisition_events WHERE source_id = ? ORDER BY observed_at, id",
            (source_id,),
        ).fetchall()
    finally:
        conn.close()
    for item in activity:
        if item["outcome"] != "no_change":
            continue
        assert events, f"no_change activity {item} without any acquisition event"
        last = events[-1]
        assert last["error_code"] is None, f"no_change activity {item} paired with errored event {last}"
        assert last["status_code"] in {200, 304}, f"no_change paired with status {last['status_code']}"


def test_no_change_requires_successful_unchanged_acquisition(tmp_db):
    """For every ``monitor_activity`` row with ``outcome = no_change``, the
    underlying ``acquisition_events`` must show a non-errored evidence-bearing
    acquisition.
    """
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)

    policy = MonitoringPolicyService(tmp_db).create({
        "name": "p-valid",
        "allowed_channels": ["direct_http"],
        "base_cadence_seconds": 60,
        "min_cadence_seconds": 30,
        "max_cadence_seconds": 300,
    })

    src_a = core.create_source({
        "name": "Valid Source", "slug": "valid-source",
        "homepage_url": "https://example.test/valid-source",
    })
    mon_a = MonitorService(tmp_db).create({
        "target_type": "source", "target_id": src_a["id"],
        "policy_id": policy["id"], "next_check_at": T0,
    })

    transport = CountingTransport([
        HttpResponse(
            200, "https://example.test/valid-source",
            {"content-type": "text/html", "etag": '"v1"'},
            b"<html><title>V</title><p>content</p></html>",
        ),
        HttpResponse(
            200, "https://example.test/valid-source",
            {"content-type": "text/html", "etag": '"v1"'},
            b"<html><title>V</title><p>content</p></html>",
        ),
    ])
    _, worker, _ = _build_runtime(tmp_db, transport, worker_id="worker-no-change")

    SchedulerProcess(tmp_db).run_once()
    assert worker.run_once(now=T0)["status"] == "succeeded"
    assert MonitorService(tmp_db).get(mon_a["id"])["last_result"] == "changed"

    _force_due(tmp_db, mon_a["id"], T1)
    SchedulerProcess(tmp_db).run_once()
    assert worker.run_once(now=T1)["status"] == "succeeded"
    assert MonitorService(tmp_db).get(mon_a["id"])["last_result"] == "no_change"

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 1
    finally:
        conn.close()

    _no_change_paths_to_cover(tmp_db, src_a["id"], mon_a["id"])


def test_false_success_invariant_all_error_paths_never_record_no_change(tmp_db):
    """Negative-space companion to the no_change invariant.

    Walks every Monitor that has been driven through an error path (SSRF,
    missing URL, network timeout) and asserts that ``last_result`` is
    ``error`` and ``monitor_activity`` contains no ``no_change`` rows.
    """
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    policy = MonitoringPolicyService(tmp_db).create({
        "name": "false-success",
        "allowed_channels": ["direct_http"],
        "base_cadence_seconds": 60,
        "min_cadence_seconds": 30,
        "max_cadence_seconds": 300,
    })

    src_b = core.create_source({
        "name": "SSRF Source", "slug": "ssrf-source",
        "homepage_url": "http://127.0.0.1/private",
    })
    mon_b = MonitorService(tmp_db).create({
        "target_type": "source", "target_id": src_b["id"],
        "policy_id": policy["id"], "next_check_at": T0,
    })

    src_c = core.create_source({"name": "Unconfigured Source", "slug": "unconfigured-source"})
    mon_c = MonitorService(tmp_db).create({
        "target_type": "source", "target_id": src_c["id"],
        "policy_id": policy["id"], "next_check_at": T0,
    })

    src_d = core.create_source({
        "name": "Timeout Source", "slug": "timeout-source",
        "homepage_url": "https://example.test/timeout-source",
    })
    mon_d = MonitorService(tmp_db).create({
        "target_type": "source", "target_id": src_d["id"],
        "policy_id": policy["id"], "next_check_at": T0,
    })

    transport = CountingTransport([
        AcquisitionTimeout("deterministic timeout"),
    ])
    _, worker, _ = _build_runtime(tmp_db, transport, worker_id="worker-false-success")

    SchedulerProcess(tmp_db).run_once()
    for _ in range(6):
        result = worker.run_once(now=T2)
        if result is None:
            break

    for monitor in (mon_b, mon_c, mon_d):
        last = MonitorService(tmp_db).get(monitor["id"])
        assert last["last_result"] == "error", (
            f"monitor {monitor['id']} last_result={last['last_result']!r}; "
            "must be 'error' for false-success scenario"
        )
        activity = MonitorService(tmp_db).activity(monitor["id"])["items"]
        assert activity, f"expected error activity for monitor {monitor['id']}"
        assert all(item["outcome"] != "no_change" for item in activity), (
            f"monitor {monitor['id']} recorded no_change activity despite an "
            f"error path: {[dict(a) for a in activity]}"
        )


# ---------------------------------------------------------------------------
# Section 11 — rerun via production API
# ---------------------------------------------------------------------------


def _api_client(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    client = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))
    assert client.post(
        "/api/v1/auth/setup", json={"username": "admin", "password": PASSWORD}
    ).status_code == 201
    assert client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}
    ).status_code == 200
    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
    return config, client, headers


def _create_source_via_api(client, headers, slug: str) -> str:
    response = client.post(
        "/api/v1/sources",
        headers=headers,
        json={"name": slug, "slug": slug, "homepage_url": f"https://example.test/{slug}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_policy_via_api(client, headers) -> str:
    response = client.post(
        "/api/v1/monitoring-policies",
        headers=headers,
        json={
            "name": "rerun-policy",
            "allowed_channels": ["direct_http"],
            "base_cadence_seconds": 60,
            "min_cadence_seconds": 30,
            "max_cadence_seconds": 300,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_monitor_via_api(client, headers, source_id: str, policy_id: str) -> str:
    response = client.post(
        "/api/v1/monitors",
        headers=headers,
        json={
            "target_type": "source",
            "target_id": source_id,
            "policy_id": policy_id,
            "next_check_at": T0,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_rerun_historical_monitor_check_via_api_creates_fresh_active_job(tmp_path):
    config, client, headers = _api_client(tmp_path)
    db_path = config.database_path

    source_id = _create_source_via_api(client, headers, "rerun-api")
    policy_id = _create_policy_via_api(client, headers)
    monitor_id = _create_monitor_via_api(client, headers, source_id, policy_id)

    transport = CountingTransport([
        HttpResponse(
            200, "https://example.test/rerun-api",
            {"content-type": "text/html"},
            b"<html><title>R</title><p>orig</p></html>",
        ),
        HttpResponse(
            200, "https://example.test/rerun-api",
            {"content-type": "text/html"},
            b"<html><title>R</title><p>rerun</p></html>",
        ),
    ])
    _, worker, _ = _build_runtime(db_path, transport, worker_id="worker-rerun-1")
    SchedulerProcess(db_path).run_once()
    finished = worker.run_once(now=T0)
    assert finished["status"] == "succeeded"
    historical_id = finished["id"]

    # Operator requests a rerun via the actual API.
    rerun = client.post(f"/api/v1/jobs/{historical_id}/rerun", headers=headers)
    assert rerun.status_code == 201
    rerun_body = rerun.json()
    assert rerun_body["id"] != historical_id
    assert rerun_body["status"] == "queued"
    assert rerun_body["job_type"] == MONITOR_CHECK_JOB_TYPE
    assert rerun_body["monitor_id"] == monitor_id

    # The fresh active obligation is drained by the same production worker.
    assert worker.run_once(now=T1)["status"] == "succeeded"
    assert MonitorService(db_path).get(monitor_id)["last_result"] == "changed"

    # Exactly two HTTP acquisitions: original + rerun.
    assert transport.get_calls == 2


def test_rerun_while_active_returns_409_via_api(tmp_path):
    config, client, headers = _api_client(tmp_path)
    db_path = config.database_path

    source_id = _create_source_via_api(client, headers, "rerun-conflict")
    policy_id = _create_policy_via_api(client, headers)
    monitor_id = _create_monitor_via_api(client, headers, source_id, policy_id)

    transport = CountingTransport([
        HttpResponse(
            200, "https://example.test/rerun-conflict",
            {"content-type": "text/html"},
            b"<html><title>R</title><p>active</p></html>",
        ),
        HttpResponse(
            200, "https://example.test/rerun-conflict",
            {"content-type": "text/html"},
            b"<html><title>R</title><p>second</p></html>",
        ),
    ])
    _, worker, _ = _build_runtime(db_path, transport, worker_id="worker-conflict")

    # Schedule + claim the active obligation.
    SchedulerProcess(db_path).run_once()
    claimed = worker.run_once(now=T0)
    assert claimed["status"] == "succeeded"

    # Re-schedule another obligation at T1 to leave it queued; rerun the
    # historical terminal job while this fresh active obligation exists.
    _force_due(db_path, monitor_id, T1)
    SchedulerProcess(db_path).run_once()
    active = _active_monitor_jobs(db_path, monitor_id)
    assert len(active) == 1

    rerun = client.post(f"/api/v1/jobs/{claimed['id']}/rerun", headers=headers)
    assert rerun.status_code == 409
    body = rerun.json()
    assert body["error"]["code"] == "job_conflict"
    assert "active" in body["error"]["message"].casefold()


# ---------------------------------------------------------------------------
# Section 10 — disable-before-execution via the production worker handler
# ---------------------------------------------------------------------------


def test_disable_before_execution_via_production_handler_does_not_acquire(tmp_db):
    """Operator disables the Monitor between scheduler tick and worker claim.
    The production worker handler must short-circuit to disabled without
    touching the network. The job terminalizes as succeeded (skipped) and
    no DocumentVersion is created.
    """
    source, _policy, monitor = _bootstrap(
        tmp_db,
        slug="disable-runtime",
        homepage="https://example.test/disable-runtime",
    )
    transport = CountingTransport([])
    _, worker, _ = _build_runtime(tmp_db, transport, worker_id="worker-disable")

    SchedulerProcess(tmp_db).run_once()
    MonitorService(tmp_db).disable(monitor["id"])

    finished = worker.run_once(now=T0)
    assert finished["status"] == "succeeded"
    assert transport.get_calls == 0

    monitor_row = MonitorService(tmp_db).get(monitor["id"])
    assert monitor_row["enabled"] == 0
    activity = MonitorService(tmp_db).activity(monitor["id"])["items"]
    assert activity == []

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM acquisition_events").fetchone()[0] == 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Section 13 — provenance / persistence assertions
# ---------------------------------------------------------------------------


def test_acquisition_persists_full_provenance_through_monitor_pipeline(tmp_db):
    """Verify Document, DocumentVersion, and acquisition_events carry the
    provenance promised by Phase 06 — Source association, canonical URL,
    retrieval timestamps, content hash, etag/last-modified, acquisition
    metadata, HTTP/feed metadata, and Document <-> DocumentVersion linkage.
    """
    source, _policy, monitor = _bootstrap(
        tmp_db,
        slug="provenance",
        homepage="https://example.test/provenance",
    )
    transport = CountingTransport([
        HttpResponse(
            200, "https://example.test/provenance",
            {"content-type": "text/html", "etag": '"prov-v1"',
             "last-modified": "Mon, 17 Aug 2026 12:00:00 GMT"},
            b"<html><title>P</title><p>provenance content</p></html>",
        ),
        HttpResponse(
            200, "https://example.test/provenance",
            {"content-type": "text/html", "etag": '"prov-v2"'},
            b"<html><title>P2</title><p>provenance content 2</p></html>",
        ),
    ])
    _, worker, _ = _build_runtime(tmp_db, transport, worker_id="worker-provenance")
    SchedulerProcess(tmp_db).run_once()
    assert worker.run_once(now=T0)["status"] == "succeeded"

    conn = storage.connect(tmp_db)
    try:
        doc = conn.execute("SELECT * FROM documents").fetchone()
        assert doc["source_id"] == source["id"]
        assert doc["canonical_url"] == "https://example.test/provenance"
        assert doc["title"] == "P"

        versions = conn.execute("SELECT * FROM document_versions").fetchall()
        assert len(versions) == 1
        version = versions[0]
        assert version["document_id"] == doc["id"]
        assert version["content_hash"]
        assert version["retrieved_at"] is not None
        assert version["etag"] == '"prov-v1"'
        assert version["last_modified"] == "Mon, 17 Aug 2026 12:00:00 GMT"

        event = conn.execute("SELECT * FROM acquisition_events").fetchone()
        assert event["source_id"] == source["id"]
        assert event["document_id"] == doc["id"]
        assert event["document_version_id"] == version["id"]
        assert event["channel"] == "direct_http"
        assert event["request_url"] == "https://example.test/provenance"
        assert event["final_url"] == "https://example.test/provenance"
        assert event["status_code"] == 200
        assert event["outcome"] == "retrieved"
        assert event["etag"] == '"prov-v1"'
        assert event["raw_content_hash"] == version["content_hash"]
        assert event["observed_at"] is not None
    finally:
        conn.close()

    transport2 = CountingTransport([
        HttpResponse(
            200, "https://example.test/provenance",
            {"content-type": "text/html", "etag": '"prov-v2"'},
            b"<html><title>P2</title><p>provenance content 2</p></html>",
        ),
    ])
    _, worker2, _ = _build_runtime(tmp_db, transport2, worker_id="worker-provenance-2")
    _force_due(tmp_db, monitor["id"], T1)
    SchedulerProcess(tmp_db).run_once()
    assert worker2.run_once(now=T1)["status"] == "succeeded"

    conn = storage.connect(tmp_db)
    try:
        versions = conn.execute(
            "SELECT id, retrieved_at FROM document_versions ORDER BY retrieved_at, id"
        ).fetchall()
        assert len(versions) == 2
        assert versions[0]["id"] != versions[1]["id"]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Section 15 — candidate_text boundary
# ---------------------------------------------------------------------------


def test_scheduler_payload_never_requires_candidate_text(tmp_db):
    """The scheduler enqueues monitor_check payloads containing ONLY the
    monitor_id. No ``candidate_text`` may be required by the production
    handler for a scheduled job.
    """
    source, _policy, monitor = _bootstrap(
        tmp_db,
        slug="no-candidate",
        homepage="https://example.test/no-candidate",
    )
    process = SchedulerProcess(tmp_db)
    result = process.run_once()
    assert result["enqueued"] == 1
    job_id = result["job_ids"][0]

    conn = storage.connect(tmp_db)
    try:
        row = conn.execute("SELECT payload_json FROM jobs WHERE id = ?", (job_id,)).fetchone()
        payload = row["payload_json"]
        assert "candidate_text" not in payload
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Production handler coverage — defensive check
# ---------------------------------------------------------------------------


def test_production_handlers_cover_monitor_check_job_type(tmp_db):
    """The central production handler registry must register a handler for
    monitor_check so that ``SchedulerService.job_type`` is always drainable.
    """
    handlers = build_worker_handlers(tmp_db)
    assert MONITOR_CHECK_JOB_TYPE in handlers
