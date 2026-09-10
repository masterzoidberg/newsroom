from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from newsroom.attention import AttentionService
from newsroom.app import create_app
from newsroom.ask import AskService
from newsroom.config import RuntimeConfig
from newsroom.domain import CoreService, DomainConflict, DomainNotFound, DomainValidation
from newsroom.evidence import EvidenceService
from newsroom.evals.semantic import SemanticCaseRunner
from newsroom.migrations import apply_migrations
from newsroom.research_questions import ResearchQuestionService
from newsroom.reports import LivingReportService
from newsroom.story_corrections import StoryCorrectionService
from newsroom.temporal import TemporalReadService
from newsroom.workbench import WorkbenchService


T1 = "2025-01-01T00:00:00Z"
T1_BEFORE = "2024-12-31T23:59:59Z"
T1_AFTER = "2025-01-01T00:00:01Z"
T2 = "2025-02-01T00:00:00Z"
T2_AFTER = "2025-02-01T00:00:01Z"
T3 = "2025-03-01T00:00:00Z"
T3_AFTER = "2025-03-01T00:00:01Z"
STORY_CORRECTION = "2099-02-01T00:00:00Z"
STORY_AFTER = "2099-02-01T00:00:01Z"
STORY_BEFORE = "2098-12-31T23:59:59Z"


def _seed_review_user(tmp_db, user_id: str = "usr-review") -> str:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        """
        INSERT INTO users(id, username, password_hash, password_algo, created_at, updated_at)
        VALUES (?, ?, 'test-hash', 'argon2id', ?, ?)
        """,
        (user_id, user_id, T1, T1),
    )
    conn.commit()
    conn.close()
    return user_id


def _seed_material_revision(tmp_db, *, known_at: str, published_at: str | None = None, suffix: str = ""):
    core = CoreService(tmp_db)
    evidence = EvidenceService(tmp_db)
    source = core.create_source({"name": f"Review Source {suffix}", "slug": f"review-source-{suffix or 'base'}"})
    document = core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": f"https://example.test/review-{suffix or 'base'}",
            "title": f"Review evidence {suffix}".strip(),
            "published_at": published_at,
        }
    )
    story = core.create_story({"headline": f"Review story {suffix}".strip()})
    version = evidence.create_document_version(
        document["id"],
        {"content_hash": (f"review-{suffix or 'base'}" * 32)[:64], "content_kind": "excerpt", "retrieved_at": known_at},
    )
    span = evidence.create_evidence_span(
        version["id"], {"excerpt": f"Evidence learned at {known_at}.", "created_at": known_at}
    )
    claim = evidence.create_claim(
        story["id"], {"proposition": f"Review proposition {suffix or 'base'}.", "created_at": known_at}
    )
    evidence.link_claim_evidence(
        claim["id"], {"evidence_span_id": span["id"], "relationship": "supports", "created_at": known_at}
    )
    evidence.set_claim_state(claim["id"], "supported", "review support", occurred_at=known_at)
    evidence.accept_claim(claim["id"], accepted_at=known_at)
    with patch("newsroom.evidence.utc_now", return_value=known_at):
        revision = evidence.create_story_revision(
            story["id"],
            {
                "headline": story["current_revision"]["headline"],
                "summary": f"Summary learned at {known_at}.",
                "why_it_matters": "This is evidence-backed material change.",
                "material_change": True,
                "claim_ids": [claim["id"]],
                "propositions": [{"text": claim["proposition"], "claim_ids": [claim["id"]]}],
            },
        )
    return {"story": story, "revision": revision["current_revision"], "document": document, "claim": claim}


