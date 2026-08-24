from __future__ import annotations

import json

import pytest

from newsroom.domain import CoreService, DomainConflict, new_id, precise_utc_now
from newsroom.evidence import EvidenceService, claim_proposition_hash
from newsroom.integrity import check_database
from newsroom.knowledge import KnowledgeService
from newsroom.migrations import apply_migrations
from newsroom.intelligent_monitoring import WatchService
from newsroom.monitoring import MonitorService, MonitoringPolicyService
from newsroom.story_corrections import StoryCorrectionService
from newsroom.story_corrections import StoryCorrectionReconciliationService
from newsroom import storage
from newsroom.jobs import JobService
from newsroom.worker import WorkerProcess
from newsroom.reports import LivingReportService


def _stories_and_claim(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    first = core.create_story({"headline": "First story"})
    second = core.create_story({"headline": "Second story"})
    claim = EvidenceService(tmp_db).create_claim(first["id"], {"proposition": "A durable proposition"})
    return first, second, claim


def test_claim_reassignment_is_append_only_and_unassignment_is_authoritative(tmp_db):
    first, second, claim = _stories_and_claim(tmp_db)
    service = StoryCorrectionService(tmp_db)

    moved = service.reassign_claim(claim["id"], second["id"], actor="user-1", reason="manual correction")
    assert moved["claim"]["story_id"] == second["id"]

    with pytest.raises(DomainConflict, match="cannot be reassigned"):
        service.automatic_initial_assignment(claim["id"], first["id"])

    unassigned = service.unassign_claim(claim["id"], actor="user-1", reason="hold for review")
    assert unassigned["claim"]["story_id"] is None

    conn = storage.connect(tmp_db)
    try:
        rows = conn.execute(
            "SELECT from_story_id, to_story_id, origin, reason_code, correction_id FROM claim_story_assignment_history WHERE claim_id = ? ORDER BY occurred_at, id",
            (claim["id"],),
        ).fetchall()
        assert [(row[0], row[1]) for row in rows] == [(first["id"], second["id"]), (second["id"], None)]
        assert all(row[4] for row in rows)
    finally:
        conn.close()
    assert check_database(tmp_db).ok

    with pytest.raises(DomainConflict, match="human unassignment"):
        service.automatic_initial_assignment(claim["id"], first["id"])


def test_extract_keeps_source_active_and_does_not_create_split_lineage(tmp_db):
    first, second, claim = _stories_and_claim(tmp_db)
    second_claim = EvidenceService(tmp_db).create_claim(first["id"], {"proposition": "A second proposition"})
    result = StoryCorrectionService(tmp_db).extract_claims(
        first["id"], [claim["id"]], {"headline": "Extracted story"}, actor="user-1"
    )

    assert result["story"]["lifecycle"] != "archived"
    assert result["new_story"]["id"] != first["id"]
    assert result["moved_claim_ids"] == [claim["id"]]
    assert EvidenceService(tmp_db).get_claim(second_claim["id"])["story_id"] == first["id"]
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT 1 FROM story_lineage WHERE source_story_id = ?", (first["id"],)).fetchone() is None
    finally:
        conn.close()


def test_merge_and_split_preserve_lineage_and_retire_source(tmp_db):
    first, second, claim = _stories_and_claim(tmp_db)
    service = StoryCorrectionService(tmp_db)
    merged = service.merge_stories(second["id"], first["id"], actor="user-1", reason="duplicate")
    assert merged["source"]["lifecycle"] == "archived"
    assert merged["destination"]["id"] == first["id"]

    split_source = CoreService(tmp_db).create_story({"headline": "Combined story"})
    split_claim_a = EvidenceService(tmp_db).create_claim(split_source["id"], {"proposition": "Development A"})
    split_claim_b = EvidenceService(tmp_db).create_claim(split_source["id"], {"proposition": "Development B"})
    split = service.split_story(
        split_source["id"],
        [[split_claim_a["id"]], [split_claim_b["id"]]],
        actor="user-1",
        reason="incompatible developments",
    )
    assert split["source"]["lifecycle"] == "archived"
    assert len(split["children"]) == 2
    conn = storage.connect(tmp_db)
    try:
        rows = conn.execute(
            "SELECT relationship, target_story_id FROM story_lineage WHERE source_story_id = ? ORDER BY target_story_id",
            (split_source["id"],),
        ).fetchall()
        assert [row[0] for row in rows] == ["split_into", "split_into"]
        assert all(row[1] != split_source["id"] for row in rows)
    finally:
        conn.close()


def test_current_story_documents_and_entities_ignore_historical_membership(tmp_db):
    first, second, claim = _stories_and_claim(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Context source", "slug": "context-source"})
    document = core.create_document({"source_id": source["id"], "canonical_url": "https://context.test/item", "title": "Context"})
    version = EvidenceService(tmp_db).create_document_version(document["id"], {"content_hash": "context-v1", "content_kind": "excerpt"})
    span = EvidenceService(tmp_db).create_evidence_span(version["id"], {"excerpt": "A durable proposition"})
    EvidenceService(tmp_db).link_claim_evidence(claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"})
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "INSERT INTO story_documents(story_id, document_id, event_key, entities_json, locations_json, linked_at) VALUES (?, ?, NULL, '[]', '[]', CURRENT_TIMESTAMP)",
                (first["id"], document["id"]),
            )
    finally:
        conn.close()


    entity = KnowledgeService(tmp_db).create_entity({"canonical_name": "Context Entity", "entity_type": "organization"})
    KnowledgeService(tmp_db).link_claim_entity(claim["id"], entity["id"])
    result = StoryCorrectionService(tmp_db).reassign_claim(claim["id"], second["id"], actor="user-1", reason="move")
    conn = storage.connect(tmp_db)
    try:
        job = dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (result["job_id"],)).fetchone())
        job["payload"] = json.loads(job.pop("payload_json"))
    finally:
        conn.close()
    reconciliation = StoryCorrectionReconciliationService(tmp_db)
    first_reconciliation = reconciliation.handle(job)
    replay = reconciliation.handle(job)
    assert first_reconciliation["reconciled"] is True
    assert replay["story_revision_ids"] == {}

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT 1 FROM story_documents WHERE story_id = ? AND document_id = ?", (first["id"], document["id"])).fetchone()
        current_first = conn.execute(
            "SELECT 1 FROM claims c JOIN claim_evidence ce ON ce.claim_id = c.id JOIN evidence_spans es ON es.id = ce.evidence_span_id JOIN document_versions dv ON dv.id = es.document_version_id WHERE c.story_id = ? AND dv.document_id = ?",
            (first["id"], document["id"]),
        ).fetchone()
        current_second = conn.execute(
            "SELECT 1 FROM claims c JOIN claim_evidence ce ON ce.claim_id = c.id JOIN evidence_spans es ON es.id = ce.evidence_span_id JOIN document_versions dv ON dv.id = es.document_version_id WHERE c.story_id = ? AND dv.document_id = ?",
            (second["id"], document["id"]),
        ).fetchone()
        assert current_first is None
        assert current_second is not None
        effective = conn.execute(
            "SELECT entity_id FROM story_entities WHERE story_id = ? AND authority = 'derived' AND entity_id = ?",
            (second["id"], entity["id"]),
        ).fetchone()
        assert effective is not None
    finally:
        conn.close()


