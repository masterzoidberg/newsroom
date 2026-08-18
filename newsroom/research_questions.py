"""Durable Research Question lifecycle and evidence-gap services.

Research Questions are intentionally separate from Claims. A question or user
hypothesis can guide bounded follow-up work, but it never becomes accepted
evidence without the normal Evidence Ledger path.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from . import storage
from .domain import DomainConflict, DomainNotFound, DomainValidation, new_id, utc_now
from .jobs import RESEARCH_QUESTION_JOB_TYPE


QUESTION_STATUSES = frozenset({"open", "resolved", "abandoned"})
QUESTION_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})
QUESTION_ORIGINS = frozenset({"story", "claim", "subject", "user", "monitor"})
LINK_RELATIONSHIPS = frozenset({"supports", "contradicts", "contextualizes", "resolves"})
NOTE_TYPES = frozenset({"note", "hypothesis"})
ATTEMPT_MODES = frozenset({"manual", "policy"})
ATTEMPT_STATUSES = frozenset({"planned", "running", "succeeded", "partial", "failed", "cancelled"})
TERMINAL_RQ_ATTEMPT_STATUSES = frozenset({"succeeded", "partial", "failed", "cancelled"})
SUGGESTION_TYPES = frozenset({"question", "search", "source"})
SUGGESTION_STATUSES = frozenset({"pending", "accepted", "rejected", "converted"})


def _json(value: Any) -> str:
    try:
        return json.dumps(value if value is not None else {}, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise DomainValidation("payload must be JSON serializable") from exc


def _decode(value: str | None) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DomainValidation(f"{label} must be a non-negative integer")
    return value


def _nonnegative_float(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise DomainValidation(f"{label} must be a non-negative number")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise DomainValidation(f"{label} must be a non-negative number") from exc
    if result < 0:
        raise DomainValidation(f"{label} must be a non-negative number")
    return result


def _validate_time(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized or len(normalized) > 64:
        raise DomainValidation(f"{label} must be a valid timestamp")
    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DomainValidation(f"{label} must be a valid timestamp") from exc
    return normalized


class ResearchQuestionService:
    """Own short SQLite transactions for Research Questions and gap work."""

    job_type = RESEARCH_QUESTION_JOB_TYPE

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @staticmethod
    def _require(conn: sqlite3.Connection, identifier: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM research_questions WHERE id = ? AND deleted_at IS NULL", (identifier,)).fetchone()
        if row is None:
            raise DomainNotFound("research question not found")
        return row

    @staticmethod
    def _require_claim(conn: sqlite3.Connection, identifier: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM claims WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise DomainNotFound("claim not found")
        return row

    @staticmethod
    def _require_span(conn: sqlite3.Connection, identifier: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM evidence_spans WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise DomainNotFound("evidence span not found")
        return row

    @staticmethod
    def _suggestion_dict(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["payload"] = _decode(result.pop("payload_json", None))
        return result

    def create(self, data: Mapping[str, Any], *, actor: str = "user") -> dict[str, Any]:
        question = str(data.get("question", "")).strip()
        origin_type = str(data.get("origin_type", "user")).strip()
        origin_id = data.get("origin_id")
        priority = str(data.get("priority", "normal")).strip()
        if not question or len(question) > 10_000:
            raise DomainValidation("question must be 1-10000 characters")
        if origin_type not in QUESTION_ORIGINS:
            raise DomainValidation("invalid research question origin")
        if origin_id is not None and not str(origin_id).strip():
            raise DomainValidation("origin_id must not be empty")
        if origin_type != "user" and not origin_id:
            raise DomainValidation("origin_id is required for this research question origin")
        if priority not in QUESTION_PRIORITIES:
            raise DomainValidation("invalid research question priority")
        attempts = _nonnegative_int(data.get("search_attempt_budget", 0), "search_attempt_budget")
        queries = _nonnegative_int(data.get("query_budget", 0), "query_budget")
        local_units = _nonnegative_int(data.get("local_model_budget", 0), "local_model_budget")
        paid = _nonnegative_float(data.get("paid_budget_usd", 0.0), "paid_budget_usd")
        next_attempt = _validate_time(data.get("next_attempt_at"), "next_attempt_at")
        now = utc_now()
        identifier = new_id("rq")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if origin_id is not None and origin_type in {"story", "claim", "subject", "monitor"}:
                    table = {
                        "story": "stories",
                        "claim": "claims",
                        "subject": "subjects",
                        "monitor": "monitors",
                    }[origin_type]
                    origin = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (str(origin_id),)).fetchone()
                    if origin is None or ("deleted_at" in origin.keys() and origin["deleted_at"] is not None):
                        raise DomainNotFound(f"{origin_type} origin not found")
                conn.execute(
                    """
                    INSERT INTO research_questions
                        (id, question, origin_type, origin_id, status, priority,
                         search_attempt_budget, next_attempt_at, resolution_note,
                         created_at, updated_at, query_budget, local_model_budget,
                         paid_budget_usd)
                    VALUES (?, ?, ?, ?, 'open', ?, ?, ?, NULL, ?, ?, ?, ?, ?)
                    """,
                    (identifier, question, origin_type, origin_id, priority, attempts, next_attempt, now, now, queries, local_units, paid),
                )
                conn.execute(
                    """
                    INSERT INTO research_question_history
                        (id, question_id, from_status, to_status, reason, actor, created_at)
                    VALUES (?, ?, NULL, 'open', ?, ?, ?)
                    """,
                    (new_id("rqh"), identifier, "question created", str(actor).strip() or "system", now),
                )
        finally:
            conn.close()
        return self.get(identifier)

    def get(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = self._require(conn, identifier)
            result = dict(row)
            attempts = conn.execute(
                "SELECT * FROM research_question_attempts WHERE question_id = ? ORDER BY attempt_no, id",
                (identifier,),
            ).fetchall()
            result["attempts"] = [dict(item) for item in attempts]
            result["attempts_used"] = len(attempts)
            result["query_used"] = sum(item["query_units"] for item in attempts)
            result["local_model_used"] = sum(item["local_model_units"] for item in attempts)
            result["paid_used_usd"] = round(sum(item["estimated_cost_usd"] for item in attempts), 8)
            result["history"] = [
                dict(item)
                for item in conn.execute(
                    "SELECT * FROM research_question_history WHERE question_id = ? ORDER BY rowid",
                    (identifier,),
                ).fetchall()
            ]
            result["claims"] = [
                dict(item)
                for item in conn.execute(
                    "SELECT * FROM research_question_claims WHERE question_id = ? ORDER BY created_at, claim_id, relationship",
                    (identifier,),
                ).fetchall()
            ]
            result["evidence"] = [
                dict(item)
                for item in conn.execute(
                    "SELECT * FROM research_question_evidence WHERE question_id = ? ORDER BY created_at, evidence_span_id, relationship",
                    (identifier,),
                ).fetchall()
            ]
            result["notes"] = [
                dict(item)
                for item in conn.execute(
                    "SELECT * FROM research_question_notes WHERE question_id = ? ORDER BY created_at, id",
                    (identifier,),
                ).fetchall()
            ]
            return result
        finally:
            conn.close()

    def list(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        origin_type: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        if status is not None and status not in QUESTION_STATUSES:
            raise DomainValidation("invalid research question status")
        if priority is not None and priority not in QUESTION_PRIORITIES:
            raise DomainValidation("invalid research question priority")
        if origin_type is not None and origin_type not in QUESTION_ORIGINS:
            raise DomainValidation("invalid research question origin")
        if page < 1 or page_size < 1 or page_size > 100:
            raise DomainValidation("invalid research question page")
        clauses = ["deleted_at IS NULL"]
        params: list[Any] = []
        for field, value in (("status", status), ("priority", priority), ("origin_type", origin_type)):
            if value is not None:
                clauses.append(f"{field} = ?")
                params.append(value)
        where = " AND ".join(clauses)
        conn = storage.connect(self.db_path)
        try:
            total = conn.execute(f"SELECT COUNT(*) FROM research_questions WHERE {where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM research_questions WHERE {where} ORDER BY CASE priority WHEN 'urgent' THEN 3 WHEN 'high' THEN 2 WHEN 'normal' THEN 1 ELSE 0 END DESC, created_at DESC, id LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
            return {"items": [dict(row) for row in rows], "page": page, "page_size": page_size, "total": total}
        finally:
            conn.close()

    def update(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"question", "priority", "search_attempt_budget", "query_budget", "local_model_budget", "paid_budget_usd", "next_attempt_at"}
        unknown = set(data) - allowed
        if unknown:
            raise DomainValidation(f"unsupported research question fields: {sorted(unknown)}")
        if not data:
            raise DomainValidation("at least one research question field must be supplied")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                current = self._require(conn, identifier)
                values: dict[str, Any] = {}
                if "question" in data:
                    value = str(data["question"]).strip()
                    if not value or len(value) > 10_000:
                        raise DomainValidation("question must be 1-10000 characters")
                    values["question"] = value
                if "priority" in data:
                    value = str(data["priority"]).strip()
                    if value not in QUESTION_PRIORITIES:
                        raise DomainValidation("invalid research question priority")
                    values["priority"] = value
                for field in ("search_attempt_budget", "query_budget", "local_model_budget"):
                    if field in data:
                        value = _nonnegative_int(data[field], field)
                        if value < self._used(conn, identifier, field):
                            raise DomainConflict(f"{field} cannot be below already used budget")
                        values[field] = value
                if "paid_budget_usd" in data:
                    value = _nonnegative_float(data["paid_budget_usd"], "paid_budget_usd")
                    if value + 1e-12 < self._used(conn, identifier, "paid_budget_usd"):
                        raise DomainConflict("paid_budget_usd cannot be below already used budget")
                    values["paid_budget_usd"] = value
                if "next_attempt_at" in data:
                    values["next_attempt_at"] = _validate_time(data["next_attempt_at"], "next_attempt_at")
                assignments = ", ".join(f"{field} = ?" for field in values)
                conn.execute(
                    f"UPDATE research_questions SET {assignments}, updated_at = ? WHERE id = ?",
                    [*values.values(), utc_now(), identifier],
                )
        finally:
            conn.close()
        return self.get(identifier)

    @staticmethod
    def _used(conn: sqlite3.Connection, question_id: str, field: str) -> int | float:
        if field == "search_attempt_budget":
            return conn.execute("SELECT COUNT(*) FROM research_question_attempts WHERE question_id = ?", (question_id,)).fetchone()[0]
        column = {"query_budget": "query_units", "local_model_budget": "local_model_units", "paid_budget_usd": "estimated_cost_usd"}[field]
        return conn.execute(f"SELECT COALESCE(SUM({column}), 0) FROM research_question_attempts WHERE question_id = ?", (question_id,)).fetchone()[0]

    def _transition(self, identifier: str, target: str, reason: str, *, actor: str) -> dict[str, Any]:
        reason = str(reason).strip()
        if target not in QUESTION_STATUSES:
            raise DomainValidation("invalid research question status")
        if not reason or len(reason) > 4_000:
            raise DomainValidation("transition reason must be 1-4000 characters")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                current = self._require(conn, identifier)
                if target == current["status"]:
                    raise DomainConflict("research question is already in that status")
                if target == "resolved" and current["status"] != "open":
                    raise DomainConflict("only open research questions can be resolved")
                if target == "abandoned" and current["status"] != "open":
                    raise DomainConflict("only open research questions can be abandoned")
                now = utc_now()
                conn.execute(
                    "UPDATE research_questions SET status = ?, resolution_note = ?, updated_at = ? WHERE id = ?",
                    (target, reason if target in {"resolved", "abandoned"} else current["resolution_note"], now, identifier),
                )
                conn.execute(
                    """
                    INSERT INTO research_question_history
                        (id, question_id, from_status, to_status, reason, actor, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (new_id("rqh"), identifier, current["status"], target, reason, str(actor).strip() or "system", now),
                )
        finally:
            conn.close()
        return self.get(identifier)

    def resolve(self, identifier: str, resolution_note: str, *, actor: str = "user") -> dict[str, Any]:
        return self._transition(identifier, "resolved", resolution_note, actor=actor)

    def abandon(self, identifier: str, reason: str, *, actor: str = "user") -> dict[str, Any]:
        return self._transition(identifier, "abandoned", reason, actor=actor)

    def reopen(self, identifier: str, reason: str, *, actor: str = "user") -> dict[str, Any]:
        return self._transition(identifier, "open", reason, actor=actor)

    def link_claim(self, identifier: str, claim_id: str, relationship: str = "resolves") -> dict[str, Any]:
        if relationship not in LINK_RELATIONSHIPS:
            raise DomainValidation("invalid research question claim relationship")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, identifier)
                self._require_claim(conn, claim_id)
                conn.execute(
                    "INSERT OR IGNORE INTO research_question_claims(question_id, claim_id, relationship, created_at) VALUES (?, ?, ?, ?)",
                    (identifier, claim_id, relationship, utc_now()),
                )
        finally:
            conn.close()
        return self.get(identifier)

    def link_evidence(self, identifier: str, evidence_span_id: str, relationship: str = "resolves") -> dict[str, Any]:
        if relationship not in LINK_RELATIONSHIPS:
            raise DomainValidation("invalid research question evidence relationship")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, identifier)
                self._require_span(conn, evidence_span_id)
                conn.execute(
                    "INSERT OR IGNORE INTO research_question_evidence(question_id, evidence_span_id, relationship, created_at) VALUES (?, ?, ?, ?)",
                    (identifier, evidence_span_id, relationship, utc_now()),
                )
        finally:
            conn.close()
        return self.get(identifier)

    def add_note(self, identifier: str, body: str, *, note_type: str = "note") -> dict[str, Any]:
        body = str(body).strip()
        if note_type not in NOTE_TYPES:
            raise DomainValidation("invalid research question note type")
        if not body or len(body) > 10_000:
            raise DomainValidation("note must be 1-10000 characters")
        note_id = new_id("rqn")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, identifier)
                conn.execute(
                    "INSERT INTO research_question_notes(id, question_id, note_type, body, created_at) VALUES (?, ?, ?, ?, ?)",
                    (note_id, identifier, note_type, body, utc_now()),
                )
        finally:
            conn.close()
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM research_question_notes WHERE id = ?", (note_id,)).fetchone()
            return dict(row)
        finally:
            conn.close()

    def schedule(self, identifier: str, next_attempt_at: str | None) -> dict[str, Any]:
        return self.update(identifier, {"next_attempt_at": next_attempt_at})

    def _attempt_summary(self, conn: sqlite3.Connection, identifier: str) -> tuple[int, int, int, float]:
        row = conn.execute(
            "SELECT COUNT(*) AS attempts, COALESCE(SUM(query_units), 0) AS queries, COALESCE(SUM(local_model_units), 0) AS local_units, COALESCE(SUM(estimated_cost_usd), 0.0) AS paid FROM research_question_attempts WHERE question_id = ?",
            (identifier,),
        ).fetchone()
        return row["attempts"], row["queries"], row["local_units"], float(row["paid"])

    @staticmethod
    def _lineage_groups(conn: sqlite3.Connection, document_ids: list[str]) -> int:
        """Count independent document/source groups without trusting publication count."""
        if not document_ids:
            return 0
        nodes = set(document_ids)
        parent: dict[str, str] = {node: node for node in nodes}

        def find(node: str) -> str:
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        def union(left: str, right: str) -> None:
            if left not in parent:
                parent[left] = left
            if right not in parent:
                parent[right] = right
            root_left, root_right = find(left), find(right)
            if root_left != root_right:
                parent[root_right] = root_left

        placeholders = ",".join("?" for _ in nodes)
        rows = conn.execute(
            f"SELECT document_id, parent_document_id FROM document_lineage WHERE relationship IN ('syndicated_from', 'wire_propagation', 'rewritten_from') AND (document_id IN ({placeholders}) OR parent_document_id IN ({placeholders}))",
            [*nodes, *nodes],
        ).fetchall()
        for row in rows:
            union(row["document_id"], row["parent_document_id"])
        return len({find(node) for node in nodes})

    def _claim_gap_types(self, conn: sqlite3.Connection, claim: sqlite3.Row) -> list[tuple[str, dict[str, Any]]]:
        evidence = conn.execute(
            """
            SELECT ce.relationship, d.id AS document_id, s.id AS source_id,
                   s.default_quality, s.source_kind
            FROM claim_evidence AS ce
            JOIN evidence_spans AS es ON es.id = ce.evidence_span_id
            JOIN document_versions AS dv ON dv.id = es.document_version_id
            JOIN documents AS d ON d.id = dv.document_id
            JOIN sources AS s ON s.id = d.source_id
            WHERE ce.claim_id = ?
            ORDER BY ce.created_at, ce.id
            """,
            (claim["id"],),
        ).fetchall()
        supporting = [row for row in evidence if row["relationship"] == "supports"]
        contradicting = [row for row in evidence if row["relationship"] == "contradicts"]
        gaps: list[tuple[str, dict[str, Any]]] = []
        if claim["state"] == "pending":
            gaps.append(("pending_claim", {"state": claim["state"]}))
        if claim["state"] == "unsubstantiated":
            gaps.append(("unsubstantiated_claim", {"state": claim["state"]}))
        if claim["state"] == "disputed" or contradicting:
            gaps.append(("contradiction", {"contradicting_evidence_count": len(contradicting), "state": claim["state"]}))
        if not supporting:
            gaps.append(("missing_support", {"supporting_evidence_count": 0}))
        if supporting:
            document_ids = list(dict.fromkeys(row["document_id"] for row in supporting))
            independent = self._lineage_groups(conn, document_ids)
            if independent < 2:
                gaps.append(("weak_independence", {"independent_group_count": independent, "document_ids": document_ids}))
        primary = [
            row for row in supporting
            if row["default_quality"] == "primary" or row["source_kind"] == "official"
        ]
        if not primary:
            gaps.append(("missing_primary_source", {"source_ids": list(dict.fromkeys(row["source_id"] for row in supporting))}))
        return gaps

    @staticmethod
    def _suggestion_text(gap_type: str, proposition: str, suggestion_type: str) -> tuple[str, str, float]:
        labels = {
            "pending_claim": "the pending claim",
            "unsubstantiated_claim": "the unsubstantiated claim",
            "missing_support": "the claim",
            "contradiction": "the conflicting reports",
            "weak_independence": "the claim's independent corroboration",
            "missing_primary_source": "a primary or official source",
            "missing_claims": "the story's important claims",
        }
        subject = labels.get(gap_type, "the evidence gap")
        rationale = f"Stored ledger state identifies a {gap_type.replace('_', ' ')} gap for {proposition}."
        value = {
            "contradiction": 0.95,
            "unsubstantiated_claim": 0.9,
            "missing_primary_source": 0.85,
            "weak_independence": 0.8,
            "missing_support": 0.8,
            "pending_claim": 0.7,
            "missing_claims": 0.65,
        }.get(gap_type, 0.5)
        if suggestion_type == "question":
            return f"What evidence would resolve {subject}: {proposition}?", rationale, value
        if suggestion_type == "search":
            return f'Find independent evidence for "{proposition}" and check official or primary sources.', rationale, value - 0.05
        return f"Candidate source search: identify an independent primary or official source about {proposition}.", rationale, value - 0.1

    def _persist_gap_suggestions(
        self,
        conn: sqlite3.Connection,
        *,
        origin_type: str,
        origin_id: str,
        gap_type: str,
        proposition: str,
        details: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        output = []
        for suggestion_type in ("question", "search", "source"):
            suggestion, rationale, information_value = self._suggestion_text(gap_type, proposition, suggestion_type)
            existing = conn.execute(
                "SELECT * FROM research_gap_suggestions WHERE origin_type = ? AND origin_id = ? AND gap_type = ? AND suggestion_type = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
                (origin_type, origin_id, gap_type, suggestion_type),
            ).fetchone()
            if existing:
                output.append(self._suggestion_dict(existing))
                continue
            identifier = new_id("gap")
            conn.execute(
                """
                INSERT INTO research_gap_suggestions
                    (id, origin_type, origin_id, gap_type, suggestion_type,
                     suggestion, rationale, expected_information_value,
                     payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (identifier, origin_type, origin_id, gap_type, suggestion_type, suggestion, rationale, information_value, _json(details), utc_now()),
            )
            row = conn.execute("SELECT * FROM research_gap_suggestions WHERE id = ?", (identifier,)).fetchone()
            output.append(self._suggestion_dict(row))
        return output

    def detect_gaps(self, *, story_id: str | None = None, claim_id: str | None = None) -> list[dict[str, Any]]:
        if (story_id is None) == (claim_id is None):
            raise DomainValidation("provide exactly one of story_id or claim_id")
        conn = storage.connect(self.db_path)
        try:
            targets: list[tuple[str, sqlite3.Row]] = []
            if claim_id is not None:
                targets.append(("claim", self._require_claim(conn, claim_id)))
            else:
                story = conn.execute("SELECT * FROM stories WHERE id = ? AND deleted_at IS NULL", (story_id,)).fetchone()
                if story is None:
                    raise DomainNotFound("story not found")
                claims = conn.execute("SELECT * FROM claims WHERE story_id = ? ORDER BY created_at, id LIMIT 100", (story_id,)).fetchall()
                if not claims:
                    with storage.write_tx(conn):
                        return self._persist_gap_suggestions(
                            conn,
                            origin_type="story",
                            origin_id=story_id,
                            gap_type="missing_claims",
                            proposition=story["headline"],
                            details={"claim_count": 0},
                        )
                targets = [("claim", claim) for claim in claims]
            suggestions: list[dict[str, Any]] = []
            with storage.write_tx(conn):
                for origin_type, claim in targets:
                    for gap_type, details in self._claim_gap_types(conn, claim):
                        suggestions.extend(
                            self._persist_gap_suggestions(
                                conn,
                                origin_type=origin_type,
                                origin_id=claim["id"],
                                gap_type=gap_type,
                                proposition=claim["proposition"],
                                details=details,
                            )
                        )
            return suggestions
        finally:
            conn.close()

    def list_suggestions(
        self,
        *,
        origin_type: str | None = None,
        origin_id: str | None = None,
        question_id: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        if origin_type is not None and origin_type not in {"story", "claim"}:
            raise DomainValidation("invalid suggestion origin")
        if status is not None and status not in SUGGESTION_STATUSES:
            raise DomainValidation("invalid suggestion status")
        if page < 1 or page_size < 1 or page_size > 200:
            raise DomainValidation("invalid suggestion page")
        clauses = ["1 = 1"]
        params: list[Any] = []
        for field, value in (("origin_type", origin_type), ("origin_id", origin_id), ("question_id", question_id), ("status", status)):
            if value is not None:
                clauses.append(f"{field} = ?")
                params.append(value)
        where = " AND ".join(clauses)
        conn = storage.connect(self.db_path)
        try:
            total = conn.execute(f"SELECT COUNT(*) FROM research_gap_suggestions WHERE {where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM research_gap_suggestions WHERE {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
            items = []
            for row in rows:
                items.append(self._suggestion_dict(row))
            return {"items": items, "page": page, "page_size": page_size, "total": total}
        finally:
            conn.close()

    def pursue(
        self,
        identifier: str,
        *,
        mode: str = "manual",
        query_units: int = 0,
        local_model_units: int = 0,
        estimated_cost_usd: float = 0.0,
        query: str | None = None,
    ) -> dict[str, Any]:
        """Enqueue exactly one bounded follow-up Job for a Question."""
        if mode not in ATTEMPT_MODES:
            raise DomainValidation("invalid research question pursuit mode")
        query_units = _nonnegative_int(query_units, "query_units")
        local_model_units = _nonnegative_int(local_model_units, "local_model_units")
        estimated_cost_usd = _nonnegative_float(estimated_cost_usd, "estimated_cost_usd")
        if query is not None and len(str(query)) > 4_000:
            raise DomainValidation("query is too long")
        now = utc_now()
        conn = storage.connect(self.db_path)
        attempt_id = new_id("rqa")
        try:
            with storage.write_tx(conn):
                question = self._require(conn, identifier)
                if question["status"] != "open":
                    raise DomainConflict("only open research questions can be pursued")
                attempts_used, queries_used, local_used, paid_used = self._attempt_summary(conn, identifier)
                if attempts_used >= question["search_attempt_budget"]:
                    raise DomainConflict("research question attempt budget exhausted")
                if queries_used + query_units > question["query_budget"]:
                    raise DomainConflict("research question query budget exhausted")
                if local_used + local_model_units > question["local_model_budget"]:
                    raise DomainConflict("research question local-model budget exhausted")
                if paid_used + estimated_cost_usd > float(question["paid_budget_usd"]) + 1e-12:
                    raise DomainConflict("research question cost budget exhausted")
                attempt_no = attempts_used + 1
                conn.execute(
                    """
                    INSERT INTO research_question_attempts
                        (id, question_id, attempt_no, mode, status, query_units,
                         local_model_units, estimated_cost_usd, query, created_at)
                    VALUES (?, ?, ?, ?, 'planned', ?, ?, ?, ?, ?)
                    """,
                    (attempt_id, identifier, attempt_no, mode, query_units, local_model_units, estimated_cost_usd, query, now),
                )
                conn.execute(
                    "UPDATE research_questions SET last_attempt_at = ?, next_attempt_at = NULL, updated_at = ? WHERE id = ?",
                    (now, now, identifier),
                )
                question_text = question["question"]
                priority = {"low": 0, "normal": 100, "high": 500, "urgent": 900}[question["priority"]]
        finally:
            conn.close()
        from .jobs import JobService

        key = f"research-question:{identifier}:{attempt_no}"
        try:
            job = JobService(self.db_path).enqueue(
                self.job_type,
                {
                    "research_question_id": identifier,
                    "attempt_id": attempt_id,
                    "question": question_text,
                    "mode": mode,
                    "query": query,
                    "budget": {
                        "acquisition_units": query_units,
                        "local_model_units": local_model_units,
                        "usd": estimated_cost_usd,
                    },
                },
                idempotency_key=key,
                research_question_id=identifier,
                priority=priority,
                max_attempts=1,
            )
        except Exception:
            conn = storage.connect(self.db_path)
            try:
                with storage.write_tx(conn):
                    conn.execute(
                        "UPDATE research_question_attempts SET status = 'failed', outcome_note = 'job enqueue failed', completed_at = ? WHERE id = ? AND status = 'planned'",
                        (utc_now(), attempt_id),
                    )
            finally:
                conn.close()
            raise
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    "UPDATE research_question_attempts SET job_id = ? WHERE id = ?",
                    (job["id"], attempt_id),
                )
        finally:
            conn.close()
        return job

    def record_attempt(
        self,
        attempt_id: str,
        status: str,
        *,
        outcome_note: str = "",
        started_at: str | None = None,
        completed_at: str | None = None,
    ) -> dict[str, Any]:
        if status not in ATTEMPT_STATUSES:
            raise DomainValidation("invalid research question attempt status")
        if len(outcome_note) > 4_000:
            raise DomainValidation("attempt outcome note is too long")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT * FROM research_question_attempts WHERE id = ?", (attempt_id,)).fetchone()
                if row is None:
                    raise DomainNotFound("research question attempt not found")
                if row["status"] in {"succeeded", "partial", "failed", "cancelled"} and status != row["status"]:
                    raise DomainConflict("terminal research question attempt cannot change status")
                started = _validate_time(started_at, "started_at") or row["started_at"]
                completed = _validate_time(completed_at, "completed_at")
                if status in {"succeeded", "partial", "failed", "cancelled"}:
                    completed = completed or utc_now()
                conn.execute(
                    "UPDATE research_question_attempts SET status = ?, outcome_note = ?, started_at = ?, completed_at = ? WHERE id = ?",
                    (status, str(outcome_note).strip(), started, completed, attempt_id),
                )
        finally:
            conn.close()
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM research_question_attempts WHERE id = ?", (attempt_id,)).fetchone()
            return dict(row)
        finally:
            conn.close()

    def pursue_due(self, *, now: str | None = None, limit: int = 25) -> dict[str, Any]:
        if limit < 1 or limit > 100:
            raise DomainValidation("pursuit limit must be between 1 and 100")
        timestamp = _validate_time(now, "now") or utc_now()
        conn = storage.connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT id FROM research_questions WHERE status = 'open' AND deleted_at IS NULL AND next_attempt_at IS NOT NULL AND next_attempt_at <= ? ORDER BY CASE priority WHEN 'urgent' THEN 3 WHEN 'high' THEN 2 WHEN 'normal' THEN 1 ELSE 0 END DESC, next_attempt_at, id LIMIT ?",
                (timestamp, limit),
            ).fetchall()
            identifiers = [row["id"] for row in rows]
        finally:
            conn.close()
        jobs = []
        errors = []
        for identifier in identifiers:
            try:
                jobs.append(self.pursue(identifier, mode="policy"))
            except DomainConflict as exc:
                errors.append({"question_id": identifier, "error": exc.message})
        return {"job_ids": [job["id"] for job in jobs], "errors": errors, "scheduled_count": len(jobs)}

    def review_suggestion(self, identifier: str, status: str, *, reviewed_by: str = "user") -> dict[str, Any]:
        if status not in {"accepted", "rejected"}:
            raise DomainValidation("suggestion review status must be accepted or rejected")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT * FROM research_gap_suggestions WHERE id = ?", (identifier,)).fetchone()
                if row is None:
                    raise DomainNotFound("research gap suggestion not found")
                if row["status"] in {"converted", "rejected"}:
                    raise DomainConflict("research gap suggestion is no longer reviewable")
                conn.execute(
                    "UPDATE research_gap_suggestions SET status = ?, reviewed_at = ?, reviewed_by = ? WHERE id = ?",
                    (status, utc_now(), str(reviewed_by).strip() or "system", identifier),
                )
        finally:
            conn.close()
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM research_gap_suggestions WHERE id = ?", (identifier,)).fetchone()
            return self._suggestion_dict(row)
        finally:
            conn.close()

    def convert_suggestion(self, identifier: str, *, priority: str = "normal", search_attempt_budget: int = 0, actor: str = "user") -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM research_gap_suggestions WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("research gap suggestion not found")
            if row["suggestion_type"] != "question":
                raise DomainValidation("only question suggestions can become Research Questions")
            if row["status"] not in {"pending", "accepted"}:
                raise DomainConflict("research gap suggestion is not convertible")
            data = {
                "question": row["suggestion"],
                "origin_type": row["origin_type"],
                "origin_id": row["origin_id"],
                "priority": priority,
                "search_attempt_budget": search_attempt_budget,
            }
        finally:
            conn.close()
        question = self.create(data, actor=actor)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    "UPDATE research_gap_suggestions SET status = 'converted', question_id = ?, reviewed_at = ?, reviewed_by = ? WHERE id = ?",
                    (question["id"], utc_now(), str(actor).strip() or "system", identifier),
                )
        finally:
            conn.close()
        return question


_SEARCH_TOKEN_RE = re.compile(r"[\w]+(?:[-'][\w]+)*", re.UNICODE)


class ResearchQuestionExecutionService:
    """Allow-listed local Research Question pursuit handler with no recursive enqueue path."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        questions: ResearchQuestionService | None = None,
        search: Any | None = None,
    ):
        self.db_path = Path(db_path)
        self.questions = questions or ResearchQuestionService(db_path)
        self._search = search

    def handlers(self) -> dict[str, Any]:
        return {self.questions.job_type: self.handle}

    def _search_service(self) -> Any:
        if self._search is not None:
            return self._search
        from .workbench import SearchService

        return SearchService(self.db_path)

    @staticmethod
    def _tokens(query: str) -> list[str]:
        seen: set[str] = set()
        tokens: list[str] = []
        for token in _SEARCH_TOKEN_RE.findall(str(query).casefold()):
            if len(token) < 2 or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
        return tokens[:50]

    def _attempt(self, job: Mapping[str, Any], question_id: str) -> dict[str, Any] | None:
        payload = job.get("payload", {})
        payload_attempt_id = payload.get("attempt_id") if isinstance(payload, Mapping) else None
        conn = storage.connect(self.db_path)
        try:
            row = None
            if payload_attempt_id:
                row = conn.execute(
                    "SELECT * FROM research_question_attempts WHERE id = ? AND question_id = ?",
                    (payload_attempt_id, question_id),
                ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM research_question_attempts WHERE job_id = ?", (job["id"],)
                ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM research_question_attempts WHERE question_id = ? AND job_id IS NULL AND status = 'planned' ORDER BY attempt_no DESC, id DESC LIMIT 1",
                    (question_id,),
                ).fetchone()
            return dict(row) if row is not None else None
        finally:
            conn.close()

    def _research(self, question_id: str, query: str, cap: int) -> list[dict[str, Any]]:
        search = self._search_service()
        terms = self._tokens(query)
        if not terms:
            return []
        queries = [" ".join(terms[:6]), *terms[:8]]
        findings: dict[tuple[str, str], dict[str, Any]] = {}
        for candidate in queries:
            if len(findings) >= cap:
                break
            try:
                result = search.search(candidate, entity_types=["claim", "evidence"], page_size=cap)
            except DomainValidation:
                continue
            for item in result.get("items", []):
                key = (item["entity_type"], item["entity_id"])
                if key not in findings:
                    findings[key] = item
                if len(findings) >= cap:
                    break
        return list(findings.values())

    def handle(self, job: Mapping[str, Any]) -> dict[str, Any]:
        """Execute the bounded Research Question pursuit and return its outcome.

        This handler deliberately does NOT commit a terminal attempt state. The
        worker's job completion writes the owning attempt's terminal state in
        the same transaction that terminalizes the durable job, so the attempt
        can never become terminal before the job outcome is durable.
        """
        payload = job.get("payload", {})
        if not isinstance(payload, Mapping):
            raise DomainValidation("research question job payload must be an object")
        question_id = payload.get("research_question_id")
        if not question_id:
            raise DomainValidation("research question job is missing research_question_id")
        question_id = str(question_id)
        attempt = self._attempt(job, question_id)
        if attempt is None:
            raise DomainNotFound("research question attempt not found")
        self.questions.record_attempt(attempt["id"], "running", started_at=utc_now())
        query = str(payload.get("query") or payload.get("question") or attempt.get("query") or "").strip()
        if not query:
            query = str(self.questions.get(question_id).get("question") or "").strip()
        findings = self._research(question_id, query, cap=25)
        claims = [item for item in findings if item["entity_type"] == "claim"]
        evidence = [item for item in findings if item["entity_type"] == "evidence"]
        for item in claims:
            self.questions.link_claim(question_id, item["entity_id"], "contextualizes")
        for item in evidence:
            self.questions.link_evidence(question_id, item["entity_id"], "contextualizes")
        status = "succeeded" if findings else "partial"
        note = f"pursuit linked {len(claims)} claims and {len(evidence)} evidence spans"
        return {
            "research_question_id": question_id,
            "attempt_id": attempt["id"],
            "attempt_status": status,
            "outcome_note": note,
            "query": query,
            "claim_count": len(claims),
            "evidence_count": len(evidence),
        }


def _research_attempt_for_job(conn: sqlite3.Connection, job_row: sqlite3.Row) -> tuple[sqlite3.Row | None, bool]:
    """Locate the Research Question attempt owned by this durable job.

    Returns ``(attempt_row, owned_by_job)``. ``owned_by_job`` is True only when
    the attempt is exactly linked to this durable job via ``job_id``, which is
    sufficient proof to align even a leftover terminal attempt. Payload and
    fallback linkage are weaker and only ever sync non-terminal attempts so that
    historical attempts (for example from a rerun) are never overwritten.
    """
    question_id = job_row["research_question_id"]
    if not question_id:
        return None, False
    row = conn.execute(
        "SELECT * FROM research_question_attempts WHERE job_id = ?",
        (job_row["id"],),
    ).fetchone()
    if row is not None:
        return row, True
    payload_attempt_id = None
    try:
        payload = json.loads(job_row["payload_json"] or "{}")
        payload_attempt_id = payload.get("attempt_id")
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    if isinstance(payload_attempt_id, str) and payload_attempt_id:
        row = conn.execute(
            "SELECT * FROM research_question_attempts WHERE id = ? AND question_id = ?",
            (payload_attempt_id, question_id),
        ).fetchone()
        if row is not None:
            return row, False
    row = conn.execute(
        "SELECT * FROM research_question_attempts WHERE question_id = ? AND job_id IS NULL AND status = 'planned' ORDER BY attempt_no DESC, id DESC LIMIT 1",
        (question_id,),
    ).fetchone()
    return row, False


def reconcile_research_job_outcome(
    conn: sqlite3.Connection,
    job_row: sqlite3.Row,
    final_status: str,
    *,
    error_code: str | None = None,
    error_detail: str | None = None,
    outcome: Mapping[str, Any] | None = None,
    outcome_note: str | None = None,
    timestamp: str | None = None,
) -> None:
    """Deterministically align the owning Research Question attempt with a job outcome.

    This is the authoritative terminalization writer for Research Question
    attempts. It runs inside the same write transaction that terminalizes the
    durable job, so the job and its owning attempt commit or roll back together:
    the attempt can never become terminal before the job outcome is durable.

    ``final_status`` is the durable job's effective post-event status
    (``"queued"`` for a bounded retry, otherwise a terminal status), matching the
    states produced by job completion, lease recovery, cancellation, and
    claim-time budget exhaustion.
    """
    if job_row["job_type"] != RESEARCH_QUESTION_JOB_TYPE:
        return
    attempt, owned = _research_attempt_for_job(conn, job_row)
    if attempt is None:
        return
    if attempt["status"] in TERMINAL_RQ_ATTEMPT_STATUSES and not owned:
        return
    now = timestamp
    if now is None:
        row = conn.execute("SELECT updated_at FROM jobs WHERE id = ?", (job_row["id"],)).fetchone()
        now = row["updated_at"] if row is not None and row["updated_at"] else utc_now()
    if final_status == "queued":
        conn.execute(
            """
            UPDATE research_question_attempts
            SET status = 'planned', outcome_note = ?, started_at = NULL, completed_at = NULL
            WHERE id = ?
            """,
            (outcome_note or "job requeued for another attempt", attempt["id"]),
        )
        return
    if final_status == "succeeded":
        attempt_status = "succeeded"
        if isinstance(outcome, Mapping) and outcome.get("attempt_status") in {"succeeded", "partial"}:
            attempt_status = outcome["attempt_status"]
        note = outcome_note
        if not note and isinstance(outcome, Mapping):
            note = str(outcome.get("outcome_note") or "").strip() or None
        conn.execute(
            "UPDATE research_question_attempts SET status = ?, outcome_note = ?, completed_at = ? WHERE id = ?",
            (attempt_status, note, now, attempt["id"]),
        )
        return
    if final_status == "partial":
        conn.execute(
            "UPDATE research_question_attempts SET status = 'partial', outcome_note = ?, completed_at = ? WHERE id = ?",
            (outcome_note or "pursuit produced partial results", now, attempt["id"]),
        )
        return
    if final_status == "failed":
        note = outcome_note
        if not note:
            note = "durable job failed"
            if error_detail:
                note = f"{note}: {error_detail}"
            elif error_code:
                note = f"{note}: {error_code}"
        conn.execute(
            "UPDATE research_question_attempts SET status = 'failed', outcome_note = ?, completed_at = ? WHERE id = ?",
            (note, now, attempt["id"]),
        )
        return
    if final_status == "cancelled":
        conn.execute(
            "UPDATE research_question_attempts SET status = 'cancelled', outcome_note = ?, completed_at = ? WHERE id = ?",
            (outcome_note or "durable job cancelled", now, attempt["id"]),
        )
        return


def reconcile_recovered_research_job(
    conn: sqlite3.Connection,
    job_row: sqlite3.Row,
    recovered_status: str,
) -> None:
    """Align the owning Research Question attempt with a lease-recovered job outcome.

    Runs inside the job recovery write transaction. Deterministic and idempotent:
    the durable job's recovered state is authoritative for the attempt it owns.
    """
    if job_row["job_type"] != RESEARCH_QUESTION_JOB_TYPE:
        return
    if not job_row["research_question_id"]:
        return
    if recovered_status == "queued":
        note = "lease expired; job requeued"
    elif recovered_status == "failed":
        note = "durable job lease expired"
    elif recovered_status == "cancelled":
        note = "durable job cancelled during recovery"
    else:
        note = None
    reconcile_research_job_outcome(
        conn,
        job_row,
        recovered_status,
        error_code="lease_expired",
        outcome_note=note,
    )


def research_job_recovery_hook(conn: sqlite3.Connection, job_row: sqlite3.Row, recovered_status: str) -> None:
    """Recovery hook that keeps Research Question attempts consistent with lease recovery."""
    reconcile_recovered_research_job(conn, job_row, recovered_status)


def research_job_rerun_factory(db_path: str | Path, job: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Rebuild a terminal Research Question job as a fresh owned attempt.

    Returns ``None`` for any other job type so JobService falls back to its
    generic clone semantics. For a research_question job it refuses with a clear
    domain diagnostic whenever the rerun would be doomed: the owning question is
    missing, the payload has no attempt identity, the question is not open, or
    the question's configured budgets cannot fund another attempt. The new
    attempt is created by the normal pursuit path, so it owns exactly one new
    durable job with deterministic ownership metadata and the historical
    terminal attempt is never reopened or mutated.
    """
    if job.get("job_type") != RESEARCH_QUESTION_JOB_TYPE:
        return None
    payload = job.get("payload") or {}
    if not isinstance(payload, Mapping):
        raise DomainValidation("research question job payload must be an object")
    question_id = str(payload.get("research_question_id") or "").strip()
    if not question_id:
        raise DomainConflict("research question job payload has no research_question_id; cannot rerun")
    if not str(payload.get("attempt_id") or "").strip():
        raise DomainConflict("research question job payload has no attempt_id; cannot rerun")
    budget = payload.get("budget") or {}
    budget = budget if isinstance(budget, Mapping) else {}
    return ResearchQuestionService(db_path).pursue(
        question_id,
        mode=str(payload.get("mode") or "manual"),
        query_units=budget.get("acquisition_units", 0),
        local_model_units=budget.get("local_model_units", 0),
        estimated_cost_usd=budget.get("usd", 0.0),
        query=payload.get("query"),
    )


def research_job_completion_hook(
    conn: sqlite3.Connection,
    job_row: sqlite3.Row,
    job_status: str,
    context: Mapping[str, Any] | None = None,
) -> None:
    """Completion hook that keeps Research Question attempts consistent with job completion.

    Runs inside the same write transaction that terminalizes the durable job, so
    the job and its owning attempt always finish in consistent states. Called by
    JobService for completion, cancellation of a queued job, and claim-time
    budget exhaustion; it is a no-op for any other job type. Research Question
    reconciliation lives here and Monitor reconciliation lives in
    ``monitoring.monitor_job_completion_hook``; a central composition point in
    the production wiring runs both hooks for the same completion event.
    """
    ctx = dict(context or {})
    trigger = str(ctx.get("trigger", "complete"))
    error_code = ctx.get("error_code")
    error_detail = ctx.get("error_detail")
    outcome = ctx.get("outcome")
    if job_status == "queued":
        note = f"attempt failed; job will retry{': ' + str(error_detail) if error_detail else ''}"
    elif job_status == "failed":
        if trigger == "budget":
            note = f"job not claimed: {error_code or 'budget_exhausted'}"
        else:
            note = f"research execution failed: {error_code or 'unknown'}"
            if error_detail:
                note = f"{note}: {error_detail}"
    elif job_status == "cancelled":
        reason = str(job_row["failure_cause"] or error_code or "").strip()
        note = f"durable job cancelled{': ' + reason if reason and reason != 'cancelled' else ''}"
    else:
        note = None
    reconcile_research_job_outcome(
        conn,
        job_row,
        job_status,
        error_code=error_code,
        error_detail=error_detail,
        outcome=outcome if isinstance(outcome, Mapping) else None,
        outcome_note=note,
    )


__all__ = [
    "ATTEMPT_MODES",
    "ATTEMPT_STATUSES",
    "LINK_RELATIONSHIPS",
    "NOTE_TYPES",
    "QUESTION_ORIGINS",
    "QUESTION_PRIORITIES",
    "QUESTION_STATUSES",
    "reconcile_recovered_research_job",
    "reconcile_research_job_outcome",
    "research_job_completion_hook",
    "research_job_rerun_factory",
    "ResearchQuestionExecutionService",
    "ResearchQuestionService",
    "research_job_recovery_hook",
    "SUGGESTION_STATUSES",
    "SUGGESTION_TYPES",
    "TERMINAL_RQ_ATTEMPT_STATUSES",
]
