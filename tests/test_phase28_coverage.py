from __future__ import annotations

import sqlite3

from newsroom.ask import AskService
from newsroom.domain import CoreService
from newsroom.migrations import apply_migrations
from newsroom.research_questions import ResearchQuestionService


REMOVED_PHASE28_TABLES = {
    "coverage_runs",
    "coverage_items",
    "coverage_summaries",
    "evidence_families",
    "evidence_family_members",
    "evidence_fragility_analyses",
    "blind_spot_suggestions",
    "attention_items",
    "attention_feedback",
    "hypothesis_gaps",
}


def test_phase28_derived_persistence_is_removed_from_schema(tmp_db):
    apply_migrations(tmp_db)
    conn = sqlite3.connect(tmp_db)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert not REMOVED_PHASE28_TABLES & tables
        assert "attention_decisions" in tables
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_ask_refuses_when_research_context_has_no_grounding_evidence(tmp_db):
    apply_migrations(tmp_db)
    question = ResearchQuestionService(tmp_db).create({"question": "What explains the event?"})
    ask = AskService(tmp_db)
    conversation = ask.create_conversation(scope_type="question", scope_id=question["id"])

    result = ask.ask(conversation["id"], "What explains the event?")

    assert result["status"] == "refused"
    assert result["refusal_code"] == "insufficient_evidence"
    assert result["retrieval"]["grounding_evidence_count"] == 0


def test_story_context_without_evidence_does_not_create_a_grounded_answer(tmp_db):
    apply_migrations(tmp_db)
    story = CoreService(tmp_db).create_story({"headline": "A story without evidence"})
    ask = AskService(tmp_db)
    conversation = ask.create_conversation(scope_type="story", scope_id=story["id"])

    result = ask.ask(conversation["id"], "What happened in the story?")

    assert result["status"] == "refused"
    assert result["refusal_code"] == "insufficient_evidence"
