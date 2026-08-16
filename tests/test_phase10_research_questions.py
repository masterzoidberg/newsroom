from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from newsroom import storage
from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.domain import CoreService, DomainConflict
from newsroom.evidence import EvidenceService
from newsroom.jobs import JobService
from newsroom.migrations import apply_migrations
from newsroom.research_questions import ResearchQuestionService


PASSWORD = "a-long-test-password-12345"


def _evidence_fixture(db_path):
    core = CoreService(db_path)
    source = core.create_source(
        {
            "name": "Local Outlet",
            "slug": "local-outlet",
            "source_kind": "web",
            "default_quality": "unknown",
        }
    )
    document = core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": "https://local.test/story",
            "title": "A developing story",
        }
    )
    story = core.create_story({"headline": "A developing story"})
    ledger = EvidenceService(db_path)
    version = ledger.create_document_version(
        document["id"], {"content_hash": "phase10-v1", "content_kind": "excerpt"}
    )
    span = ledger.create_evidence_span(
        version["id"], {"excerpt": "The outlet reported an unresolved detail."}
    )
    claim = ledger.create_claim(
        story["id"],
        {"proposition": "The unresolved detail is true", "importance": "major"},
    )
    return core, ledger, story, claim, span


def test_research_question_lifecycle_preserves_history_and_links(tmp_db):
    apply_migrations(tmp_db)
    _, ledger, story, claim, span = _evidence_fixture(tmp_db)
    service = ResearchQuestionService(tmp_db)

    question = service.create(
        {
            "question": "Can the unresolved detail be confirmed by a primary source?",
            "origin_type": "claim",
            "origin_id": claim["id"],
            "priority": "high",
            "search_attempt_budget": 2,
            "query_budget": 3,
            "next_attempt_at": "2026-08-17T12:00:00Z",
        }
    )
    service.link_claim(question["id"], claim["id"], "resolves")
    service.link_evidence(question["id"], span["id"], "contextualizes")
    resolved = service.resolve(question["id"], "Primary source confirmed the detail.")
    reopened = service.reopen(question["id"], "A later correction reopened the question.")

    assert resolved["status"] == "resolved"
    assert reopened["status"] == "open"
    current = service.get(question["id"])
    assert current["claims"][0]["claim_id"] == claim["id"]
    assert current["evidence"][0]["evidence_span_id"] == span["id"]
    assert [row["to_status"] for row in current["history"]] == [
        "open",
        "resolved",
        "open",
    ]
    assert current["resolution_note"] == "Primary source confirmed the detail."

    conn = storage.connect(tmp_db)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(
                "UPDATE research_question_claims SET relationship = 'supports' WHERE question_id = ?",
                (question["id"],),
            )
    finally:
        conn.close()


def test_gap_detection_derives_question_search_and_source_suggestions_from_ledger(tmp_db):
    apply_migrations(tmp_db)
    _, ledger, story, claim, _ = _evidence_fixture(tmp_db)
    ledger.set_claim_state(claim["id"], "unsubstantiated", "support is not sufficient")
    service = ResearchQuestionService(tmp_db)

    suggestions = service.detect_gaps(claim_id=claim["id"])

    assert {item["suggestion_type"] for item in suggestions} == {"question", "search", "source"}
    assert {item["gap_type"] for item in suggestions} >= {"unsubstantiated_claim", "missing_primary_source"}
    assert all(item["rationale"] and item["expected_information_value"] > 0 for item in suggestions)
    assert all(item["origin_id"] == claim["id"] for item in suggestions)
    assert service.detect_gaps(story_id=story["id"])
    assert service.list_suggestions(origin_id=claim["id"])["total"] == len(suggestions)


def test_user_hypotheses_are_notes_and_never_claims(tmp_db):
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = service.create(
        {
            "question": "What should be checked next?",
            "origin_type": "user",
            "priority": "normal",
        }
    )

    note = service.add_note(
        question["id"],
        "Hypothesis: the official release may contain the missing date.",
        note_type="hypothesis",
    )

    assert note["note_type"] == "hypothesis"
    assert service.get(question["id"])["notes"] == [note]
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0
    finally:
        conn.close()


