from __future__ import annotations

import pytest

from newsroom.attention import AttentionService
from newsroom.coverage import CoverageService
from newsroom.domain import CoreService, DomainNotFound
from newsroom.evidence import EvidenceService
from newsroom.hypotheses import HypothesisService
from newsroom.migrations import apply_migrations
from newsroom.research_questions import ResearchQuestionService


def test_attention_refresh_ranks_incomplete_coverage_and_preserves_feedback(tmp_db):
    apply_migrations(tmp_db)
    coverage = CoverageService(tmp_db)
    run = coverage.create_run(
        "story",
        "story-1",
        "2026-08-24T00:00:00Z",
        "2026-08-24T23:59:59Z",
        expected_channels=[{"key": "official", "channel_type": "official", "required": True}],
    )
    coverage.complete(run["id"])
    attention = AttentionService(tmp_db)
    refreshed = attention.refresh()
    assert refreshed["created_count"] == 1
    item = refreshed["items"][0]
    assert item["reason_code"] == "coverage_gap"
    assert item["state"] == "open"
    assert attention.feedback(item["id"], "not_important", actor="tester")["state"] == "dismissed"
    assert attention.refresh()["created_count"] == 0


def test_hypotheses_link_claims_without_mutating_canonical_claim_state(tmp_db):
    apply_migrations(tmp_db)
    question = ResearchQuestionService(tmp_db).create({"question": "What explains the event?"})
    story = CoreService(tmp_db).create_story({"headline": "Hypothesis story"})
    claim = EvidenceService(tmp_db).create_claim(story["id"], {"proposition": "The event occurred"})
    hypotheses = HypothesisService(tmp_db)
    hypothesis = hypotheses.create(question["id"], "The event was caused by factor A")
    linked = hypotheses.link_claim(hypothesis["id"], claim["id"], "supports")
    assert linked["claim_id"] == claim["id"]
    assert EvidenceService(tmp_db).get_claim(claim["id"])["state"] == "pending"
    assert hypotheses.get(hypothesis["id"])["claims"][0]["claim_id"] == claim["id"]
    with pytest.raises(DomainNotFound):
        hypotheses.link_claim(hypothesis["id"], "missing-claim", "supports")
