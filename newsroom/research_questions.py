"""Durable Research Question lifecycle and evidence-gap services.

Research Questions are intentionally separate from Claims. A question or user
hypothesis can guide bounded follow-up work, but it never becomes accepted
evidence without the normal Evidence Ledger path.
"""
from __future__ import annotations

import json
import hashlib
import re
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from . import storage
from .domain import DomainConflict, DomainNotFound, DomainValidation, new_id, utc_now
from .jobs import RESEARCH_QUESTION_JOB_TYPE


QUESTION_STATUSES = frozenset({"open", "resolved", "abandoned"})
ASSESSMENT_STATES = frozenset({"open", "partially_answered", "supported", "contradicted", "resolved", "stale"})
QUESTION_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})
QUESTION_ORIGINS = frozenset({"story", "claim", "subject", "user", "monitor"})
LINK_RELATIONSHIPS = frozenset({"supports", "contradicts", "contextualizes", "resolves"})
NOTE_TYPES = frozenset({"note", "hypothesis"})
ATTEMPT_MODES = frozenset({"manual", "policy"})
ATTEMPT_STATUSES = frozenset({"planned", "running", "succeeded", "partial", "failed", "cancelled"})
TERMINAL_RQ_ATTEMPT_STATUSES = frozenset({"succeeded", "partial", "failed", "cancelled"})
SUGGESTION_TYPES = frozenset({"question", "search", "source"})
SUGGESTION_STATUSES = frozenset({"pending", "accepted", "rejected", "converted"})
GAP_TYPES = frozenset({"supporting_evidence", "contradiction_review", "independent_support", "primary_source"})
GAP_STATUSES = frozenset({"open", "pursuing", "satisfied", "dismissed", "blocked"})
RESEARCH_TASK_STATUSES = frozenset({
    "planned", "running", "completed_with_evidence", "completed_with_candidates",
    "completed_no_findings", "deferred", "failed", "cancelled",
})
RESEARCH_TASK_TERMINAL_STATUSES = frozenset({
    "completed_with_evidence", "completed_with_candidates", "completed_no_findings",
    "failed", "cancelled",
})
DEFAULT_TASK_LIMITS = {
    "max_queries": 12,
    "max_provider_calls": 1,
    "max_candidates": 25,
    "max_documents": 5,
    "max_runtime_seconds": 120,
    "max_retries": 0,
    "max_discovery_depth": 0,
}
_ASSESSMENT_STOPWORDS = frozenset(
    "a an and are as at be been but by can could did do does for from has have how in is it of on or that the this to was were what when where which who why will with would".split()
)


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


def _plus_seconds(timestamp: str, seconds: int) -> str:
    value = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return (value + timedelta(seconds=max(0, seconds))).isoformat().replace("+00:00", "Z")


def _bounded_text(value: Any, label: str, maximum: int) -> str:
    result = str(value or "").strip()
    if len(result) > maximum:
        raise DomainValidation(f"{label} is too long")
    return result


