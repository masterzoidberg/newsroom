"""Phase 19 — durable changed DocumentVersion processing obligations.

These tests prove the durable orchestration substrate added between
acquisition and future intelligence stages:

    Source → Monitor → monitor_check Job → Worker → Acquisition
      → changed DocumentVersion + Phase 18 artifact
      → durable document_version_process Job (same transaction)
      → processing Worker handler
      → deterministic Phase-19 result

Only queue/orchestration behavior is exercised here. Nothing invokes
relevance, AI providers, Evidence/Claims, Story evolution, Reports, or Alerts.
The transport is deterministic (no real internet).
"""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

import pytest

from newsroom import storage
from newsroom.acquisition import AcquisitionService, AcquisitionTimeout, HttpResponse
from newsroom.content_artifacts import normalized_text_hash
from newsroom.document_processing import enqueue_document_version_processing_tx
from newsroom.domain import CoreService
from newsroom.integrity import check_database
from newsroom.jobs import (
    DOCUMENT_VERSION_PROCESS_JOB_TYPE,
    JobConflict,
    JobService,
    MONITOR_CHECK_JOB_TYPE,
    RESEARCH_QUESTION_JOB_TYPE,
)
from newsroom.migrations import apply_migrations
from newsroom.monitoring import MonitorExecutionService, MonitorService, MonitoringPolicyService
from newsroom.research_questions import ResearchQuestionService
from newsroom.runtime import build_worker_handlers, build_worker_queue
from newsroom.scheduler import SchedulerProcess
from newsroom.worker import WorkerProcess

T0 = "2026-08-18T12:00:00Z"
T1 = "2026-08-18T12:01:00Z"
T2 = "2026-08-18T12:02:00Z"

HTML_A = b"<html><title>Title A</title><p>First paragraph, visible text A.</p></html>"

RSS_TWO = b"""<rss version="2.0"><channel><title>Feed</title>
<item><title>Entry One</title><link>https://example.test/f/1</link><description>desc 1</description></item>
<item><title>Entry Two</title><link>https://example.test/f/2</link><description>desc 2</description></item>
</channel></rss>"""


class CountingTransport:
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


def _bootstrap(tmp_db, *, slug: str, homepage: str, feed_url: str | None = None):
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


def _direct_acquisition(tmp_db, *, slug: str, url: str):
    source = CoreService(tmp_db).create_source({"name": slug, "slug": slug, "homepage_url": url})
    AcquisitionService(
        tmp_db,
        transport=CountingTransport([HttpResponse(200, url, {"content-type": "text/html"}, HTML_A)]),
    ).acquire_document(source["id"], url)
    return _get(tmp_db, "SELECT * FROM document_versions")


def _get(db, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row:
    conn = storage.connect(db)
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _count(db, table: str, where: str = "1=1", params: tuple[Any, ...] = ()) -> int:
    conn = storage.connect(db)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0]
    finally:
        conn.close()


def _processing_jobs(db, version_id: str | None = None) -> list[sqlite3.Row]:
    conn = storage.connect(db)
    try:
        if version_id is None:
            return list(conn.execute(
                "SELECT * FROM jobs WHERE job_type = ? ORDER BY created_at, id",
                (DOCUMENT_VERSION_PROCESS_JOB_TYPE,),
            ).fetchall())
        return list(conn.execute(
            "SELECT * FROM jobs WHERE job_type = ? AND document_version_id = ? ORDER BY created_at, id",
            (DOCUMENT_VERSION_PROCESS_JOB_TYPE, version_id),
        ).fetchall())
    finally:
        conn.close()


def _payload(row: sqlite3.Row) -> dict[str, Any]:
    return json.loads(row["payload_json"])


def _monitor_worker(tmp_db, transport, *, worker_id: str = "worker-p19") -> WorkerProcess:
    acquisition = AcquisitionService(tmp_db, transport=transport)
    handlers = MonitorExecutionService(tmp_db, acquisition_service=acquisition).handlers()
    return WorkerProcess(tmp_db, handlers, worker_id=worker_id, queue=build_worker_queue(tmp_db))


# ---------------------------------------------------------------------------
# 1-6. Which acquisitions create processing work
# ---------------------------------------------------------------------------


