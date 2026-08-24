from __future__ import annotations

import json
import pytest

from newsroom.domain import CoreService, DomainConflict
from newsroom.evidence import EvidenceService
from newsroom.knowledge import KnowledgeService
from newsroom.migrations import apply_migrations
from newsroom.research_questions import ResearchQuestionService
from newsroom.workbench import SearchService
from newsroom.ask import AskService
from newsroom.integrity import check_database
from newsroom.operations import export_logical
from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from fastapi.testclient import TestClient


def _ledger_fixture(db_path):
    core = CoreService(db_path)
    source = core.create_source(
        {
            "name": "Knowledge Source",
            "slug": "knowledge-source",
            "source_kind": "official",
            "default_quality": "primary",
            "homepage_url": "https://knowledge.example.test",
        }
    )
    document = core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": "https://knowledge.example.test/report",
            "title": "Knowledge report",
        }
    )
    version = EvidenceService(db_path).create_document_version(
        document["id"], {"content_hash": "knowledge-content", "content_kind": "excerpt"}
    )
    return core, source, document, version


def test_entity_alias_resolution_is_idempotent_and_conservative(tmp_db):
    apply_migrations(tmp_db)
    service = KnowledgeService(tmp_db)

    entity = service.create_entity(
        {
            "canonical_name": "All-domain Anomaly Resolution Office",
            "entity_type": "agency",
            "aliases": [{"alias": "AARO", "alias_type": "acronym"}],
        }
    )
    duplicate = service.create_entity(
        {
            "canonical_name": "All-domain Anomaly Resolution Office",
            "entity_type": "agency",
        }
    )

    assert duplicate["id"] == entity["id"]
    assert service.resolve_entity("AARO")["entity"]["id"] == entity["id"]
    assert service.resolve_entity("AARO")["match_reason"] == "exact_alias"

    first = service.create_entity({"canonical_name": "Jordan", "entity_type": "person"})
    second = service.create_entity({"canonical_name": "Jordan Organization", "entity_type": "organization"})
    service.add_alias(first["id"], {"alias": "J", "alias_type": "abbreviation"})
    service.add_alias(second["id"], {"alias": "J", "alias_type": "abbreviation"})
    ambiguous = service.resolve_entity("J")
    assert ambiguous["status"] == "ambiguous"
    assert {item["id"] for item in ambiguous["candidates"]} == {first["id"], second["id"]}


