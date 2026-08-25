from __future__ import annotations

import pytest

from newsroom.domain import CoreService
from newsroom.evidence import EvidenceService
from newsroom.migrations import apply_migrations
from newsroom.source_robustness import SourceRobustnessService
from newsroom.story_evolution import StoryEvolutionService


def _evidence(db, source_name, slug, title, excerpt):
    core = CoreService(db)
    source = core.create_source({"name": source_name, "slug": slug})
    document = core.create_document({"source_id": source["id"], "canonical_url": f"https://{slug}.test/item", "title": title})
    version = EvidenceService(db).create_document_version(document["id"], {"content_hash": f"hash-{slug}", "content_kind": "excerpt"})
    span = EvidenceService(db).create_evidence_span(version["id"], {"excerpt": excerpt})
    return source, document, span


def test_dependency_groups_are_current_and_do_not_call_sources_independent(tmp_db):
    apply_migrations(tmp_db)
    story = CoreService(tmp_db).create_story({"headline": "Dependency story"})
    claim = EvidenceService(tmp_db).create_claim(story["id"], {"proposition": "The event occurred"})
    _, primary, primary_span = _evidence(tmp_db, "Primary", "primary", "Primary", "The event occurred")
    _, syndicated, syndicated_span = _evidence(tmp_db, "Syndicated", "syndicated", "Syndicated", "The event occurred")
    _, independent, independent_span = _evidence(tmp_db, "Independent", "independent", "Independent", "The event occurred")
    evidence = EvidenceService(tmp_db)
    for span in (primary_span, syndicated_span, independent_span):
        evidence.link_claim_evidence(claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"})
    evidence.set_claim_state(claim["id"], "supported", "test")
    evidence.accept_claim(claim["id"])
    StoryEvolutionService(tmp_db).link_lineage(syndicated["id"], primary["id"], "syndicated_from", confidence=1.0, rationale="wire copy")

    summary = SourceRobustnessService(tmp_db).evidence_summary("claim", claim["id"])

    assert summary["distinct_source_count"] == 3
    assert summary["dependency_group_count"] == 2
    assert summary["largest_group_share"] == pytest.approx(2 / 3, abs=1e-6)
    assert all("independent" not in str(item).casefold() for item in summary["dependency_groups"])


def test_counterfactual_excludes_current_source_without_mutating_canonical_state(tmp_db):
    apply_migrations(tmp_db)
    story = CoreService(tmp_db).create_story({"headline": "Counterfactual story"})
    claim = EvidenceService(tmp_db).create_claim(story["id"], {"proposition": "The event occurred"})
    primary, _, primary_span = _evidence(tmp_db, "Primary", "primary2", "Primary", "The event occurred")
    independent, _, independent_span = _evidence(tmp_db, "Independent", "independent2", "Independent", "The event occurred")
    evidence = EvidenceService(tmp_db)
    for span in (primary_span, independent_span):
        evidence.link_claim_evidence(claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"})
    evidence.set_claim_state(claim["id"], "supported", "test")
    evidence.accept_claim(claim["id"])
    robustness = SourceRobustnessService(tmp_db)
    before = evidence.get_claim(claim["id"])
    result = robustness.counterfactual("claim", claim["id"], exclude_source_ids=[independent["id"]])
    after = evidence.get_claim(claim["id"])

    assert result["changed"] is True
    assert result["surviving_claim_ids"] == [claim["id"]]
    assert result["dropped_claim_ids"] == []
    assert before["state"] == after["state"] == "supported"
    assert "fragility_score" not in result