def test_story_correction_metrics_are_derived_from_durable_history(tmp_db):
    first, second, _ = _stories_and_claim(tmp_db)
    service = StoryCorrectionService(tmp_db)
    claim_id = new_id("claim")
    proposition = "An automatically assigned proposition"
    now = precise_utc_now()
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "INSERT INTO claims(id, story_id, proposition, proposition_hash, importance, state, created_at) VALUES (?, NULL, ?, ?, 'relevant', 'pending', ?)",
                (claim_id, proposition, claim_proposition_hash(proposition), now),
            )
    finally:
        conn.close()
    service.automatic_initial_assignment(claim_id, first["id"])
    service.reassign_claim(claim_id, second["id"], actor="user-1", reason="correct resolver")
    service.unassign_claim(claim_id, actor="user-1", reason="hold")
    metrics = service.metrics()
    assert metrics["automatic_assignment_count"] == 1
    assert metrics["manual_reassignment_count"] == 1
    assert metrics["manual_unassignment_count"] == 1
    assert metrics["time_to_correction_seconds"] is not None
    assert metrics["resolver_algorithm_version"] == "automatic_story_resolver_v1"


def test_duplicate_review_identity_and_watch_resolution_are_durable(tmp_db):
    first, second, _ = _stories_and_claim(tmp_db)
    evidence = "A durable proposition"
    EvidenceService(tmp_db).create_claim(second["id"], {"proposition": evidence})
    service = StoryCorrectionService(tmp_db)
    suggestion = service.suggest_duplicates(first["id"])[0]
    dismissed = service.dismiss_duplicate(
        suggestion["source_story_id"],
        suggestion["destination_story_id"],
        evidence_hash=suggestion["evidence_hash"],
        actor="user-1",
        reason="distinct context",
    )
    assert dismissed["decision"] == "dismissed"
    assert service.suggest_duplicates(first["id"]) == []

    third = CoreService(tmp_db).create_story({"headline": "Third duplicate"})
    EvidenceService(tmp_db).create_claim(third["id"], {"proposition": evidence})
    approval = service.suggest_duplicates(third["id"])[0]
    merged = service.approve_duplicate(
        approval["source_story_id"],
        approval["destination_story_id"],
        evidence_hash=approval["evidence_hash"],
        actor="user-1",
        reason="duplicate confirmed",
    )
    assert merged["source"]["lifecycle"] == "archived"
    assert merged["duplicate_evidence_hash"] == approval["evidence_hash"]

    policy = MonitoringPolicyService(tmp_db).create(
        {
            "name": "Story corrections",
            "allowed_channels": ["direct_http"],
            "base_cadence_seconds": 60,
            "min_cadence_seconds": 30,
            "max_cadence_seconds": 300,
        }
    )
    watch_source = CoreService(tmp_db).create_story({"headline": "Watch source"})
    watch_destination = CoreService(tmp_db).create_story({"headline": "Watch destination"})
    watch = WatchService(tmp_db).create(
        {"name": "Merged Story", "target_type": "story", "target_id": watch_source["id"], "policy_id": policy["id"]}
    )
    monitor = MonitorService(tmp_db).create(
        {"target_type": "story", "target_id": watch_source["id"], "policy_id": policy["id"]}
    )
    service.merge_stories(watch_source["id"], watch_destination["id"], actor="user-1", reason="watch canonical")
    merged_watch = WatchService(tmp_db).get(watch["id"])
    assert merged_watch["target_id"] == watch_destination["id"]
    assert merged_watch["historical_target_id"] == watch_source["id"]
    merged_monitor = MonitorService(tmp_db).get(monitor["id"])
    assert merged_monitor["target_id"] == watch_destination["id"]
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute(
            "SELECT 1 FROM monitor_scope_history WHERE monitor_id = ? AND change_type = 'manual'",
            (monitor["id"],),
        ).fetchone()
    finally:
        conn.close()

    split_source = CoreService(tmp_db).create_story({"headline": "Watch split"})
    split_claim_a = EvidenceService(tmp_db).create_claim(split_source["id"], {"proposition": "Watch split A"})
    split_claim_b = EvidenceService(tmp_db).create_claim(split_source["id"], {"proposition": "Watch split B"})
    split_watch = WatchService(tmp_db).create(
        {"name": "Split Story", "target_type": "story", "target_id": split_source["id"], "policy_id": policy["id"]}
    )
    split = service.split_story(split_source["id"], [[split_claim_a["id"]], [split_claim_b["id"]]], actor="user-1")
    split_watch_after = WatchService(tmp_db).get(split_watch["id"])
    assert split_watch_after["resolution_state"] == "needs_review"
    assert json.loads(split_watch_after["resolution_options_json"]) == [item["id"] for item in split["children"]]
    resolved_watch = service.resolve_split_target("watch", split_watch["id"], [split["children"][0]["id"]], actor="user-1")
    assert resolved_watch["target_id"] == split["children"][0]["id"]
    assert resolved_watch["resolution_state"] == "active"
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT 1 FROM story_target_resolution_history WHERE target_kind = 'watch' AND target_id = ?", (split_watch["id"],)).fetchone()
    finally:
        conn.close()


