from __future__ import annotations

import sqlite3

import pytest

from newsroom.ask import AskService
from newsroom.domain import CoreService, DomainNotFound, DomainValidation
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
STORY_CORRECTION = "2099-02-01T00:00:00Z"
STORY_AFTER = "2099-02-01T00:00:01Z"
STORY_BEFORE = "2098-12-31T23:59:59Z"


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
