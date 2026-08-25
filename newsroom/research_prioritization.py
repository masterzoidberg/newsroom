"""Explainable prioritization of existing Research Question Gaps."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import storage
from .domain import DomainNotFound, DomainValidation


QUESTION_PRIORITY = {"urgent": 1.0, "high": 0.75, "normal": 0.5, "low": 0.25}
GAP_IMPORTANCE = {"primary_source": 1.0, "contradiction_review": 0.9, "discriminating": 0.85, "dependency_group_support": 0.75, "supporting_evidence": 0.6, "independent_support": 0.6}


class ResearchPrioritizationService:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def prioritize(self, question_id: str, *, limit: int = 100) -> dict[str, Any]:
        if limit < 1 or limit > 500:
            raise DomainValidation("research priority limit must be between 1 and 500")
        conn = storage.connect(self.db_path)
        try:
            question = conn.execute("SELECT id, priority FROM research_questions WHERE id = ? AND deleted_at IS NULL", (question_id,)).fetchone()
            if question is None:
                raise DomainNotFound("research question not found")
            gaps = conn.execute(
                """
                SELECT g.id, g.gap_type, g.description, g.status, g.rationale,
                       EXISTS(SELECT 1 FROM research_tasks t WHERE t.gap_id = g.id AND t.status IN ('planned','running')) AS has_active_task
                FROM research_question_gaps g
                WHERE g.question_id = ? AND g.status IN ('open', 'pursuing')
                ORDER BY g.updated_at DESC, g.id DESC LIMIT ?
                """,
                (question_id, limit),
            ).fetchall()
        finally:
            conn.close()
        items = []
        for gap in gaps:
            components = {
                "question_priority": QUESTION_PRIORITY.get(question["priority"], 0.5),
                "gap_importance": GAP_IMPORTANCE.get(gap["gap_type"], 0.5),
                "executor_availability": 0.5 if gap["has_active_task"] else 1.0,
            }
            score = round(sum(components.values()) / len(components), 6)
            items.append({"gap": dict(gap), "priority": score, "components": components, "rationale": "Priority combines the Question priority, canonical Gap type, and whether a Research Task is already active."})
        items.sort(key=lambda item: (-item["priority"], item["gap"]["id"]))
        return {"question_id": question_id, "items": items}


__all__ = ["ResearchPrioritizationService"]