def test_merge_fingerprint_rejects_claim_set_change_after_preview(tmp_db):
    first, second, claim = _stories_and_claim(tmp_db)
    service = StoryCorrectionService(tmp_db)
    preview = service.preview_merge(first["id"], second["id"])
    extra = EvidenceService(tmp_db).create_claim(first["id"], {"proposition": "Added after preview"})

    with pytest.raises(DomainConflict, match="merge preview is stale"):
        service.merge_stories(
            first["id"],
            second["id"],
            expected_current_state_fingerprint=preview["expected_current_state_fingerprint"],
        )

    assert EvidenceService(tmp_db).get_claim(claim["id"])["story_id"] == first["id"]
    assert EvidenceService(tmp_db).get_claim(extra["id"])["story_id"] == first["id"]


def test_lineage_resolution_composes_merge_then_split_and_later_merge(tmp_db):
    first, second, _ = _stories_and_claim(tmp_db)
    service = StoryCorrectionService(tmp_db)
    merged = service.merge_stories(second["id"], first["id"])
    source = CoreService(tmp_db).create_story({"headline": "Split source"})
    claims = [
        EvidenceService(tmp_db).create_claim(source["id"], {"proposition": value})
        for value in ("A", "B")
    ]
    split = service.split_story(source["id"], [[claims[0]["id"]], [claims[1]["id"]]])
    later = service.merge_stories(split["children"][0]["id"], first["id"])

    resolved_merged = service.resolve_story(second["id"])
    assert resolved_merged["resulting_story_ids"] == [first["id"]]
    resolved_split = service.resolve_story(source["id"])
    assert resolved_split["resulting_story_ids"] == sorted([first["id"], split["children"][1]["id"]])
    assert later["destination"]["id"] == first["id"]