def test_review_cursor_is_explicit_monotonic_and_reading_does_not_advance(tmp_db):
    apply_migrations(tmp_db)
    user_id = _seed_review_user(tmp_db)
    first = _seed_material_revision(tmp_db, known_at=T1, suffix="one")
    later = _seed_material_revision(tmp_db, known_at=T2, suffix="two")
    attention = AttentionService(tmp_db, clock=lambda: T2_AFTER)

    assert attention.review_cursor(user_id)["cursor"] is None
    first_read = attention.changes_since(user_id)
    assert {item["revision_id"] for item in first_read["items"]} == {
        first["revision"]["id"],
        later["revision"]["id"],
    }
    assert attention.review_cursor(user_id)["cursor"] is None

    advanced = attention.advance_review_cursor(user_id, T1)
    assert advanced["cursor"] == "2025-01-01T00:00:00.000000Z"
    assert [item["revision_id"] for item in attention.changes_since(user_id)["items"]] == [later["revision"]["id"]]
    assert attention.advance_review_cursor(user_id, T1) == advanced
    with pytest.raises(DomainConflict):
        attention.advance_review_cursor(user_id, T1_BEFORE)
    with pytest.raises(DomainValidation, match="future"):
        attention.advance_review_cursor(user_id, T3)


def test_review_changes_use_knowledge_time_and_include_late_arrivals(tmp_db):
    apply_migrations(tmp_db)
    user_id = _seed_review_user(tmp_db)
    late = _seed_material_revision(tmp_db, known_at=T2, published_at=T1, suffix="late")
    attention = AttentionService(tmp_db, clock=lambda: T3_AFTER)

    result = attention.changes_since(user_id, since=T1)

    assert [item["revision_id"] for item in result["items"]] == [late["revision"]["id"]]
    assert result["items"][0]["knowledge_at"] == "2025-02-01T00:00:00Z"
    assert result["items"][0]["publication_at"] == T1
    assert result["items"][0]["story"]["headline"] == "Review story late"
    assert result["items"][0]["evidence_backed"] is True


def test_review_cursor_normalizes_timezone_offsets_as_utc(tmp_db):
    apply_migrations(tmp_db)
    user_id = _seed_review_user(tmp_db)
    attention = AttentionService(tmp_db, clock=lambda: T2_AFTER)

    advanced = attention.advance_review_cursor(user_id, "2025-02-01T01:00:00+01:00")

    assert advanced["cursor"] == "2025-02-01T00:00:00.000000Z"
    assert attention.advance_review_cursor(user_id, T2) == advanced


def test_review_changes_paginate_stably_with_replay_and_high_water_mark(tmp_db):
    apply_migrations(tmp_db)
    user_id = _seed_review_user(tmp_db)
    seeded = [
        _seed_material_revision(tmp_db, known_at=T2, suffix=f"page-{index}")
        for index in range(5)
    ]
    attention = AttentionService(tmp_db, clock=lambda: T3_AFTER)

    page_one = attention.changes_since(user_id, since=T1_BEFORE, limit=2)
    replay = attention.changes_since(user_id, since=T1_BEFORE, limit=2)
    assert page_one == replay
    assert page_one["next_cursor"]

    _seed_material_revision(tmp_db, known_at=T3, suffix="new-after-page-one")
    page_two = attention.changes_since(user_id, limit=2, page_token=page_one["next_cursor"])
    page_three = attention.changes_since(user_id, limit=2, page_token=page_two["next_cursor"])
    ids = [item["revision_id"] for page in (page_one, page_two, page_three) for item in page["items"]]

    assert len(ids) == len(set(ids)) == len(seeded)
    assert set(ids) == {item["revision"]["id"] for item in seeded}
    assert page_three["next_cursor"] is None


def test_review_boundary_api_is_authenticated_csrf_protected_and_explicit(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    client = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))

    assert client.get("/api/v1/review-boundary").status_code == 401
    assert client.post(
        "/api/v1/auth/setup", json={"username": "admin", "password": "a-long-test-password-12345"}
    ).status_code == 201
    assert client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "a-long-test-password-12345"}
    ).status_code == 200
    assert client.get("/api/v1/review-boundary").json()["cursor"] is None
    assert client.put("/api/v1/review-boundary", json={"cursor": T1}).status_code == 403

    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
    advanced = client.put("/api/v1/review-boundary", json={"cursor": T1}, headers=headers)
    assert advanced.status_code == 200, advanced.text
    assert advanced.json()["cursor"] == "2025-01-01T00:00:00.000000Z"
    assert client.get("/api/v1/review-boundary/changes").status_code == 200