def test_new_changed_html_version_creates_exactly_one_processing_job(tmp_db):
    source, _policy, monitor = _bootstrap(tmp_db, slug="p19-html", homepage="https://example.test/p19-html")
    transport = CountingTransport([HttpResponse(200, "https://example.test/p19-html", {"content-type": "text/html"}, HTML_A)])
    worker = _monitor_worker(tmp_db, transport, worker_id="worker-p19-html")

    SchedulerProcess(tmp_db).run_once()
    finished = worker.run_once(now=T0)
    assert finished["status"] == "succeeded"
    assert finished["job_type"] == MONITOR_CHECK_JOB_TYPE

    version = _get(tmp_db, "SELECT * FROM document_versions")
    obligations = _processing_jobs(tmp_db, version["id"])
    assert len(obligations) == 1
    ob = obligations[0]
    assert ob["status"] == "queued"
    assert ob["document_version_id"] == version["id"]
    # jobs.monitor_id stays NULL: it remains the monitor_check execution
    # ownership column only; provenance lives in the canonical-ID payload.
    assert ob["monitor_id"] is None
    payload = _payload(ob)
    assert payload["document_version_id"] == version["id"]
    assert payload["document_id"] == version["document_id"]
    assert payload["source_id"] == source["id"]
    assert payload["monitor_id"] == monitor["id"]
    assert "candidate_text" not in payload