def test_mentions_are_not_evidence_and_claim_relationships_are_provenance_bound(tmp_db):
    apply_migrations(tmp_db)
    core, _source, _document, version = _ledger_fixture(tmp_db)
    story = core.create_story({"headline": "Knowledge story"})
    ledger = EvidenceService(tmp_db)
    span = ledger.create_evidence_span(version["id"], {"excerpt": "AARO published a report."})
    claim = ledger.create_claim(story["id"], {"proposition": "AARO published a report."})
    ledger.link_claim_evidence(claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"})

    service = KnowledgeService(tmp_db)
    entity = service.create_entity({"canonical_name": "AARO", "entity_type": "agency"})
    mention = service.record_mention(
        {
            "entity_id": entity["id"],
            "mention_text": "AARO",
            "source_type": "document_version",
            "source_id": version["id"],
            "resolution_method": "deterministic",
        }
    )
    service.link_claim_entity(claim["id"], entity["id"], role="subject", mention_id=mention["id"])

    detail = service.get_entity(entity["id"])
    assert detail["claims"][0]["id"] == claim["id"]
    assert detail["claims"][0]["evidence"][0]["id"] == span["id"]
    assert detail["mentions"][0]["id"] == mention["id"]
    assert not any(item["id"] == mention["id"] for item in detail["evidence"])


def test_entity_aliases_are_searchable_through_existing_fts_substrate(tmp_db):
    apply_migrations(tmp_db)
    service = KnowledgeService(tmp_db)
    entity = service.create_entity(
        {
            "canonical_name": "All-domain Anomaly Resolution Office",
            "entity_type": "agency",
            "aliases": [{"alias": "AARO", "alias_type": "acronym"}],
        }
    )

    results = SearchService(tmp_db).search("AARO", entity_types=["entity"])

    assert results["items"][0]["entity_id"] == entity["id"]
    assert results["items"][0]["match_reason"] == "exact_alias"


def test_shared_typed_retrieval_returns_bounded_stable_candidates(tmp_db):
    apply_migrations(tmp_db)
    service = KnowledgeService(tmp_db)
    entity = service.create_entity(
        {
            "canonical_name": "All-domain Anomaly Resolution Office",
            "entity_type": "agency",
            "aliases": [{"alias": "AARO", "alias_type": "acronym"}],
        }
    )

    result = SearchService(tmp_db).retrieve_typed("What does AARO know?", entity_types=["entity"], max_results=5)

    assert result["candidate_count"] == 1
    assert result["items"][0]["entity_id"] == entity["id"]
    assert result["items"][0]["entity_type"] == "entity"
    assert result["items"][0]["match_reason"] == "exact_alias"
    assert result["items"][0]["rank"] == 1


def test_question_entity_relationship_uses_phase25_question_and_gap_records(tmp_db):
    apply_migrations(tmp_db)
    question = ResearchQuestionService(tmp_db).create({"question": "What did AARO publish?"})
    gap = question["gaps"][0]
    entity = KnowledgeService(tmp_db).create_entity({"canonical_name": "AARO", "entity_type": "agency"})

    service = KnowledgeService(tmp_db)
    service.link_research_question_entity(question["id"], entity["id"])
    service.link_gap_entity(gap["id"], entity["id"])

    detail = service.get_entity(entity["id"])
    assert detail["research_questions"][0]["id"] == question["id"]
    assert detail["gaps"][0]["id"] == gap["id"]
    refreshed = ResearchQuestionService(tmp_db).get(question["id"])
    assert refreshed["status"] == "open"
    assert refreshed["assessment_state"] == "open"


def test_smart_tags_are_deduplicated_and_assignments_are_cross_object_and_idempotent(tmp_db):
    apply_migrations(tmp_db)
    core, _source, _document, version = _ledger_fixture(tmp_db)
    story = core.create_story({"headline": "Tagged story"})
    claim = EvidenceService(tmp_db).create_claim(story["id"], {"proposition": "AARO published a report."})
    entity = KnowledgeService(tmp_db).create_entity({"canonical_name": "AARO", "entity_type": "agency"})
    service = KnowledgeService(tmp_db)

    first = service.create_tag({"name": "Official", "namespace": "knowledge", "tag_type": "smart"})
    second = service.create_tag({"name": " official ", "namespace": "knowledge", "tag_type": "smart"})
    assignment = service.assign_tag(first["id"], "entity", entity["id"], origin="deterministic", reason="entity type")
    repeated = service.assign_tag(first["id"], "entity", entity["id"], origin="deterministic", reason="entity type")
    service.assign_tag(first["id"], "claim", claim["id"], origin="deterministic", reason="claim context")

    assert second["id"] == first["id"]
    assert repeated["id"] == assignment["id"]
    assert service.get_entity(entity["id"])["tags"][0]["id"] == first["id"]
    tagged = SearchService(tmp_db).search("AARO", tag_id=first["id"])
    assert any(item["entity_type"] == "entity" and item["entity_id"] == entity["id"] for item in tagged["items"])


def test_smart_tag_backfill_is_bounded_durable_and_restart_safe(tmp_db):
    apply_migrations(tmp_db)
    service = KnowledgeService(tmp_db)
    entity = service.create_entity({"canonical_name": "AARO", "entity_type": "agency"})
    run = service.start_backfill("smart_tags", row_limit=10, batch_size=1)
    completed = service.run_backfill(run["id"])
    repeated = service.run_backfill(run["id"])

    assert completed["status"] == "completed"
    assert completed["processed"] == 1
    assert repeated == completed
    assert service.get_entity(entity["id"])["tags"][0]["assignment_origin"] == "deterministic"


def test_entity_and_tag_api_exposes_bounded_pivots(tmp_path):
    client = TestClient(create_app(config=RuntimeConfig.for_environment("dev", root=tmp_path / "dev"), frontend_dist=tmp_path / "missing-dist"))
    assert client.post("/api/v1/auth/setup", json={"username": "admin", "password": "a-long-test-password-12345"}).status_code == 201
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "a-long-test-password-12345"}).status_code == 200
    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
    created = client.post(
        "/api/v1/entities",
        headers=headers,
        json={"canonical_name": "AARO", "entity_type": "agency", "aliases": [{"alias": "All-domain Anomaly Resolution Office", "alias_type": "expanded_name"}]},
    )
    assert created.status_code == 201, created.text
    entity = created.json()
    tag = client.post("/api/v1/tags", headers=headers, json={"name": "Official", "namespace": "knowledge", "tag_type": "smart"})
    assert tag.status_code == 201, tag.text
    assigned = client.post(
        f"/api/v1/tags/{tag.json()['id']}/assignments",
        headers=headers,
        json={"object_type": "entity", "object_id": entity["id"], "origin": "user", "reason": "reviewed"},
    )
    assert assigned.status_code == 201, assigned.text
    detail = client.get(f"/api/v1/entities/{entity['id']}")
    assert detail.status_code == 200
    assert detail.json()["aliases"][0]["alias"] == "All-domain Anomaly Resolution Office"
    assert detail.json()["tags"][0]["id"] == tag.json()["id"]


