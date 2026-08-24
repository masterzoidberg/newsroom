"""Deterministic, durable Attention ranking over existing Newsroom state."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from . import storage
from .coverage import CoverageService
from .domain import DomainNotFound, DomainValidation, new_id, utc_now


FEEDBACK = frozenset({"useful", "not_important", "already_knew", "needs_investigation", "mute_pattern"})
ATTENTION_REFRESH_JOB_TYPE = "attention_refresh"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _decode(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


class AttentionService:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.coverage = CoverageService(db_path)

    def handlers(self) -> dict[str, Any]:
        return {ATTENTION_REFRESH_JOB_TYPE: self.handle}

    def handle(self, job: dict[str, Any]) -> dict[str, Any]:
        return self.refresh(limit=int((job.get("payload") or {}).get("limit", 200)))

    @staticmethod
    def _fingerprint(candidate: dict[str, Any]) -> str:
        return hashlib.sha256(_json(candidate).encode("utf-8")).hexdigest()

    def _candidates(self) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        conn = storage.connect(self.db_path)
        try:
            for row in conn.execute(
                "SELECT id, story_id, event_type, title, body, importance_score, created_at FROM alerts WHERE status = 'unread' ORDER BY importance_score DESC, created_at DESC, id DESC LIMIT 100"
            ):
                candidates.append(
                    {
                        "object_type": "alert",
                        "object_id": row["id"],
                        "reason_code": {
                            "contradiction": "new_contradiction",
                            "correction": "correction",
                            "new_primary_evidence": "new_primary_source",
                            "material_update": "material_change",
                        }.get(row["event_type"], "alert_followup"),
                        "importance_score": float(row["importance_score"]),
                        "explanation": {"title": row["title"], "body": row["body"], "story_id": row["story_id"], "created_at": row["created_at"]},
                    }
                )
            for row in conn.execute(
                "SELECT id, target_type, target_id, status FROM coverage_runs WHERE status <> 'completed' ORDER BY created_at DESC, id DESC LIMIT 100"
            ):
                summary = conn.execute(
                    "SELECT completeness, state_counts_json, explanation_json, qualified_negative FROM coverage_summaries WHERE run_id = ?",
                    (row["id"],),
                ).fetchone()
                explanation = _decode(summary["explanation_json"], {}) if summary else {}
                blocking = explanation.get("blocking_states", [])
                score = 0.85 if blocking else 0.65
                candidates.append(
                    {
                        "object_type": "coverage_run",
                        "object_id": row["id"],
                        "reason_code": "coverage_gap",
                        "importance_score": score,
                        "explanation": {"target_type": row["target_type"], "target_id": row["target_id"], "status": row["status"], "blocking_states": blocking, "completeness": summary["completeness"] if summary else 0.0},
                    }
                )
            for row in conn.execute(
                "SELECT id, operation_type, reason, reason_code, cause_class, occurred_at FROM story_corrections ORDER BY occurred_at DESC, id DESC LIMIT 50"
            ):
                candidates.append(
                    {
                        "object_type": "story_correction",
                        "object_id": row["id"],
                        "reason_code": "correction",
                        "importance_score": 0.8,
                        "explanation": {"operation_type": row["operation_type"], "reason": row["reason"], "reason_code": row["reason_code"], "cause_class": row["cause_class"], "occurred_at": row["occurred_at"]},
                    }
                )
            for row in conn.execute(
                "SELECT id, target_type, target_id, source_class, coverage_run_id, priority, reason FROM blind_spot_suggestions WHERE status = 'pending' ORDER BY priority DESC, created_at DESC, id DESC LIMIT 50"
            ):
                candidates.append(
                    {
                        "object_type": "blind_spot",
                        "object_id": row["id"],
                        "reason_code": "blind_spot",
                        "importance_score": float(row["priority"]),
                        "explanation": {"target_type": row["target_type"], "target_id": row["target_id"], "source_class": row["source_class"], "coverage_run_id": row["coverage_run_id"], "reason": row["reason"]},
                    }
                )
        finally:
            conn.close()
        return candidates

    @staticmethod
    def _result(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["explanation"] = _decode(result.pop("explanation_json"), {})
        return result

    def refresh(self, *, limit: int = 200) -> dict[str, Any]:
        if limit < 1 or limit > 500:
            raise DomainValidation("attention limit must be between 1 and 500")
        candidates = self._candidates()[:limit]
        now = utc_now()
        conn = storage.connect(self.db_path)
        created_count = 0
        try:
            with storage.write_tx(conn):
                for candidate in candidates:
                    fingerprint = self._fingerprint(candidate)
                    cursor = conn.execute(
                        "INSERT OR IGNORE INTO attention_items(id, object_type, object_id, reason_code, importance_score, state, source_fingerprint, explanation_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)",
                        (new_id("attention"), candidate["object_type"], candidate["object_id"], candidate["reason_code"], max(0.0, min(1.0, candidate["importance_score"])), fingerprint, _json(candidate["explanation"]), now, now),
                    )
                    created_count += cursor.rowcount
            rows = conn.execute(
                "SELECT * FROM attention_items WHERE state = 'open' ORDER BY importance_score DESC, updated_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return {"created_count": created_count, "items": [self._result(conn, row) for row in rows]}
        finally:
            conn.close()

    def list(self, *, state: str | None = None, limit: int = 100) -> dict[str, Any]:
        if state is not None and state not in {"open", "seen", "dismissed"}:
            raise DomainValidation("invalid attention state")
        if limit < 1 or limit > 500:
            raise DomainValidation("attention limit must be between 1 and 500")
        conn = storage.connect(self.db_path)
        try:
            if state:
                rows = conn.execute("SELECT * FROM attention_items WHERE state = ? ORDER BY importance_score DESC, updated_at DESC, id DESC LIMIT ?", (state, limit)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM attention_items WHERE state <> 'dismissed' ORDER BY importance_score DESC, updated_at DESC, id DESC LIMIT ?", (limit,)).fetchall()
            return {"items": [self._result(conn, row) for row in rows], "count": len(rows)}
        finally:
            conn.close()

    def get(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM attention_items WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("attention item not found")
            return self._result(conn, row)
        finally:
            conn.close()

    def feedback(self, identifier: str, feedback: str, *, actor: str | None = None) -> dict[str, Any]:
        if feedback not in FEEDBACK:
            raise DomainValidation("invalid attention feedback")
        state = "dismissed" if feedback in {"not_important", "mute_pattern"} else "seen"
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT id FROM attention_items WHERE id = ?", (identifier,)).fetchone()
                if row is None:
                    raise DomainNotFound("attention item not found")
                now = utc_now()
                conn.execute("INSERT INTO attention_feedback(id, attention_id, feedback, actor, created_at) VALUES (?, ?, ?, ?, ?)", (new_id("attention-feedback"), identifier, feedback, actor, now))
                conn.execute("UPDATE attention_items SET state = ?, updated_at = ? WHERE id = ?", (state, now, identifier))
        finally:
            conn.close()
        return self.get(identifier)


__all__ = ["ATTENTION_REFRESH_JOB_TYPE", "AttentionService", "FEEDBACK"]
