from __future__ import annotations

from newsroom.domain import CoreService
from newsroom.evidence import EvidenceService
from newsroom.jobs import JobService
from newsroom.migrations import apply_migrations
from newsroom.research_questions import (
    ResearchQuestionExecutionService,
    ResearchQuestionService,
)
from newsroom.runtime import build_worker_handlers, build_worker_queue
from newsroom.worker import WorkerProcess


T0 = "2026-08-23T12:00:00Z"


def _ledger_fixture(db_path):
    core = CoreService(db_path)
    source = core.create_source(
        {
            "name": "Phase 25 Official",
            "slug": "phase-25-official",
            "source_kind": "official",
            "default_quality": "primary",
            "homepage_url": "https://official.example.test",
        }
    )
    document = core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": "https://official.example.test/report",
            "title": "Phase 25 report",
        }
    )
    story = core.create_story({"headline": "Phase 25 report"})
    ledger = EvidenceService(db_path)
    version = ledger.create_document_version(
        document["id"], {"content_hash": "phase25-content", "content_kind": "excerpt"}
    )
    return core, ledger, story, version


def _claim(ledger, story_id, version_id, proposition, excerpt, *, state="supported"):
    span = ledger.create_evidence_span(version_id, {"excerpt": excerpt})
    claim = ledger.create_claim(story_id, {"proposition": proposition, "importance": "major"})
    if state != "pending":
        ledger.set_claim_state(claim["id"], state, "Phase 25 fixture")
    ledger.link_claim_evidence(
        claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"}
    )
    return claim, span


def _question(db_path, **overrides):
    data = {
        "question": "Did the satellite launch occur?",
        "origin_type": "user",
        "search_attempt_budget": 2,
        "query_budget": 4,
        "pursuit_policy": "manual",
    }
    data.update(overrides)
    return ResearchQuestionService(db_path).create(data)


def test_question_assessment_is_deterministic_and_distinguishes_relationships(tmp_db):
    apply_migrations(tmp_db)
    _core, ledger, story, version = _ledger_fixture(tmp_db)
    supporting, _support_span = _claim(
        ledger, story["id"], version["id"],
        "The satellite launch occurred", "The launch occurred on Tuesday.",
    )
    contextual, _context_span = _claim(
        ledger, story["id"], version["id"],
        "The weather was cloudy", "The weather was cloudy on Tuesday.",
    )
    question = _question(tmp_db)
    service = ResearchQuestionService(tmp_db)
    service.link_claim(question["id"], supporting["id"], "supports")
    service.link_claim(question["id"], contextual["id"], "contextualizes")

    current = service.get(question["id"])
    assert current["assessment_state"] == "supported"
    assert current["gaps"][0]["status"] == "satisfied"
    assert any(item["claim_id"] == contextual["id"] and item["relationship"] == "contextualizes" for item in current["claims"])
    before = len(current["assessment_history"])
    service.evaluate(question["id"])
    assert len(service.get(question["id"])["assessment_history"]) == before

    contradiction, _contradiction_span = _claim(
        ledger, story["id"], version["id"],
        "The satellite launch did not occur", "The launch did not occur.",
    )
    service.link_claim(question["id"], contradiction["id"], "contradicts")
    current = service.get(question["id"])
    assert current["assessment_state"] == "partially_answered"
    assert any(item["relationship"] == "contradicts" for item in current["claims"])


def test_unsubstantiated_claim_does_not_resolve_question_and_gap_dismissal_is_stable(tmp_db):
    apply_migrations(tmp_db)
    _core, ledger, story, version = _ledger_fixture(tmp_db)
    pending, _span = _claim(
        ledger, story["id"], version["id"],
        "The satellite launch occurred", "A draft says the launch occurred.", state="pending",
    )
    question = _question(tmp_db)
    service = ResearchQuestionService(tmp_db)
    service.link_claim(question["id"], pending["id"], "supports")
    assert service.get(question["id"])["assessment_state"] == "open"
    gap = service.get(question["id"])["gaps"][0]
    service.set_gap_status(gap["id"], "dismissed", reason="Not useful for this question")
    service.evaluate(question["id"])
    assert service.get(question["id"])["gaps"][0]["status"] == "dismissed"


def test_bounded_task_no_findings_is_successful_and_does_not_satisfy_gap(tmp_db):
    apply_migrations(tmp_db)
    question = _question(tmp_db)

    class EmptySearch:
        def search(self, *args, **kwargs):
            return {"items": []}

    service = ResearchQuestionService(tmp_db)
    job = service.pursue(question["id"], query="unavailable material", query_units=1)
    execution = ResearchQuestionExecutionService(tmp_db, search=EmptySearch())
    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(tmp_db, execution.handlers(), worker_id="phase25-test", queue=queue)
    result = worker.run_once(now=T0)
    assert result["status"] == "succeeded"
    current = service.get(question["id"])
    assert current["tasks"][0]["status"] == "completed_no_findings"
    assert current["gaps"][0]["status"] == "open"
    assert current["tasks"][0]["limits"]["max_queries"] <= 12
    assert job["task_id"] == current["tasks"][0]["id"]


def test_duplicate_pursuit_converges_on_one_active_task_per_gap(tmp_db):
    apply_migrations(tmp_db)
    question = _question(tmp_db, search_attempt_budget=3, query_budget=4)
    service = ResearchQuestionService(tmp_db)
    first = service.pursue(question["id"], query="same bounded pursuit", query_units=1)
    second = service.pursue(question["id"], query="same bounded pursuit", query_units=1)
    assert second["coalesced"] is True
    assert second["id"] == first["id"]
    assert len(service.get(question["id"])["tasks"]) == 1

