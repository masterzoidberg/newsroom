from __future__ import annotations

import sqlite3
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from newsroom import storage
from newsroom.ai import AIRouter, CapabilityBundle, RoutePolicy
from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.domain import CoreService, DomainConflict, DomainNotFound, DomainValidation
from newsroom.evidence_promotion import ArticleAnalysisPromotionService
from newsroom.integrity import check_database
from newsroom.intelligent_monitoring import WatchMaintenanceService, WatchService
from newsroom.jobs import BudgetService, SchedulerService
from newsroom import migrations
from newsroom.migrations import apply_migrations, migration_status
from newsroom.monitoring import MonitorService, MonitoringPolicyService
from newsroom.operations import backup_database, export_logical, restore_database
from newsroom.report_automation import AutomaticReportStageExecutionService
from newsroom.reports import AlertService
from newsroom.runtime import build_worker_queue

from test_phase22_evidence_promotion import _analysis
from test_phase23c_report_automation import _complete_story_stage
from test_phase23d_alert_automation import _alert_stage_job, _run_alert_stage


def _fixture(db_path):
    apply_migrations(db_path)
    core = CoreService(db_path)
    category = core.create_category({"slug": "aerospace", "name": "Aerospace"})
    topic = core.create_topic(
        {"category_id": category["id"], "slug": "uap", "name": "UAP disclosure"}
    )
    policy = MonitoringPolicyService(db_path).create(
        {
            "name": "Watch policy",
            "allowed_channels": ["direct_http"],
            "base_cadence_seconds": 3600,
            "min_cadence_seconds": 900,
            "max_cadence_seconds": 86400,
            "query_budget": 10,
        }
    )
    return core, topic, policy


def _watch(watches, topic, policy, name="UAP disclosure"):
    return watches.create(
        {
            "name": name,
            "target_type": "topic",
            "target_id": topic["id"],
            "policy_id": policy["id"],
        }
    )