def _criteria(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise DomainValidation("research question criteria must be an object")
    if len(value) > 12:
        raise DomainValidation("research question criteria is too large")
    result: dict[str, Any] = {}
    for key, item in value.items():
        key = str(key).strip()
        if not key or len(key) > 80:
            raise DomainValidation("research question criteria contains an invalid key")
        if isinstance(item, bool):
            result[key] = item
        elif isinstance(item, int) and not isinstance(item, bool) and 0 <= item <= 100:
            result[key] = item
        elif isinstance(item, str) and len(item) <= 300:
            result[key] = item.strip()
        else:
            raise DomainValidation("research question criteria contains an invalid value")
    return result


def _task_limits(value: Any) -> dict[str, int]:
    raw = value if isinstance(value, Mapping) else {}
    limits: dict[str, int] = {}
    for key, default in DEFAULT_TASK_LIMITS.items():
        item = raw.get(key, default)
        limits[key] = _nonnegative_int(item, key)
        if limits[key] > (1000 if key != "max_runtime_seconds" else 3600):
            raise DomainValidation(f"{key} exceeds the supported bound")
    if limits["max_queries"] < 1 or limits["max_candidates"] < 1 or limits["max_documents"] < 1:
        raise DomainValidation("task query, candidate, and document limits must be positive")
    return limits


class ResearchQuestionService:
    """Own short SQLite transactions for Research Questions and gap work."""

    job_type = RESEARCH_QUESTION_JOB_TYPE

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @staticmethod
    def _gap_dict(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["condition"] = _decode(result.pop("condition_json", None))
        return result

    @staticmethod
    def _task_dict(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for source, target in (("plan_json", "plan"), ("limits_json", "limits"), ("outcome_json", "outcome")):
            result[target] = _decode(result.pop(source, None))
        return result

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
        criteria = _criteria(data.get("criteria"))
        pursuit_policy = str(data.get("pursuit_policy", "manual")).strip()
        if pursuit_policy not in {"disabled", "manual", "automatic"}:
            raise DomainValidation("invalid research question pursuit policy")
        cooldown = _nonnegative_int(data.get("pursuit_cooldown_seconds", 3600), "pursuit_cooldown_seconds")
        if cooldown > 31_536_000:
            raise DomainValidation("pursuit_cooldown_seconds exceeds the supported bound")
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
                         paid_budget_usd, criteria_json, pursuit_policy,
                         pursuit_cooldown_seconds)
                    VALUES (?, ?, ?, ?, 'open', ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (identifier, question, origin_type, origin_id, priority, attempts, next_attempt, now, now, queries, local_units, paid, _json(criteria), pursuit_policy, cooldown),
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
        self.evaluate(identifier)
        return self.get(identifier)

    def get(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = self._require(conn, identifier)
            if conn.execute(
                "SELECT 1 FROM research_question_assessments WHERE question_id = ? LIMIT 1",
                (identifier,),
            ).fetchone() is None:
                # Migration 0025 is intentionally additive and does not
                # fabricate historical transitions.  Lazily materialize the
                # first deterministic assessment when an upgraded legacy
                # Question is first read.
                conn.close()
                self.evaluate(identifier)
                conn = storage.connect(self.db_path)
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
            result["criteria"] = _decode(result.get("criteria_json"))
            result["assessment_history"] = [
                dict(item)
                for item in conn.execute(
                    "SELECT * FROM research_question_assessment_history WHERE question_id = ? ORDER BY created_at, id",
                    (identifier,),
                ).fetchall()
            ]
            result["assessments"] = [
                dict(item)
                for item in conn.execute(
                    "SELECT * FROM research_question_assessments WHERE question_id = ? ORDER BY created_at, id",
                    (identifier,),
                ).fetchall()
            ]
            result["gaps"] = [self._gap_dict(item) for item in conn.execute(
                "SELECT * FROM research_question_gaps WHERE question_id = ? ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'pursuing' THEN 1 WHEN 'blocked' THEN 2 WHEN 'satisfied' THEN 3 ELSE 4 END, created_at, id",
                (identifier,),
            ).fetchall()]
            result["tasks"] = [self._task_dict(item) for item in conn.execute(
                "SELECT * FROM research_tasks WHERE question_id = ? ORDER BY task_no, id",
                (identifier,),
            ).fetchall()]
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
        allowed = {
            "question", "priority", "search_attempt_budget", "query_budget", "local_model_budget",
            "paid_budget_usd", "next_attempt_at", "criteria", "pursuit_policy", "pursuit_cooldown_seconds",
        }
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
                if "criteria" in data:
                    values["criteria_json"] = _json(_criteria(data["criteria"]))
                if "pursuit_policy" in data:
                    value = str(data["pursuit_policy"]).strip()
                    if value not in {"disabled", "manual", "automatic"}:
                        raise DomainValidation("invalid research question pursuit policy")
                    values["pursuit_policy"] = value
                if "pursuit_cooldown_seconds" in data:
                    value = _nonnegative_int(data["pursuit_cooldown_seconds"], "pursuit_cooldown_seconds")
                    if value > 31_536_000:
                        raise DomainValidation("pursuit_cooldown_seconds exceeds the supported bound")
                    values["pursuit_cooldown_seconds"] = value
                assignments = ", ".join(f"{field} = ?" for field in values)
                conn.execute(
                    f"UPDATE research_questions SET {assignments}, updated_at = ? WHERE id = ?",
                    [*values.values(), utc_now(), identifier],
                )
                if "question" in values and values["question"] != current["question"]:
                    from .monitoring import MonitorService

                    MonitorService._refresh_need_scopes_tx(
                        conn,
                        "research_question",
                        identifier,
                        changed_by=data.get("changed_by"),
                        change_type="approved",
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

    @staticmethod
    def _claim_has_qualifying_evidence(conn: sqlite3.Connection, claim_id: str) -> bool:
        return conn.execute(
            """
            SELECT 1
            FROM claim_evidence AS ce
            JOIN evidence_spans AS es ON es.id = ce.evidence_span_id
            WHERE ce.claim_id = ? AND ce.relationship IN ('supports','contradicts')
            LIMIT 1
            """,
            (claim_id,),
        ).fetchone() is not None

    @staticmethod
    def _question_terms(value: str) -> list[str]:
        seen: set[str] = set()
        terms: list[str] = []
        for token in re.findall(r"[\w]+", str(value).casefold()):
            if len(token) < 3 or token in _ASSESSMENT_STOPWORDS or token in seen:
                continue
            seen.add(token)
            terms.append(token)
        return terms[:25]

    def _auto_link_claims_tx(self, conn: sqlite3.Connection, question: sqlite3.Row) -> None:
        """Add only conservative, evidence-bearing automatic relationships.

        Lexical overlap selects candidates; canonical Claim/Evidence state is
        required before anything can count as support or contradiction.  A
        broad match is retained as contextual rather than promoted.
        """
        terms = set(self._question_terms(question["question"]))
        if not terms:
            return
        candidates = conn.execute(
            """
            SELECT * FROM claims
            WHERE state IN ('supported','partially_supported','disputed')
            ORDER BY created_at, id
            LIMIT 100
            """
        ).fetchall()
        question_negative = bool(terms.intersection({"not", "never", "false", "without", "denied"}))
        for claim in candidates:
            proposition_terms = set(re.findall(r"[\w]+", claim["proposition"].casefold()))
            overlap = terms.intersection(proposition_terms)
            threshold = max(1, (len(terms) + 2) // 3)
            if len(overlap) < threshold:
                continue
            if not self._claim_has_qualifying_evidence(conn, claim["id"]):
                continue
            existing = conn.execute(
                "SELECT 1 FROM research_question_claims WHERE question_id = ? AND claim_id = ? LIMIT 1",
                (question["id"], claim["id"]),
            ).fetchone()
            if existing is not None:
                continue
            claim_negative = bool(proposition_terms.intersection({"not", "never", "false", "without", "denied"}))
            if claim_negative != question_negative:
                relationship = "contradicts"
            elif len(overlap) >= max(2, (len(terms) + 1) // 2):
                relationship = "supports"
            else:
                relationship = "contextualizes"
            confidence = min(1.0, max(0.35, len(overlap) / max(1, len(terms))))
            conn.execute(
                """
                INSERT OR IGNORE INTO research_question_claims
                    (question_id, claim_id, relationship, created_at, origin, confidence, rationale, actor)
                VALUES (?, ?, ?, ?, 'automatic', ?, ?, 'system')
                """,
                (
                    question["id"], claim["id"], relationship, utc_now(), confidence,
                    "bounded lexical overlap with canonical evidence-bearing Claim",
                ),
            )

    def _evaluate_tx(self, conn: sqlite3.Connection, identifier: str, *, origin: str = "automatic") -> dict[str, Any]:
        question = self._require(conn, identifier)
        self._auto_link_claims_tx(conn, question)

        overrides: dict[tuple[str, str], str] = {}
        for row in conn.execute(
            "SELECT claim_id, relationship, action FROM research_question_claim_overrides WHERE question_id = ? ORDER BY created_at, id",
            (identifier,),
        ):
            overrides[(row["claim_id"], row["relationship"])] = row["action"]

        supporting_claim_ids: list[str] = []
        contradicting_claim_ids: list[str] = []
        contextual_claim_ids: list[str] = []
        qualifying_evidence_ids: set[str] = set()
        source_ids: set[str] = set()
        primary_source_ids: set[str] = set()
        for link in conn.execute(
            "SELECT l.*, c.state FROM research_question_claims AS l JOIN claims AS c ON c.id = l.claim_id WHERE l.question_id = ? ORDER BY l.created_at, l.claim_id, l.relationship",
            (identifier,),
        ):
            if overrides.get((link["claim_id"], link["relationship"])) == "exclude":
                continue
            evidence = conn.execute(
                """
                SELECT ce.evidence_span_id, d.source_id, s.default_quality, s.source_kind
                FROM claim_evidence AS ce
                JOIN evidence_spans AS es ON es.id = ce.evidence_span_id
                JOIN document_versions AS dv ON dv.id = es.document_version_id
                JOIN documents AS d ON d.id = dv.document_id
                JOIN sources AS s ON s.id = d.source_id
                WHERE ce.claim_id = ? AND ce.relationship IN ('supports','contradicts')
                ORDER BY ce.created_at, ce.id
                """,
                (link["claim_id"],),
            ).fetchall()
            for evidence_row in evidence:
                qualifying_evidence_ids.add(evidence_row["evidence_span_id"])
                source_ids.add(evidence_row["source_id"])
                if evidence_row["default_quality"] == "primary" or evidence_row["source_kind"] == "official":
                    primary_source_ids.add(evidence_row["source_id"])
            qualified = bool(evidence) and link["state"] in {"supported", "partially_supported", "disputed"}
            relationship = "supports" if link["relationship"] == "resolves" else link["relationship"]
            if relationship == "supports" and qualified and link["state"] in {"supported", "partially_supported"}:
                supporting_claim_ids.append(link["claim_id"])
            elif relationship == "contradicts" and qualified:
                contradicting_claim_ids.append(link["claim_id"])
            else:
                contextual_claim_ids.append(link["claim_id"])

        for link in conn.execute(
            "SELECT * FROM research_question_evidence WHERE question_id = ? ORDER BY created_at, evidence_span_id, relationship",
            (identifier,),
        ):
            evidence_row = conn.execute(
                """
                SELECT es.id, d.source_id, s.default_quality, s.source_kind
                FROM evidence_spans AS es
                JOIN document_versions AS dv ON dv.id = es.document_version_id
                JOIN documents AS d ON d.id = dv.document_id
                JOIN sources AS s ON s.id = d.source_id
                WHERE es.id = ?
                """,
                (link["evidence_span_id"],),
            ).fetchone()
            if evidence_row is None:
                continue
            qualifying_evidence_ids.add(evidence_row["id"])
            source_ids.add(evidence_row["source_id"])
            if evidence_row["default_quality"] == "primary" or evidence_row["source_kind"] == "official":
                primary_source_ids.add(evidence_row["source_id"])
            relationship = "supports" if link["relationship"] == "resolves" else link["relationship"]
            if relationship == "supports":
                supporting_claim_ids.append(f"evidence:{link['evidence_span_id']}")
            elif relationship == "contradicts":
                contradicting_claim_ids.append(f"evidence:{link['evidence_span_id']}")

        criteria = _decode(question["criteria_json"])
        min_support = max(1, int(criteria.get("min_supporting_claims", 1) or 1))
        min_independent = max(0, int(criteria.get("min_independent_sources", 0) or 0))
        require_primary = bool(criteria.get("require_primary_source", False))
        support_count = len(set(supporting_claim_ids))
        contradiction_count = len(set(contradicting_claim_ids))
        if question["status"] == "resolved":
            state = "resolved"
        elif question["status"] == "abandoned":
            state = "stale"
        elif support_count and contradiction_count:
            state = "partially_answered"
        elif contradiction_count:
            state = "contradicted"
        elif support_count:
            state = "supported"
        else:
            state = "open"

        desired: list[tuple[str, str, str, str, dict[str, Any], bool]] = []
        support_qualifies = support_count >= min_support
        desired.append((
            f"supporting_evidence:{min_support}", "supporting_evidence",
            f"At least {min_support} qualifying supporting Claim or Evidence relationship",
            "The Question has not reached its configured supporting-evidence threshold.",
            {"minimum": min_support}, support_qualifies,
        ))
        if contradiction_count and not support_count:
            desired.append((
                "contradiction_review:current", "contradiction_review",
                "A contradictory Claim or Evidence relationship requires review",
                "Canonical evidence currently points against the Question without qualifying support.",
                {"minimum_supporting_claims": min_support}, False,
            ))
        if min_independent:
            independent_qualifies = len(source_ids) >= min_independent
            desired.append((
                f"independent_support:{min_independent}", "independent_support",
                f"Support from at least {min_independent} independent Source(s)",
                "The configured independent-source threshold has not been met.",
                {"minimum": min_independent}, independent_qualifies,
            ))
        if require_primary:
            desired.append((
                "primary_source:required", "primary_source",
                "A qualifying primary or official Source is required",
                "No qualifying primary or official Source is linked yet.",
                {"required": True}, bool(primary_source_ids),
            ))

        snapshot_payload = {
            "question": question["question"],
            "status": question["status"],
            "criteria": criteria,
            "supporting": sorted(set(supporting_claim_ids)),
            "contradicting": sorted(set(contradicting_claim_ids)),
            "contextual": sorted(set(contextual_claim_ids)),
            "evidence": sorted(qualifying_evidence_ids),
        }
        snapshot_hash = hashlib.sha256(_json(snapshot_payload).encode("utf-8")).hexdigest()
        explanation = (
            f"{support_count} qualifying supporting relationship(s), "
            f"{contradiction_count} qualifying contradictory relationship(s), "
            f"{len(contextual_claim_ids)} contextual relationship(s)."
        )
        now = utc_now()
        conn.execute(
            """
            INSERT OR IGNORE INTO research_question_assessments
                (id, question_id, snapshot_hash, state, explanation,
                 supporting_claim_count, contradicting_claim_count,
                 contextual_claim_count, qualifying_evidence_count,
                 open_gap_count, origin, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                new_id("rqa"), identifier, snapshot_hash, state, explanation,
                support_count, contradiction_count, len(contextual_claim_ids),
                len(qualifying_evidence_ids), origin, now,
            ),
        )
        assessment = conn.execute(
            "SELECT * FROM research_question_assessments WHERE question_id = ? AND snapshot_hash = ?",
            (identifier, snapshot_hash),
        ).fetchone()
        previous_state = question["assessment_state"]
        if assessment is not None and previous_state != state:
            conn.execute(
                """
                INSERT OR IGNORE INTO research_question_assessment_history
                    (id, question_id, assessment_id, from_state, to_state,
                     reason_code, claim_ids_json, origin, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("rqah"), identifier, assessment["id"], previous_state,
                    state, "canonical_evidence_reassessment", _json(sorted(set(supporting_claim_ids + contradicting_claim_ids))),
                    origin, now,
                ),
            )

        for gap_key, gap_type, description, rationale, condition, qualifies in desired:
            existing = conn.execute(
                "SELECT * FROM research_question_gaps WHERE question_id = ? AND gap_key = ?",
                (identifier, gap_key),
            ).fetchone()
            if existing is None:
                gap_id = new_id("rqg")
                conn.execute(
                    """
                    INSERT INTO research_question_gaps
                        (id, question_id, gap_key, gap_type, description, rationale,
                         condition_json, status, origin, assessment_hash,
                         first_seen_at, last_evaluated_at, satisfied_at,
                         created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'automatic', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        gap_id, identifier, gap_key, gap_type, description, rationale,
                        _json(condition), "satisfied" if qualifies else "open", snapshot_hash,
                        now, now, now if qualifies else None, now, now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO research_question_gap_history
                        (id, gap_id, from_status, to_status, reason_code,
                         assessment_hash, actor, created_at)
                    VALUES (?, ?, NULL, ?, ?, ?, 'system', ?)
                    """,
                    (new_id("rqgh"), gap_id, "satisfied" if qualifies else "open", "initial_assessment", snapshot_hash, now),
                )
                continue
            target_status = existing["status"]
            if existing["status"] == "dismissed":
                target_status = "dismissed"
            elif qualifies and existing["status"] in {"open", "pursuing", "blocked"}:
                target_status = "satisfied"
            elif not qualifies and existing["status"] == "satisfied":
                target_status = "open"
            if target_status != existing["status"]:
                conn.execute(
                    """
                    INSERT INTO research_question_gap_history
                        (id, gap_id, from_status, to_status, reason_code,
                         assessment_hash, actor, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'system', ?)
                    """,
                    (new_id("rqgh"), existing["id"], existing["status"], target_status,
                     "qualifying_evidence" if qualifies else "condition_not_met", snapshot_hash, now),
                )
            conn.execute(
                """
                UPDATE research_question_gaps
                   SET status = ?, assessment_hash = ?, last_evaluated_at = ?,
                       satisfied_at = CASE WHEN ? = 'satisfied' THEN COALESCE(satisfied_at, ?) ELSE NULL END,
                       updated_at = ?
                 WHERE id = ?
             """,
                (target_status, snapshot_hash, now, target_status, now, now, existing["id"]),
            )

        open_gap_count = conn.execute(
            "SELECT COUNT(*) FROM research_question_gaps WHERE question_id = ? AND status IN ('open','pursuing')",
            (identifier,),
        ).fetchone()[0]
        conn.execute(
            """
            UPDATE research_question_assessments
               SET open_gap_count = ?
               WHERE id = ?
            """,
            (open_gap_count, assessment["id"]),
        )
        conn.execute(
            """
            UPDATE research_questions
               SET assessment_state = ?, assessment_hash = ?,
                   assessment_explanation = ?, assessment_at = ?, updated_at = ?
             WHERE id = ?
            """,
            (state, snapshot_hash, explanation, now, now, identifier),
        )
        # Canonical evidence can arrive after a Research Task has already
        # recorded candidate material (for example when the normal document
        # processing worker promotes a verified Claim later).  Reconcile that
        # durable task projection without allowing a stale task to overwrite
        # the current evidence-grounded result.
        conn.execute(
            """
            UPDATE research_tasks
               SET status = 'completed_with_evidence',
                   completed_at = COALESCE(completed_at, ?),
                   updated_at = ?
             WHERE question_id = ?
               AND status = 'completed_with_candidates'
               AND gap_id IN (
                   SELECT id FROM research_question_gaps
                   WHERE question_id = ? AND status = 'satisfied'
               )
            """,
            (now, now, identifier, identifier),
        )
        return {
            "question_id": identifier,
            "state": state,
            "snapshot_hash": snapshot_hash,
            "explanation": explanation,
            "supporting_claim_ids": sorted(set(supporting_claim_ids)),
            "contradicting_claim_ids": sorted(set(contradicting_claim_ids)),
            "contextual_claim_ids": sorted(set(contextual_claim_ids)),
            "qualifying_evidence_count": len(qualifying_evidence_ids),
            "open_gap_count": open_gap_count,
        }

    def evaluate(self, identifier: str, *, origin: str = "automatic") -> dict[str, Any]:
        if origin not in {"automatic", "manual"}:
            raise DomainValidation("invalid research question assessment origin")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                result = self._evaluate_tx(conn, identifier, origin=origin)
            return result
        finally:
            conn.close()

    def reevaluate_for_claim(self, claim_id: str, *, limit: int = 50) -> dict[str, Any]:
        """Reevaluate bounded Question candidates after trusted Claim changes."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise DomainValidation("claim reevaluation limit must be between 1 and 100")
        conn = storage.connect(self.db_path)
        try:
            self._require_claim(conn, claim_id)
            rows = conn.execute(
                """
                SELECT id FROM research_questions
                WHERE deleted_at IS NULL AND status = 'open'
                ORDER BY CASE priority WHEN 'urgent' THEN 3 WHEN 'high' THEN 2 WHEN 'normal' THEN 1 ELSE 0 END DESC, id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            identifiers = [row["id"] for row in rows]
        finally:
            conn.close()
        results = [self.evaluate(identifier) for identifier in identifiers]
        return {"claim_id": claim_id, "evaluated_count": len(results), "question_ids": identifiers}

    def list_gaps(self, identifier: str, *, status: str | None = None, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        if status is not None and status not in GAP_STATUSES:
            raise DomainValidation("invalid research question gap status")
        if page < 1 or page_size < 1 or page_size > 200:
            raise DomainValidation("invalid research question gap page")
        conn = storage.connect(self.db_path)
        try:
            self._require(conn, identifier)
            clauses = ["question_id = ?"]
            params: list[Any] = [identifier]
            if status is not None:
                clauses.append("status = ?")
                params.append(status)
            where = " AND ".join(clauses)
            total = conn.execute(f"SELECT COUNT(*) FROM research_question_gaps WHERE {where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM research_question_gaps WHERE {where} ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
            return {"items": [self._gap_dict(row) for row in rows], "page": page, "page_size": page_size, "total": total}
        finally:
            conn.close()

    def list_tasks(self, identifier: str, *, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        if page < 1 or page_size < 1 or page_size > 200:
            raise DomainValidation("invalid research task page")
        conn = storage.connect(self.db_path)
        try:
            self._require(conn, identifier)
            total = conn.execute("SELECT COUNT(*) FROM research_tasks WHERE question_id = ?", (identifier,)).fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM research_tasks WHERE question_id = ? ORDER BY task_no DESC, id DESC LIMIT ? OFFSET ?",
                (identifier, page_size, (page - 1) * page_size),
            ).fetchall()
            return {"items": [self._task_dict(row) for row in rows], "page": page, "page_size": page_size, "total": total}
        finally:
            conn.close()

    def get_task(self, identifier: str, task_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            self._require(conn, identifier)
            row = conn.execute(
                "SELECT * FROM research_tasks WHERE id = ? AND question_id = ?",
                (task_id, identifier),
            ).fetchone()
            if row is None:
                raise DomainNotFound("research task not found")
            result = self._task_dict(row)
            result["queries"] = [
                dict(item) for item in conn.execute(
                    "SELECT id, query, query_hash, strategy, ordinal, created_at FROM research_task_queries WHERE task_id = ? ORDER BY ordinal, id LIMIT 100",
                    (task_id,),
                ).fetchall()
            ]
            result["findings"] = []
            for item in conn.execute(
                "SELECT id, finding_type, identity_key, status, source_id, document_id, document_version_id, claim_id, evidence_span_id, rank, metadata_json, created_at, updated_at FROM research_task_findings WHERE task_id = ? ORDER BY rank, created_at, id LIMIT 100",
                (task_id,),
            ):
                finding = dict(item)
                finding["metadata"] = _decode(finding.pop("metadata_json", None))
                result["findings"].append(finding)
            return result
        finally:
            conn.close()

    def set_gap_status(
        self,
        gap_id: str,
        status: str,
        *,
        question_id: str | None = None,
        actor: str = "user",
        reason: str = "",
    ) -> dict[str, Any]:
        if status not in {"dismissed", "open"}:
            raise DomainValidation("gap status may only be dismissed or open manually")
        reason = _bounded_text(reason, "gap reason", 4_000)
        if not reason:
            raise DomainValidation("gap reason is required")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                gap = conn.execute("SELECT * FROM research_question_gaps WHERE id = ?", (gap_id,)).fetchone()
                if gap is None:
                    raise DomainNotFound("research question gap not found")
                if question_id is not None and gap["question_id"] != question_id:
                    raise DomainNotFound("research question gap not found")
                if gap["status"] == status:
                    raise DomainConflict("gap is already in that status")
                now = utc_now()
                conn.execute(
                    "UPDATE research_question_gaps SET status = ?, dismissed_at = ?, dismissed_by = ?, dismissal_reason = ?, updated_at = ? WHERE id = ?",
                    (status, now if status == "dismissed" else None, str(actor).strip() or "user" if status == "dismissed" else None, reason if status == "dismissed" else None, now, gap_id),
                )
                conn.execute(
                    "INSERT INTO research_question_gap_history(id, gap_id, from_status, to_status, reason_code, actor, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (new_id("rqgh"), gap_id, gap["status"], status, "manual_review", str(actor).strip() or "user", now),
                )
                question_id = gap["question_id"]
        finally:
            conn.close()
        self.evaluate(question_id, origin="manual")
        conn = storage.connect(self.db_path)
        try:
            return self._gap_dict(conn.execute("SELECT * FROM research_question_gaps WHERE id = ?", (gap_id,)).fetchone())
        finally:
            conn.close()

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

    def link_claim(
        self,
        identifier: str,
        claim_id: str,
        relationship: str = "resolves",
        *,
        origin: str = "manual",
        actor: str = "user",
        rationale: str = "",
    ) -> dict[str, Any]:
        if relationship not in LINK_RELATIONSHIPS:
            raise DomainValidation("invalid research question claim relationship")
        if origin not in {"manual", "automatic", "task"}:
            raise DomainValidation("invalid research question claim link origin")
        rationale = _bounded_text(rationale, "claim link rationale", 2_000)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, identifier)
                self._require_claim(conn, claim_id)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO research_question_claims
                        (question_id, claim_id, relationship, created_at, origin,
                         confidence, rationale, actor)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (identifier, claim_id, relationship, utc_now(), origin, 1.0 if origin == "manual" else 0.75, rationale, str(actor).strip() or "system"),
                )
        finally:
            conn.close()
        self.evaluate(identifier, origin="manual" if origin == "manual" else "automatic")
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
        self.evaluate(identifier, origin="manual")
        return self.get(identifier)

    def correct_claim_link(
        self,
        identifier: str,
        claim_id: str,
        relationship: str,
        *,
        action: str = "exclude",
        actor: str = "user",
        reason: str = "",
    ) -> dict[str, Any]:
        if relationship not in LINK_RELATIONSHIPS:
            raise DomainValidation("invalid research question claim relationship")
        if action not in {"exclude", "restore"}:
            raise DomainValidation("claim link action must be exclude or restore")
        reason = _bounded_text(reason, "claim correction reason", 2_000)
        if not reason:
            raise DomainValidation("claim correction reason is required")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, identifier)
                self._require_claim(conn, claim_id)
                existing = conn.execute(
                    "SELECT 1 FROM research_question_claims WHERE question_id = ? AND claim_id = ? AND relationship = ?",
                    (identifier, claim_id, relationship),
                ).fetchone()
                if existing is None:
                    raise DomainNotFound("research question claim link not found")
                conn.execute(
                    "INSERT OR IGNORE INTO research_question_claim_overrides(id, question_id, claim_id, relationship, action, reason, actor, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_id("rqco"), identifier, claim_id, relationship, action, reason, str(actor).strip() or "user", utc_now()),
                )
        finally:
            conn.close()
        self.evaluate(identifier, origin="manual")
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
        gap_id: str | None = None,
        limits: Mapping[str, Any] | None = None,
        allow_active_replay: bool = False,
    ) -> dict[str, Any]:
        """Create one bounded Research Task and enqueue its existing Job type."""
        if mode not in ATTEMPT_MODES:
            raise DomainValidation("invalid research question pursuit mode")
        query_units = _nonnegative_int(query_units, "query_units")
        local_model_units = _nonnegative_int(local_model_units, "local_model_units")
        estimated_cost_usd = _nonnegative_float(estimated_cost_usd, "estimated_cost_usd")
        if query is not None and len(str(query)) > 4_000:
            raise DomainValidation("query is too long")
        task_limits = _task_limits(limits)
        now = utc_now()
        conn = storage.connect(self.db_path)
        attempt_id = new_id("rqa")
        task_id = new_id("rqt")
        try:
            with storage.write_tx(conn):
                question = self._require(conn, identifier)
                if question["status"] != "open":
                    raise DomainConflict("only open research questions can be pursued")
                if mode == "policy":
                    if question["pursuit_policy"] == "disabled":
                        raise DomainConflict("automatic research pursuit is disabled for this question")
                    if question["next_attempt_at"] and question["next_attempt_at"] > now:
                        raise DomainConflict("research pursuit cooldown has not elapsed")
                attempts_used, queries_used, local_used, paid_used = self._attempt_summary(conn, identifier)
                if attempts_used >= question["search_attempt_budget"]:
                    raise DomainConflict("research question attempt budget exhausted")
                if queries_used + query_units > question["query_budget"]:
                    raise DomainConflict("research question query budget exhausted")
                if local_used + local_model_units > question["local_model_budget"]:
                    raise DomainConflict("research question local-model budget exhausted")
                if paid_used + estimated_cost_usd > float(question["paid_budget_usd"]) + 1e-12:
                    raise DomainConflict("research question cost budget exhausted")
                self._evaluate_tx(conn, identifier)
                if gap_id is None:
                    gap = conn.execute(
                        "SELECT * FROM research_question_gaps WHERE question_id = ? AND status = 'open' ORDER BY created_at, id LIMIT 1",
                        (identifier,),
                    ).fetchone()
                    if gap is None and mode == "manual":
                        gap = conn.execute(
                            "SELECT * FROM research_question_gaps WHERE question_id = ? AND status IN ('satisfied','blocked','pursuing') ORDER BY created_at, id LIMIT 1",
                            (identifier,),
                        ).fetchone()
                else:
                    gap = conn.execute(
                        "SELECT * FROM research_question_gaps WHERE id = ? AND question_id = ? AND status <> 'dismissed'",
                        (gap_id, identifier),
                    ).fetchone()
                if gap is None:
                    raise DomainNotFound("research question gap not found")
                active = conn.execute(
                    "SELECT * FROM research_tasks WHERE gap_id = ? AND status IN ('planned','running') LIMIT 1",
                    (gap["id"],),
                ).fetchone()
                if active is not None:
                    if allow_active_replay:
                        conn.execute(
                            "UPDATE research_tasks SET status = 'deferred', outcome_json = ?, updated_at = ? WHERE id = ? AND status IN ('planned','running')",
                            (_json({"reason": "superseded_by_explicit_replay"}), now, active["id"]),
                        )
                    elif active["job_id"]:
                        return {"id": active["job_id"], "status": "queued", "coalesced": True, "task_id": active["id"], "gap_id": active["gap_id"]}
                    else:
                        raise DomainConflict("research task is already being created for this gap")
                if active is not None and not allow_active_replay:
                    raise DomainConflict("research task is already being created for this gap")
                attempt_no = attempts_used + 1
                task_no = conn.execute(
                    "SELECT COALESCE(MAX(task_no), 0) + 1 FROM research_tasks WHERE gap_id = ?",
                    (gap["id"],),
                ).fetchone()[0]
                plan = {
                    "question": question["question"],
                    "gap_id": gap["id"],
                    "gap_type": gap["gap_type"],
                    "gap_description": gap["description"],
                    "query": str(query or "").strip()[:4_000],
                    "strategies": ["existing_corpus", "approved_sources", "source_discovery", "bounded_search"],
                }
                conn.execute(
                    """
                    INSERT INTO research_question_attempts
                        (id, question_id, attempt_no, mode, status, query_units,
                         local_model_units, estimated_cost_usd, query, task_id,
                         gap_id, created_at)
                    VALUES (?, ?, ?, ?, 'planned', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (attempt_id, identifier, attempt_no, mode, query_units, local_model_units, estimated_cost_usd, query, task_id, gap["id"], now),
                )
                conn.execute(
                    """
                    INSERT INTO research_tasks
                        (id, question_id, gap_id, task_no, mode, status, attempt_id,
                         snapshot_hash, plan_json, limits_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'planned', ?, ?, ?, ?, ?, ?)
                    """,
                    (task_id, identifier, gap["id"], task_no, "automatic" if mode == "policy" else "manual", attempt_id,
                     question["assessment_hash"], _json(plan), _json(task_limits), now, now),
                )
                conn.execute(
                    """
                    INSERT INTO research_question_gap_history
                        (id, gap_id, from_status, to_status, reason_code,
                         assessment_hash, task_id, actor, created_at)
                    VALUES (?, ?, ?, 'pursuing', 'task_created', ?, ?, 'system', ?)
                    """,
                    (new_id("rqgh"), gap["id"], gap["status"], question["assessment_hash"], task_id, now),
                )
                conn.execute(
                    "UPDATE research_question_gaps SET status = 'pursuing', updated_at = ? WHERE id = ? AND status = 'open'",
                    (now, gap["id"]),
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
                    "task_id": task_id,
                    "gap_id": gap["id"],
                    "question": question_text,
                    "mode": mode,
                    "query": query,
                    "plan": plan,
                    "limits": task_limits,
                    "budget": {
                        "acquisition_units": query_units,
                        "local_model_units": local_model_units,
                        "usd": estimated_cost_usd,
                    },
                },
                idempotency_key=key,
                research_question_id=identifier,
                priority=priority,
                max_attempts=1 + task_limits["max_retries"],
            )
        except Exception:
            conn = storage.connect(self.db_path)
            try:
                with storage.write_tx(conn):
                    conn.execute(
                        "UPDATE research_question_attempts SET status = 'failed', outcome_note = 'job enqueue failed', completed_at = ? WHERE id = ? AND status = 'planned'",
                        (utc_now(), attempt_id),
                    )
                    conn.execute(
                        "UPDATE research_tasks SET status = 'failed', error_code = 'enqueue_failed', error_detail = 'job enqueue failed', completed_at = ?, updated_at = ? WHERE id = ? AND status = 'planned'",
                        (utc_now(), utc_now(), task_id),
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
                conn.execute(
                    "UPDATE research_tasks SET job_id = ?, updated_at = ? WHERE id = ?",
                    (job["id"], utc_now(), task_id),
                )
        finally:
            conn.close()
        return {**job, "task_id": task_id, "gap_id": gap["id"]}

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
                task_status = {
                    "planned": "planned",
                    "running": "running",
                    "succeeded": "completed_with_candidates",
                    "partial": "completed_with_candidates",
                    "failed": "failed",
                    "cancelled": "cancelled",
                }[status]
                if row["task_id"]:
                    conn.execute(
                        "UPDATE research_tasks SET status = ?, started_at = COALESCE(started_at, ?), completed_at = ?, updated_at = ? WHERE id = ? AND status NOT IN ('completed_with_evidence','completed_with_candidates','completed_no_findings','failed','cancelled')",
                        (task_status, started, completed, utc_now(), row["task_id"]),
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
                "SELECT id FROM research_questions WHERE status = 'open' AND deleted_at IS NULL AND pursuit_policy <> 'disabled' AND next_attempt_at IS NOT NULL AND next_attempt_at <= ? ORDER BY CASE priority WHEN 'urgent' THEN 3 WHEN 'high' THEN 2 WHEN 'normal' THEN 1 ELSE 0 END DESC, next_attempt_at, id LIMIT ?",
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
    """Allow-listed bounded Research Task handler.

    Corpus retrieval and candidate discovery are deliberately kept separate:
    search metadata can be recorded as a finding, but only existing canonical
    Claim/Evidence rows or the normal Source → Document processing path can
    affect a Question assessment.
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        questions: ResearchQuestionService | None = None,
        search: Any | None = None,
        external_search: Any | None = None,
        acquirer: Any | None = None,
        router: Any | None = None,
    ):
        self.db_path = Path(db_path)
        self.questions = questions or ResearchQuestionService(db_path)
        self._search = search
        self._external_search = external_search
        self._acquirer = acquirer
        self._router = router

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

    def _task(self, job: Mapping[str, Any], question_id: str) -> dict[str, Any] | None:
        payload = job.get("payload", {})
        task_id = payload.get("task_id") if isinstance(payload, Mapping) else None
        conn = storage.connect(self.db_path)
        try:
            row = None
            if task_id:
                row = conn.execute(
                    "SELECT * FROM research_tasks WHERE id = ? AND question_id = ?",
                    (task_id, question_id),
                ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT * FROM research_tasks WHERE job_id = ?", (job["id"],)
                ).fetchone()
            return dict(row) if row is not None else None
        finally:
            conn.close()

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

    def _watch_context(self, question_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            watches = conn.execute(
                "SELECT id FROM watches WHERE target_type = 'research_question' AND target_id = ? AND status = 'active' ORDER BY id LIMIT 10",
                (question_id,),
            ).fetchall()
            watch_ids = [row["id"] for row in watches]
            if not watch_ids:
                return {"watch_ids": [], "terms": [], "sources": []}
            placeholders = ",".join("?" for _ in watch_ids)
            terms = [
                row["term"] for row in conn.execute(
                    f"SELECT term FROM watch_vocabulary WHERE watch_id IN ({placeholders}) AND status = 'approved' AND enabled = 1 AND kind <> 'exclude' ORDER BY created_at, id LIMIT 25",
                    watch_ids,
                )
            ]
            sources = [
                dict(row) for row in conn.execute(
                    f"""
                    SELECT ws.watch_id, ws.source_id, ws.monitor_id, s.name,
                           s.homepage_url, s.feed_url
                    FROM watch_sources AS ws
                    JOIN sources AS s ON s.id = ws.source_id AND s.deleted_at IS NULL
                    WHERE ws.watch_id IN ({placeholders})
                    ORDER BY ws.watch_id, ws.source_id
                    LIMIT 25
                    """,
                    watch_ids,
                )
            ]
            return {"watch_ids": watch_ids, "terms": terms, "sources": sources}
        finally:
            conn.close()

    def _plan_queries(
        self,
        question: Mapping[str, Any],
        task: Mapping[str, Any],
        query: str,
        limit: int,
        *,
        allow_provider: bool = True,
    ) -> list[tuple[str, str]]:
        plan = _decode(task.get("plan_json"))
        context = self._watch_context(str(question["id"]))
        raw: list[tuple[str, str]] = []
        if query.strip():
            raw.append((query.strip(), "explicit"))
        raw.append((str(question["question"]).strip(), "question"))
        gap_type = str(plan.get("gap_type") or "")
        gap_terms = {
            "supporting_evidence": "evidence support",
            "contradiction_review": "contradiction rebuttal",
            "independent_support": "independent source",
            "primary_source": "official primary source",
        }.get(gap_type)
        if gap_terms:
            raw.append((f"{question['question']} {gap_terms}", "gap"))
        if self._router is not None and allow_provider:
            try:
                from .ai import ResearchPlanRequest

                provider_plan = self._router.research_plan(
                    ResearchPlanRequest(
                        question=str(question["question"]),
                        gap_type=gap_type or "supporting_evidence",
                        gap_description=str(plan.get("gap_description") or "Find qualifying evidence"),
                        approved_vocabulary=tuple(context["terms"]),
                        max_queries=min(limit, 20),
                    ),
                    work_id=str(task.get("id") or ""),
                )
                raw.extend((str(item), "provider_suggestion") for item in provider_plan.query_suggestions)
            except Exception:
                # Provider planning is advisory.  Deterministic queries remain
                # valid when the provider is disabled, unavailable, or returns
                # a rejected structured value.
                pass
        raw.extend((str(term), "watch_vocabulary") for term in context["terms"])
        output: list[tuple[str, str]] = []
        seen: set[str] = set()
        for value, strategy in raw:
            terms = self._tokens(value)
            if not terms:
                continue
            normalized = " ".join(terms[:12])
            if normalized in seen:
                continue
            seen.add(normalized)
            output.append((normalized, strategy))
            if len(output) >= limit:
                break
        return output

    def _persist_query(self, task_id: str, query: str, strategy: str, ordinal: int) -> None:
        digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    "INSERT OR IGNORE INTO research_task_queries(id, task_id, query, query_hash, strategy, ordinal, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (new_id("rqq"), task_id, query[:500], digest, strategy[:50], ordinal, utc_now()),
                )
        finally:
            conn.close()

    def _persist_finding(self, task_id: str, item: Mapping[str, Any], *, rank: int, status: str = "candidate") -> None:
        entity_type = str(item.get("entity_type") or item.get("finding_type") or "corpus")
        entity_id = str(item.get("entity_id") or item.get("identity_key") or "").strip()
        if not entity_id:
            return
        finding_type = {
            "claim": "claim", "evidence": "evidence", "document": "document",
            "document_version": "document_version", "source_candidate": "source_candidate",
        }.get(entity_type, "corpus")
        identity = f"{finding_type}:{entity_id}"
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    """
                    INSERT INTO research_task_findings
                        (id, task_id, finding_type, identity_key, status, source_id,
                         document_id, document_version_id, claim_id, evidence_span_id,
                         rank, metadata_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(task_id, finding_type, identity_key) DO UPDATE SET
                        status = excluded.status, rank = MIN(research_task_findings.rank, excluded.rank),
                        updated_at = excluded.updated_at
                    """,
                    (
                        new_id("rqf"), task_id, finding_type, identity, status,
                        item.get("source_id"), item.get("document_id"), item.get("document_version_id"),
                        (item.get("claim_id") or item.get("entity_id")) if finding_type == "claim" else None,
                        (item.get("evidence_span_id") or item.get("entity_id")) if finding_type == "evidence" else None,
                        max(0, rank), _json({"title": str(item.get("title") or "")[:300], "snippet": str(item.get("snippet") or "")[:500]}),
                        utc_now(), utc_now(),
                    ),
                )
        finally:
            conn.close()

    def _research(self, query_plan: list[tuple[str, str]], cap: int, *, deadline: float | None = None) -> list[dict[str, Any]]:
        search = self._search_service()
        findings: dict[tuple[str, str], dict[str, Any]] = {}
        for candidate, _strategy in query_plan:
            if deadline is not None and time.monotonic() >= deadline:
                break
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

    def _external_candidates(
        self,
        query_plan: list[tuple[str, str]],
        cap: int,
        *,
        deadline: float | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        if self._external_search is None:
            return [], None
        output: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        try:
            for query, _strategy in query_plan:
                if deadline is not None and time.monotonic() >= deadline:
                    break
                if len(output) >= cap:
                    break
                raw = self._external_search.search(query, limit=min(cap - len(output), 10))
                if not isinstance(raw, (list, tuple)):
                    raise DomainValidation("external research search must return a bounded list")
                for item in raw:
                    if not isinstance(item, Mapping):
                        continue
                    url = str(item.get("url") or item.get("homepage_url") or "").strip()
                    title = str(item.get("title") or item.get("name") or "").strip()
                    if not url or len(url) > 2048 or len(title) > 500:
                        continue
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    output.append({"url": url, "title": title, "source_id": item.get("source_id"), "snippet": str(item.get("snippet") or "")[:500]})
                    if len(output) >= cap:
                        break
        except Exception as exc:
            return output, type(exc).__name__
        return output, None

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
        task = self._task(job, question_id)
        if task is None:
            raise DomainNotFound("research task not found")
        self.questions.record_attempt(attempt["id"], "running", started_at=utc_now())
        query = str(payload.get("query") or payload.get("question") or attempt.get("query") or "").strip()
        if not query:
            query = str(self.questions.get(question_id).get("question") or "").strip()
        limits = _decode(task.get("limits_json"))
        task_limits = _task_limits(limits)
        deadline = time.monotonic() + task_limits["max_runtime_seconds"]
        question = self.questions.get(question_id)
        query_plan = self._plan_queries(
            question,
            task,
            query,
            min(task_limits["max_queries"], 25),
            allow_provider=task_limits["max_provider_calls"] > 0,
        )
        for ordinal, (planned_query, strategy) in enumerate(query_plan):
            self._persist_query(task["id"], planned_query, strategy, ordinal)
        findings = self._research(query_plan, cap=task_limits["max_candidates"], deadline=deadline)
        claims = [item for item in findings if item["entity_type"] == "claim"]
        evidence = [item for item in findings if item["entity_type"] == "evidence"]
        for rank, item in enumerate(findings):
            self._persist_finding(task["id"], item, rank=rank, status="processed")
        for item in claims:
            self.questions.link_claim(question_id, item["entity_id"], "contextualizes", origin="task", rationale="Corpus-first Research Task finding")
        for item in evidence:
            self.questions.link_evidence(question_id, item["entity_id"], "contextualizes")

        watch_context = self._watch_context(question_id)
        discovery_count = 0
        if not findings and watch_context["watch_ids"]:
            from .intelligent_monitoring import WatchService

            watches = WatchService(self.db_path)
            for watch_id in watch_context["watch_ids"][:2]:
                discovery = watches.discover_sources(watch_id, limit=min(5, task_limits["max_candidates"]))
                discovery_count += int(discovery.get("candidate_count", 0))
                for rank, candidate in enumerate(discovery.get("candidates", [])):
                    self._persist_finding(task["id"], {"finding_type": "source_candidate", "identity_key": candidate["id"], "title": candidate.get("name")}, rank=rank)

        external, provider_error = ([], None)
        if not findings and discovery_count == 0:
            external, provider_error = self._external_candidates(
                query_plan,
                min(task_limits["max_candidates"], 25),
                deadline=deadline,
            )
            for rank, candidate in enumerate(external):
                self._persist_finding(task["id"], {"finding_type": "source_candidate", "identity_key": candidate["url"], "title": candidate.get("title"), "snippet": candidate.get("snippet")}, rank=rank)

        if external and watch_context["watch_ids"]:
            from .intelligent_monitoring import WatchService

            watches = WatchService(self.db_path)
            for candidate in external:
                for watch_id in watch_context["watch_ids"][:2]:
                    try:
                        watches.add_source_candidate(
                            watch_id,
                            {
                                "name": candidate.get("title") or candidate["url"],
                                "homepage_url": candidate["url"],
                                "discovery_method": "web_search",
                                "rationale": "Bounded Research Task candidate; approval remains required",
                                "provenance": {"task_id": task["id"]},
                            },
                        )
                    except Exception:
                        continue

        acquired_documents = 0
        acquisition_results: list[dict[str, Any]] = []
        approved_sources = {str(item["source_id"]): item for item in watch_context["sources"]}
        if external and approved_sources:
            acquirer = self._acquirer
            if acquirer is None:
                from .acquisition import AcquisitionService

                acquirer = AcquisitionService(self.db_path)
            for candidate in external[: task_limits["max_documents"]]:
                source = approved_sources.get(str(candidate.get("source_id") or ""))
                if source is None:
                    continue
                try:
                    acquired = acquirer.acquire_document(
                        source["source_id"], candidate["url"],
                        channel="direct_http", monitor_id=source["monitor_id"],
                    )
                except Exception as exc:
                    acquisition_results.append({"url": candidate["url"], "error": type(exc).__name__})
                    continue
                acquired_documents += int(bool(acquired.document_id))
                acquisition_results.append({
                    "url": candidate["url"],
                    "document_id": acquired.document_id,
                    "document_version_id": acquired.document_version_id,
                    "outcome": acquired.outcome,
                })
                if acquired.document_id:
                    self._persist_finding(
                        task["id"],
                        {
                            "finding_type": "document",
                            "identity_key": acquired.document_id,
                            "entity_id": acquired.document_id,
                            "document_id": acquired.document_id,
                            "source_id": source["source_id"],
                        },
                        rank=0,
                        status="acquired",
                    )

        self.questions.evaluate(question_id)
        current = self.questions.get(question_id)
        gap_id = str(payload.get("gap_id") or task.get("gap_id"))
        gap_row = next((item for item in current.get("gaps", []) if item["id"] == gap_id), None)
        if gap_row is not None and gap_row["status"] == "satisfied":
            task_status = "completed_with_evidence"
        elif findings or discovery_count or external:
            task_status = "completed_with_candidates"
        else:
            task_status = "completed_no_findings"
        status = "succeeded" if findings or discovery_count or external else "partial"
        note = f"pursuit linked {len(claims)} claims and {len(evidence)} evidence spans"
        return {
            "research_question_id": question_id,
            "attempt_id": attempt["id"],
            "attempt_status": status,
            "outcome_note": note,
            "query": query,
            "claim_count": len(claims),
            "evidence_count": len(evidence),
            "task_status": task_status,
            "search_query_count": len(query_plan),
            "source_candidate_count": discovery_count + len(external),
            "documents_acquired": acquired_documents,
            "acquisition_results": acquisition_results[:task_limits["max_documents"]],
            "provider_unavailable": provider_error,
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
    task_id = attempt["task_id"]

    def update_task(status: str, *, result: Mapping[str, Any] | None = None, error: str | None = None) -> None:
        if not task_id:
            return
        conn.execute(
            """
            UPDATE research_tasks
               SET status = CASE WHEN status = 'completed_with_evidence' THEN status ELSE ? END,
                   outcome_json = CASE WHEN status = 'completed_with_evidence' THEN outcome_json ELSE ? END,
                   error_code = CASE WHEN status = 'completed_with_evidence' THEN error_code ELSE ? END,
                   error_detail = CASE WHEN status = 'completed_with_evidence' THEN error_detail ELSE ? END,
                   started_at = COALESCE(started_at, ?),
                   completed_at = CASE WHEN status = 'completed_with_evidence' THEN COALESCE(completed_at, ?) ELSE ? END,
                   updated_at = ?
             WHERE id = ? AND status <> 'deferred'
            """,
            (
                status,
                _json(result or {}),
                error_code,
                error,
                now,
                now if status in RESEARCH_TASK_TERMINAL_STATUSES else None,
                now if status in RESEARCH_TASK_TERMINAL_STATUSES else None,
                now,
                task_id,
            ),
        )
        effective_task = conn.execute("SELECT status FROM research_tasks WHERE id = ?", (task_id,)).fetchone()
        if effective_task is None or effective_task["status"] == "completed_with_evidence":
            return
        if status in {"completed_with_candidates", "completed_no_findings", "failed", "cancelled"}:
            task = conn.execute("SELECT gap_id, question_id FROM research_tasks WHERE id = ?", (task_id,)).fetchone()
            if task is not None:
                gap = conn.execute("SELECT status FROM research_question_gaps WHERE id = ?", (task["gap_id"],)).fetchone()
                if gap is not None and gap["status"] == "pursuing":
                    conn.execute(
                        "UPDATE research_question_gaps SET status = 'open', updated_at = ? WHERE id = ?",
                        (now, task["gap_id"]),
                    )
                    conn.execute(
                        "INSERT INTO research_question_gap_history(id, gap_id, from_status, to_status, reason_code, task_id, actor, created_at) VALUES (?, ?, 'pursuing', 'open', ?, ?, 'system', ?)",
                        (new_id("rqgh"), task["gap_id"], "task_failed" if status in {"failed", "cancelled"} else "task_completed_without_qualifying_evidence", task_id, now),
                    )
                if status in {"completed_with_candidates", "completed_no_findings", "failed"}:
                    question = conn.execute(
                        "SELECT pursuit_policy, pursuit_cooldown_seconds FROM research_questions WHERE id = ?",
                        (task["question_id"],),
                    ).fetchone()
                    if question is not None and question["pursuit_policy"] == "automatic":
                        conn.execute(
                            "UPDATE research_questions SET next_attempt_at = ?, updated_at = ? WHERE id = ? AND status = 'open'",
                            (_plus_seconds(now, int(question["pursuit_cooldown_seconds"] or 0)), now, task["question_id"]),
                        )

    if final_status == "queued":
        conn.execute(
            """
            UPDATE research_question_attempts
            SET status = 'planned', outcome_note = ?, started_at = NULL, completed_at = NULL
            WHERE id = ?
            """,
            (outcome_note or "job requeued for another attempt", attempt["id"]),
        )
        update_task("planned", result=outcome, error=outcome_note)
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
        task_status = "completed_with_candidates"
        if isinstance(outcome, Mapping) and outcome.get("task_status") in RESEARCH_TASK_TERMINAL_STATUSES:
            task_status = str(outcome["task_status"])
        update_task(task_status, result=outcome)
        return
    if final_status == "partial":
        conn.execute(
            "UPDATE research_question_attempts SET status = 'partial', outcome_note = ?, completed_at = ? WHERE id = ?",
            (outcome_note or "pursuit produced partial results", now, attempt["id"]),
        )
        update_task("completed_with_candidates", result=outcome, error=outcome_note)
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
        update_task("failed", result=outcome, error=note)
        return
    if final_status == "cancelled":
        conn.execute(
            "UPDATE research_question_attempts SET status = 'cancelled', outcome_note = ?, completed_at = ? WHERE id = ?",
            (outcome_note or "durable job cancelled", now, attempt["id"]),
        )
        update_task("cancelled", result=outcome, error=outcome_note)
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
        allow_active_replay=True,
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
    "ASSESSMENT_STATES",
    "DEFAULT_TASK_LIMITS",
    "GAP_STATUSES",
    "GAP_TYPES",
    "LINK_RELATIONSHIPS",
    "NOTE_TYPES",
    "QUESTION_ORIGINS",
    "QUESTION_PRIORITIES",
    "QUESTION_STATUSES",
    "RESEARCH_TASK_STATUSES",
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