def test_feed_new_entries_each_create_processing_job(tmp_db):
    source, _policy, monitor = _bootstrap(
        tmp_db,
        slug="p19-feed",
        homepage="https://example.test/p19-feed-home",
        feed_url="https://example.test/feed.xml",
    )
    transport = CountingTransport([HttpResponse(200, "https://example.test/feed.xml", {"content-type": "application/rss+xml"}, RSS_TWO)])
    worker = _monitor_worker(tmp_db, transport, worker_id="worker-p19-feed")

    SchedulerProcess(tmp_db).run_once()
    finished = worker.run_once(now=T0)
    assert finished["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"

    obligations = _processing_jobs(tmp_db)
    assert len(obligations) == 2
    assert len({row["document_version_id"] for row in obligations}) == 2
    assert _count(tmp_db, "document_versions") == 2


def test_http_304_creates_no_processing_job(tmp_db):
    source, _policy, monitor = _bootstrap(tmp_db, slug="p19-304", homepage="https://example.test/p19-304")
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/p19-304", {"content-type": "text/html", "etag": '"v1"'}, HTML_A),
        HttpResponse(304, "https://example.test/p19-304", {"etag": '"v1"'}, b""),
    ])
    worker = _monitor_worker(tmp_db, transport, worker_id="worker-p19-304")

    SchedulerProcess(tmp_db).run_once()
    assert worker.run_once(now=T0)["status"] == "succeeded"
    # The changed first acquisition created exactly one obligation.
    first = _processing_jobs(tmp_db)
    assert len(first) == 1

    MonitorService(tmp_db).update(monitor["id"], {"next_check_at": T1})
    SchedulerProcess(tmp_db).run_once()
    assert worker.run_once(now=T1)["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "no_change"
    # HTTP 304 added no additional processing obligation.
    assert _processing_jobs(tmp_db) == first


def test_unchanged_feed_creates_no_new_processing_job(tmp_db):
    source, _policy, monitor = _bootstrap(
        tmp_db,
        slug="p19-fn",
        homepage="https://example.test/p19-fn-home",
        feed_url="https://example.test/feed-nc.xml",
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/feed-nc.xml", {"content-type": "application/rss+xml", "etag": '"f1"'}, RSS_TWO),
        HttpResponse(304, "https://example.test/feed-nc.xml", {"etag": '"f1"'}, b""),
    ])
    worker = _monitor_worker(tmp_db, transport, worker_id="worker-p19-fn")

    SchedulerProcess(tmp_db).run_once()
    assert worker.run_once(now=T0)["status"] == "succeeded"
    first = _processing_jobs(tmp_db)
    assert len(first) == 2

    MonitorService(tmp_db).update(monitor["id"], {"next_check_at": T1})
    SchedulerProcess(tmp_db).run_once()
    assert worker.run_once(now=T1)["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "no_change"
    assert _processing_jobs(tmp_db) == first


def test_acquisition_error_creates_no_processing_job(tmp_db):
    source, _policy, monitor = _bootstrap(tmp_db, slug="p19-err", homepage="https://example.test/p19-err")
    transport = CountingTransport([AcquisitionTimeout("deterministic timeout")])
    worker = _monitor_worker(tmp_db, transport, worker_id="worker-p19-err")

    SchedulerProcess(tmp_db).run_once()
    worker.run_once(now=T0)
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "error"
    assert _processing_jobs(tmp_db) == []
    assert _count(tmp_db, "document_versions") == 0


def test_disabled_monitor_creates_no_processing_job(tmp_db):
    source, _policy, monitor = _bootstrap(tmp_db, slug="p19-dis", homepage="https://example.test/p19-dis")
    transport = CountingTransport([])
    worker = _monitor_worker(tmp_db, transport, worker_id="worker-p19-dis")

    SchedulerProcess(tmp_db).run_once()
    MonitorService(tmp_db).disable(monitor["id"])
    finished = worker.run_once(now=T0)
    assert finished["status"] == "succeeded"
    assert transport.get_calls == 0
    assert _processing_jobs(tmp_db) == []
    assert _count(tmp_db, "document_versions") == 0


# ---------------------------------------------------------------------------
# 7-9. Handler: resolve version + artifact, deterministic result, no AI
# ---------------------------------------------------------------------------


def test_processing_handler_resolves_version_and_verified_artifact(tmp_db):
    source, _policy, monitor = _bootstrap(tmp_db, slug="p19-hdl", homepage="https://example.test/p19-hdl")
    transport = CountingTransport([HttpResponse(200, "https://example.test/p19-hdl", {"content-type": "text/html"}, HTML_A)])
    worker = _monitor_worker(tmp_db, transport, worker_id="worker-p19-hdl")
    SchedulerProcess(tmp_db).run_once()
    assert worker.run_once(now=T0)["status"] == "succeeded"

    version = _get(tmp_db, "SELECT * FROM document_versions")
    artifact = _get(tmp_db, "SELECT * FROM content_artifacts WHERE id = ?", (version["artifact_id"],))

    handlers = build_worker_handlers(tmp_db)
    processor = WorkerProcess(tmp_db, handlers, worker_id="worker-p19-proc", queue=build_worker_queue(tmp_db))
    result = processor.run_once(now=T1)
    assert result is not None
    assert result["job_type"] == DOCUMENT_VERSION_PROCESS_JOB_TYPE
    assert result["status"] == "succeeded"
    assert result["result"]["document_version_id"] == version["id"]
    assert result["result"]["artifact_id"] == artifact["id"]
    assert result["result"]["normalized_content_hash"] == artifact["normalized_content_hash"]
    assert result["result"]["content_hash"] == version["content_hash"]
    assert result["result"]["content_length"] == artifact["text_length"]
    assert result["result"]["content_kind"] == "visible_text"
    assert result["result"]["processing_status"] == "completed"
    assert normalized_text_hash(artifact["normalized_text"]) == result["result"]["normalized_content_hash"]
    assert check_database(tmp_db).ok is True


def test_processing_handler_only_runs_deterministic_local_relevance(tmp_db):
    source, _policy, monitor = _bootstrap(tmp_db, slug="p19-noai", homepage="https://example.test/noai")
    transport = CountingTransport([HttpResponse(200, "https://example.test/noai", {"content-type": "text/html"}, HTML_A)])
    worker = _monitor_worker(tmp_db, transport, worker_id="worker-p19-noai")
    SchedulerProcess(tmp_db).run_once()
    assert worker.run_once(now=T0)["status"] == "succeeded"

    processor = WorkerProcess(
        tmp_db, build_worker_handlers(tmp_db), worker_id="worker-p19-noai-2", queue=build_worker_queue(tmp_db)
    )
    finished = processor.run_once(now=T1)
    assert finished["status"] == "succeeded"
    # Phase 20 evaluates deterministic relevance. This monitor carries no
    # approved information need, so the truthful outcome is an explicit
    # not_applicable, never a fabricated relevant/not-relevant and never an
    # analysis stage.
    relevance = finished["result"]["relevance"]
    assert relevance["status"] == "not_applicable"
    assert "relevant" not in relevance
    assert relevance["paid_used"] is False
    assert "analysis" not in finished["result"]

    for table in ("evidence_spans", "claims", "stories", "story_revisions", "living_reports", "alerts"):
        assert _count(tmp_db, table) == 0, table
    conn = storage.connect(tmp_db)
    try:
        rows = conn.execute("SELECT capability FROM provider_usage").fetchall()
    finally:
        conn.close()
    assert rows and all(row[0] == "acquisition" for row in rows)
    assert _count(tmp_db, "document_version_relevance") == 0


# ---------------------------------------------------------------------------
# 10-11. Idempotency / coalescing / concurrency
# ---------------------------------------------------------------------------


def test_autonomous_duplicate_enqueue_is_coalesced(tmp_db):
    apply_migrations(tmp_db)
    version = _direct_acquisition(tmp_db, slug="p19-dup", url="https://example.test/dup")
    obligations = _processing_jobs(tmp_db, version["id"])
    assert len(obligations) == 1

    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            same = enqueue_document_version_processing_tx(conn, version_id=version["id"])
    finally:
        conn.close()
    assert same["coalesced"] is True
    assert same["id"] == obligations[0]["id"]
    assert len(_processing_jobs(tmp_db, version["id"])) == 1


def test_concurrent_enqueue_produces_one_active_obligation(tmp_db):
    apply_migrations(tmp_db)
    version = _direct_acquisition(tmp_db, slug="p19-con", url="https://example.test/con")
    _processing_jobs(tmp_db, version["id"])

    # Remove the first obligation: the concurrent writers are the only ones
    # creating work for this version.
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DELETE FROM jobs")
    finally:
        conn.close()

    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def attempt() -> None:
        try:
            barrier.wait(timeout=5.0)
            c = storage.connect(tmp_db)
            try:
                with storage.write_tx(c):
                    enqueue_document_version_processing_tx(c, version_id=version["id"])
            finally:
                c.close()
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10.0)
    assert not errors, errors
    assert len(_processing_jobs(tmp_db, version["id"])) == 1