def test_watch_lifecycle_vocabulary_review_and_source_approval(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    assert watch["status"] == "active"

    suggestions = watches.suggest_vocabulary(watch["id"], limit=20)
    # Deterministic suggestions are derived from persisted domain state: the
    # Watch title plus a structurally derived initialism, not a hardcoded list.
    assert ("UAP disclosure", "primary") in {
        (item["term"], item["kind"]) for item in suggestions
    }
    assert all(item["status"] == "suggested" for item in suggestions)
    assert all(item["enabled"] == 0 for item in suggestions)

    approved = watches.review_vocabulary(
        watch["id"], suggestions[0]["id"], "approved", "editor"
    )
    assert approved["status"] == "approved"
    assert approved["enabled"] == 1

    candidate = watches.add_source_candidate(
        watch["id"],
        {
            "name": "NASA News",
            "homepage_url": "https://www.nasa.gov/news/",
            "rationale": "Primary agency publication",
            "discovery_method": "manual",
        },
    )
    assert candidate["status"] == "suggested"
    assert watches.get(watch["id"])["sources"] == []

    result = watches.review_source_candidate(
        watch["id"], candidate["id"], "approved", "editor"
    )
    assert result["status"] == "approved"

    detail = watches.get(watch["id"])
    assert len(detail["sources"]) == 1
    assert detail["sources"][0]["monitor"]["need_id"] == topic["id"]
    assert detail["sources"][0]["monitor"]["need_type"] == "topic"
    assert detail["sources"][0]["monitor"]["enabled"] == 1

    watches.pause(watch["id"])
    paused = watches.get(watch["id"])
    assert paused["status"] == "paused"
    assert paused["sources"][0]["monitor"]["enabled"] == 0

    watches.resume(watch["id"])
    resumed = watches.get(watch["id"])
    assert resumed["status"] == "active"
    assert resumed["sources"][0]["monitor"]["enabled"] == 1
    assert check_database(tmp_db).ok


def test_two_watches_share_one_source_with_independent_monitors(tmp_db):
    core, topic, policy = _fixture(tmp_db)
    other_topic = core.create_topic(
        {
            "category_id": core.list_categories()["items"][0]["id"],
            "slug": "aviation",
            "name": "Civil aviation safety",
        }
    )
    watches = WatchService(tmp_db)
    first = _watch(watches, topic, policy)
    second = _watch(watches, other_topic, policy, name="Civil aviation safety")

    payload = {
        "name": "NASA News",
        "homepage_url": "https://www.nasa.gov/news/",
        "rationale": "Primary agency publication",
        "discovery_method": "manual",
    }
    first_candidate = watches.add_source_candidate(first["id"], payload)
    watches.review_source_candidate(
        first["id"], first_candidate["id"], "approved", "editor"
    )
    second_candidate = watches.add_source_candidate(second["id"], payload)
    watches.review_source_candidate(
        second["id"], second_candidate["id"], "approved", "editor"
    )

    first_source = watches.get(first["id"])["sources"][0]
    second_source = watches.get(second["id"])["sources"][0]

    # One shared Source, one Monitor per Watch, each pinned to its own need.
    assert first_source["source"]["id"] == second_source["source"]["id"]
    assert first_source["monitor"]["id"] != second_source["monitor"]["id"]
    assert first_source["monitor"]["need_id"] == topic["id"]
    assert second_source["monitor"]["need_id"] == other_topic["id"]

    # Pausing one Watch must not disturb the other Watch's monitoring.
    watches.pause(first["id"])
    assert watches.get(first["id"])["sources"][0]["monitor"]["enabled"] == 0
    assert watches.get(second["id"])["sources"][0]["monitor"]["enabled"] == 1
    assert check_database(tmp_db).ok


def test_removing_one_watch_relationship_preserves_the_shared_source(tmp_db):
    core, topic, policy = _fixture(tmp_db)
    other_topic = core.create_topic(
        {
            "category_id": core.list_categories()["items"][0]["id"],
            "slug": "aviation",
            "name": "Civil aviation safety",
        }
    )
    watches = WatchService(tmp_db)
    first = _watch(watches, topic, policy)
    second = _watch(watches, other_topic, policy, name="Civil aviation safety")
    payload = {
        "name": "NASA News",
        "homepage_url": "https://www.nasa.gov/news/",
        "rationale": "Primary agency publication",
        "discovery_method": "manual",
    }
    for watch in (first, second):
        candidate = watches.add_source_candidate(watch["id"], payload)
        watches.review_source_candidate(
            watch["id"], candidate["id"], "approved", "editor"
        )
    source_id = watches.get(first["id"])["sources"][0]["source"]["id"]

    watches.remove_source(first["id"], source_id)

    assert watches.get(first["id"])["sources"] == []
    assert watches.get(second["id"])["sources"][0]["source"]["id"] == source_id
    conn = storage.connect(tmp_db)
    try:
        assert (
            conn.execute(
                "SELECT deleted_at FROM sources WHERE id = ?", (source_id,)
            ).fetchone()[0]
            is None
        )
    finally:
        conn.close()
    assert check_database(tmp_db).ok


def test_candidate_dedupe_unsafe_url_and_referential_integrity(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)

    first = watches.add_source_candidate(
        watch["id"],
        {
            "name": "NASA",
            "homepage_url": "https://NASA.gov/news",
            "rationale": "Primary",
            "discovery_method": "web_search",
        },
    )
    second = watches.add_source_candidate(
        watch["id"],
        {
            "name": "NASA duplicate",
            "homepage_url": "https://nasa.gov/news/",
            "rationale": "Duplicate",
            "discovery_method": "web_search",
        },
    )
    assert first["id"] == second["id"]

    for unsafe in ("http://127.0.0.1/admin", "http://localhost/admin", "file:///etc/passwd"):
        with pytest.raises(DomainValidation):
            watches.add_source_candidate(
                watch["id"],
                {
                    "name": "Private",
                    "homepage_url": unsafe,
                    "rationale": "unsafe",
                    "discovery_method": "web_search",
                },
            )

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO watch_sources(watch_id, source_id, monitor_id, created_at)
                VALUES ('missing', 'missing', 'missing', '2026-01-01T00:00:00Z')
                """
            )
    finally:
        conn.close()


def test_rejected_vocabulary_is_recorded_and_not_resurrected_by_a_later_run(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    suggestions = watches.suggest_vocabulary(watch["id"], limit=20)
    target = suggestions[0]

    rejected = watches.review_vocabulary(watch["id"], target["id"], "rejected", "editor")
    assert rejected["status"] == "rejected"
    assert rejected["enabled"] == 0

    watches.suggest_vocabulary(watch["id"], limit=20)
    still_rejected = watches.get_vocabulary(watch["id"], target["id"])
    assert still_rejected["status"] == "rejected"
    assert still_rejected["enabled"] == 0

    with pytest.raises(DomainConflict):
        watches.review_vocabulary(watch["id"], target["id"], "approved", "editor")


def test_invalid_provider_output_leaves_the_watch_unchanged(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    baseline = watches.suggest_vocabulary(watch["id"], limit=20)

    def malformed(_context):
        return [
            {"term": "", "kind": "alias"},
            {"term": "x" * 5000, "kind": "alias"},
            {"term": "valid looking", "kind": "not_a_kind"},
            "not a mapping",
            {"term": "drop table watches", "kind": "alias", "rationale": "ok"},
        ]

    after = watches.suggest_vocabulary(watch["id"], limit=20, provider=malformed)
    terms = {item["term"] for item in after}
    assert "" not in terms
    assert "x" * 5000 not in terms
    # The only survivor is a well-formed suggestion, persisted as inert text.
    assert "drop table watches" in terms
    assert all(item["status"] == "suggested" for item in after if item["origin"] == "ai")

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM watches").fetchone()[0] == 1
    finally:
        conn.close()
    assert len(after) >= len(baseline)


def test_provider_failure_does_not_break_vocabulary_suggestion(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)

    def exploding(_context):
        raise RuntimeError("provider unavailable")

    suggestions = watches.suggest_vocabulary(watch["id"], limit=20, provider=exploding)

    # Deterministic suggestions survive an unavailable optional provider.
    assert suggestions
    assert all(item["origin"] != "ai" for item in suggestions)
    assert watches.get(watch["id"])["status"] == "active"


def test_structured_provider_output_is_validated_and_cannot_mutate_watch(tmp_db):
    _core, topic, policy = _fixture(tmp_db)

    class InvalidProvider:
        def suggest(self, _request):
            return {
                "suggestions": [
                    {"term": "x" * 301, "kind": "alias", "rationale": "too long"},
                    {"term": "unsafe", "kind": "not-a-kind", "rationale": "bad kind"},
                ],
                "confidence": 1.0,
            }

    router = AIRouter(
        local=CapabilityBundle(vocabulary=InvalidProvider()),
        policy=RoutePolicy(local_enabled=True, paid_enabled=False),
    )
    watches = WatchService(tmp_db, router=router)
    watch = _watch(watches, topic, policy)
    baseline = watches.suggest_vocabulary(watch["id"], limit=20)

    after = watches.suggest_vocabulary(watch["id"], limit=20)

    assert after == baseline
    assert all(item["origin"] != "ai" for item in after)
    assert watches.get(watch["id"])["status"] == "active"


def test_watch_requires_a_live_target_and_rejects_duplicates(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    _watch(watches, topic, policy)

    with pytest.raises(DomainConflict):
        _watch(watches, topic, policy, name="Duplicate watch")
    with pytest.raises(DomainNotFound):
        watches.create(
            {
                "name": "Missing target",
                "target_type": "topic",
                "target_id": "topic_missing",
                "policy_id": policy["id"],
            }
        )
    with pytest.raises(DomainValidation):
        watches.create(
            {
                "name": "Bad type",
                "target_type": "nonsense",
                "target_id": topic["id"],
                "policy_id": policy["id"],
            }
        )


def test_watch_listing_is_bounded(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    _watch(watches, topic, policy)

    listing = watches.list(page=1, page_size=10)
    assert listing["total"] == 1
    assert listing["page_size"] == 10
    for bad in ({"page": 0}, {"page_size": 0}, {"page_size": 500}):
        with pytest.raises(DomainValidation):
            watches.list(**bad)
    with pytest.raises(DomainValidation):
        watches.list(status="nonsense")


def test_integrity_detects_a_watch_source_monitor_with_the_wrong_need(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    candidate = watches.add_source_candidate(
        watch["id"],
        {
            "name": "NASA News",
            "homepage_url": "https://www.nasa.gov/news/",
            "rationale": "Primary agency publication",
            "discovery_method": "manual",
        },
    )
    watches.review_source_candidate(watch["id"], candidate["id"], "approved", "editor")
    assert check_database(tmp_db).ok

    monitor_id = watches.get(watch["id"])["sources"][0]["monitor"]["id"]
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE monitors SET need_type = NULL, need_id = NULL WHERE id = ?",
                (monitor_id,),
            )
    finally:
        conn.close()

    report = check_database(tmp_db)
    assert not report.ok
    assert any(issue.code == "invalid_watch_source_monitor" for issue in report.issues)


def _attach_source(watches, watch_id, *, name, homepage):
    candidate = watches.add_source_candidate(
        watch_id,
        {
            "name": name,
            "homepage_url": homepage,
            "rationale": "fixture",
            "discovery_method": "manual",
        },
    )
    watches.review_source_candidate(watch_id, candidate["id"], "approved", "editor")
    for entry in watches.get(watch_id)["sources"]:
        if entry["source"]["name"] == name:
            return entry
    raise AssertionError("source was not attached")


def _relevant_document(db_path, *, monitor_id, source_id, canonical_url, title):
    """Persist a Document/version plus a confirmed Phase 20 relevance decision."""
    core = CoreService(db_path)
    document = core.create_document(
        {"source_id": source_id, "canonical_url": canonical_url, "title": title}
    )
    conn = storage.connect(db_path)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO document_versions(
                    id, document_id, retrieved_at, content_hash, content_kind,
                    created_at)
                VALUES (?, ?, ?, ?, 'full_text', ?)
                """,
                (
                    f"dv_{document['id']}",
                    document["id"],
                    "2026-01-01T00:00:00Z",
                    f"hash_{document['id']}",
                    "2026-01-01T00:00:00Z",
                ),
            )
            conn.execute(
                """
                INSERT INTO document_version_relevance(
                    id, document_version_id, monitor_id, scope_version, scope_json,
                    relevant, stage, score, created_at)
                VALUES (?, ?, ?, 1, '{}', 1, 'exact', 1.0, ?)
                """,
                (
                    f"rel_{document['id']}",
                    f"dv_{document['id']}",
                    monitor_id,
                    "2026-01-01T00:00:00Z",
                ),
            )
    finally:
        conn.close()
    return document