def _seed_temporal_claim(tmp_db, *, retract: bool = True):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    evidence = EvidenceService(tmp_db)
    source = core.create_source({"name": "Temporal Source", "slug": "temporal-source"})
    document = core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": "https://example.test/temporal",
            "title": "Temporal evidence",
        }
    )
    story = core.create_story({"headline": "Temporal story"})
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "UPDATE sources SET created_at = ?, updated_at = ? WHERE id = ?",
        (T1, T1, source["id"]),
    )
    conn.execute(
        "UPDATE documents SET created_at = ?, first_seen_at = ? WHERE id = ?",
        (T1, T1, document["id"]),
    )
    conn.execute(
        "UPDATE stories SET created_at = ?, updated_at = ? WHERE id = ?",
        (T1, T1, story["id"]),
    )
    conn.commit()
    conn.close()
    version = evidence.create_document_version(
        document["id"],
        {
            "content_hash": "a" * 64,
            "content_kind": "excerpt",
            "retrieved_at": T1,
        },
    )
    span = evidence.create_evidence_span(
        version["id"],
        {"excerpt": "The launch occurred in January.", "created_at": T1},
    )
    claim = evidence.create_claim(
        story["id"],
        {"proposition": "The launch occurred in January.", "created_at": T1},
    )
    evidence.link_claim_evidence(
        claim["id"],
        {"evidence_span_id": span["id"], "relationship": "supports", "created_at": T1},
    )
    evidence.set_claim_state(claim["id"], "supported", "initial support", occurred_at=T1)
    evidence.accept_claim(claim["id"], accepted_at=T1)
    if retract:
        evidence.set_claim_state(claim["id"], "disputed", "later correction", occurred_at=T2)
    return claim, span


def test_temporal_claim_reads_use_state_and_evidence_history(tmp_db):
    claim, span = _seed_temporal_claim(tmp_db)
    reads = TemporalReadService(tmp_db)

    before = reads.claims_as_of(T1_BEFORE)
    at_initial = reads.claims_as_of(T1_AFTER)
    current = reads.claims_as_of(T2_AFTER)

    assert before == []
    assert at_initial[0]["id"] == claim["id"]
    assert at_initial[0]["state"] == "supported"
    assert at_initial[0]["evidence"][0]["id"] == span["id"]
    assert current[0]["state"] == "disputed"


def test_historical_ask_restricts_grounding_to_as_of_knowledge(tmp_db):
    claim, _span = _seed_temporal_claim(tmp_db, retract=False)
    ask = AskService(tmp_db)
    conversation = ask.create_conversation()

    historical = ask.ask(
        conversation["id"],
        "What occurred in January?",
        as_of=T1_AFTER,
    )
    current = ask.ask(conversation["id"], "What occurred in January?")

    assert historical["status"] in {"answered", "qualified"}
    assert historical["status"] != "refused"
    assert historical["retrieval"]["as_of"].startswith(T1_AFTER[:-1])
    assert any(item["classification"] == "fact" for item in historical["statements"])
    assert current["retrieval"].get("as_of") is None
    assert any(
        claim["id"] in item
        for item in current["retrieval"]["retrieved_object_ids"]
    )


def test_historical_ask_rejects_invalid_as_of(tmp_db):
    apply_migrations(tmp_db)
    ask = AskService(tmp_db)
    conversation = ask.create_conversation()

    try:
        ask.ask(conversation["id"], "What is known?", as_of="not-a-time")
    except DomainValidation as exc:
        assert "ISO-8601" in str(exc)
    else:
        raise AssertionError("invalid as_of must be rejected")


