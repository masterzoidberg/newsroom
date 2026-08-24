"""Human-reviewable hypotheses linked to, but never substituted for, Claims."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from . import storage
from .domain import DomainConflict, DomainNotFound, DomainValidation, new_id, utc_now


STATUSES = frozenset({"draft", "approved", "rejected", "archived"})
RELATIONSHIPS = frozenset({"supports", "contradicts", "discriminates"})


def _decode(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


class HypothesisService:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @staticmethod
    def _result(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["claims"] = [dict(item) for item in conn.execute("SELECT * FROM hypothesis_claim_links WHERE hypothesis_id = ? ORDER BY created_at, id", (row["id"],)).fetchall()]
        result["gaps"] = [dict(item) for item in conn.execute("SELECT * FROM hypothesis_gaps WHERE hypothesis_id = ? ORDER BY created_at, id", (row["id"],)).fetchall()]
        result["history"] = [dict(item) for item in conn.execute("SELECT * FROM hypothesis_history WHERE hypothesis_id = ? ORDER BY created_at, id", (row["id"],)).fetchall()]
        return result

    def _require(self, conn: sqlite3.Connection, identifier: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM hypotheses WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise DomainNotFound("hypothesis not found")
        return row

    def create(self, question_id: str, statement: str, *, origin: str = "human", provider_route: str = "local_deterministic") -> dict[str, Any]:
        statement = str(statement or "").strip()
        if not statement or len(statement) > 10_000:
            raise DomainValidation("hypothesis statement must be between 1 and 10000 characters")
        if origin not in {"human", "deterministic", "provider"}:
            raise DomainValidation("invalid hypothesis origin")
        identifier = new_id("hypothesis")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                question = conn.execute("SELECT id FROM research_questions WHERE id = ? AND deleted_at IS NULL", (question_id,)).fetchone()
                if question is None:
                    raise DomainNotFound("research question not found")
                conn.execute("INSERT INTO hypotheses(id, question_id, statement, status, origin, provider_route, created_at, updated_at) VALUES (?, ?, ?, 'draft', ?, ?, ?, ?)", (identifier, question_id, statement, origin, provider_route, now, now))
                conn.execute("INSERT INTO hypothesis_history(id, hypothesis_id, from_status, to_status, actor, reason, created_at) VALUES (?, ?, NULL, 'draft', NULL, 'created', ?)", (new_id("hypothesis-history"), identifier, now))
            return self.get(identifier)
        finally:
            conn.close()

    def get(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return self._result(conn, self._require(conn, identifier))
        finally:
            conn.close()

    def list(self, question_id: str, *, status: str | None = None, limit: int = 100) -> dict[str, Any]:
        if status is not None and status not in STATUSES:
            raise DomainValidation("invalid hypothesis status")
        if limit < 1 or limit > 500:
            raise DomainValidation("hypothesis limit must be between 1 and 500")
        conn = storage.connect(self.db_path)
        try:
            if conn.execute("SELECT id FROM research_questions WHERE id = ? AND deleted_at IS NULL", (question_id,)).fetchone() is None:
                raise DomainNotFound("research question not found")
            params: list[Any] = [question_id]
            clause = "question_id = ?"
            if status:
                clause += " AND status = ?"
                params.append(status)
            rows = conn.execute(f"SELECT * FROM hypotheses WHERE {clause} ORDER BY updated_at DESC, id DESC LIMIT ?", [*params, limit]).fetchall()
            return {"items": [self._result(conn, row) for row in rows], "count": len(rows)}
        finally:
            conn.close()

    def link_claim(self, identifier: str, claim_id: str, relationship: str) -> dict[str, Any]:
        if relationship not in RELATIONSHIPS:
            raise DomainValidation("invalid hypothesis claim relationship")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, identifier)
                if conn.execute("SELECT id FROM claims WHERE id = ?", (claim_id,)).fetchone() is None:
                    raise DomainNotFound("claim not found")
                link_id = new_id("hypothesis-claim")
                now = utc_now()
                conn.execute("INSERT OR IGNORE INTO hypothesis_claim_links(id, hypothesis_id, claim_id, relationship, created_at) VALUES (?, ?, ?, ?, ?)", (link_id, identifier, claim_id, relationship, now))
                row = conn.execute("SELECT * FROM hypothesis_claim_links WHERE hypothesis_id = ? AND claim_id = ? AND relationship = ?", (identifier, claim_id, relationship)).fetchone()
                return dict(row)
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("hypothesis claim link could not be created") from exc
        finally:
            conn.close()

    def add_gap(self, identifier: str, description: str) -> dict[str, Any]:
        description = str(description or "").strip()
        if not description or len(description) > 4_000:
            raise DomainValidation("hypothesis gap must be between 1 and 4000 characters")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, identifier)
                gap_id = new_id("hypothesis-gap")
                now = utc_now()
                conn.execute("INSERT INTO hypothesis_gaps(id, hypothesis_id, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", (gap_id, identifier, description, now, now))
                return dict(conn.execute("SELECT * FROM hypothesis_gaps WHERE id = ?", (gap_id,)).fetchone())
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("hypothesis gap already exists") from exc
        finally:
            conn.close()

    def review(self, identifier: str, status: str, *, actor: str | None = None, reason: str = "") -> dict[str, Any]:
        if status not in {"approved", "rejected", "archived"}:
            raise DomainValidation("invalid hypothesis review status")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = self._require(conn, identifier)
                now = utc_now()
                conn.execute("UPDATE hypotheses SET status = ?, updated_at = ?, approved_at = CASE WHEN ? = 'approved' THEN ? ELSE approved_at END, approved_by = CASE WHEN ? = 'approved' THEN ? ELSE approved_by END WHERE id = ?", (status, now, status, now, status, actor, identifier))
                conn.execute("INSERT INTO hypothesis_history(id, hypothesis_id, from_status, to_status, actor, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (new_id("hypothesis-history"), identifier, row["status"], status, actor, reason, now))
            return self.get(identifier)
        finally:
            conn.close()


__all__ = ["HypothesisService", "RELATIONSHIPS", "STATUSES"]