def test_shared_retrieval_grounds_entity_ask_and_preserves_question_lifecycle(tmp_db):
    apply_migrations(tmp_db)
    core, _source, _document, version = _ledger_fixture(tmp_db)
    story = core.create_story({"headline": "AARO story"})
    ledger = EvidenceService(tmp_db)
    span = ledger.create_evidence_span(version["id"], {"excerpt": "AARO published a report."})
    claim = ledger.create_claim(story["id"], {"proposition": "AARO published a report.", "importance": "major"})
    ledger.link_claim_evidence(claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"})
    ledger.set_claim_state(claim["id"], "supported", "controlled Phase 26 fixture")
    entity = KnowledgeService(tmp_db).create_entity({"canonical_name": "AARO", "entity_type": "agency", "aliases": [{"alias": "All-domain Anomaly Resolution Office", "alias_type": "expanded_name"}]})
    knowledge = KnowledgeService(tmp_db)
    knowledge.link_claim_entity(claim["id"], entity["id"], role="subject")
    question = ResearchQuestionService(tmp_db).create({"question": "What did AARO publish?"})
    knowledge.link_research_question_entity(question["id"], entity["id"])

    ask = AskService(tmp_db)
    conversation = ask.create_conversation(scope_type="entity", scope_id=entity["id"])
    result = ask.ask(conversation["id"], "What does AARO know?")

    assert any(item["object_id"] == claim["id"] for item in result["citations"])
    assert any(item["object_id"] == span["id"] for item in result["citations"])
    assert any(item["object_type"] == "source" for item in result["citations"])
    assert f"claim:{claim['id']}" in result["retrieval"]["packet_ids"]
    assert "lifecycle: open" in result["answer"]
    assert question["id"] in {item["object_id"] for item in result["citations"] if item["object_type"] == "question"}

    with pytest.raises(DomainConflict):
        ask._resolve_citation(None, {"object_type": "claim", "object_id": "cl_outside"}, packet_ids={f"claim:{claim['id']}"})


def test_phase26_logical_export_reconstructs_knowledge_path_and_integrity(tmp_db, tmp_path):
    apply_migrations(tmp_db)
    core, _source, document, version = _ledger_fixture(tmp_db)
    story = core.create_story({"headline": "Export story"})
    ledger = EvidenceService(tmp_db)
    span = ledger.create_evidence_span(version["id"], {"excerpt": "AARO is named in the export fixture."})
    claim = ledger.create_claim(story["id"], {"proposition": "AARO is named in the export fixture."})
    ledger.link_claim_evidence(claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"})
    entity = KnowledgeService(tmp_db).create_entity({"canonical_name": "AARO", "entity_type": "agency", "aliases": [{"alias": "AARO Agency", "alias_type": "alternate_name"}]})
    knowledge = KnowledgeService(tmp_db)
    knowledge.link_claim_entity(claim["id"], entity["id"], role="subject")
    question = ResearchQuestionService(tmp_db).create({"question": "Is AARO named in the fixture?"})
    knowledge.link_research_question_entity(question["id"], entity["id"])
    output = export_logical(tmp_db, tmp_path / "phase26.jsonl")
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    tables = {row.get("table") for row in rows if row.get("table")}
    assert {"entities", "entity_aliases", "claim_entities", "research_question_entities", "claims", "claim_evidence", "evidence_spans", "documents", "sources"} <= tables
    assert not {"search_records", "search_index_meta"} & tables
    assert check_database(tmp_db).ok


def test_ask_research_bridge_queues_the_existing_phase25_task_service(tmp_path):
    client = TestClient(create_app(config=RuntimeConfig.for_environment("dev", root=tmp_path / "dev"), frontend_dist=tmp_path / "missing-dist"))
    assert client.post("/api/v1/auth/setup", json={"username": "admin", "password": "a-long-test-password-12345"}).status_code == 201
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "a-long-test-password-12345"}).status_code == 200
    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
    question = client.post(
        "/api/v1/research-questions",
        headers=headers,
        json={"question": "What controlled report remains unresolved?", "search_attempt_budget": 1, "query_budget": 1},
    )
    assert question.status_code == 201, question.text
    question_id = question.json()["id"]
    ask = client.post(
        "/api/v1/ask",
        headers=headers,
        json={"scope_type": "question", "scope_id": question_id, "prompt": "What controlled report remains unresolved?"},
    )
    assert ask.status_code == 201, ask.text
    option = ask.json()["retrieval"]["research_options"][0]
    bridged = client.post(f"/api/v1/ask/runs/{ask.json()['run_id']}/research", headers=headers, json={"gap_id": option["gap_id"]})
    assert bridged.status_code == 201, bridged.text
    assert bridged.json()["task_id"]