def test_story_as_of_preserves_pre_correction_membership(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    evidence = EvidenceService(tmp_db)
    source = core.create_source({"name": "Story Source", "slug": "story-source"})
    document = core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": "https://example.test/story",
            "title": "Story evidence",
        }
    )
    original = core.create_story({"headline": "Original story"})
    corrected = core.create_story({"headline": "Corrected story"})
    version = evidence.create_document_version(
        document["id"],
        {"content_hash": "b" * 64, "content_kind": "excerpt"},
    )
    span = evidence.create_evidence_span(version["id"], {"excerpt": "A story fact."})
    claim = evidence.create_claim(original["id"], {"proposition": "A story fact."})
    evidence.link_claim_evidence(
        claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"}
    )
    evidence.set_claim_state(claim["id"], "supported", "support")
    evidence.accept_claim(claim["id"])
    before = STORY_BEFORE

    correction = StoryCorrectionService(tmp_db).reassign_claim(
        claim["id"], corrected["id"], reason="late reassignment", occurred_at=STORY_CORRECTION
    )
    after = STORY_AFTER
    reads = TemporalReadService(tmp_db)

    historical = reads.story_as_of(original["id"], before)
    current = reads.story_as_of(corrected["id"], after)

    assert historical["claims"][0]["id"] == claim["id"]
    assert historical["corrections"] == []
    assert current["claims"][0]["id"] == claim["id"]
    assert current["corrections"][0]["id"] == correction["correction_id"]


def test_report_as_of_selects_revision_and_exact_causes(tmp_db):
    claim, _span = _seed_temporal_claim(tmp_db, retract=False)
    reports = LivingReportService(tmp_db)
    report = reports.create(
        {"name": "Temporal report", "target_type": "story", "target_id": claim["story_id"]}
    )
    conn = sqlite3.connect(tmp_db)
    conn.execute("UPDATE living_reports SET created_at = ?, updated_at = ? WHERE id = ?", (T1, T1, report["id"]))
    conn.commit()
    conn.close()
    generated = reports.generate(report["id"], generated_at=T1)

    historical = TemporalReadService(tmp_db).report_as_of(report["id"], T1_AFTER)

    assert historical["revision"]["id"] == generated["generation"]["revision_id"]
    assert historical["claims"][0]["id"] == claim["id"]
    assert historical["causes"]
    assert all(item["cause_id"] for item in historical["causes"])


def _backdate_question(tmp_db, question_id: str, timestamp: str = T1) -> None:
    conn = sqlite3.connect(tmp_db)
    conn.execute(
        "UPDATE research_questions SET created_at = ?, updated_at = ? WHERE id = ?",
        (timestamp, timestamp, question_id),
    )
    conn.commit()
    conn.close()


def test_historical_ask_excludes_future_research_question_from_context(tmp_db):
    _claim, _span = _seed_temporal_claim(tmp_db, retract=False)
    questions = ResearchQuestionService(tmp_db)
    future = questions.create({"question": "Future research question about the January launch"})
    ask = AskService(tmp_db)
    conversation = ask.create_conversation()

    result = ask.ask(conversation["id"], "What occurred in January?", as_of=T1_AFTER)

    assert f"question:{future['id']}" not in result["retrieval"]["retrieved_object_ids"]
    assert future["id"] not in {item["object_id"] for item in result["citations"] if item["object_type"] == "question"}
    assert "Future research question" not in result["answer"]


def test_historical_ask_excludes_future_question_notes_notes_gaps_and_tasks(tmp_db):
    _claim, _span = _seed_temporal_claim(tmp_db, retract=False)
    questions = ResearchQuestionService(tmp_db)
    question = questions.create({"question": "What occurred in January?", "search_attempt_budget": 1})
    _backdate_question(tmp_db, question["id"])
    note = questions.add_note(question["id"], "Future note about January")
    future = questions.pursue(question["id"], query="future January task")

    result = AskService(tmp_db).ask(
        AskService(tmp_db).create_conversation()["id"],
        "What occurred in January?",
        as_of=T1_AFTER,
    )

    assert note["id"] not in {item["citation_id"] for item in result["citations"] if item["object_type"] == "question_note"}
    assert result["retrieval"]["research_options"] == []
    assert not any(item["object_id"] == future["task_id"] for item in result["citations"] if item["object_type"] == "research_task")
    assert all(not item.startswith(f"research_task:{future['task_id']}") for item in result["retrieval"]["retrieved_object_ids"])