def test_discovery_recognizes_a_known_source_that_is_not_attached(tmp_db):
    core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    attached = _attach_source(
        watches, watch["id"], name="NASA News", homepage="https://www.nasa.gov/news/"
    )

    # A second Source that Newsroom already knows, producing relevant material
    # for this Watch's monitor, but which the user has not attached.
    other = core.create_source(
        {
            "name": "AARO",
            "slug": "aaro",
            "homepage_url": "https://www.aaro.mil/",
            "source_kind": "official",
        }
    )
    _relevant_document(
        tmp_db,
        monitor_id=attached["monitor"]["id"],
        source_id=other["id"],
        canonical_url="https://www.aaro.mil/report-1",
        title="AARO report",
    )

    result = watches.discover_sources(watch["id"])
    assert result["external_requests"] == 0
    methods = {item["discovery_method"] for item in result["candidates"]}
    assert "existing_source" in methods

    candidate = next(
        item
        for item in result["candidates"]
        if item["discovery_method"] == "existing_source"
    )
    # Existing Source recognition: resolves to the known Source, never a copy.
    assert candidate["source_id"] == other["id"]
    assert candidate["rationale"]
    assert candidate["status"] == "suggested"
    assert watches.get(watch["id"])["last_discovery_at"] is not None


def test_discovery_proposes_a_lineage_referenced_source(tmp_db):
    core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    attached = _attach_source(
        watches, watch["id"], name="NASA News", homepage="https://www.nasa.gov/news/"
    )
    cited = core.create_source(
        {
            "name": "Defense Department",
            "slug": "defense-dept",
            "homepage_url": "https://www.defense.gov/",
            "source_kind": "official",
        }
    )
    child = _relevant_document(
        tmp_db,
        monitor_id=attached["monitor"]["id"],
        source_id=attached["source"]["id"],
        canonical_url="https://www.nasa.gov/news/story-1",
        title="NASA story",
    )
    parent = core.create_document(
        {
            "source_id": cited["id"],
            "canonical_url": "https://www.defense.gov/primary-1",
            "title": "DoD primary",
        }
    )
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO document_lineage(
                    id, document_id, parent_document_id, relationship, rationale, created_at)
                VALUES ('lin_1', ?, ?, 'cites', 'fixture', '2026-01-01T00:00:00Z')
                """,
                (child["id"], parent["id"]),
            )
    finally:
        conn.close()

    result = watches.discover_sources(watch["id"])
    candidate = next(
        item
        for item in result["candidates"]
        if item["discovery_method"] == "document_link"
    )
    assert candidate["source_id"] == cited["id"]
    assert "cites" in candidate["provenance"]["relationship"]


def test_discovery_proposes_the_syndicated_original_publisher(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    attached = _attach_source(
        watches, watch["id"], name="Aggregator", homepage="https://aggregator.example/"
    )
    # Relevant material delivered by the aggregator but canonically published
    # on a domain Newsroom has no Source for.
    _relevant_document(
        tmp_db,
        monitor_id=attached["monitor"]["id"],
        source_id=attached["source"]["id"],
        canonical_url="https://originalpublisher.example/story-9",
        title="Syndicated story",
    )

    result = watches.discover_sources(watch["id"])
    candidate = next(
        item
        for item in result["candidates"]
        if item["discovery_method"] == "feed_discovery"
    )
    assert candidate["name"] == "originalpublisher.example"
    assert candidate["source_id"] is None
    assert candidate["provenance"]["observed_url"].startswith(
        "https://originalpublisher.example"
    )


def test_repeated_discovery_converges_and_is_bounded(tmp_db):
    core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    attached = _attach_source(
        watches, watch["id"], name="NASA News", homepage="https://www.nasa.gov/news/"
    )
    other = core.create_source(
        {
            "name": "AARO",
            "slug": "aaro",
            "homepage_url": "https://www.aaro.mil/",
            "source_kind": "official",
        }
    )
    _relevant_document(
        tmp_db,
        monitor_id=attached["monitor"]["id"],
        source_id=other["id"],
        canonical_url="https://www.aaro.mil/report-1",
        title="AARO report",
    )

    first = watches.discover_sources(watch["id"])
    second = watches.discover_sources(watch["id"])

    assert {item["id"] for item in first["candidates"]} == {
        item["id"] for item in second["candidates"]
    }
    conn = storage.connect(tmp_db)
    try:
        # Only the discovered rows matter here; the fixture also created one
        # manual candidate when it attached the starting Source.
        discovered = conn.execute(
            """
            SELECT COUNT(*) FROM source_candidates
            WHERE watch_id = ? AND discovery_method <> 'manual'
            """,
            (watch["id"],),
        ).fetchone()[0]
    finally:
        conn.close()
    assert discovered == len(first["candidates"])

    with pytest.raises(DomainValidation):
        watches.discover_sources(watch["id"], limit=0)
    with pytest.raises(DomainValidation):
        watches.discover_sources(watch["id"], limit=1000)


def test_discovery_with_no_corpus_is_a_successful_empty_run(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)

    result = watches.discover_sources(watch["id"])

    # A run that finds nothing is success, not failure (§86).
    assert result["candidates"] == []
    assert result["candidate_count"] == 0
    detail = watches.get(watch["id"])
    assert detail["last_discovery_at"] is not None
    assert detail["discovery_error"] is None


def test_discovery_never_attaches_a_candidate_or_creates_evidence(tmp_db):
    core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    attached = _attach_source(
        watches, watch["id"], name="NASA News", homepage="https://www.nasa.gov/news/"
    )
    other = core.create_source(
        {
            "name": "AARO",
            "slug": "aaro",
            "homepage_url": "https://www.aaro.mil/",
            "source_kind": "official",
        }
    )
    _relevant_document(
        tmp_db,
        monitor_id=attached["monitor"]["id"],
        source_id=other["id"],
        canonical_url="https://www.aaro.mil/report-1",
        title="AARO report",
    )

    watches.discover_sources(watch["id"])

    # Candidates are inert until approved: still exactly one attached Source,
    # and discovery creates no Claims or Evidence.
    assert len(watches.get(watch["id"])["sources"]) == 1
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM evidence_spans").fetchone()[0] == 0
    finally:
        conn.close()
    assert check_database(tmp_db).ok


def test_discovery_error_is_recorded_without_disturbing_monitoring(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    attached = _attach_source(
        watches, watch["id"], name="NASA News", homepage="https://www.nasa.gov/news/"
    )

    watches.record_discovery_error(watch["id"], "search backend unavailable")

    detail = watches.get(watch["id"])
    assert detail["discovery_error"] == "search backend unavailable"
    # Normal monitoring is untouched by an optional discovery failure (§82).
    assert detail["status"] == "active"
    assert detail["sources"][0]["monitor"]["id"] == attached["monitor"]["id"]
    assert detail["sources"][0]["monitor"]["enabled"] == 1


def _run_worker(db_path, handlers, worker_id="worker-1"):
    from newsroom.worker import WorkerProcess

    return WorkerProcess(db_path, handlers, worker_id=worker_id).run_once()


def test_discovery_job_runs_through_the_real_worker(tmp_db):
    core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    maintenance = WatchMaintenanceService(tmp_db, watches=watches)
    watch = _watch(watches, topic, policy)
    attached = _attach_source(
        watches, watch["id"], name="NASA News", homepage="https://www.nasa.gov/news/"
    )
    other = core.create_source(
        {
            "name": "AARO",
            "slug": "aaro",
            "homepage_url": "https://www.aaro.mil/",
            "source_kind": "official",
        }
    )
    _relevant_document(
        tmp_db,
        monitor_id=attached["monitor"]["id"],
        source_id=other["id"],
        canonical_url="https://www.aaro.mil/report-1",
        title="AARO report",
    )

    job = maintenance.enqueue_discovery(watch["id"])
    assert job["job_type"] == "watch_source_discovery"

    completed = _run_worker(tmp_db, maintenance.handlers())
    assert completed["status"] == "succeeded"
    assert completed["result"]["outcome"] == "completed"
    assert completed["result"]["candidate_count"] >= 1
    assert completed["result"]["external_requests"] == 0

    candidates = watches.get(watch["id"])["source_candidates"]
    assert any(item["discovery_method"] == "existing_source" for item in candidates)


def test_suggestion_job_runs_through_the_real_worker(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    maintenance = WatchMaintenanceService(tmp_db, watches=watches)
    watch = _watch(watches, topic, policy)

    maintenance.enqueue_suggestion(watch["id"])
    completed = _run_worker(tmp_db, maintenance.handlers())

    assert completed["status"] == "succeeded"
    assert completed["result"]["outcome"] == "completed"
    assert completed["result"]["pending_review"] >= 1
    # Suggested terms stay inert until a human approves them.
    assert all(
        item["enabled"] == 0
        for item in watches.get(watch["id"])["vocabulary"]
        if item["status"] == "suggested"
    )


def test_duplicate_dispatch_coalesces_but_a_later_run_is_allowed(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    maintenance = WatchMaintenanceService(tmp_db, watches=watches)
    watch = _watch(watches, topic, policy)

    first = maintenance.enqueue_discovery(watch["id"], requested_at="2026-01-01T00:00:00Z")
    duplicate = maintenance.enqueue_discovery(
        watch["id"], requested_at="2026-01-01T00:00:00Z"
    )
    # Same requested run coalesces onto one durable obligation.
    assert duplicate["id"] == first["id"]

    later = maintenance.enqueue_discovery(watch["id"], requested_at="2026-02-01T00:00:00Z")
    # A genuinely new user-triggered run must still be possible (§50/§81).
    assert later["id"] != first["id"]


def test_scheduler_coalesces_due_watch_monitor_work(tmp_db):
    core, topic, policy = _fixture(tmp_db)
    source = core.create_source(
        {
            "name": "NASA News",
            "slug": "nasa-news",
            "homepage_url": "https://www.nasa.gov/news/",
        }
    )
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    candidate = watches.add_source_candidate(
        watch["id"],
        {
            "name": "NASA News",
            "homepage_url": source["homepage_url"],
            "rationale": "Existing source",
            "discovery_method": "manual",
        },
    )
    watches.review_source_candidate(watch["id"], candidate["id"], "approved", "editor")
    monitor_id = watches.get(watch["id"])["sources"][0]["monitor"]["id"]
    MonitorService(tmp_db).update(
        monitor_id,
        {"next_check_at": "2026-08-23T12:00:00Z"},
    )

    scheduler = SchedulerService(tmp_db)
    first = scheduler.tick(now="2026-08-23T12:00:00Z")
    second = scheduler.tick(now="2026-08-23T12:00:00Z")

    assert first["enqueued"] == 1
    assert second["enqueued"] == 0
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE job_type = 'monitor_check'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_empty_discovery_job_succeeds_rather_than_failing(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    maintenance = WatchMaintenanceService(tmp_db, watches=watches)
    watch = _watch(watches, topic, policy)

    maintenance.enqueue_discovery(watch["id"])
    completed = _run_worker(tmp_db, maintenance.handlers())

    assert completed["status"] == "succeeded"
    assert completed["result"]["candidate_count"] == 0


def test_discovery_job_failure_is_retryable_and_records_the_error(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    maintenance = WatchMaintenanceService(tmp_db, watches=watches)
    watch = _watch(watches, topic, policy)
    _attach_source(
        watches, watch["id"], name="NASA News", homepage="https://www.nasa.gov/news/"
    )

    def exploding(_watch_id, *, limit=25):
        raise RuntimeError("search backend unavailable")

    watches.discover_sources = exploding  # type: ignore[method-assign]
    maintenance.enqueue_discovery(watch["id"])
    completed = _run_worker(tmp_db, maintenance.handlers())

    # A retryable failure returns the obligation to the queue for a bounded
    # retry rather than terminating it.
    assert completed["status"] == "queued"
    assert completed["attempts"] == 1

    detail = WatchService(tmp_db).get(watch["id"])
    assert detail["discovery_error"] == "search backend unavailable"
    # Optional discovery failing must never stop normal monitoring (§82).
    assert detail["status"] == "active"
    assert detail["sources"][0]["monitor"]["enabled"] == 1


def test_watch_jobs_are_registered_in_the_production_worker(tmp_db):
    from newsroom.runtime import build_worker_handlers

    apply_migrations(tmp_db)
    handlers = build_worker_handlers(tmp_db)

    assert "watch_source_discovery" in handlers
    assert "watch_vocabulary_suggestion" in handlers


def test_integrity_detects_an_orphan_watch_target(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE watches SET target_id = 'topic_missing' WHERE id = ?",
                (watch["id"],),
            )
    finally:
        conn.close()

    report = check_database(tmp_db)
    assert not report.ok
    assert any(issue.code == "orphan_watch_target" for issue in report.issues)


class _VocabularyProvider:
    model_name = "test-vocabulary-provider"

    def __init__(self):
        self.calls = 0

    def suggest(self, request):
        self.calls += 1
        assert len(request.approved_terms) <= 200
        assert request.max_suggestions <= 50
        return {
            "suggestions": [
                {
                    "term": "unidentified flying object",
                    "kind": "synonym",
                    "expansion_of": "UAP",
                    "rationale": "Provider-assisted alternate terminology",
                }
            ],
            "confidence": 0.95,
        }


def test_provider_vocabulary_uses_airouter_and_existing_paid_controls(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    policy = MonitoringPolicyService(tmp_db).update(
        policy["id"], {"paid_budget_usd": 0.01}
    )
    provider = _VocabularyProvider()
    router = AIRouter(
        local=CapabilityBundle.local_defaults(),
        paid=CapabilityBundle(vocabulary=provider),
        policy=RoutePolicy(
            paid_enabled=True,
            max_paid_calls=1,
            max_paid_cost_usd=0.01,
            max_paid_calls_per_work=1,
            max_paid_cost_usd_per_work=0.01,
            paid_request_cost_usd=0.01,
        ),
    )
    BudgetService(tmp_db).set_paid_enabled(True)
    watches = WatchService(tmp_db, router=router)
    watch = _watch(watches, topic, policy)

    suggestions = watches.suggest_vocabulary(watch["id"], limit=20)

    assert provider.calls == 1
    provider_terms = [item for item in suggestions if item["origin"] == "ai"]
    assert provider_terms[0]["term"] == "unidentified flying object"
    assert provider_terms[0]["status"] == "suggested"
    assert provider_terms[0]["enabled"] == 0


def test_provider_vocabulary_is_not_called_when_paid_budget_is_disabled(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    provider = _VocabularyProvider()
    router = AIRouter(
        local=CapabilityBundle.local_defaults(),
        paid=CapabilityBundle(vocabulary=provider),
        policy=RoutePolicy(paid_enabled=True, max_paid_calls=1),
    )
    BudgetService(tmp_db).set_paid_enabled(False)
    watches = WatchService(tmp_db, router=router)
    watch = _watch(watches, topic, policy)

    suggestions = watches.suggest_vocabulary(watch["id"], limit=20)

    assert provider.calls == 0
    assert suggestions
    assert all(item["origin"] != "ai" for item in suggestions)


def test_watch_query_plan_is_bounded_and_excludes_pending_terms(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    watches.add_vocabulary(
        watch["id"],
        {
            "term": "AARO",
            "kind": "include",
            "rationale": "Approved institutional term",
        },
    )
    watches.add_vocabulary(
        watch["id"],
        {
            "term": "fiction",
            "kind": "exclude",
            "rationale": "Avoid entertainment coverage",
        },
    )
    pending = next(
        item["term"]
        for item in watches.suggest_vocabulary(watch["id"], limit=20)
        if item["status"] == "suggested"
    )

    plan = watches.query_plan(watch["id"], limit=100)

    assert plan["variant_count"] <= policy["query_budget"]
    assert plan["variant_count"] <= 12
    assert "fiction" in plan["excluded_terms"]
    assert pending not in {term for variant in plan["variants"] for term in variant["terms"]}
    assert all(len(variant["terms"]) <= 2 for variant in plan["variants"])


def test_watch_health_and_collection_views_are_bounded(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    watches.add_vocabulary(
        watch["id"],
        {"term": "AARO", "kind": "include", "rationale": "Agency"},
    )
    suggestions = watches.suggest_vocabulary(watch["id"], limit=20)
    pending = next(item for item in suggestions if item["status"] == "suggested")
    watches.review_vocabulary(watch["id"], pending["id"], "rejected", "editor")
    watches.add_source_candidate(
        watch["id"],
        {
            "name": "NASA News",
            "homepage_url": "https://www.nasa.gov/news/",
            "rationale": "Agency publication",
            "discovery_method": "manual",
        },
    )

    health = watches.health(watch["id"])
    vocabulary = watches.list_vocabulary(watch["id"], page=1, page_size=1)
    candidates = watches.list_source_candidates(watch["id"], page=1, page_size=1)

    assert health["status"] == "active"
    assert health["active_source_count"] == 0
    assert health["pending_source_candidate_count"] == 1
    assert health["pending_vocabulary_suggestion_count"] >= 0
    assert health["discovery_enabled"] is True
    assert vocabulary["page_size"] == 1
    assert vocabulary["total"] >= 2
    assert candidates["page_size"] == 1
    assert candidates["total"] == 1

    with pytest.raises(DomainValidation):
        watches.list_vocabulary(watch["id"], page_size=101)


def test_watch_management_api_exposes_health_and_bounded_collections(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    app = create_app(config=config, frontend_dist=tmp_path / "missing-dist")
    with TestClient(app) as client:
        assert client.post(
            "/api/v1/auth/setup",
            json={"username": "admin", "password": "a-long-test-password-12345"},
        ).status_code == 201
        assert client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "a-long-test-password-12345"},
        ).status_code == 200
        csrf = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
        category = client.post(
            "/api/v1/categories",
            json={"slug": "aerospace", "name": "Aerospace"},
            headers=csrf,
        ).json()
        topic = client.post(
            "/api/v1/topics",
            json={
                "category_id": category["id"],
                "slug": "uap",
                "name": "UAP disclosure",
            },
            headers=csrf,
        ).json()
        policy = client.post(
            "/api/v1/monitoring-policies",
            json={
                "name": "Watch policy",
                "allowed_channels": ["direct_http"],
                "base_cadence_seconds": 3600,
                "min_cadence_seconds": 900,
                "max_cadence_seconds": 86400,
                "query_budget": 10,
            },
            headers=csrf,
        ).json()
        created = client.post(
            "/api/v1/watches",
            json={
                "name": "UAP disclosure",
                "target_type": "topic",
                "target_id": topic["id"],
                "policy_id": policy["id"],
            },
            headers=csrf,
        )
        assert created.status_code == 201
        watch_id = created.json()["id"]

        assert client.patch(
            f"/api/v1/watches/{watch_id}",
            json={"name": "UAP disclosure updates"},
            headers=csrf,
        ).status_code == 200
        health = client.get(f"/api/v1/watches/{watch_id}/health")
        vocabulary = client.get(
            f"/api/v1/watches/{watch_id}/vocabulary?page_size=1"
        )
        plan = client.get(f"/api/v1/watches/{watch_id}/query-plan?limit=100")

        assert health.status_code == 200
        assert health.json()["watch_id"] == watch_id
        assert vocabulary.status_code == 200
        assert vocabulary.json()["page_size"] == 1
        assert plan.status_code == 200
        assert plan.json()["variant_count"] <= 12


def test_concurrent_candidate_creation_and_approval_converge(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    payload = {
        "name": "NASA News",
        "homepage_url": "https://www.nasa.gov/news/",
        "rationale": "Agency publication",
        "discovery_method": "manual",
    }

    with ThreadPoolExecutor(max_workers=2) as pool:
        candidates = list(
            pool.map(lambda _item: watches.add_source_candidate(watch["id"], payload), range(2))
        )
    assert len({candidate["id"] for candidate in candidates}) == 1

    with ThreadPoolExecutor(max_workers=2) as pool:
        reviewed = list(
            pool.map(
                lambda _item: watches.review_source_candidate(
                    watch["id"], candidates[0]["id"], "approved", "editor"
                ),
                range(2),
            )
        )
    assert all(candidate["status"] == "approved" for candidate in reviewed)
    assert len(watches.get(watch["id"])["sources"]) == 1


def test_concurrent_suggestion_runs_converge_without_duplicate_terms(tmp_db):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _item: watches.suggest_vocabulary(watch["id"], limit=20), range(2))
        )

    assert results[0] and results[1]
    conn = storage.connect(tmp_db)
    try:
        duplicate_count = conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT term_normalized, kind, COUNT(*) AS count
                FROM watch_vocabulary
                WHERE watch_id = ?
                GROUP BY term_normalized, kind
                HAVING COUNT(*) > 1
            )
            """,
            (watch["id"],),
        ).fetchone()[0]
    finally:
        conn.close()
    assert duplicate_count == 0