# ---------------------------------------------------------------------------
# 12-14. Direct enqueue and rerun semantics
# ---------------------------------------------------------------------------


def test_direct_enqueue_requires_canonical_ownership_and_version_exists(tmp_db):
    apply_migrations(tmp_db)
    version = _direct_acquisition(tmp_db, slug="p19-de", url="https://example.test/de")
    queue = build_worker_queue(tmp_db)
    # The automatic obligation is still active; remove it so the direct
    # enqueue path below is exercised on a version without active work.
    auto = _processing_jobs(tmp_db, version["id"])[0]
    queue.cancel(auto["id"], reason="test-harness")

    with pytest.raises(Exception):
        queue.enqueue(DOCUMENT_VERSION_PROCESS_JOB_TYPE, {}, idempotency_key="p19-de-k1")
    with pytest.raises(Exception):
        queue.enqueue(
            DOCUMENT_VERSION_PROCESS_JOB_TYPE,
            {"document_version_id": "nonexistent-dv"},
            idempotency_key="p19-de-k2",
            document_version_id="nonexistent-dv",
        )
    # A conflicting caller-supplied document_id passes queue validation but is
    # rejected authoritatively by the processing handler against the
    # persisted version.
    conflicting = queue.enqueue(
        DOCUMENT_VERSION_PROCESS_JOB_TYPE,
        {"document_version_id": version["id"], "document_id": "wrong-owner"},
        document_version_id=version["id"],
    )
    assert conflicting["status"] == "queued"
    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-p19-de", queue=queue)
    finished = worker.run_once(now=T1)
    assert finished["status"] == "failed"
    assert finished["failure_cause"] == "DomainValidation"