def test_historical_ask_excludes_future_generic_note(tmp_db):
    claim, _span = _seed_temporal_claim(tmp_db, retract=False)
    note = WorkbenchService(tmp_db).add_note("story", claim["story_id"], "Future generic note about January")

    result = AskService(tmp_db).ask(
        AskService(tmp_db).create_conversation()["id"],
        "What occurred in January?",
        as_of=T1_AFTER,
    )

    assert note["id"] not in {item["citation_id"] for item in result["citations"] if item["object_type"] == "note"}
    assert all(not item.startswith(f"note:{note['id']}") for item in result["retrieval"]["retrieved_object_ids"])
    assert "Future generic note" not in result["answer"]


def test_historical_ask_excludes_future_report_and_future_story_context(tmp_db):
    claim, _span = _seed_temporal_claim(tmp_db, retract=False)
    from newsroom.reports import LivingReportService

    future_story = CoreService(tmp_db).create_story({"headline": "Future January story"})
    future_report = LivingReportService(tmp_db).create(
        {"name": "Future January report", "target_type": "story", "target_id": future_story["id"]}
    )
    ask = AskService(tmp_db)
    result = ask.ask(
        ask.create_conversation()["id"],
        "What occurred in January?",
        as_of=T1_AFTER,
    )

    assert f"story:{future_story['id']}" not in result["retrieval"]["retrieved_object_ids"]
    assert f"report:{future_report['id']}" not in result["retrieval"]["retrieved_object_ids"]
    assert all(item["object_id"] != future_report["id"] for item in result["citations"] if item["object_type"] == "report")


def test_report_as_of_rejects_report_created_after_boundary_and_hides_future_revision(tmp_db):
    claim, span = _seed_temporal_claim(tmp_db, retract=False)
    from newsroom.reports import LivingReportService

    reports = LivingReportService(tmp_db)
    report = reports.create({"name": "Temporal report", "target_type": "story", "target_id": claim["story_id"]})
    conn = sqlite3.connect(tmp_db)
    conn.execute("UPDATE living_reports SET created_at = ?, updated_at = ? WHERE id = ?", (T1, T1, report["id"]))
    conn.commit()
    conn.close()
    first = reports.generate(report["id"], generated_at=T1)

    evidence = EvidenceService(tmp_db)
    version = evidence.create_document_version(
        _document_id_for_span(tmp_db, span["id"]),
        {"content_hash": "c" * 64, "content_kind": "excerpt", "retrieved_at": T2},
    )
    future_span = evidence.create_evidence_span(version["id"], {"excerpt": "A later January fact.", "created_at": T2})
    future_claim = evidence.create_claim(claim["story_id"], {"proposition": "A later January fact.", "created_at": T2})
    evidence.link_claim_evidence(future_claim["id"], {"evidence_span_id": future_span["id"], "relationship": "supports", "created_at": T2})
    evidence.set_claim_state(future_claim["id"], "supported", "later support", occurred_at=T2)
    evidence.accept_claim(future_claim["id"], accepted_at=T2)
    reports.generate(report["id"], generated_at=T2_AFTER)

    historical = TemporalReadService(tmp_db).report_as_of(report["id"], T1_AFTER)
    assert historical["revision"]["id"] == first["generation"]["revision_id"]
    assert historical["report"]["current_revision_id"] == first["generation"]["revision_id"]

    future_story = CoreService(tmp_db).create_story({"headline": "Another future story"})
    future_report = reports.create({"name": "Future report", "target_type": "story", "target_id": future_story["id"]})
    with pytest.raises(DomainNotFound):
        TemporalReadService(tmp_db).report_as_of(future_report["id"], T1_AFTER)


