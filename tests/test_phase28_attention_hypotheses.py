from __future__ import annotations

import json

import pytest

from newsroom.attention import AttentionService
from newsroom.domain import CoreService, DomainNotFound, new_id, utc_now
from newsroom.evidence import EvidenceService
from newsroom.hypotheses import HypothesisService
from newsroom.migrations import apply_migrations
from newsroom.research_questions import ResearchQuestionService
from newsroom import storage


def test_attention_computes_current_candidates_and_persists_only_decisions(tmp_db):
    apply_migrations(tmp_db)
    story = CoreService(tmp_db).create_story({"headline": "Alert story"})
    now = utc_now()
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            rule_id = new_id("alertrule")
            conn.execute(
                "INSERT INTO alert_rules(id, name, target_type, target_id, event_types_json, min_importance, browser_enabled, enabled, dedupe_window_seconds, timezone_name, created_at, updated_at) VALUES (?, 'Test', 'story', ?, '[]', 0, 0, 1, 0, 'UTC', ?, ?)",
                (rule_id, story["id"], now, now),
            )
            conn.execute(
                "INSERT INTO alerts(id, rule_id, story_id, event_type, title, body, importance_score, dedupe_key, cause_json, status, created_at) VALUES (?, ?, ?, 'correction', 'Correction', 'A correction', 0.9, ?, ?, 'unread', ?)",
                (new_id("alert"), rule_id, story["id"], new_id("dedupe"), json.dumps({"cause": "test"}), now),
            )
    finally:
        conn.close()

    attention = AttentionService(tmp_db)
    item = attention.list()["items"][0]
    assert item["reason_code"] == "correction"
    assert item["basis_fingerprint"]
    assert attention.decide(item["id"], "not_useful", actor="tester")["decision"]["action"] == "not_useful"
    assert attention.list()["items"] == []


def test_hypotheses_link_claims_and_create_canonical_discriminating_gap(tmp_db):
    apply_migrations(tmp_db)
    question = ResearchQuestionService(tmp_db).create({"question": "What explains the event?"})
    story = CoreService(tmp_db).create_story({"headline": "Hypothesis story"})
    claim = EvidenceService(tmp_db).create_claim(story["id"], {"proposition": "The event occurred"})
    hypotheses = HypothesisService(tmp_db)
    hypothesis = hypotheses.create(question["id"], "The event was caused by factor A")
    alternative = hypotheses.create(question["id"], "The event was caused by factor B")
    linked = hypotheses.link_claim(hypothesis["id"], claim["id"], "supports")
    hypotheses.link_claim(alternative["id"], claim["id"], "contradicts")
    gap = hypotheses.add_gap(hypothesis["id"], "Find an observation that distinguishes factor A from factor B")

    assert linked["claim_id"] == claim["id"]
    assert gap["gap_type"] == "discriminating"
    assert gap["origin_hypothesis_id"] == hypothesis["id"]
    assert hypotheses.get(hypothesis["id"])["gaps"][0]["id"] == gap["id"]
    comparison = hypotheses.compare(hypothesis["id"], alternative["id"])
    assert comparison["shared_claim_ids"] == [claim["id"]]
    assert comparison["relationship_conflicts"][0]["left"] == "supports"
    assert hypotheses.review(hypothesis["id"], "approved", actor="tester")["status"] == "approved"
    assert EvidenceService(tmp_db).get_claim(claim["id"])["state"] == "pending"
    with pytest.raises(DomainNotFound):
        hypotheses.link_claim(hypothesis["id"], "missing-claim", "supports")
