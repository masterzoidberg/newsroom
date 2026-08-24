"""Explainable prioritization of existing Research Question Gaps."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import storage
from .coverage import CoverageService
from .domain import DomainNotFound, DomainValidation


QUESTION_PRIORITY = {"urgent": 1.0, "high": 0.75, "normal": 0.5, "low": 0.25}
GAP_IMPORTANCE = {"primary_source": 1.0, "contradiction_review": 0.9, "independent_support": 0.75, "supporting_evidence": 0.6}


class ResearchPrioritizationService:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.coverage = CoverageService(db_path)

    def prioritize(self, question_id: str, *, limit: int = 100) -> dict[str, Any]:
        if limit < 1 or limit > 500:
            raise DomainValidation("research priority limit must be between 1 and 500")
        conn = storage.connect(self.db_path)
        try:
            question = conn.execute("SELECT id, priority FROM research_questions WHERE id = ? AND deleted_at IS NULL", (question_id,)).fetchone()
            if question is None:
                raise DomainNotFound("research question not found")
            gaps = conn.execute(
                "SELECT id, gap_type, description, status, rationale FROM research_question_gaps WHERE question_id = ? AND status IN ('open', 'pursuing') ORDER BY updated_at DESC, id DESC LIMIT ?",
                (question_id, limit),
            ).fetchall()
            coverage_runs = self.coverage.list_runs(target_type="research_question", target_id=question_id, limit=20)
        finally:
            conn.close()
        coverage_deficiency = max((1.0 - float(run["summary"].get("completeness", 0.0)) for run in coverage_runs if run["status"] != "completed"), default=0.0)
        items = []
        for gap in gaps:
            components = {
                "question_priority": QUESTION_PRIORITY.get(question["priority"], 0.5),
                "gap_importance": GAP_IMPORTANCE.get(gap["gap_type"], 0.5),
                "coverage_deficiency": coverage_deficiency,
                "freshness": 1.0 if gap["status"] == "open" else 0.6,
                "cost_budget": 1.0,
            }
            score = round(sum(components.values()) / len(components), 6)
            items.append({"gap": dict(gap), "priority": score, "components": components, "rationale": "Priority combines the Question priority, Gap type, coverage deficiency, open/pursuing state, and current budget availability."})
        items.sort(key=lambda item: (-item["priority"], item["gap"]["id"]))
        return {"question_id": question_id, "items": items, "coverage_runs": coverage_runs}


__all__ = ["ResearchPrioritizationService"]