def test_logical_export_reconstructs_watch_configuration(tmp_db, tmp_path):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    active = watches.add_vocabulary(
        watch["id"],
        {"term": "AARO", "kind": "include", "rationale": "Agency"},
    )
    rejected = next(
        item
        for item in watches.suggest_vocabulary(watch["id"], limit=20)
        if item["status"] == "suggested"
    )
    watches.review_vocabulary(watch["id"], rejected["id"], "rejected", "editor")
    approved_candidate = watches.add_source_candidate(
        watch["id"],
        {
            "name": "NASA News",
            "homepage_url": "https://www.nasa.gov/news/",
            "rationale": "Agency publication",
            "discovery_method": "manual",
        },
    )
    watches.review_source_candidate(
        watch["id"], approved_candidate["id"], "approved", "editor"
    )
    rejected_candidate = watches.add_source_candidate(
        watch["id"],
        {
            "name": "Example Research",
            "homepage_url": "https://research.example/",
            "rationale": "Research archive",
            "discovery_method": "manual",
        },
    )
    watches.review_source_candidate(
        watch["id"], rejected_candidate["id"], "rejected", "editor"
    )

    destination = export_logical(tmp_db, tmp_path / "watch.jsonl")
    rows = [
        json.loads(line)
        for line in destination.read_text(encoding="utf-8").splitlines()
        if line.startswith('{"data"')
    ]
    by_table: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_table.setdefault(str(row["table"]), []).append(row["data"])

    exported_watch = next(row for row in by_table["watches"] if row["id"] == watch["id"])
    exported_active = next(row for row in by_table["watch_vocabulary"] if row["id"] == active["id"])
    exported_rejected = next(row for row in by_table["watch_vocabulary"] if row["id"] == rejected["id"])
    exported_candidates = {row["id"]: row for row in by_table["source_candidates"]}

    assert exported_watch["target_id"] == topic["id"]
    assert exported_active["status"] == "approved"
    assert exported_active["enabled"] == 1
    assert exported_rejected["status"] == "rejected"
    assert exported_rejected["enabled"] == 0
    assert exported_candidates[approved_candidate["id"]]["status"] == "approved"
    assert exported_candidates[rejected_candidate["id"]]["status"] == "rejected"
    assert len([row for row in by_table["watch_sources"] if row["watch_id"] == watch["id"]]) == 1
    monitor = next(row for row in by_table["monitors"] if row["id"] == watches.get(watch["id"])["sources"][0]["monitor"]["id"])
    assert monitor["need_type"] == "topic"
    assert monitor["need_id"] == topic["id"]


