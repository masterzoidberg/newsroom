from __future__ import annotations

from newsroom.domain import CoreService
from newsroom.evidence import EvidenceService
from newsroom.migrations import apply_migrations
from newsroom.source_robustness import SourceRobustnessService
from newsroom.story_evolution import StoryEvolutionService


def _evidence(db, story_id, source_name, slug, title, excerpt):
    core = CoreService(db)
    source = core.create_source({"name": source_name, "slug": slug})
    document = core.create_document({"source_id": source["id"], "canonical_url": f"https://{slug}.test/item", "title": title})
    version = EvidenceService(db).create_document_version(document["id"], {"content_hash": f"hash-{slug}", "content_kind": "excerpt"})
    span = EvidenceService(db).create_evidence_span(version["id"], {"excerpt": excerpt})
    return source, document, span


def test_dependency_rebuild_groups_derivative_documents_without_calling_sources_independent(tmp_db):
    apply_migrations(tmp_db)
    story = CoreService(tmp_db).create_story({"headline": "Dependency story"})
    claim = EvidenceService(tmp_db).create_claim(story["id"], {"proposition": "The event occurred"})
    _, primary, primary_span = _evidence(tmp_db, story["id"], "Primary", "primary", "Primary", "The event occurred")
    _, syndicated, syndicated_span = _evidence(tmp_db, story["id"], "Syndicated", "syndicated", "Syndicated", "The event occurred")
    _, independent, independent_span = _evidence(tmp_db, story["id"], "Independent", "independent", "Independent", "The event occurred")
    evidence = EvidenceService(tmp_db)
    for span in (primary_span, syndicated_span, independent_span):
        evidence.link_claim_evidence(claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"})
    evidence.set_claim_state(claim["id"], "supported", "test")
    evidence.accept_claim(claim["id"])
    StoryEvolutionService(tmp_db).link_lineage(syndicated["id"], primary["id"], "syndicated_from", confidence=1.0, rationale="wire copy")

    robustness = SourceRobustnessService(tmp_db)
    families = robustness.rebuild_evidence_families([primary["id"], syndicated["id"], independent["id"]])
    assert len(families) == 2
    summary = robustness.evidence_summary("claim", claim["id"])
    assert summary["distinct_source_count"] == 3
    assert summary["evidence_family_count"] == 2
    assert summary["lineage_group_count"] == 2


def test_fragility_counterfactual_is_non_mutating_and_explains_family_dependence(tmp_db):
    apply_migrations(tmp_db)
    story = CoreService(tmp_db).create_story({"headline": "Fragile story"})
    claim = EvidenceService(tmp_db).create_claim(story["id"], {"proposition": "The event occurred"})
    _, primary, primary_span = _evidence(tmp_db, story["id"], "Primary", "primary2", "Primary", "The event occurred")
    _, syndicated, syndicated_span = _evidence(tmp_db, story["id"], "Syndicated", "syndicated2", "Syndicated", "The event occurred")
    _, independent, independent_span = _evidence(tmp_db, story["id"], "Independent", "independent2", "Independent", "The event occurred")
    evidence = EvidenceService(tmp_db)
    for span in (primary_span, syndicated_span, independent_span):
        evidence.link_claim_evidence(claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"})
    evidence.set_claim_state(claim["id"], "supported", "test")
    evidence.accept_claim(claim["id"])
    StoryEvolutionService(tmp_db).link_lineage(syndicated["id"], primary["id"], "syndicated_from")
    robustness = SourceRobustnessService(tmp_db)
    robustness.rebuild_evidence_families([primary["id"], syndicated["id"], independent["id"]])
    analysis = robustness.analyze_fragility("claim", claim["id"])
    family_id = analysis["support_paths"][0]["family_ids"][0]
    before = evidence.get_claim(claim["id"])
    counterfactual = robustness.counterfactual("claim", claim["id"], [family_id])
    after = evidence.get_claim(claim["id"])
    assert counterfactual["changed"] is True
    assert claim["id"] in counterfactual["surviving_claim_ids"]
    assert counterfactual["dropped_claim_ids"] == []
    assert before["state"] == after["state"] == "supported"