def test_manual_pursuit_consumes_attempt_query_and_cost_budgets(tmp_db):
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = service.create(
        {
            "question": "Find one confirming source.",
            "origin_type": "user",
            "search_attempt_budget": 1,
            "query_budget": 2,
            "paid_budget_usd": 0.25,
        }
    )

    job = service.pursue(
        question["id"],
        mode="manual",
        query_units=1,
        estimated_cost_usd=0.10,
        query="confirming source",
    )
    assert job["research_question_id"] == question["id"]
    assert job["max_attempts"] == 1
    assert service.get(question["id"])["attempts_used"] == 1

    with pytest.raises(DomainConflict, match="attempt budget"):
        service.pursue(question["id"], mode="manual", query_units=1)
    assert JobService(tmp_db).list()["total"] == 1


def test_policy_pursuit_and_query_cost_limits_are_bounded(tmp_db):
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    due = service.create(
        {
            "question": "Run the scheduled confirmation check.",
            "origin_type": "user",
            "search_attempt_budget": 1,
            "next_attempt_at": "2026-08-16T12:00:00Z",
        }
    )
    scheduled = service.pursue_due(now="2026-08-16T12:00:00Z", limit=1)
    assert scheduled["scheduled_count"] == 1
    assert JobService(tmp_db).get(scheduled["job_ids"][0])["research_question_id"] == due["id"]

    limited = service.create(
        {
            "question": "Use no more than one query or ten cents.",
            "origin_type": "user",
            "search_attempt_budget": 2,
            "query_budget": 1,
            "paid_budget_usd": 0.10,
        }
    )
    service.pursue(limited["id"], query_units=1, estimated_cost_usd=0.10)
    with pytest.raises(DomainConflict, match="query budget"):
        service.pursue(limited["id"], query_units=1)


def test_contradiction_and_weak_independence_are_separate_gap_signals(tmp_db):
    apply_migrations(tmp_db)
    core, ledger, story, claim, span = _evidence_fixture(tmp_db)
    second_source = core.create_source(
        {"name": "Second Outlet", "slug": "second-outlet", "default_quality": "low"}
    )
    second_document = core.create_document(
        {
            "source_id": second_source["id"],
            "canonical_url": "https://second.test/story",
            "title": "A conflicting story",
        }
    )
    second_version = ledger.create_document_version(
        second_document["id"], {"content_hash": "phase10-v2", "content_kind": "excerpt"}
    )
    contradicting_span = ledger.create_evidence_span(
        second_version["id"], {"excerpt": "The second outlet disputes the detail."}
    )
    ledger.link_claim_evidence(
        claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"}
    )
    ledger.link_claim_evidence(
        claim["id"], {"evidence_span_id": contradicting_span["id"], "relationship": "contradicts"}
    )
    ledger.set_claim_state(claim["id"], "disputed", "conflicting reports")

    gaps = ResearchQuestionService(tmp_db).detect_gaps(story_id=story["id"])
    gap_types = {item["gap_type"] for item in gaps}
    assert "contradiction" in gap_types
    assert "weak_independence" in gap_types


def test_research_question_api_is_authenticated_and_csrf_protected(tmp_path):
    client = TestClient(
        create_app(
            config=RuntimeConfig.for_environment("dev", root=tmp_path / "dev"),
            frontend_dist=tmp_path / "missing-dist",
        )
    )
    assert client.get("/api/v1/research-questions").status_code == 401
    assert client.post(
        "/api/v1/auth/setup", json={"username": "admin", "password": PASSWORD}
    ).status_code == 201
    assert client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}
    ).status_code == 200

    assert client.post(
        "/api/v1/research-questions",
        json={"question": "A protected question", "origin_type": "user"},
    ).status_code == 403
    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
    created = client.post(
        "/api/v1/research-questions",
        json={"question": "A protected question", "origin_type": "user"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert client.get("/api/v1/research-questions").json()["total"] == 1