def test_backup_restore_preserves_watch_state(tmp_db, tmp_path):
    _core, topic, policy = _fixture(tmp_db)
    watches = WatchService(tmp_db)
    watch = _watch(watches, topic, policy)
    active = watches.add_vocabulary(
        watch["id"],
        {"term": "AARO", "kind": "include", "rationale": "Agency"},
    )
    candidate = watches.add_source_candidate(
        watch["id"],
        {
            "name": "NASA News",
            "homepage_url": "https://www.nasa.gov/news/",
            "rationale": "Agency publication",
            "discovery_method": "manual",
        },
    )

    backup = backup_database(tmp_db, tmp_path / "backups", label="phase24")
    restored_path = tmp_path / "restored" / "newsroom.db"
    restored = restore_database(backup["path"], restored_path)

    assert backup["verified"] is True
    assert restored["verified"] is True
    restored_watch = WatchService(restored_path).get(watch["id"])
    assert restored_watch["name"] == watch["name"]
    assert any(item["id"] == active["id"] and item["enabled"] == 1 for item in restored_watch["vocabulary"])
    assert any(item["id"] == candidate["id"] and item["status"] == "suggested" for item in restored_watch["source_candidates"])
    assert check_database(restored_path).ok


def _apply_phase23_schema(db_path):
    conn = storage.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        with storage.write_tx(conn):
            migrations._ensure_ledger(conn)
            for version in range(1, 24):
                statements = getattr(migrations, f"MIGRATION_{version:04d}_STATEMENTS")
                for statement in statements:
                    conn.execute(statement)
                now = migrations.utc_now()
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, now),
                )
                if version == 1:
                    conn.execute(
                        "INSERT INTO app_meta(key, value) VALUES ('schema_version', '1')"
                    )
                    conn.execute(
                        "INSERT INTO app_meta(key, value) VALUES ('schema_seeded_at', ?)",
                        (now,),
                    )
                else:
                    conn.execute(
                        "UPDATE app_meta SET value = ? WHERE key = 'schema_version'",
                        (str(version),),
                    )
        conn.execute("PRAGMA foreign_keys = ON")
    finally:
        conn.close()