def test_direct_enqueue_rejects_second_active_obligation(tmp_db):
    apply_migrations(tmp_db)
    version = _direct_acquisition(tmp_db, slug="p19-da", url="https://example.test/da")
    queue = build_worker_queue(tmp_db)
    # Retire the automatic obligation so the direct enqueue below becomes the
    # first active obligation for the version.
    auto = _processing_jobs(tmp_db, version["id"])[0]
    queue.cancel(auto["id"], reason="test-harness")
    first = queue.enqueue(
        DOCUMENT_VERSION_PROCESS_JOB_TYPE,
        {"document_version_id": version["id"]},
        document_version_id=version["id"],
    )
    assert first["status"] == "queued"
    with pytest.raises(JobConflict):
        queue.enqueue(
            DOCUMENT_VERSION_PROCESS_JOB_TYPE,
            {"document_version_id": version["id"]},
            idempotency_key="p19-da-unique",
            document_version_id=version["id"],
        )


def test_rerun_rejected_while_active_processing_job_exists(tmp_db):
    apply_migrations(tmp_db)
    version = _direct_acquisition(tmp_db, slug="p19-ra", url="https://example.test/ra")
    queue = build_worker_queue(tmp_db)
    ob = _processing_jobs(tmp_db, version["id"])[0]
    claimed = queue.claim(ob["id"], "worker-a", now=T0)
    assert claimed["status"] == "running"
    with pytest.raises(JobConflict):
        queue.rerun(ob["id"])


def test_rerun_of_terminal_processing_job_creates_fresh_obligation(tmp_db):
    apply_migrations(tmp_db)
    version = _direct_acquisition(tmp_db, slug="p19-rt", url="https://example.test/rt")
    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-p19-rt", queue=queue)
    finished = worker.run_once(now=T0)
    assert finished["job_type"] == DOCUMENT_VERSION_PROCESS_JOB_TYPE
    assert finished["status"] == "succeeded"

    rerun = queue.rerun(finished["id"])
    assert rerun["id"] != finished["id"]
    assert rerun["status"] == "queued"
    assert rerun["document_version_id"] == version["id"]
    second = worker.run_once(now=T1)
    assert second["status"] == "succeeded"
    assert second["document_version_id"] == version["id"]
    assert len(_processing_jobs(tmp_db, version["id"])) == 2


# ---------------------------------------------------------------------------
# 15-17. Failure semantics
# ---------------------------------------------------------------------------


def _insert_job_raw(db, job_id: str, version_id: str, *, payload_version: str | None = None) -> None:
    payload = json.dumps({"document_version_id": payload_version or version_id}, sort_keys=True, separators=(",", ":"))
    raw = sqlite3.connect(str(db))
    raw.execute("PRAGMA foreign_keys = OFF")
    raw.execute(
        "INSERT INTO jobs (id, job_type, status, payload_json, idempotency_key, document_version_id, priority, max_attempts, created_at, updated_at) "
        "VALUES (?, ?, 'queued', ?, ?, ?, 0, 1, ?, ?)",
        (job_id, DOCUMENT_VERSION_PROCESS_JOB_TYPE, payload, f"raw-{job_id}", version_id, T0, T0),
    )
    raw.commit()
    raw.close()


def test_missing_document_version_fails_terminally(tmp_db):
    apply_migrations(tmp_db)
    _insert_job_raw(tmp_db, "job_ghost", "dv_ghost")

    processor = WorkerProcess(
        tmp_db, build_worker_handlers(tmp_db), worker_id="worker-ghost", queue=build_worker_queue(tmp_db)
    )
    finished = processor.run_once(now=T1)
    assert finished["status"] == "failed"
    assert finished["failure_cause"] == "DomainNotFound"
    assert finished["attempts"] == 1


