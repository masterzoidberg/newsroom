from __future__ import annotations

from newsroom.ask import AskService
from newsroom.domain import CoreService, DomainValidation
from newsroom.evidence import EvidenceService
from newsroom.evals.semantic import SemanticCaseRunner
from newsroom.migrations import apply_migrations
from newsroom.reports import LivingReportService
from newsroom.story_corrections import StoryCorrectionService
from newsroom.temporal import TemporalReadService


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
    generated = reports.generate(report["id"], generated_at=T1)

    historical = TemporalReadService(tmp_db).report_as_of(report["id"], T1_AFTER)

    assert historical["revision"]["id"] == generated["generation"]["revision_id"]
    assert historical["claims"][0]["id"] == claim["id"]
    assert historical["causes"]
    assert all(item["cause_id"] for item in historical["causes"])


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