def test_duplicate_identity_is_symmetric_and_dismissal_is_direction_independent(tmp_db):
    first, second, _ = _stories_and_claim(tmp_db)
    EvidenceService(tmp_db).create_claim(second["id"], {"proposition": "A durable proposition"})
    service = StoryCorrectionService(tmp_db)
    from_first = service.suggest_duplicates(first["id"])
    from_second = service.suggest_duplicates(second["id"])
    assert from_first and from_second
    assert from_first[0]["evidence_hash"] == from_second[0]["evidence_hash"]
    assert from_first[0]["id"] == from_second[0]["id"]

    service.dismiss_duplicate(first["id"], second["id"], evidence_hash=from_first[0]["evidence_hash"])
    assert service.suggest_duplicates(first["id"]) == []
    assert service.suggest_duplicates(second["id"]) == []


def test_merge_tag_propagation_keeps_legacy_and_phase26_assignments_in_sync(tmp_db):
    first, second, _ = _stories_and_claim(tmp_db)
    service = StoryCorrectionService(tmp_db)
    tag_id = CoreService(tmp_db).create_tag({"name": "Phase 28"})["id"]
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("INSERT INTO story_tags(story_id, tag_id, created_at) VALUES (?, ?, ?)", (first["id"], tag_id, precise_utc_now()))
            conn.execute("INSERT INTO tag_assignments(id, tag_id, object_type, object_id, origin, created_at) VALUES (?, ?, 'story', ?, 'user', ?)", (new_id("ta"), tag_id, first["id"], precise_utc_now()))
    finally:
        conn.close()

    service.merge_stories(first["id"], second["id"], metadata_decisions={"copy_tags": True})
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT 1 FROM story_tags WHERE story_id = ? AND tag_id = ?", (second["id"], tag_id)).fetchone()
        assert conn.execute("SELECT 1 FROM tag_assignments WHERE object_type = 'story' AND object_id = ? AND tag_id = ?", (second["id"], tag_id)).fetchone()
    finally:
        conn.close()


def test_reconciliation_downstream_failure_remains_retryable(tmp_db, monkeypatch):
    first, second, claim = _stories_and_claim(tmp_db)
    LivingReportService(tmp_db).create({"name": "Second report", "target_type": "story", "target_id": second["id"]})
    result = StoryCorrectionService(tmp_db).reassign_claim(claim["id"], second["id"])
    job = JobService(tmp_db).get(result["job_id"])

    class FailingReports:
        def __init__(self, db_path):
            pass

        def generate(self, report_id):
            raise RuntimeError("temporary report failure")

    monkeypatch.setattr("newsroom.reports.LivingReportService", FailingReports)
    worker = WorkerProcess(tmp_db, StoryCorrectionReconciliationService(tmp_db).handlers(), worker_id="phase28-test")
    worker.run_once()
    retried = JobService(tmp_db).get(job["id"])
    assert retried["status"] == "queued"
    assert retried["attempts"] == 1
