from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from newsroom import storage
from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.domain import CoreService, DomainValidation, utc_now
from newsroom.evidence import EvidenceService
from newsroom.migrations import apply_migrations
from newsroom.monitoring import MonitorService, MonitoringPolicyService
from newsroom.workbench import ComparisonService, DiagnosticsService, SearchService, WorkbenchService


def _fixture(db_path):
    apply_migrations(db_path)
    core = CoreService(db_path)
    official = core.create_source(
        {
            "name": "Atlas Official",
            "slug": "atlas-official",
            "source_kind": "official",
            "default_quality": "primary",
        }
    )
    secondary = core.create_source(
        {
            "name": "Atlas Journal",
            "slug": "atlas-journal",
            "source_kind": "web",
            "default_quality": "medium",
        }
    )
    first = core.create_document(
        {
            "source_id": official["id"],
            "canonical_url": "https://atlas.test/launch",
            "title": "Atlas launch on August 16",
            "published_at": "2025-08-16T12:00:00Z",
        }
    )
    second = core.create_document(
        {
            "source_id": secondary["id"],
            "canonical_url": "https://journal.test/atlas-update",
            "title": "Atlas update on August 17",
            "published_at": "2025-08-17T12:00:00Z",
        }
    )
    story = core.create_story(
        {
            "headline": "Atlas launches",
            "summary": "The Atlas launch is being tracked.",
            "subject_ids": [],
        }
    )
    ledger = EvidenceService(db_path)
    first_version = ledger.create_document_version(
        first["id"], {"content_hash": "atlas-v1", "content_kind": "excerpt"}
    )
    second_version = ledger.create_document_version(
        second["id"], {"content_hash": "atlas-v2", "content_kind": "excerpt"}
    )
    first_span = ledger.create_evidence_span(
        first_version["id"],
        {"excerpt": "Atlas launched on August 16 with 100 users."},
    )
    second_span = ledger.create_evidence_span(
        second_version["id"],
        {"excerpt": "Atlas launched on August 17 with 120 users."},
    )
    shared = ledger.create_claim(
        story["id"], {"proposition": "Atlas launched", "importance": "major"}
    )
    ledger.link_claim_evidence(
        shared["id"], {"evidence_span_id": first_span["id"], "relationship": "supports"}
    )
    ledger.link_claim_evidence(
        shared["id"], {"evidence_span_id": second_span["id"], "relationship": "supports"}
    )
    ledger.set_claim_state(shared["id"], "supported", "two sources")
    ledger.accept_claim(shared["id"])
    conflicting = ledger.create_claim(
        story["id"],
        {"proposition": "Atlas launched on August 17", "importance": "major"},
    )
    ledger.link_claim_evidence(
        conflicting["id"],
        {"evidence_span_id": second_span["id"], "relationship": "contradicts"},
    )
    ledger.set_claim_state(conflicting["id"], "disputed", "date differs")
    return core, ledger, official, secondary, first, second, story, first_span, second_span, shared, conflicting


def test_search_is_bounded_escaped_ranked_and_reflects_updates_and_soft_deletes(tmp_db):
    core, _, _, _, first, _, story, _, _, _, _ = _fixture(tmp_db)
    tags = WorkbenchService(tmp_db)
    tags.create_tag({"name": "Launch", "namespace": "user", "tag_type": "user"})
    tags.add_note("story", story["id"], "Hypothesis: the launch date may move.", note_type="hypothesis")
    search = SearchService(tmp_db)

    result = search.search("launch", page=1, page_size=2)
    assert result["total"] >= 4
    assert len(result["items"]) == 2
    assert result["items"] == search.search("launch", page=1, page_size=2)["items"]
    assert any(item["entity_type"] == "evidence" for item in search.search("100 users")["items"])
    assert search.search('launch" OR *')["total"] == 0

    core.update_document(first["id"], {"title": "Renamed document"})
    assert search.search("Atlas launch on", entity_types=["document"])["total"] == 0
    core.delete_story(story["id"])
    assert search.search("Atlas launches", entity_types=["story"])["total"] == 0

    with pytest.raises(DomainValidation):
        search.search("launch", page_size=201)


