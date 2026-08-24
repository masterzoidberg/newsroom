"""Phase 20 — semantic scope and automatic relevance.

These tests prove every changed DocumentVersion from an eligible Monitor is
automatically evaluated against the actual approved information need that
caused Newsroom to care about it:

    Source → Monitor (explicit approved information need)
      → monitor_check Job → Worker → Acquisition
      → DocumentVersion + Phase 18 artifact
      → document_version_process Job (scope version pinned at acquisition)
      → fresh Worker → verified artifact → approved RelevanceScope snapshot
      → deterministic local RelevanceCascade → durable relevance decision
      → terminal processing result → STOP before article analysis

The relevance scope is never inferred from Source name/URL, never global, and
never caller-supplied (no candidate_text). Pending/rejected vocabulary
suggestions never participate. Exclusions are first-class. Relevant and
not-relevant are both successful processing outcomes; a missing scope or
invalid provenance is a truthful terminal failure (COULD NOT EVALUATE), never
a false negative. No remote AI provider, no article analysis, no
Evidence/Claims/Story/Report/Alert work.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest

from newsroom import storage
from newsroom.acquisition import AcquisitionService, HttpResponse
from newsroom.domain import CoreService
from newsroom.integrity import check_database
from newsroom.jobs import DOCUMENT_VERSION_PROCESS_JOB_TYPE, MONITOR_CHECK_JOB_TYPE
from newsroom.migrations import (
    MIGRATION_0001_STATEMENTS,
    MIGRATION_0002_STATEMENTS,
    MIGRATION_0003_STATEMENTS,
    MIGRATION_0004_STATEMENTS,
    MIGRATION_0005_STATEMENTS,
    MIGRATION_0006_STATEMENTS,
    MIGRATION_0007_STATEMENTS,
    MIGRATION_0008_STATEMENTS,
    MIGRATION_0009_STATEMENTS,
    MIGRATION_0010_STATEMENTS,
    MIGRATION_0011_STATEMENTS,
    MIGRATION_0012_STATEMENTS,
    MIGRATION_0013_STATEMENTS,
    MIGRATION_0014_STATEMENTS,
    MIGRATION_0015_STATEMENTS,
    MIGRATION_0016_STATEMENTS,
    apply_migrations,
    migration_status,
)
from newsroom.monitoring import (
    DocumentVersionRelevanceService,
    MonitorExecutionService,
    MonitorService,
    MonitoringPolicyService,
    ScopeSuggestionService,
)
from newsroom.runtime import build_worker_handlers, build_worker_queue
from newsroom.scheduler import SchedulerProcess
from newsroom.worker import WorkerProcess

T0 = "2026-08-18T12:00:00Z"
T1 = "2026-08-18T12:01:00Z"
T2 = "2026-08-18T12:02:00Z"

HTML_RELEVANT = b"<html><title>Aviary</title><p>The Pentagon released the new UAP report today.</p></html>"
HTML_IRRELEVANT = b"<html><title>Markets</title><p>Central banks raise interest rates amid inflation.</p></html>"
HTML_UFO_ONLY = b"<html><title>Nevada</title><p>A strange light over Nevada was filmed last night.</p></html>"
HTML_UAP_NEW = b"<html><title>Saucers</title><p>Officials confirmed the new UAP and a flying saucer appearance.</p></html>"

RSS_MIXED = b"""<rss version="2.0"><channel><title>Mixed Feed</title>
<item><title>UAP video from squadron cockpit</title><link>https://example.test/a/1</link><description>Pilots describe the object.</description></item>
<item><title>Economy forecast</title><link>https://example.test/uap/2</link><description>The headline rally continues.</description></item>
</channel></rss>"""


class CountingTransport:
    def __init__(self, responses):
        self._responses = list(responses)
        self.get_calls = 0

    def get(self, url, *, headers, policy):
        self.get_calls += 1
        if not self._responses:
            raise AssertionError("CountingTransport exhausted: unexpected acquisition call")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class UrlKeyedTransport:
    """Returns the response registered for the exact requested URL."""

    def __init__(self, responses: dict[str, HttpResponse]):
        self.responses = dict(responses)
        self.get_calls = 0

    def get(self, url, *, headers, policy):
        self.get_calls += 1
        if url not in self.responses:
            raise AssertionError(f"UrlKeyedTransport: unexpected acquisition call to {url}")
        return self.responses.pop(url)


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


def _payload(row: sqlite3.Row) -> dict[str, Any]:
    return json.loads(row["payload_json"])


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


def _relevance_records(db) -> list[dict[str, Any]]:
    service = DocumentVersionRelevanceService(db)
    conn = storage.connect(db)
    try:
        rows = conn.execute(
            "SELECT id FROM document_version_relevance ORDER BY created_at, id"
        ).fetchall()
    finally:
        conn.close()
    return [service.get(row[0]) for row in rows]


def _topic_with_vocabulary(db, term: str, *, term_type: str = "include") -> tuple[CoreService, dict[str, Any]]:
    core = CoreService(db)
    category = core.create_category({"slug": "science", "name": "Science"})
    topic = core.create_topic({
        "category_id": category["id"],
        "slug": "aeronautics",
        "name": "Aeronautics",
    })
    core.create_vocabulary(topic["id"], {"term": term, "term_type": term_type})
    return core, topic


def _create_monitor(db, *, slug: str, url: str, need: tuple[str, str] | None, policy_extra: dict[str, Any] | None = None, feed_url: str | None = None):
    core = CoreService(db)
    source_data: dict[str, Any] = {"name": f"{slug}-source", "slug": slug, "homepage_url": url}
    if feed_url:
        source_data["feed_url"] = feed_url
        source_data["source_kind"] = "feed"
    source = core.create_source(source_data)
    policy = MonitoringPolicyService(db).create({
        "name": f"{slug}-policy",
        "allowed_channels": ["direct_http", "rss"],
        "base_cadence_seconds": 60,
        "min_cadence_seconds": 30,
        "max_cadence_seconds": 300,
        **(policy_extra or {}),
    })
    data: dict[str, Any] = {
        "target_type": "source",
        "target_id": source["id"],
        "policy_id": policy["id"],
        "next_check_at": T0,
    }
    if need is not None:
        data["need_type"], data["need_id"] = need
    monitor = MonitorService(db).create(data)
    return source, policy, monitor


def _monitor_worker(db, transport, *, worker_id: str = "worker-p20") -> WorkerProcess:
    acquisition = AcquisitionService(db, transport=transport)
    handlers = MonitorExecutionService(db, acquisition_service=acquisition).handlers()
    return WorkerProcess(db, handlers, worker_id=worker_id, queue=build_worker_queue(db))


def _acquire_once(db, transport, *, now: str = T0) -> dict[str, Any]:
    worker = _monitor_worker(db, transport)
    SchedulerProcess(db).run_once()
    finished = worker.run_once(now=now)
    assert finished["status"] == "succeeded"
    assert finished["job_type"] == MONITOR_CHECK_JOB_TYPE
    return finished


def _acquire_again(db, transport, monitor_id: str, *, now: str = T2) -> dict[str, Any]:
    MonitorService(db).update(monitor_id, {"next_check_at": now})
    worker = _monitor_worker(db, transport, worker_id="worker-p2")
    SchedulerProcess(db).run_once()
    finished = worker.run_once(now=now)
    assert finished["status"] == "succeeded"
    return finished


def _processing_worker(db, *, worker_id: str = "worker-proc") -> WorkerProcess:
    return WorkerProcess(
        db,
        build_worker_handlers(db),
        worker_id=worker_id,
        queue=build_worker_queue(db),
    )


# ---------------------------------------------------------------------------
# Task group 1: relevant HTML → relevant=true persisted
# ---------------------------------------------------------------------------


def test_relevant_html_version_gets_persisted_relevance_true(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    core.create_vocabulary(topic["id"], {"term": "squadron", "term_type": "include"})
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-rel", url="https://example.test/rel", need=("topic", topic["id"])
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/rel", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    _acquire_once(tmp_db, transport)

    version = _get(tmp_db, "SELECT * FROM document_versions")
    assert _count(tmp_db, "document_version_relevance") == 0
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"

    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["job_type"] == DOCUMENT_VERSION_PROCESS_JOB_TYPE
    assert finished["status"] == "succeeded"
    relevance = finished["result"]["relevance"]
    assert relevance["status"] == "evaluated"
    assert relevance["relevant"] is True
    assert relevance["paid_used"] is False
    assert relevance["algorithm"] == "deterministic_relevance_cascade_v1"

    records = _relevance_records(tmp_db)
    assert len(records) == 1
    record = records[0]
    assert record["document_version_id"] == version["id"]
    assert record["monitor_id"] == monitor["id"]
    assert record["scope_version"] == 1
    assert record["relevant"] is True
    assert "UAP" in record["matched_terms"]
    assert record["score"] == 1.0
    assert record["paid_used"] is False
    assert set(record["scope"]["exact_terms"]) == {"UAP", "squadron"}
    assert record["job_id"] == finished["id"]

    monitor_now = MonitorService(tmp_db).get(monitor["id"])
    assert monitor_now["last_result"] == "relevant_change"
    activity = MonitorService(tmp_db).activity(monitor["id"])["items"]
    assert {row["outcome"] for row in activity} == {"changed", "relevant_change"}
    assert activity[0]["outcome"] == "relevant_change"
    assert activity[0]["relevant_items"] == 1
    assert monitor_now["next_check_at"] == "2026-08-18T12:01:30Z"
    assert check_database(tmp_db).ok is True


# ---------------------------------------------------------------------------
# Task group 2: acquisition-level 'changed' never claims relevance
# ---------------------------------------------------------------------------


def test_acquisition_changed_alone_never_emits_relevant_change(tmp_db):
    """Regression: acquisition-level 'changed' alone must never claim relevance."""
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-boundary", url="https://example.test/boundary", need=("topic", topic["id"])
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/boundary", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    _acquire_once(tmp_db, transport)

    activity = MonitorService(tmp_db).activity(monitor["id"])["items"]
    assert [row["outcome"] for row in activity] == ["changed"]
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"
    assert _count(tmp_db, "document_version_relevance") == 0
    assert _count(tmp_db, "monitor_activity", where="outcome = 'relevant_change'") == 0
    assert _count(tmp_db, "provider_usage", where="capability = 'relevance'") == 0


# ---------------------------------------------------------------------------
# Task group 3: non-relevant HTML -> relevant=false persisted, job succeeds
# ---------------------------------------------------------------------------


def test_nonrelevant_html_version_is_false_and_job_succeeds(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-nr", url="https://example.test/nr", need=("topic", topic["id"])
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/nr", {"content-type": "text/html"}, HTML_IRRELEVANT),
    ])
    _acquire_once(tmp_db, transport)

    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "succeeded"
    assert finished["result"]["relevance"]["status"] == "evaluated"
    assert finished["result"]["relevance"]["relevant"] is False

    records = _relevance_records(tmp_db)
    assert len(records) == 1
    assert records[0]["relevant"] is False
    assert records[0]["monitor_id"] == monitor["id"]
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"
    assert _count(tmp_db, "monitor_activity", where="outcome = 'relevant_change'") == 0
    assert check_database(tmp_db).ok is True


# ---------------------------------------------------------------------------
# Task group 4: feed entries through the same pipeline
# ---------------------------------------------------------------------------


def test_feed_entries_through_the_same_pipeline(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    source, _policy, monitor = _create_monitor(
        tmp_db,
        slug="p20-feed",
        url="https://example.test/feed-home",
        need=("topic", topic["id"]),
        feed_url="https://example.test/feed.xml",
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/feed.xml", {"content-type": "application/rss+xml"}, RSS_MIXED),
    ])
    _acquire_once(tmp_db, transport)
    assert _count(tmp_db, "document_versions") == 2

    worker = _processing_worker(tmp_db)
    finished = []
    while len(_relevance_records(tmp_db)) < 2:
        result = worker.run_once(now=T1 if not finished else T2)
        assert result is not None
        assert result["status"] == "succeeded"
        finished.append(result)

    records = _relevance_records(tmp_db)
    assert len(records) == 2
    relevant = next(record for record in records if record["relevant"])
    irrelevant = next(record for record in records if not record["relevant"])
    assert relevant["document_version_id"] != irrelevant["document_version_id"]
    assert "UAP" in relevant["matched_terms"]
    # The evaluation text is the entry title+summary: the second entry's URL
    # contains 'uap' but its title/summary do not, so it must NOT match.
    assert irrelevant["relevant"] is False
    assert relevant["monitor_id"] == monitor["id"]
    assert check_database(tmp_db).ok is True


# ---------------------------------------------------------------------------
# Task group 5: no candidate_text, explicit validated information need
# ---------------------------------------------------------------------------


def test_automatic_path_requires_no_candidate_text(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-noct", url="https://example.test/noct", need=("topic", topic["id"])
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/noct", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    _acquire_once(tmp_db, transport)

    version = _get(tmp_db, "SELECT * FROM document_versions")
    obligations = _processing_jobs(tmp_db, version["id"])
    assert len(obligations) == 1
    assert "candidate_text" not in _payload(obligations[0])
    assert _payload(obligations[0])["scope_version"] == 1

    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "succeeded"
    assert finished["result"]["relevance"]["relevant"] is True
    assert "candidate_text" not in finished["result"]
    assert len(_relevance_records(tmp_db)) == 1


def test_information_need_is_explicit_and_validated(tmp_db):
    apply_migrations(tmp_db)
    source = CoreService(tmp_db).create_source({
        "name": "need", "slug": "p20-needval", "homepage_url": "https://example.test/needval",
    })
    policy = MonitoringPolicyService(tmp_db).create({
        "name": "p", "allowed_channels": ["direct_http"],
        "base_cadence_seconds": 60, "min_cadence_seconds": 30, "max_cadence_seconds": 300,
    })
    monitors = MonitorService(tmp_db)
    base = {"target_type": "source", "target_id": source["id"], "policy_id": policy["id"]}
    with pytest.raises(Exception):
        monitors.create({**base, "need_type": "topic"})
    with pytest.raises(Exception):
        monitors.create({**base, "need_type": "topic", "need_id": "ghost-topic"})
    with pytest.raises(Exception):
        monitors.create({**base, "need_type": "source", "need_id": source["id"]})
    # No need association at all (API `exclude_none` shape): acquisition-only.
    semantic = monitors.create(base)
    assert semantic["need_type"] is None
    assert semantic["need_id"] is None


# ---------------------------------------------------------------------------
# Task group 6: approved alias/acronym terms participate
# ---------------------------------------------------------------------------


def test_approved_alias_and_acronym_participate(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "quantum chip")
    suggestions = ScopeSuggestionService(tmp_db)
    acronym = suggestions.create(topic["id"], {"suggestion_type": "acronym", "value": "QC", "rationale": "common acronym"})
    suggestions.review(acronym["id"], approved=True, reviewed_by="editor")
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-acro", url="https://example.test/acro", need=("topic", topic["id"])
    )
    html = b"<html><title>QC launch</title><p>The new QC processor enters production.</p></html>"
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/acro", {"content-type": "text/html"}, html),
    ])
    _acquire_once(tmp_db, transport)

    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "succeeded"
    assert finished["result"]["relevance"]["relevant"] is True
    record = _relevance_records(tmp_db)[0]
    assert record["stage"] in {"exact", "vocabulary"}
    assert "QC" in record["matched_terms"]


# ---------------------------------------------------------------------------
# Task group 7: pending/rejected suggestions never participate
# ---------------------------------------------------------------------------


def test_pending_and_rejected_suggestions_never_participate(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "quantum chip")
    suggestions = ScopeSuggestionService(tmp_db)
    pending = suggestions.create(topic["id"], {"suggestion_type": "related_concept", "value": "warp drive", "rationale": "candidate"})
    rejected = suggestions.create(topic["id"], {"suggestion_type": "term", "value": "hyperdrive", "rationale": "candidate"})
    suggestions.review(rejected["id"], approved=False, reviewed_by="editor")
    assert pending["status"] == "pending"

    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-sug", url="https://example.test/sug", need=("topic", topic["id"])
    )
    history = MonitorService(tmp_db).scope(monitor["id"])
    assert "warp drive" not in history.all_terms()
    assert "hyperdrive" not in history.all_terms()

    html = b"<html><title>Warp</title><p>The new warp drive prototype works.</p></html>"
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/sug", {"content-type": "text/html"}, html),
    ])
    _acquire_once(tmp_db, transport)
    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "succeeded"
    assert finished["result"]["relevance"]["relevant"] is False
    assert _relevance_records(tmp_db)[0]["relevant"] is False


# ---------------------------------------------------------------------------
# Task group 8: exclusions are first-class and suppress false positives
# ---------------------------------------------------------------------------


def test_exclusion_suppresses_a_would_be_positive(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    core.create_vocabulary(topic["id"], {"term": "hoax", "term_type": "exclude"})
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-excl", url="https://example.test/excl", need=("topic", topic["id"])
    )
    html = b"<html><title>Alert</title><p>The latest UAP sighting is a hoax.</p></html>"
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/excl", {"content-type": "text/html"}, html),
    ])
    _acquire_once(tmp_db, transport)
    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "succeeded"
    record = _relevance_records(tmp_db)[0]
    assert record["relevant"] is False
    assert record["stage"] == "excluded"
    assert record["matched_terms"] == ["hoax"]
    monitor_now = MonitorService(tmp_db).get(monitor["id"])
    assert monitor_now["last_result"] == "changed"
    assert _count(tmp_db, "monitor_activity", where="outcome = 'relevant_change'") == 0


# ---------------------------------------------------------------------------
# Task group 9: empty/invalid scope fails truthfully, never a false negative
# ---------------------------------------------------------------------------


def test_empty_approved_scope_fails_truthfully_not_as_false(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    category = core.create_category({"slug": "empty", "name": "Empty"})
    topic = core.create_topic({"category_id": category["id"], "slug": "empty-need", "name": "Empty need"})
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-empty", url="https://example.test/empty", need=("topic", topic["id"])
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/empty", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    _acquire_once(tmp_db, transport)
    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "failed"
    assert finished["failure_cause"] == "DomainValidation"
    assert _count(tmp_db, "document_version_relevance") == 0
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"


# ---------------------------------------------------------------------------
# Task group 10: provenance — missing is not_applicable, invalid is rejected
# ---------------------------------------------------------------------------


def test_missing_monitor_provenance_is_explicitly_not_applicable(tmp_db):
    apply_migrations(tmp_db)
    source = CoreService(tmp_db).create_source({
        "name": "direct", "slug": "p20-direct", "homepage_url": "https://example.test/direct",
    })
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/direct", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    result = AcquisitionService(tmp_db, transport=transport).acquire_document(
        source["id"], "https://example.test/direct"
    )
    assert result.outcome == "retrieved"
    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "succeeded"
    relevance = finished["result"]["relevance"]
    assert relevance["status"] == "not_applicable"
    assert "relevant" not in relevance
    assert _count(tmp_db, "document_version_relevance") == 0


def test_invalid_monitor_provenance_is_rejected_truthfully(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-ghostmon", url="https://example.test/ghostmon", need=("topic", topic["id"])
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/ghostmon", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    _acquire_once(tmp_db, transport)
    ob = _processing_jobs(tmp_db)[0]
    payload = _payload(ob)
    payload["monitor_id"] = "monitor_missing"
    queue = build_worker_queue(tmp_db)
    queue.cancel(ob["id"], reason="test-harness")
    queue.enqueue(
        DOCUMENT_VERSION_PROCESS_JOB_TYPE,
        payload,
        document_version_id=payload["document_version_id"],
        idempotency_key="p20-ghostmon-invalid-prov",
    )
    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "failed"
    assert finished["failure_cause"] == "DomainValidation"
    assert _count(tmp_db, "document_version_relevance") == 0


def test_pinned_version_missing_from_history_is_rejected(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-pin", url="https://example.test/pin", need=("topic", topic["id"])
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/pin", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    _acquire_once(tmp_db, transport)
    ob = _processing_jobs(tmp_db)[0]
    queue = build_worker_queue(tmp_db)
    queue.cancel(ob["id"], reason="test-harness")
    queue.enqueue(
        DOCUMENT_VERSION_PROCESS_JOB_TYPE,
        {"document_version_id": ob["document_version_id"], "monitor_id": monitor["id"], "scope_version": 99},
        document_version_id=ob["document_version_id"],
        idempotency_key="p20-pin-missing",
    )
    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "failed"
    assert finished["failure_cause"] == "DomainNotFound"
    assert _count(tmp_db, "document_version_relevance") == 0


def test_malformed_persisted_scope_is_rejected(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-mal", url="https://example.test/mal", need=("topic", topic["id"])
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/mal", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    _acquire_once(tmp_db, transport)
    ob = _processing_jobs(tmp_db)[0]
    # History rows are immutable once written, so inject a malformed row at a
    # fresh version number (simulating storage-level corruption) and pin it.
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "INSERT INTO monitor_scope_history(id, monitor_id, version, scope_json, change_type, created_at) "
                "VALUES (?, ?, 2, '{not-json', 'manual', ?)",
                ("scopehist_malformed", monitor["id"], T0),
            )
    finally:
        conn.close()
    queue = build_worker_queue(tmp_db)
    queue.cancel(ob["id"], reason="test-harness")
    queue.enqueue(
        DOCUMENT_VERSION_PROCESS_JOB_TYPE,
        {"document_version_id": ob["document_version_id"], "monitor_id": monitor["id"], "scope_version": 99},
        document_version_id=ob["document_version_id"],
        idempotency_key="p20-mal-requeued",
    )
    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "failed"
    assert _count(tmp_db, "document_version_relevance") == 0


# ---------------------------------------------------------------------------
# Task groups 11-12: retry/recovery and explicit rerun stay idempotent
# ---------------------------------------------------------------------------


def test_retry_and_recovery_never_duplicate_relevance_records(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-retry", url="https://example.test/retry", need=("topic", topic["id"])
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/retry", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    _acquire_once(tmp_db, transport)
    ob = _processing_jobs(tmp_db)[0]
    queue = build_worker_queue(tmp_db)
    job = queue.claim(ob["id"], "worker-a", now=T0)
    assert job["status"] == "running"
    # Simulate a crash after the decision persisted but before completion:
    # decision, activity, and usage must exist exactly once already.
    build_worker_handlers(tmp_db)[DOCUMENT_VERSION_PROCESS_JOB_TYPE](job)
    assert _count(tmp_db, "document_version_relevance") == 1
    assert _count(tmp_db, "monitor_activity", where="outcome = 'relevant_change'") == 1
    assert _count(tmp_db, "provider_usage", where="capability = 'relevance'") == 1
    # Lease expiry + recovery re-runs the same obligation with no duplication
    # (the recovered job's backoff gates the next attempt).
    assert queue.recover_expired(now=T2) == 1
    finished = _processing_worker(tmp_db).run_once(now="2026-08-18T12:05:00Z")
    assert finished["status"] == "succeeded"
    assert _count(tmp_db, "document_version_relevance") == 1
    assert _count(tmp_db, "monitor_activity", where="outcome = 'relevant_change'") == 1
    assert _count(tmp_db, "provider_usage", where="capability = 'relevance'") == 1


def test_explicit_rerun_preserves_idempotency_and_auditability(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-rerun", url="https://example.test/rerun", need=("topic", topic["id"])
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/rerun", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    _acquire_once(tmp_db, transport)
    worker = _processing_worker(tmp_db)
    first = worker.run_once(now=T1)
    assert first["status"] == "succeeded"
    records = _relevance_records(tmp_db)
    assert len(records) == 1
    canonical_id = records[0]["id"]
    assert first["result"]["relevance"]["relevance_id"] == canonical_id

    rerun = build_worker_queue(tmp_db).rerun(first["id"])
    assert rerun["status"] == "queued"
    second = None
    for _ in range(10):
        finished = worker.run_once(now=T2)
        if finished is None:
            break
        if finished["id"] == rerun["id"]:
            second = finished
            break
    assert second is not None
    assert second["status"] == "succeeded"
    assert _count(tmp_db, "document_version_relevance") == 1
    assert second["result"]["relevance"]["relevance_id"] == canonical_id
    assert second["result"]["relevance"]["scope_version"] == 1
    assert _count(tmp_db, "monitor_activity", where="outcome = 'relevant_change'") == 1


# ---------------------------------------------------------------------------
# Task group 13: artifact corruption fails before any relevance decision
# ---------------------------------------------------------------------------


def test_corrupt_artifact_fails_before_any_relevance_decision(tmp_db):
    apply_migrations(tmp_db)
    raw = sqlite3.connect(str(tmp_db))
    raw.execute("PRAGMA foreign_keys = OFF")
    raw.execute(
        "INSERT INTO content_artifacts "
        "(id, normalized_content_hash, content_kind, norm_version, normalized_text, text_length, retention_eligible, created_at) "
        "VALUES ('art_corrupt20', 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef', "
        "'visible_text', 'visible_text_v1', 'tampered content', 15, 1, ?)",
        (T0,),
    )
    raw.execute(
        "INSERT INTO documents "
        "(id, source_id, canonical_url, canonical_url_hash, title, title_normalized, first_seen_at, created_at) "
        "VALUES ('doc_ghost20', 'src_ghost20', 'https://example.test/ghost20', 'ghost-fp20', 'Ghost', 'ghost', ?, ?)",
        (T0, T0),
    )
    raw.execute(
        "INSERT INTO document_versions "
        "(id, document_id, retrieved_at, content_hash, content_kind, artifact_id, normalized_json, created_at) "
        "VALUES ('dv_corrupt20', 'doc_ghost20', ?, 'rawhash', 'excerpt', 'art_corrupt20', '{}', ?)",
        (T0, T0),
    )
    raw.execute(
        "INSERT INTO jobs (id, job_type, status, payload_json, idempotency_key, document_version_id, priority, max_attempts, created_at, updated_at) "
        "VALUES ('job_corrupt20', ?, 'queued', '{\"document_version_id\": \"dv_corrupt20\"}', 'corrupt-key20', 'dv_corrupt20', 0, 1, ?, ?)",
        (DOCUMENT_VERSION_PROCESS_JOB_TYPE, T0, T0),
    )
    raw.commit()
    raw.close()

    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "failed"
    assert finished["failure_cause"] in {"ArtifactHashMismatch", "ArtifactLengthMismatch"}
    assert _count(tmp_db, "document_version_relevance") == 0


# ---------------------------------------------------------------------------
# Task group 14: scope history / mutation semantics (scope-at-acquisition)
# ---------------------------------------------------------------------------


def test_scope_pin_survives_later_scope_mutation(tmp_db):
    """Versions are evaluated against the scope that existed at acquisition."""
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UFO")
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-hist", url="https://example.test/hist", need=("topic", topic["id"])
    )
    # First version: acquired while the approved scope contained only 'UFO'
    # (the article mentions UAP, not UFO).
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/hist", {"content-type": "text/html"}, HTML_UFO_ONLY),
        HttpResponse(200, "https://example.test/hist", {"content-type": "text/html"}, HTML_UAP_NEW),
    ])
    _acquire_once(tmp_db, transport)
    assert _count(tmp_db, "monitor_scope_history") == 1
    version_one = _get(tmp_db, "SELECT * FROM document_versions ORDER BY retrieved_at LIMIT 1")

    # The user edits the approved scope before processing: UAP joins.
    core.create_vocabulary(topic["id"], {"term": "UAP", "term_type": "include"})
    core.create_vocabulary(topic["id"], {"term": "flying saucer", "term_type": "include"})
    assert _count(tmp_db, "monitor_scope_history") == 3

    worker = _processing_worker(tmp_db)
    first = worker.run_once(now=T1)
    assert first["status"] == "succeeded"
    records = _relevance_records(tmp_db)
    assert len(records) == 1
    # The first version was pinned to scope version 1 (UFO-only approved
    # scope at acquisition): the UAP-only article is NOT relevant there.
    assert records[0]["scope_version"] == 1
    assert records[0]["relevant"] is False
    assert "UAP" not in json.dumps(records[0]["scope"])
    assert "UFO" in records[0]["scope"]["exact_terms"]

    # A second version acquired after the scope edit pins the current
    # snapshot and is evaluated against the widened approved scope.
    _acquire_again(tmp_db, transport, monitor["id"])
    second = None
    for _ in range(10):
        result = worker.run_once(now=T2)
        assert result is not None
        assert result["status"] == "succeeded"
        if len(_relevance_records(tmp_db)) == 2:
            second = result
            break
    assert second is not None
    records = _relevance_records(tmp_db)
    assert len(records) == 2
    newer = records[1]
    assert newer["scope_version"] == 3
    assert newer["relevant"] is True
    assert set(newer["scope"]["exact_terms"]) == {"UFO", "UAP", "flying saucer"}
    # Historical versions never get re-scored: still exactly two decisions.
    assert _count(tmp_db, "document_version_relevance") == 2


# ---------------------------------------------------------------------------
# Task group 15: result survives object/process recreation
# ---------------------------------------------------------------------------


def test_relevance_result_survives_database_reopen(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-reopen", url="https://example.test/reopen", need=("topic", topic["id"])
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/reopen", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    _acquire_once(tmp_db, transport)
    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "succeeded"
    records_before = _relevance_records(tmp_db)
    assert len(records_before) == 1

    conn = sqlite3.connect(str(tmp_db))
    rows = conn.execute("SELECT * FROM document_version_relevance").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][2] == monitor["id"]  # monitor_id
    reopened = DocumentVersionRelevanceService(tmp_db)
    assert reopened.get(rows[0][0]) == records_before[0]


# ---------------------------------------------------------------------------
# Task groups 16-17: relevant_change and cadence only after real relevance
# ---------------------------------------------------------------------------


def test_cadence_acceleration_only_after_real_relevance(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    source, _policy, monitor = _create_monitor(
        tmp_db,
        slug="p20-cadence",
        url="https://example.test/cadence",
        need=("topic", topic["id"]),
        policy_extra={"min_cadence_seconds": 30, "base_cadence_seconds": 60, "max_cadence_seconds": 300},
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/cadence", {"content-type": "text/html"}, HTML_IRRELEVANT),
        HttpResponse(200, "https://example.test/cadence", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    _acquire_once(tmp_db, transport)
    monitor_row = MonitorService(tmp_db).get(monitor["id"])
    assert monitor_row["last_result"] == "changed"
    before = monitor_row["next_check_at"]

    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "succeeded"
    assert finished["result"]["relevance"]["relevant"] is False
    monitor_row = MonitorService(tmp_db).get(monitor["id"])
    assert monitor_row["last_result"] == "changed"
    assert monitor_row["next_check_at"] == before

    _acquire_again(tmp_db, transport, monitor["id"])
    monitor_row = MonitorService(tmp_db).get(monitor["id"])
    assert monitor_row["last_result"] == "changed"
    processed = _processing_worker(tmp_db).run_once(now=T2)
    assert processed["status"] == "succeeded"
    assert processed["result"]["relevance"]["relevant"] is True
    monitor_row = MonitorService(tmp_db).get(monitor["id"])
    assert monitor_row["last_result"] == "relevant_change"
    assert monitor_row["next_check_at"] == "2026-08-18T12:02:30Z"


# ---------------------------------------------------------------------------
# Task groups 18-19: local-only usage, acquisition-only monitors
# ---------------------------------------------------------------------------


def test_relevance_usage_is_local_only_and_never_paid(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-usage", url="https://example.test/usage", need=("topic", topic["id"])
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/usage", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    _acquire_once(tmp_db, transport)
    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "succeeded"
    assert finished["result"]["relevance"]["paid_used"] is False

    conn = storage.connect(tmp_db)
    try:
        rows = conn.execute(
            "SELECT * FROM provider_usage WHERE capability = 'relevance'"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    row = rows[0]
    assert row["provider"] == "local"
    assert row["request_type"] == "deterministic_cascade"
    assert row["estimated_cost_usd"] == 0.0
    assert row["query_units"] == 0
    assert row["token_units"] == 0
    assert "paid" not in (row["outcome"] or "")
    assert _count(tmp_db, "provider_usage", where="capability LIKE '%paid%'") == 0
    assert _relevance_records(tmp_db)[0]["paid_used"] is False


def test_acquisition_only_monitor_records_no_relevance_at_all(tmp_db):
    apply_migrations(tmp_db)
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-acqonly", url="https://example.test/acqonly", need=None
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/acqonly", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    _acquire_once(tmp_db, transport)
    obligations = _processing_jobs(tmp_db)
    assert len(obligations) == 1
    assert "scope_version" not in _payload(obligations[0])

    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "succeeded"
    assert finished["result"]["relevance"]["status"] == "not_applicable"
    assert "relevant" not in finished["result"]["relevance"]
    assert _count(tmp_db, "document_version_relevance") == 0
    assert _count(tmp_db, "provider_usage") == 1  # acquisition only
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"


# ---------------------------------------------------------------------------
# Task group 20: production-composition acceptance (A relevant, B not)
# ---------------------------------------------------------------------------


def test_production_composition_relevant_and_not_relevant(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    source_a, _policy_a, monitor_a = _create_monitor(
        tmp_db, slug="prod-a", url="https://example.test/prod-a", need=("topic", topic["id"])
    )
    source_b, _policy_b, monitor_b = _create_monitor(
        tmp_db, slug="prod-b", url="https://example.test/prod-b", need=("topic", topic["id"])
    )

    transport = UrlKeyedTransport({
        "https://example.test/prod-a": HttpResponse(200, "https://example.test/prod-a", {"content-type": "text/html"}, HTML_RELEVANT),
        "https://example.test/prod-b": HttpResponse(200, "https://example.test/prod-b", {"content-type": "text/html"}, HTML_IRRELEVANT),
    })
    acquisition = AcquisitionService(tmp_db, transport=transport)
    handlers = MonitorExecutionService(tmp_db, acquisition_service=acquisition).handlers()
    queue = build_worker_queue(tmp_db)
    monitor_worker = WorkerProcess(tmp_db, handlers, worker_id="composition-1", queue=queue)

    scheduled = SchedulerProcess(tmp_db).run_once()
    assert scheduled["enqueued"] == 2
    assert monitor_worker.run_once(now=T0)["status"] == "succeeded"
    assert monitor_worker.run_once(now=T0)["status"] == "succeeded"

    assert _count(tmp_db, "document_versions") == 2
    assert _count(tmp_db, "document_version_relevance") == 0
    assert _count(tmp_db, "jobs", where="job_type = ?", params=(DOCUMENT_VERSION_PROCESS_JOB_TYPE,)) == 2

    # Teardown + fresh worker objects process the durable obligations.
    del monitor_worker, queue, handlers, acquisition, transport
    proc_worker = _processing_worker(tmp_db, worker_id="composition-2")
    first = proc_worker.run_once(now=T1)
    second = proc_worker.run_once(now=T2)
    assert first["status"] == "succeeded"
    assert second["status"] == "succeeded"
    remaining = []
    while True:
        finished = proc_worker.run_once(now=T2)
        if finished is None:
            break
        remaining.append(finished)
    assert remaining
    assert all(item["status"] == "succeeded" for item in remaining)
    assert proc_worker.run_once(now=T2) is None

    records = _relevance_records(tmp_db)
    assert len(records) == 2
    by_monitor = {record["monitor_id"]: record for record in records}
    assert by_monitor[monitor_a["id"]]["relevant"] is True
    assert by_monitor[monitor_b["id"]]["relevant"] is False
    assert set(by_monitor[monitor_a["id"]]["matched_terms"]) == {"UAP"}
    assert by_monitor[monitor_a["id"]]["stage"] == "exact"
    assert MonitorService(tmp_db).get(monitor_a["id"])["last_result"] == "relevant_change"
    assert MonitorService(tmp_db).get(monitor_b["id"])["last_result"] == "changed"
    assert check_database(tmp_db).ok is True


# ---------------------------------------------------------------------------
# Task group 21: process-restart acceptance
# ---------------------------------------------------------------------------


def test_restart_acceptance_relevance_survives_object_recreation(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _topic_with_vocabulary(tmp_db, "UAP")
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-restart", url="https://example.test/restart", need=("topic", topic["id"])
    )
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/restart", {"content-type": "text/html"}, HTML_RELEVANT),
    ])
    _acquire_once(tmp_db, transport)

    # Destroy every service object; rebuild the composition from scratch.
    del transport
    proc = _processing_worker(tmp_db, worker_id="restarted")
    finished = proc.run_once(now=T1)
    assert finished["status"] == "succeeded"
    assert finished["result"]["relevance"]["relevant"] is True
    del proc

    version = _get(tmp_db, "SELECT * FROM document_versions")
    conn = sqlite3.connect(str(tmp_db))
    try:
        row = conn.execute(
            "SELECT * FROM document_version_relevance WHERE document_version_id = ?",
            (version["id"],),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[2] == monitor["id"]  # monitor_id
    assert row[4] == 1  # scope_version
    assert row[6] == 1  # relevant
    reopened = DocumentVersionRelevanceService(tmp_db)
    assert reopened.get(row[0])["relevant"] is True
    assert reopened.get(row[0])["algorithm"] == "deterministic_relevance_cascade_v1"


# ---------------------------------------------------------------------------
# Task group 22: UAP/UFO approved-vocabulary fixture (not generation)
# ---------------------------------------------------------------------------


def _build_uap_scope(tmp_db) -> tuple[CoreService, dict[str, Any]]:
    """Approved-vocabulary fixture inserted through the current approval path."""
    core, topic = _topic_with_vocabulary(tmp_db, "UFO")
    core.create_vocabulary(topic["id"], {"term": "unidentified flying object", "term_type": "include"})
    core.create_vocabulary(topic["id"], {"term": "unidentified anomalous phenomena", "term_type": "include"})
    core.create_vocabulary(topic["id"], {"term": "non-human intelligence", "term_type": "include", "concept_kind": "related_concept"})
    core.create_vocabulary(topic["id"], {"term": "flying saucer", "term_type": "include"})
    core.create_vocabulary(topic["id"], {"term": "hoax", "term_type": "exclude"})
    suggestions = ScopeSuggestionService(tmp_db)
    for value in ("UAP", "NHI"):
        suggestion = suggestions.create(
            topic["id"], {"suggestion_type": "acronym", "value": value, "rationale": "approved acronym"}
        )
        suggestions.review(suggestion["id"], approved=True, reviewed_by="editor")
    return core, topic


def test_uap_fixture_relevant_article(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _build_uap_scope(tmp_db)
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-uap", url="https://example.test/uap", need=("topic", topic["id"])
    )
    article = b"<html><title>UAP</title><p>The pilot reported a UAP over the ocean this morning.</p></html>"
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/uap", {"content-type": "text/html"}, article),
    ])
    _acquire_once(tmp_db, transport)
    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "succeeded"
    record = _relevance_records(tmp_db)[0]
    assert record["relevant"] is True
    assert record["matched_terms"] == ["UAP"]
    # The approved acronym participates through the vocabulary stage.
    assert record["stage"] == "vocabulary"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "relevant_change"


def test_uap_fixture_unrelated_article(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _build_uap_scope(tmp_db)
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-uap2", url="https://example.test/uap2", need=("topic", topic["id"])
    )
    article = b"<html><title>Finance</title><p>The city council approved the roadworks budget proposal.</p></html>"
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/uap2", {"content-type": "text/html"}, article),
    ])
    _acquire_once(tmp_db, transport)
    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "succeeded"
    record = _relevance_records(tmp_db)[0]
    assert record["relevant"] is False
    assert record["stage"] in {"none", "semantic"}
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"


def test_uap_fixture_exclusion_wins_over_positive(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _build_uap_scope(tmp_db)
    source, _policy, monitor = _create_monitor(
        tmp_db, slug="p20-uap3", url="https://example.test/uap3", need=("topic", topic["id"])
    )
    article = b"<html><title>Debunked</title><p>The famous UFO photograph is a hoax.</p></html>"
    transport = CountingTransport([
        HttpResponse(200, "https://example.test/uap3", {"content-type": "text/html"}, article),
    ])
    _acquire_once(tmp_db, transport)
    finished = _processing_worker(tmp_db).run_once(now=T1)
    assert finished["status"] == "succeeded"
    record = _relevance_records(tmp_db)[0]
    assert record["relevant"] is False
    assert record["stage"] == "excluded"
    assert record["matched_terms"] == ["hoax"]
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"


# ---------------------------------------------------------------------------
# Task group 23: migration 0017 is additive and preserves schema-16 data
# ---------------------------------------------------------------------------


def test_migration_0017_preserves_schema_16_data(tmp_db):
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            for statements in (
                MIGRATION_0001_STATEMENTS,
                MIGRATION_0002_STATEMENTS,
                MIGRATION_0003_STATEMENTS,
                MIGRATION_0004_STATEMENTS,
                MIGRATION_0005_STATEMENTS,
                MIGRATION_0006_STATEMENTS,
                MIGRATION_0007_STATEMENTS,
                MIGRATION_0008_STATEMENTS,
                MIGRATION_0009_STATEMENTS,
                MIGRATION_0010_STATEMENTS,
                MIGRATION_0011_STATEMENTS,
                MIGRATION_0012_STATEMENTS,
                MIGRATION_0013_STATEMENTS,
                MIGRATION_0014_STATEMENTS,
                MIGRATION_0015_STATEMENTS,
                MIGRATION_0016_STATEMENTS,
            ):
                for statement in statements:
                    conn.execute(statement)
            for version in range(1, 17):
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, "2026-08-18T00:00:00Z"),
                )
            conn.execute(
                "INSERT INTO app_meta(key, value) VALUES ('schema_version', '16')"
            )
            conn.execute(
                "INSERT INTO monitoring_policies (id, name, allowed_channels, base_cadence_seconds, min_cadence_seconds, max_cadence_seconds, created_at, updated_at) "
                "VALUES ('pol-old20', 'Old', '[]', 60, 30, 300, ?, ?)",
                (T0, T0),
            )
            conn.execute(
                "INSERT INTO monitors (id, target_type, target_id, policy_id, next_check_at, created_at, updated_at) "
                "VALUES ('mon-old20', 'source', 'src-old20', 'pol-old20', ?, ?, ?)",
                (T0, T0, T0),
            )
            conn.execute(
                "INSERT INTO sources (id, name, slug, created_at, updated_at) VALUES ('src-old20', 'Old', 'old20', ?, ?)",
                (T0, T0),
            )
    finally:
        conn.close()

    result = apply_migrations(tmp_db)
    assert result.applied_versions == (17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31)
    assert result.current_version == 31
    assert migration_status(tmp_db) == tuple(range(1, 32))
    monitor = _get(tmp_db, "SELECT need_type, need_id FROM monitors WHERE id = 'mon-old20'")
    assert monitor[0] is None
    assert monitor[1] is None
    assert _get(tmp_db, "SELECT value FROM app_meta WHERE key = 'schema_version'")[0] == "31"
    # No historical relevance rows are manufactured.
    assert _count(tmp_db, "document_version_relevance") == 0
    # No historical article analyses are fabricated either.
    assert _count(tmp_db, "article_analyses") == 0