def _document_id_for_span(tmp_db, span_id: str) -> str:
    conn = sqlite3.connect(tmp_db)
    document_id = conn.execute(
        "SELECT dv.document_id FROM evidence_spans es JOIN document_versions dv ON dv.id = es.document_version_id WHERE es.id = ?",
        (span_id,),
    ).fetchone()[0]
    conn.close()
    return document_id


def test_story_as_of_rejects_story_created_after_boundary(tmp_db):
    apply_migrations(tmp_db)
    story = CoreService(tmp_db).create_story({"headline": "Future story"})

    with pytest.raises(DomainNotFound):
        TemporalReadService(tmp_db).story_as_of(story["id"], T1_AFTER)


def test_story_as_of_does_not_back_project_split_archive_lifecycle(tmp_db):
    claim, span = _seed_temporal_claim(tmp_db, retract=False)
    evidence = EvidenceService(tmp_db)
    second_claim = evidence.create_claim(claim["story_id"], {"proposition": "A second story fact.", "created_at": T1})
    evidence.link_claim_evidence(second_claim["id"], {"evidence_span_id": span["id"], "relationship": "supports", "created_at": T1})
    evidence.set_claim_state(second_claim["id"], "supported", "second support", occurred_at=T1)
    evidence.accept_claim(second_claim["id"], accepted_at=T1)
    StoryCorrectionService(tmp_db).split_story(
        claim["story_id"],
        [[claim["id"]], [second_claim["id"]]],
        reason="later split",
        occurred_at=STORY_CORRECTION,
    )

    historical = TemporalReadService(tmp_db).story_as_of(claim["story_id"], STORY_BEFORE)

    assert {item["id"] for item in historical["claims"]} == {claim["id"], second_claim["id"]}
    assert historical["lineage"] == []
    assert historical["story"]["lifecycle"] != "archived"


def test_historical_ask_staleness_is_relative_to_as_of(tmp_db):
    _claim, _span = _seed_temporal_claim(tmp_db, retract=False)
    ask = AskService(tmp_db)
    result = ask.ask(ask.create_conversation()["id"], "What occurred in January?", as_of=T1_AFTER)

    assert result["retrieval"]["stale_evidence_count"] == 0
    assert "stale and should be rechecked" not in result["answer"]


def test_historical_citations_are_independently_temporally_eligible(tmp_db):
    claim, _span = _seed_temporal_claim(tmp_db, retract=False)
    question = ResearchQuestionService(tmp_db).create({"question": "What occurred in January?"})
    result = AskService(tmp_db).ask(AskService(tmp_db).create_conversation()["id"], "What occurred in January?", as_of=T1_AFTER)
    reads = TemporalReadService(tmp_db)

    assert question["id"] not in {item["object_id"] for item in result["citations"] if item["object_type"] == "question"}
    assert all(reads.eligible_as_of(item["object_type"], item["object_id"], T1_AFTER) for item in result["citations"])
    assert any(item["object_id"] == claim["id"] for item in result["citations"] if item["object_type"] == "claim")


def test_phase29_temporal_executor_fails_when_as_of_reads_are_removed(monkeypatch):
    monkeypatch.setattr("newsroom.temporal.TemporalReadService.claims_as_of", lambda *args, **kwargs: [])

    result = SemanticCaseRunner().run("phase29-unconfirmation")

    assert result.score.semantic.failed_assertion_ids == ("unconfirmation_history",)


def test_phase29_historical_ask_executor_fails_when_ask_is_bypassed(monkeypatch):
    monkeypatch.setattr(
        "newsroom.ask.AskService.ask",
        lambda self, *args, **kwargs: {"status": "refused", "refusal_code": "answer_failed"},
    )

    result = SemanticCaseRunner().run("phase29-historical-ask")

    assert result.score.semantic.failed_assertion_ids == ("historical_ask_boundary",)


def test_phase29_report_executor_fails_without_report_generation(monkeypatch):
    monkeypatch.setattr("newsroom.reports.LivingReportService.generate", lambda *args, **kwargs: {})

    result = SemanticCaseRunner().run("phase29-report-cause")

    assert result.score.semantic.failed_assertion_ids == ("report_revision_cause",)