def test_comparison_links_shared_unique_conflicting_values_primary_use_and_lineage(tmp_db):
    _, _, official, _, first, second, story, first_span, second_span, shared, conflicting = _fixture(tmp_db)
    WorkbenchService(tmp_db).link_lineage(
        second["id"], first["id"], "rewritten_from", confidence=0.8, rationale="same launch"
    )
    comparison = ComparisonService(tmp_db).compare([first["id"], second["id"]])

    assert comparison["document_ids"] == [first["id"], second["id"]]
    assert shared["id"] in comparison["shared_claims"][0]["claim_ids"]
    assert comparison["unique_claims"]
    assert comparison["contradictions"]
    assert {first_span["id"], second_span["id"]} <= set(comparison["contradictions"][0]["evidence_span_ids"])
    assert any(item["document_id"] == first["id"] and item["is_primary"] for item in comparison["primary_source_use"])
    assert comparison["lineage"][0]["relationship"] == "rewritten_from"
    assert comparison["dates_and_numbers"]["differences"]
    assert comparison["interpretations"]
    assert conflicting["id"] in comparison["contradictions"][0]["claim_ids"]


def test_subject_context_and_monitor_diagnostics_distinguish_no_change_from_failure(tmp_db):
    core, ledger, _, _, first, _, story, first_span, _, _, _ = _fixture(tmp_db)
    subject = core.create_subject(
        {"canonical_name": "Atlas", "subject_type": "company", "description": "Launch subject"}
    )
    with storage.connect(tmp_db) as conn:
        conn.execute("INSERT INTO story_subjects(story_id, subject_id) VALUES (?, ?)", (story["id"], subject["id"]))
        conn.execute(
            "INSERT INTO acquisition_events(id, source_id, document_id, channel, request_url, outcome, observed_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("acq-failed", first["source_id"], first["id"], "direct_http", first["canonical_url"], "failed", utc_now(), utc_now()),
        )
    policy = MonitoringPolicyService(tmp_db).create(
        {
            "name": "Atlas monitor",
            "allowed_channels": ["direct_http"],
            "base_cadence_seconds": 60,
            "min_cadence_seconds": 30,
            "max_cadence_seconds": 300,
        }
    )
    monitor = MonitorService(tmp_db).create(
        {"target_type": "story", "target_id": story["id"], "policy_id": policy["id"]}
    )
    MonitorService(tmp_db).record_activity(monitor["id"], "no_change")
    MonitorService(tmp_db).record_activity(monitor["id"], "error", error_code="timeout")

    workbench = WorkbenchService(tmp_db)
    context = workbench.subject_page(subject["id"])
    assert context["subject"]["canonical_name"] == "Atlas"
    assert context["timeline"]
    assert context["historical_context"]["evidence"]
    assert first_span["id"] in {item["id"] for item in context["historical_context"]["evidence"]}

    diagnostics = DiagnosticsService(tmp_db).monitor(monitor["id"])
    assert diagnostics["coverage"]["no_meaningful_change"] == 1
    assert diagnostics["coverage"]["failed_processing"] == 1
    assert diagnostics["coverage"]["latest_status"] == "failed_processing"
    health = DiagnosticsService(tmp_db).health()
    assert health["status"] in {"healthy", "degraded"}
    assert health["counts"]["failed_acquisitions"] == 1


def test_phase13_api_is_authenticated_and_mutations_remain_csrf_protected(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    client = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))
    assert client.get("/api/v1/search?q=launch").status_code == 401
    assert client.post("/api/v1/auth/setup", json={"username": "admin", "password": "a-long-test-password-12345"}).status_code == 201
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "a-long-test-password-12345"}).status_code == 200
    assert client.get("/api/v1/diagnostics/health").status_code == 200
    assert client.get("/api/v1/search?q=launch").status_code == 200
    assert client.post(
        "/api/v1/workbench/notes",
        json={"object_type": "story", "object_id": "missing", "body": "note"},
    ).status_code == 403