def test_legacy_artifactless_version_terminates_truthfully(tmp_db):
    apply_migrations(tmp_db)
    source = CoreService(tmp_db).create_source({"name": "s", "slug": "p19-legacy", "homepage_url": "https://example.test/legacy"})
    document = CoreService(tmp_db).create_document({"source_id": source["id"], "canonical_url": "https://example.test/legacy", "title": "Legacy"})
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "INSERT INTO document_versions (id, document_id, retrieved_at, content_hash, content_kind, normalized_json, created_at) "
                "VALUES ('dv_legacy_p19', ?, ?, 'oldhash', 'excerpt', ?, ?)",
                (document["id"], T0, '{"title": "Legacy"}', T0),
            )
            conn.execute(
                "INSERT INTO jobs (id, job_type, status, payload_json, idempotency_key, document_version_id, priority, max_attempts, created_at, updated_at) "
                "VALUES ('job_legacy', ?, 'queued', '{\"document_version_id\": \"dv_legacy_p19\"}', 'legacy-key', 'dv_legacy_p19', 0, 1, ?, ?)",
                (DOCUMENT_VERSION_PROCESS_JOB_TYPE, T0, T0),
            )
    finally:
        conn.close()

    processor = WorkerProcess(
        tmp_db, build_worker_handlers(tmp_db), worker_id="worker-legacy", queue=build_worker_queue(tmp_db)
    )
    finished = processor.run_once(now=T0)
    assert finished["status"] == "failed"
    assert finished["failure_cause"] == "LegacyVersionWithoutArtifact"
    # No content was fabricated and history stays untouched.
    row = _get(tmp_db, "SELECT normalized_json FROM document_versions WHERE id = 'dv_legacy_p19'")
    assert row[0] == '{"title": "Legacy"}'


def test_artifact_hash_mismatch_fails_terminally_without_refetch(tmp_db):
    apply_migrations(tmp_db)
    # Build a version referencing a corrupted artifact directly (FK off
    # simulates the storage-level corruption Phase 18's loader must detect).
    raw = sqlite3.connect(str(tmp_db))
    raw.execute("PRAGMA foreign_keys = OFF")
    raw.execute(
        "INSERT INTO content_artifacts "
        "(id, normalized_content_hash, content_kind, norm_version, normalized_text, text_length, retention_eligible, created_at) "
        "VALUES ('art_corrupt19', 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef', "
        "'visible_text', 'visible_text_v1', 'tampered content', 15, 1, ?)",
        (T0,),
    )
    raw.execute(
        "INSERT INTO documents "
        "(id, source_id, canonical_url, canonical_url_hash, title, title_normalized, first_seen_at, created_at) "
        "VALUES ('doc_ghost', 'src_ghost', 'https://example.test/ghost', 'ghost-fp', 'Ghost', 'ghost', ?, ?)",
        (T0, T0),
    )
    raw.execute(
        "INSERT INTO document_versions "
        "(id, document_id, retrieved_at, content_hash, content_kind, artifact_id, normalized_json, created_at) "
        "VALUES ('dv_corrupt19', 'doc_ghost', ?, 'rawhash', 'excerpt', 'art_corrupt19', '{}', ?)",
        (T0, T0),
    )
    raw.execute(
        "INSERT INTO jobs (id, job_type, status, payload_json, idempotency_key, document_version_id, priority, max_attempts, created_at, updated_at) "
        "VALUES ('job_corrupt', ?, 'queued', '{\"document_version_id\": \"dv_corrupt19\"}', 'corrupt-key', 'dv_corrupt19', 0, 1, ?, ?)",
        (DOCUMENT_VERSION_PROCESS_JOB_TYPE, T0, T0),
    )
    raw.commit()
    raw.close()

    processor = WorkerProcess(
        tmp_db, build_worker_handlers(tmp_db), worker_id="worker-corrupt", queue=build_worker_queue(tmp_db)
    )
    finished = processor.run_once(now=T1)
    assert finished["status"] == "failed"
    assert finished["failure_cause"] in {"ArtifactHashMismatch", "ArtifactLengthMismatch"}
    assert finished["attempts"] == 1


# ---------------------------------------------------------------------------
# 18-20. Restart / recovery / cancellation
# ---------------------------------------------------------------------------


def test_queue_survives_process_object_restart(tmp_db):
    source, _policy, monitor = _bootstrap(tmp_db, slug="p19-restart", homepage="https://example.test/restart")
    transport = CountingTransport([HttpResponse(200, "https://example.test/restart", {"content-type": "text/html"}, HTML_A)])
    worker = _monitor_worker(tmp_db, transport, worker_id="worker-restart-1")
    SchedulerProcess(tmp_db).run_once()
    assert worker.run_once(now=T0)["status"] == "succeeded"
    obligations = _processing_jobs(tmp_db)
    assert len(obligations) == 1

    del worker
    processor = WorkerProcess(
        tmp_db, build_worker_handlers(tmp_db), worker_id="worker-restart-2", queue=build_worker_queue(tmp_db)
    )
    finished = processor.run_once(now=T1)
    assert finished["status"] == "succeeded"
    assert finished["id"] == obligations[0]["id"]