def test_phase23_database_upgrades_to_phase24_without_recreating_monitors(tmp_db):
    _apply_phase23_schema(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source(
        {
            "name": "Legacy NASA",
            "slug": "legacy-nasa",
            "homepage_url": "https://www.nasa.gov/",
        }
    )
    policy = MonitoringPolicyService(tmp_db).create(
        {
            "name": "Legacy policy",
            "allowed_channels": ["direct_http"],
            "base_cadence_seconds": 3600,
            "min_cadence_seconds": 900,
            "max_cadence_seconds": 86400,
            "query_budget": 3,
        }
    )
    legacy_monitor = MonitorService(tmp_db).create(
        {
            "target_type": "source",
            "target_id": source["id"],
            "policy_id": policy["id"],
            "enabled": True,
        }
    )

    result = apply_migrations(tmp_db)

    assert result.applied_versions == (24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36)
    assert migration_status(tmp_db) == tuple(range(1, 37))
    assert apply_migrations(tmp_db).applied_versions == ()
    preserved = MonitorService(tmp_db).get(legacy_monitor["id"])
    assert preserved["target_id"] == source["id"]
    assert preserved["need_type"] is None
    assert preserved["need_id"] is None
    watches = WatchService(tmp_db)
    watch = watches.create(
        {
            "name": "Legacy source Watch",
            "target_type": "source",
            "target_id": source["id"],
            "policy_id": policy["id"],
        }
    )
    candidate = watches.add_source_candidate(
        watch["id"],
        {
            "name": "Legacy NASA",
            "homepage_url": "https://www.nasa.gov/",
            "rationale": "Existing source",
            "discovery_method": "manual",
        },
    )
    watches.review_source_candidate(watch["id"], candidate["id"], "approved", "editor")
    assert watches.get(watch["id"])["status"] == "active"
    assert watches.get(watch["id"])["sources"][0]["monitor"]["id"] == legacy_monitor["id"]


def test_watch_source_preserves_phase23_evidence_story_report_alert_chain(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="The agency released a UAP report.",
        proposition="The agency released a UAP report",
    )
    promotion = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    promotion_id = promotion["outcomes"][0]["id"]

    conn = storage.connect(tmp_db)
    try:
        topic = conn.execute("SELECT id FROM topics WHERE slug = 'uap'").fetchone()
        source = conn.execute("SELECT id FROM sources WHERE slug = 'example'").fetchone()
        policy = conn.execute("SELECT id FROM monitoring_policies WHERE name = 'Policy'").fetchone()
    finally:
        conn.close()

    watches = WatchService(tmp_db)
    watch = watches.create(
        {
            "name": "UAP Watch",
            "target_type": "topic",
            "target_id": topic["id"],
            "policy_id": policy["id"],
        }
    )
    candidate = watches.add_source_candidate(
        watch["id"],
        {
            "name": "Example",
            "homepage_url": "https://example.test",
            "rationale": "Existing source carrying relevant material",
            "discovery_method": "existing_source",
        },
    )
    watches.review_source_candidate(watch["id"], candidate["id"], "approved", "editor")
    assert watches.get(watch["id"])["sources"][0]["source"]["id"] == source["id"]

    _story_job, report_job = _complete_story_stage(tmp_db, promotion_id)
    queue = build_worker_queue(tmp_db)
    claimed_report = queue.claim(report_job["id"], "report-worker", now="2026-08-23T12:01:00Z")
    report_outcome = AutomaticReportStageExecutionService(tmp_db).handle(claimed_report)
    queue.complete(
        report_job["id"],
        "report-worker",
        "succeeded",
        outcome=report_outcome,
    )
    rule = AlertService(tmp_db).create_rule(
        {
            "name": "Watch chain alert",
            "target_type": "report",
            "target_id": report_outcome["report_id"],
        }
    )
    alert_job = _alert_stage_job(tmp_db, report_job["id"])
    alert_outcome, _completed_alert = _run_alert_stage(tmp_db, alert_job)

    assert rule["id"] in alert_outcome["evaluated_rule_ids"]
    assert alert_outcome["stage_status"] == "completed"
    assert len(alert_outcome["alert_ids"]) == len(alert_outcome["delivery_ids"]) == 1
    assert check_database(tmp_db).ok
