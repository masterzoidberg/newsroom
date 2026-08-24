from __future__ import annotations

from newsroom.domain import CoreService
from newsroom.evidence import EvidenceService
from newsroom.knowledge import KnowledgeService
from newsroom.migrations import apply_migrations
from newsroom.research_questions import ResearchQuestionService
from newsroom.workbench import SearchService


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