def test_lease_expiry_recovers_processing_obligation(tmp_db):
    apply_migrations(tmp_db)
    version = _direct_acquisition(tmp_db, slug="lease", url="https://example.test/lease")
    queue = JobService(tmp_db, lease_seconds=10, backoff_base_seconds=20)
    ob = _processing_jobs(tmp_db, version["id"])[0]
    claimed = queue.claim(ob["id"], "worker-a", now=T0)
    assert claimed["status"] == "running"

    recovered = queue.recover_expired(now=T1)
    assert recovered == 1
    state = queue.get(ob["id"])
    assert state["status"] == "queued"
    assert state["failure_cause"] == "lease_expired"

    assert queue.claim(ob["id"], "worker-b", now=T1) is None
    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-lease", queue=queue)
    finished = worker.run_once(now=T2)
    assert finished["status"] == "succeeded"


def test_cancellation_never_falsely_reports_processing_success(tmp_db):
    apply_migrations(tmp_db)
    version = _direct_acquisition(tmp_db, slug="cancel", url="https://example.test/cancel")
    queue = build_worker_queue(tmp_db)
    ob = _processing_jobs(tmp_db, version["id"])[0]

    cancelled = queue.cancel(ob["id"], reason="operator")
    assert cancelled["status"] == "cancelled"
    assert cancelled["result"] is None

    running = queue.enqueue(
        DOCUMENT_VERSION_PROCESS_JOB_TYPE,
        {"document_version_id": version["id"]},
        document_version_id=version["id"],
    )
    claimed = queue.claim(running["id"], "worker-a", now=T0)
    assert claimed["status"] == "running"
    requested = queue.cancel(running["id"], reason="operator")
    assert requested["cancel_requested_at"] is not None
    finished = queue.complete(running["id"], "worker-a", "succeeded", now=T0)
    assert finished["status"] == "cancelled"
    assert finished["result"] is None
    assert check_database(tmp_db).ok is True


# ---------------------------------------------------------------------------
# 21-22. Existing job families unchanged
# ---------------------------------------------------------------------------


def test_monitor_check_coalescing_remains_unchanged(tmp_db):
    source, _policy, monitor = _bootstrap(tmp_db, slug="coalesce", homepage="https://example.test/coalesce")
    transport = CountingTransport([HttpResponse(200, "https://example.test/coalesce", {"content-type": "text/html"}, HTML_A)])
    worker = _monitor_worker(tmp_db, transport, worker_id="worker-coalesce")
    scheduler = SchedulerProcess(tmp_db)
    first = scheduler.run_once()
    second = scheduler.run_once()
    assert len(first["job_ids"]) == 1
    assert second["job_ids"] == []
    assert worker.run_once(now=T0)["status"] == "succeeded"
    assert _count(
        tmp_db,
        "jobs",
        where="monitor_id = ? AND job_type = ? AND status IN ('queued','running')",
        params=(monitor["id"], MONITOR_CHECK_JOB_TYPE),
    ) == 0


def test_research_question_jobs_remain_unchanged(tmp_db):
    apply_migrations(tmp_db)
    question = ResearchQuestionService(tmp_db).create({"question": "Why?", "search_attempt_budget": 2})
    pursuit = ResearchQuestionService(tmp_db).pursue(
        question["id"], mode="manual", query_units=0, local_model_units=0, query="Why?"
    )
    assert pursuit["job_type"] == RESEARCH_QUESTION_JOB_TYPE
    assert pursuit["document_version_id"] is None
    worker = WorkerProcess(
        tmp_db, build_worker_handlers(tmp_db), worker_id="worker-rq", queue=build_worker_queue(tmp_db)
    )
    finished = worker.run_once(now=T0)
    assert finished["status"] == "succeeded"
    assert finished["job_type"] == RESEARCH_QUESTION_JOB_TYPE
    attempt = _get(tmp_db, "SELECT status FROM research_question_attempts WHERE job_id = ?", (finished["id"],))
    # Research runs with zero local findings truthfully reconcile to 'partial'
    # (existing behavior); the attempt must be terminal and consistent.
    assert attempt is not None and attempt[0] in {"succeeded", "partial"}


