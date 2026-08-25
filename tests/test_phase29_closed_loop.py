from __future__ import annotations

from newsroom.domain import CoreService
from newsroom.evidence import EvidenceService
from newsroom.migrations import apply_migrations
from newsroom.research_questions import ResearchQuestionExecutionService, ResearchQuestionService
from newsroom.runtime import build_worker_queue
from newsroom.worker import WorkerProcess


class _CanonicalCorpusSearch:
    def __init__(self, *, claim_id: str, evidence_id: str, source_id: str):
        self.items = [
            {"entity_type": "claim", "entity_id": claim_id, "source_id": source_id},
            {"entity_type": "evidence", "entity_id": evidence_id, "source_id": source_id},
        ]

    def search(self, _query: str, **_kwargs):
        return {"items": self.items}


def test_research_question_task_reaches_canonical_evidence_and_reevaluates(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source(
        {
            "name": "Phase 29 Official",
            "slug": "phase-29-official",
            "source_kind": "official",
            "default_quality": "primary",
        }
    )
    document = core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": "https://phase29.example.test/launch",
            "title": "Satellite launch",
        }
    )
    story = core.create_story({"headline": "Satellite launch"})
    ledger = EvidenceService(tmp_db)
    version = ledger.create_document_version(
        document["id"], {"content_hash": "p" * 64, "content_kind": "excerpt"}
    )
    span = ledger.create_evidence_span(
        version["id"], {"excerpt": "The satellite launch occurred."}
    )
    claim = ledger.create_claim(
        story["id"], {"proposition": "The satellite launch occurred"}
    )
    ledger.link_claim_evidence(
        claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"}
    )
    ledger.set_claim_state(claim["id"], "supported", "canonical support")

    questions = ResearchQuestionService(tmp_db)
    question = questions.create(
        {
            "question": "Did the satellite launch occur?",
            "search_attempt_budget": 2,
            "query_budget": 4,
            "pursuit_policy": "manual",
        }
    )
    task = questions.pursue(question["id"], query="satellite launch")
    execution = ResearchQuestionExecutionService(
        tmp_db,
        search=_CanonicalCorpusSearch(
            claim_id=claim["id"], evidence_id=span["id"], source_id=source["id"]
        ),
    )
    worker = WorkerProcess(
        tmp_db,
        execution.handlers(),
        worker_id="phase29-research",
        queue=build_worker_queue(tmp_db),
    )

    result = worker.run_once(now="2026-08-25T00:00:00Z")
    current = questions.get(question["id"])

    assert result["status"] == "succeeded"
    assert result["result"]["task_status"] == "completed_with_evidence"
    assert current["assessment_state"] == "supported"
    assert any(item["claim_id"] == claim["id"] for item in current["claims"])
    assert any(item["evidence_span_id"] == span["id"] for item in current["evidence"])
    assert current["tasks"][0]["status"] == "completed_with_evidence"

    # The task linked existing canonical rows and changed no factual Claim
    # state itself; reevaluation supplied the Question state.
    assert ledger.get_claim(claim["id"])["state"] == "supported"
    assert current["tasks"][0]["outcome"]["claim_count"] == 1