# ---------------------------------------------------------------------------
# Production-composition acceptance
# ---------------------------------------------------------------------------


def test_production_composition_changed_version_to_durable_processing(tmp_db):
    source, _policy, monitor = _bootstrap(tmp_db, slug="prod", homepage="https://example.test/prod")
    transport = CountingTransport([HttpResponse(200, "https://example.test/prod", {"content-type": "text/html"}, HTML_A)])
    acquisition = AcquisitionService(tmp_db, transport=transport)
    monitor_handlers = MonitorExecutionService(tmp_db, acquisition_service=acquisition).handlers()
    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(tmp_db, monitor_handlers, worker_id="worker-prod-1", queue=queue)

    scheduled = SchedulerProcess(tmp_db).run_once()
    assert scheduled["enqueued"] == 1
    acquisition_job = worker.run_once(now=T0)
    assert acquisition_job["status"] == "succeeded"
    assert acquisition_job["job_type"] == MONITOR_CHECK_JOB_TYPE

    assert _count(tmp_db, "monitor_activity", where="outcome = 'changed'") == 1
    assert _count(tmp_db, "document_versions") == 1
    assert _count(tmp_db, "content_artifacts") == 1
    assert len(_processing_jobs(tmp_db)) == 1
    transport_calls = transport.get_calls

    del worker, queue, monitor_handlers, transport, acquisition
    handlers = build_worker_handlers(tmp_db)
    queue2 = build_worker_queue(tmp_db)
    worker2 = WorkerProcess(tmp_db, handlers, worker_id="worker-prod-2", queue=queue2)
    processing = worker2.run_once(now=T1)
    assert processing is not None
    assert processing["job_type"] == DOCUMENT_VERSION_PROCESS_JOB_TYPE
    assert processing["status"] == "succeeded"

    assert _count(tmp_db, "jobs", where="job_type = ?", params=(MONITOR_CHECK_JOB_TYPE,)) == 1
    assert _count(tmp_db, "jobs", where="job_type = ?", params=(DOCUMENT_VERSION_PROCESS_JOB_TYPE,)) == 1
    version = _get(tmp_db, "SELECT * FROM document_versions")
    artifact = _get(tmp_db, "SELECT * FROM content_artifacts WHERE id = ?", (version["artifact_id"],))
    assert processing["result"]["document_version_id"] == version["id"]
    assert processing["result"]["artifact_id"] == artifact["id"]
    assert processing["result"]["normalized_content_hash"] == artifact["normalized_content_hash"]
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"
    assert transport_calls == 1
    assert worker2.run_once(now=T1) is None


# ---------------------------------------------------------------------------
# Crash-gap acceptance: same-transaction handoff
# ---------------------------------------------------------------------------


def test_crash_gap_no_commit_state_without_processing_obligation(tmp_db, monkeypatch):
    source, _policy, monitor = _bootstrap(tmp_db, slug="crash", homepage="https://example.test/crash")
    transport = CountingTransport([HttpResponse(200, "https://example.test/crash", {"content-type": "text/html"}, HTML_A)])
    from newsroom import acquisition as acquisition_module  # noqa: PLC0415

    def boom(*args, **kwargs):
        raise RuntimeError("injected processing enqueue failure")

    monkeypatch.setattr(acquisition_module, "enqueue_document_version_processing_tx", boom)
    worker = _monitor_worker(tmp_db, transport, worker_id="worker-crash")

    SchedulerProcess(tmp_db).run_once()
    finished = worker.run_once(now=T0)
    assert finished["status"] == "failed"

    # The whole DocumentVersion / artifact / event transaction rolled back
    # together with the obligation: no commit state can retain the version
    # while losing its processing obligation.
    assert _count(tmp_db, "documents") == 0
    assert _count(tmp_db, "document_versions") == 0
    assert _count(tmp_db, "content_artifacts") == 0
    assert _count(tmp_db, "acquisition_events") == 0
    assert _count(tmp_db, "jobs", where="job_type = ?", params=(DOCUMENT_VERSION_PROCESS_JOB_TYPE,)) == 0