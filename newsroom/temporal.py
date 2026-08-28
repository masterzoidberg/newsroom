"""Deterministic knowledge-time reads over Newsroom's canonical histories.

This module deliberately stays a read boundary. It does not add a second
temporal copy of the database or rewrite current pointers. A record is visible
as-of a boundary only when its durable knowledge/creation time and the
append-only relationship that made it usable are no later than that boundary.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import storage
from .domain import DomainNotFound, DomainValidation
from .evidence import ACCEPTED_STATES


TEMPORAL_CLAIM_STATES = frozenset({*ACCEPTED_STATES, "disputed"})


def normalize_as_of(value: str | datetime) -> str:
    """Return an ISO-8601 UTC boundary or raise a domain validation error."""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise DomainValidation("as_of must be an ISO-8601 timestamp") from exc
    else:
        raise DomainValidation("as_of must be an ISO-8601 timestamp")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _before(column: str) -> str:
    # julianday handles the repository's second- and microsecond-precision
    # timestamps consistently, unlike SQLite's lexical TEXT comparison.
    return f"julianday({column}) <= julianday(?)"


def _before_value(value: str | None, boundary: str) -> bool:
    if not value:
        return False
    try:
        return normalize_as_of(value) <= boundary
    except DomainValidation:
        return False


def _json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class TemporalReadService:
    """Read canonical evidence, Claims, Stories, and Reports as-of a boundary."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def eligible_as_of(
        self,
        object_type: str,
        object_id: str | None,
        as_of: str | datetime,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> bool:
        """Return whether one canonical object was knowable at ``as_of``.

        This is intentionally an allow-list of domain timestamps.  Creation
        time is sufficient for immutable records, while evidence, revisions,
        corrections, and lineage use the timestamp at which that relationship
        became available.  Unknown object types fail closed.
        """

        boundary = normalize_as_of(as_of)
        owned = conn is None
        connection = conn or storage.connect(self.db_path)
        try:
            kind = str(object_type).strip().casefold().replace("-", "_")
            if object_id is None:
                return False
            identifier = str(object_id).strip()
            if kind == "research_question":
                kind = "question"
            if kind == "question_note":
                row = connection.execute(
                    """SELECT n.created_at, q.created_at AS question_created_at,
                              q.deleted_at AS question_deleted_at
                       FROM research_question_notes n
                       JOIN research_questions q ON q.id = n.question_id
                      WHERE n.id = ?""",
                    (identifier,),
                ).fetchone()
                return bool(row and self._known(row[0], boundary) and self._live(row[1], row[2], boundary))
            if kind == "note" and identifier.startswith("research-question:"):
                return self.eligible_as_of("question_note", identifier.split(":", 1)[1], boundary, conn=connection)
            if kind == "claim_evidence":
                row = connection.execute(
                    "SELECT created_at, claim_id, evidence_span_id FROM claim_evidence WHERE id = ?",
                    (identifier,),
                ).fetchone()
                return bool(
                    row
                    and self._known(row[0], boundary)
                    and self.eligible_as_of("claim", row[1], boundary, conn=connection)
                    and self.eligible_as_of("evidence", row[2], boundary, conn=connection)
                )
            if kind == "question_claim":
                row = connection.execute(
                    "SELECT created_at, question_id, claim_id FROM research_question_claims WHERE rowid = ?",
                    (identifier,),
                ).fetchone()
                return bool(
                    row
                    and self._known(row[0], boundary)
                    and self.eligible_as_of("question", row[1], boundary, conn=connection)
                    and self.eligible_as_of("claim", row[2], boundary, conn=connection)
                )

            definitions = {
                "source": ("sources", "created_at", "deleted_at"),
                "document": ("documents", "created_at", None),
                "document_version": ("document_versions", "retrieved_at", None),
                "evidence": ("evidence_spans", "created_at", None),
                "claim": ("claims", "created_at", None),
                "story": ("stories", "created_at", "deleted_at"),
                "story_revision": ("story_revisions", "created_at", None),
                "subject": ("subjects", "created_at", "deleted_at"),
                "entity": ("entities", "created_at", None),
                "monitor": ("monitors", "created_at", None),
                "watch": ("watches", "created_at", None),
                "question": ("research_questions", "created_at", "deleted_at"),
                "gap": ("research_question_gaps", "created_at", None),
                "research_gap": ("research_question_gaps", "created_at", None),
                "task": ("research_tasks", "created_at", None),
                "research_task": ("research_tasks", "created_at", None),
                "report": ("living_reports", "created_at", None),
                "report_revision": ("report_revisions", "generated_at", None),
                "report_revision_cause": ("report_revision_causes", "created_at", None),
                "story_correction": ("story_corrections", "occurred_at", None),
                "lineage": ("story_lineage", "created_at", None),
                "note": ("notes", "created_at", None),
            }
            definition = definitions.get(kind)
            if definition is None:
                return False
            table, time_column, deleted_column = definition
            columns = f"{time_column}{', ' + deleted_column if deleted_column else ''}"
            row = connection.execute(f"SELECT {columns} FROM {table} WHERE id = ?", (identifier,)).fetchone()
            if row is None or not self._known(row[0], boundary):
                return False
            if deleted_column and not self._live(row[0], row[1], boundary):
                return False
            if kind == "document":
                return self.eligible_as_of("source", self._foreign_id(connection, "documents", "source_id", identifier), boundary, conn=connection)
            if kind == "document_version":
                return self._known(row[0], boundary) and self.eligible_as_of(
                    "document", self._foreign_id(connection, "document_versions", "document_id", identifier), boundary, conn=connection
                )
            if kind == "evidence":
                return self.eligible_as_of(
                    "document_version", self._foreign_id(connection, "evidence_spans", "document_version_id", identifier), boundary, conn=connection
                )
            if kind == "claim":
                story_id = self._foreign_id(connection, "claims", "story_id", identifier)
                return not story_id or self.eligible_as_of("story", story_id, boundary, conn=connection)
            if kind == "story_revision":
                return self.eligible_as_of("story", self._foreign_id(connection, "story_revisions", "story_id", identifier), boundary, conn=connection)
            if kind == "question":
                return True
            if kind == "note":
                object_row = connection.execute(
                    "SELECT object_type, object_id, updated_at FROM notes WHERE id = ?",
                    (identifier,),
                ).fetchone()
                if object_row is None:
                    return False
                parent_kind = str(object_row[0]).casefold().replace("-", "_")
                return _before_value(object_row[2], boundary) and self.eligible_as_of(parent_kind, object_row[1], boundary, conn=connection)
            if kind in {"gap", "research_gap", "task", "research_task"}:
                if kind in {"gap", "research_gap"}:
                    parent_id = self._foreign_id(connection, "research_question_gaps", "question_id", identifier)
                else:
                    parent_id = self._foreign_id(connection, "research_tasks", "question_id", identifier)
                return self.eligible_as_of("question", parent_id, boundary, conn=connection) if parent_id else True
            if kind == "report_revision":
                return self.eligible_as_of("report", self._foreign_id(connection, "report_revisions", "report_id", identifier), boundary, conn=connection)
            if kind == "report_revision_cause":
                return self.eligible_as_of("report_revision", self._foreign_id(connection, "report_revision_causes", "revision_id", identifier), boundary, conn=connection)
            return True
        finally:
            if owned:
                connection.close()

    @staticmethod
    def _known(value: str | None, boundary: str) -> bool:
        return bool(value) and _before_value(value, boundary)

    @staticmethod
    def _live(created_at: str | None, deleted_at: str | None, boundary: str) -> bool:
        return bool(created_at) and _before_value(created_at, boundary) and (not deleted_at or not _before_value(deleted_at, boundary))

    @staticmethod
    def _foreign_id(conn: sqlite3.Connection, table: str, column: str, identifier: str) -> str | None:
        row = conn.execute(f"SELECT {column} FROM {table} WHERE id = ?", (identifier,)).fetchone()
        return str(row[0]) if row and row[0] is not None else None

    def question_as_of(self, question_id: str, as_of: str | datetime, *, conn: sqlite3.Connection | None = None) -> dict[str, Any] | None:
        boundary = normalize_as_of(as_of)
        owned = conn is None
        connection = conn or storage.connect(self.db_path)
        try:
            row = connection.execute("SELECT * FROM research_questions WHERE id = ?", (question_id,)).fetchone()
            if row is None or not self.eligible_as_of("question", question_id, boundary, conn=connection):
                return None
            result = dict(row)
            status = connection.execute(
                f"SELECT to_status, reason FROM research_question_history WHERE question_id = ? AND {_before('created_at')} ORDER BY julianday(created_at) DESC, rowid DESC LIMIT 1",
                (question_id, boundary),
            ).fetchone()
            assessment = connection.execute(
                f"SELECT to_state FROM research_question_assessment_history WHERE question_id = ? AND {_before('created_at')} ORDER BY julianday(created_at) DESC, id DESC LIMIT 1",
                (question_id, boundary),
            ).fetchone()
            result["status"] = status[0] if status else "unknown"
            result["resolution_note"] = status[1] if status and result["status"] in {"resolved", "abandoned"} else None
            result["assessment_state"] = assessment[0] if assessment else "unknown"
            result["assessment_explanation"] = "Historical assessment is unavailable from stored history." if assessment is None else result.get("assessment_explanation")
            result["as_of"] = boundary
            return result
        finally:
            if owned:
                connection.close()

    def question_notes_as_of(
        self,
        question_ids: Iterable[str],
        as_of: str | datetime,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        values = tuple(dict.fromkeys(str(item) for item in question_ids if str(item)))
        if not values:
            return []
        boundary = normalize_as_of(as_of)
        owned = conn is None
        connection = conn or storage.connect(self.db_path)
        try:
            rows = connection.execute(
                f"SELECT * FROM research_question_notes WHERE question_id IN ({','.join('?' for _ in values)}) AND {_before('created_at')} ORDER BY created_at, id",
                [*values, boundary],
            ).fetchall()
            return [dict(row) for row in rows if self.eligible_as_of("question_note", row["id"], boundary, conn=connection)]
        finally:
            if owned:
                connection.close()

    def gaps_as_of(
        self,
        question_ids: Iterable[str],
        as_of: str | datetime,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        values = tuple(dict.fromkeys(str(item) for item in question_ids if str(item)))
        if not values:
            return []
        boundary = normalize_as_of(as_of)
        owned = conn is None
        connection = conn or storage.connect(self.db_path)
        try:
            rows = connection.execute(
                f"SELECT * FROM research_question_gaps WHERE question_id IN ({','.join('?' for _ in values)}) AND {_before('created_at')} ORDER BY question_id, created_at, id",
                [*values, boundary],
            ).fetchall()
            result: list[dict[str, Any]] = []
            for row in rows:
                if not self.eligible_as_of("research_gap", row["id"], boundary, conn=connection):
                    continue
                item = dict(row)
                history = connection.execute(
                    f"SELECT to_status FROM research_question_gap_history WHERE gap_id = ? AND {_before('created_at')} ORDER BY julianday(created_at) DESC, id DESC LIMIT 1",
                    (row["id"], boundary),
                ).fetchone()
                item["status"] = history[0] if history else "unknown"
                item["as_of"] = boundary
                result.append(item)
            return result
        finally:
            if owned:
                connection.close()

    def tasks_as_of(
        self,
        task_ids: Iterable[str],
        as_of: str | datetime,
        *,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        values = tuple(dict.fromkeys(str(item) for item in task_ids if str(item)))
        if not values:
            return []
        boundary = normalize_as_of(as_of)
        owned = conn is None
        connection = conn or storage.connect(self.db_path)
        try:
            rows = connection.execute(
                f"SELECT * FROM research_tasks WHERE id IN ({','.join('?' for _ in values)}) AND {_before('created_at')} ORDER BY created_at, id",
                [*values, boundary],
            ).fetchall()
            result: list[dict[str, Any]] = []
            for row in rows:
                if not self.eligible_as_of("research_task", row["id"], boundary, conn=connection):
                    continue
                item = dict(row)
                if not _before_value(item.get("updated_at"), boundary):
                    item["status"] = "unknown"
                    item["outcome_json"] = "{}"
                    item["error_code"] = None
                    item["error_detail"] = None
                    item["historical_state"] = "unavailable"
                item["as_of"] = boundary
                result.append(item)
            return result
        finally:
            if owned:
                connection.close()

    def filter_items_as_of(
        self,
        items: Iterable[Mapping[str, Any]],
        as_of: str | datetime,
        *,
        terms: Iterable[str] = (),
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        """Filter and project current search rows into a historical packet."""

        boundary = normalize_as_of(as_of)
        wanted = tuple(str(term).casefold() for term in terms if str(term))
        owned = conn is None
        connection = conn or storage.connect(self.db_path)
        try:
            result: list[dict[str, Any]] = []
            for raw in items:
                item = dict(raw)
                kind = str(item.get("entity_type") or "").casefold()
                identifier = str(item.get("entity_id") or "")
                eligibility_id = identifier
                eligibility_kind = kind
                if kind == "note" and identifier.startswith("research-question:"):
                    eligibility_kind = "question_note"
                    eligibility_id = identifier.split(":", 1)[1]
                if not self.eligible_as_of(eligibility_kind, eligibility_id, boundary, conn=connection):
                    continue
                if kind == "story":
                    story = self.story_as_of(identifier, boundary)
                    revision = story.get("revision") or {}
                    item["title"] = revision.get("headline") or identifier
                    item["body"] = " ".join(filter(None, (revision.get("summary"), revision.get("why_it_matters"), story["story"].get("lifecycle"))))
                    item["lifecycle"] = story["story"].get("lifecycle")
                elif kind == "question":
                    question = self.question_as_of(identifier, boundary, conn=connection)
                    if question is None:
                        continue
                    item["title"] = question["question"]
                    item["body"] = " ".join(filter(None, (question.get("status"), question.get("priority"), question.get("assessment_state"))))
                    item["state"] = question.get("status")
                    item["assessment_state"] = question.get("assessment_state")
                elif kind in {"research_task", "task"}:
                    task = next((value for value in self.tasks_as_of((identifier,), boundary, conn=connection)), None)
                    if task is None:
                        continue
                    item["body"] = " ".join(filter(None, (task.get("status"), task.get("plan_json"))))
                    item["state"] = task.get("status")
                elif kind == "report":
                    report = self.report_as_of(identifier, boundary)
                    revision = report.get("revision") or {}
                    item["body"] = " ".join(filter(None, (report["report"].get("status"), json.dumps(revision.get("sections", {}), sort_keys=True))))
                    item["current_revision_id"] = revision.get("id")
                    item["report_revision_id"] = revision.get("id")
                elif kind == "claim":
                    claim = next((value for value in self.claims_as_of(boundary, claim_ids=(identifier,))), None)
                    if claim is None:
                        continue
                    item["state"] = claim.get("state")
                elif kind in {"note", "question_note"}:
                    if kind == "note":
                        row = connection.execute("SELECT body FROM notes WHERE id = ?", (identifier,)).fetchone()
                    else:
                        row = connection.execute("SELECT body FROM research_question_notes WHERE id = ?", (eligibility_id,)).fetchone()
                    if row:
                        item["body"] = row[0]
                safe_text = " ".join((str(item.get("title") or ""), str(item.get("body") or ""))).casefold()
                if wanted and not any(term in safe_text for term in wanted):
                    continue
                result.append(item)
            return result
        finally:
            if owned:
                connection.close()

    def evidence_as_of(
        self,
        as_of: str | datetime,
        *,
        evidence_ids: Iterable[str] | None = None,
        claim_ids: Iterable[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        boundary = normalize_as_of(as_of)
        evidence_values = tuple(dict.fromkeys(str(item) for item in (evidence_ids or ()) if str(item)))
        claim_values = tuple(dict.fromkeys(str(item) for item in (claim_ids or ()) if str(item)))
        clauses = [_before("dv.retrieved_at"), _before("es.created_at")]
        params: list[Any] = [boundary, boundary]
        if evidence_values:
            clauses.append(f"es.id IN ({','.join('?' for _ in evidence_values)})")
            params.extend(evidence_values)
        if claim_values:
            clauses.append(f"ce.claim_id IN ({','.join('?' for _ in claim_values)})")
            params.extend(claim_values)
        where = " AND ".join(clauses)
        conn = storage.connect(self.db_path)
        try:
            rows = conn.execute(
                f"""
                SELECT DISTINCT es.id, es.document_version_id, es.excerpt,
                       es.locator_type, es.locator_value, es.created_at,
                       dv.document_id, dv.retrieved_at, dv.content_hash,
                       d.canonical_url, d.title AS document_title, d.source_id,
                       s.name AS source_name, s.slug AS source_slug
                FROM evidence_spans es
                JOIN document_versions dv ON dv.id = es.document_version_id
                JOIN documents d ON d.id = dv.document_id
                JOIN sources s ON s.id = d.source_id
                LEFT JOIN claim_evidence ce
                  ON ce.evidence_span_id = es.id AND {_before('ce.created_at')}
                WHERE {where}
                ORDER BY julianday(dv.retrieved_at), es.id
                """,
                [boundary, *params],
            ).fetchall()
            return {
                row["id"]: self._evidence_row(row)
                for row in rows
                if self.eligible_as_of("evidence", row["id"], boundary, conn=conn)
            }
        finally:
            conn.close()

    @staticmethod
    def _evidence_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "excerpt": row["excerpt"],
            "locator_type": row["locator_type"],
            "locator_value": row["locator_value"],
            "created_at": row["created_at"],
            "document_version_id": row["document_version_id"],
            "retrieved_at": row["retrieved_at"],
            "content_hash": row["content_hash"],
            "document_id": row["document_id"],
            "document_title": row["document_title"],
            "canonical_url": row["canonical_url"],
            "source_id": row["source_id"],
            "source_name": row["source_name"],
            "source_slug": row["source_slug"],
        }

    def _claim_state_as_of(self, conn: sqlite3.Connection, claim_id: str, boundary: str) -> str | None:
        row = conn.execute(
            f"""
            SELECT to_state
            FROM claim_state_history
            WHERE claim_id = ? AND {_before('created_at')}
            ORDER BY julianday(created_at) DESC, rowid DESC
            LIMIT 1
            """,
            (claim_id, boundary),
        ).fetchone()
        return row[0] if row else None

    def _story_id_as_of(self, conn: sqlite3.Connection, claim: sqlite3.Row, boundary: str) -> str | None:
        row = conn.execute(
            f"""
            SELECT to_story_id
            FROM claim_story_assignment_history
            WHERE claim_id = ? AND {_before('occurred_at')}
            ORDER BY julianday(occurred_at) DESC, rowid DESC
            LIMIT 1
            """,
            (claim["id"], boundary),
        ).fetchone()
        if row:
            return row[0]
        first = conn.execute(
            """
            SELECT from_story_id
            FROM claim_story_assignment_history
            WHERE claim_id = ?
            ORDER BY julianday(occurred_at), rowid
            LIMIT 1
            """,
            (claim["id"],),
        ).fetchone()
        if first:
            return first[0]
        # Older/manual rows predate assignment history. Their immutable
        # creation-time Story pointer is the only honest historical fallback.
        return claim["story_id"]

    def claims_as_of(
        self,
        as_of: str | datetime,
        *,
        claim_ids: Iterable[str] | None = None,
        story_id: str | None = None,
    ) -> list[dict[str, Any]]:
        boundary = normalize_as_of(as_of)
        values = tuple(dict.fromkeys(str(item) for item in (claim_ids or ()) if str(item)))
        clauses = [_before("c.created_at")]
        params: list[Any] = [boundary]
        if values:
            clauses.append(f"c.id IN ({','.join('?' for _ in values)})")
            params.extend(values)
        conn = storage.connect(self.db_path)
        try:
            rows = conn.execute(
                f"SELECT c.* FROM claims c WHERE {' AND '.join(clauses)} ORDER BY julianday(c.created_at), c.id",
                params,
            ).fetchall()
            selected: list[dict[str, Any]] = []
            for row in rows:
                if not self.eligible_as_of("claim", row["id"], boundary, conn=conn):
                    continue
                state = self._claim_state_as_of(conn, row["id"], boundary)
                if state not in TEMPORAL_CLAIM_STATES:
                    continue
                historical_story_id = self._story_id_as_of(conn, row, boundary)
                if story_id is not None and historical_story_id != story_id:
                    continue
                evidence_rows = conn.execute(
                    f"""
                    SELECT ce.relationship, ce.created_at AS relationship_created_at,
                           es.id, es.document_version_id, es.excerpt,
                           es.locator_type, es.locator_value, es.created_at,
                           dv.document_id, dv.retrieved_at, dv.content_hash,
                           d.canonical_url, d.title AS document_title, d.source_id,
                           s.name AS source_name, s.slug AS source_slug
                    FROM claim_evidence ce
                    JOIN evidence_spans es ON es.id = ce.evidence_span_id
                    JOIN document_versions dv ON dv.id = es.document_version_id
                    JOIN documents d ON d.id = dv.document_id
                    JOIN sources s ON s.id = d.source_id
                    WHERE ce.claim_id = ?
                      AND {_before('ce.created_at')}
                      AND {_before('es.created_at')}
                      AND {_before('dv.retrieved_at')}
                    ORDER BY ce.id
                    """,
                    (row["id"], boundary, boundary, boundary),
                ).fetchall()
                evidence = []
                for item in evidence_rows:
                    if not self.eligible_as_of("evidence", item["id"], boundary, conn=conn):
                        continue
                    value = self._evidence_row(item)
                    value["relationship"] = item["relationship"]
                    evidence.append(value)
                if not any(item["relationship"] == "supports" for item in evidence):
                    continue
                selected.append(
                    {
                        **dict(row),
                        "state": state,
                        "story_id": historical_story_id,
                        "evidence": evidence,
                        "as_of": boundary,
                    }
                )
            return selected
        finally:
            conn.close()

    def story_as_of(self, story_id: str, as_of: str | datetime) -> dict[str, Any]:
        boundary = normalize_as_of(as_of)
        conn = storage.connect(self.db_path)
        try:
            story = conn.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()
            if story is None or not self.eligible_as_of("story", story_id, boundary, conn=conn):
                raise DomainNotFound("story not found")
            claim_ids = {
                row[0]
                for row in conn.execute(
                    "SELECT id FROM claims WHERE story_id = ? UNION SELECT claim_id FROM claim_story_assignment_history WHERE from_story_id = ? OR to_story_id = ?",
                    (story_id, story_id, story_id),
                ).fetchall()
            }
            corrections = [
                dict(row)
                for row in conn.execute(
                    f"""
                    SELECT DISTINCT sc.*
                    FROM story_corrections sc
                    LEFT JOIN claim_story_assignment_history h ON h.correction_id = sc.id
                    LEFT JOIN story_lineage sl ON sl.correction_id = sc.id
                    WHERE (h.from_story_id = ? OR h.to_story_id = ? OR sl.source_story_id = ? OR sl.target_story_id = ?)
                      AND {_before('sc.occurred_at')}
                    ORDER BY julianday(sc.occurred_at), sc.id
                    """,
                    (story_id, story_id, story_id, story_id, boundary),
                ).fetchall()
            ]
            lineage = [
                dict(row)
                for row in conn.execute(
                    f"SELECT * FROM story_lineage WHERE (source_story_id = ? OR target_story_id = ?) AND {_before('created_at')} ORDER BY julianday(created_at), id",
                    (story_id, story_id, boundary),
                ).fetchall()
            ]
            claims = self.claims_as_of(boundary, claim_ids=claim_ids, story_id=story_id)
            historical_story = dict(story)
            revision = conn.execute(
                f"SELECT * FROM story_revisions WHERE story_id = ? AND {_before('created_at')} ORDER BY revision_number DESC, id DESC LIMIT 1",
                (story_id, boundary),
            ).fetchone()
            if revision is not None:
                historical_story["revision"] = dict(revision)
            else:
                historical_story["revision"] = None
            historical_story["lifecycle"] = self._story_lifecycle_as_of(conn, story, boundary)
            if historical_story["lifecycle"] == "unknown":
                historical_story["lifecycle_state"] = "unavailable"
            return {
                "story": historical_story,
                "as_of": boundary,
                "claims": claims,
                "corrections": corrections,
                "lineage": lineage,
                "identity": {
                    "story_id": story_id,
                    "correction_count": len(corrections),
                    "lineage_count": len(lineage),
                },
            }
        finally:
            conn.close()

    def _story_lifecycle_as_of(self, conn: sqlite3.Connection, story: sqlite3.Row, boundary: str) -> str:
        """Return a lifecycle only when it is supported by stored history."""

        archive_before = conn.execute(
            f"""SELECT 1
                  FROM story_lineage sl
                  JOIN story_corrections sc ON sc.id = sl.correction_id
                 WHERE sl.source_story_id = ?
                   AND sl.relationship IN ('merged_into', 'split_into')
                   AND {_before('sc.occurred_at')}
                 LIMIT 1""",
            (story["id"], boundary),
        ).fetchone()
        if archive_before:
            return "archived"
        future_archive = conn.execute(
            f"""SELECT 1
                  FROM story_lineage sl
                  JOIN story_corrections sc ON sc.id = sl.correction_id
                 WHERE sl.source_story_id = ?
                   AND sl.relationship IN ('merged_into', 'split_into')
                   AND julianday(sc.occurred_at) > julianday(?)
                 LIMIT 1""",
            (story["id"], boundary),
        ).fetchone()
        if future_archive:
            return "unknown"
        if _before_value(story["updated_at"], boundary):
            return str(story["lifecycle"])
        return "unknown"

    def report_as_of(self, report_id: str, as_of: str | datetime) -> dict[str, Any]:
        boundary = normalize_as_of(as_of)
        conn = storage.connect(self.db_path)
        try:
            report = conn.execute("SELECT * FROM living_reports WHERE id = ?", (report_id,)).fetchone()
            if report is None or not self.eligible_as_of("report", report_id, boundary, conn=conn):
                raise DomainNotFound("living report not found")
            revision = conn.execute(
                f"SELECT * FROM report_revisions WHERE report_id = ? AND {_before('generated_at')} ORDER BY revision_number DESC, id DESC LIMIT 1",
                (report_id, boundary),
            ).fetchone()
            historical_report = dict(report)
            if revision is not None:
                historical_report["current_revision_id"] = revision["id"]
            elif report["current_revision_id"]:
                historical_report["current_revision_id"] = None
            if not _before_value(report["updated_at"], boundary):
                historical_report["status"] = "unknown"
                historical_report["historical_state"] = "unavailable"
            if revision is None:
                return {"report": historical_report, "as_of": boundary, "revision": None, "claims": [], "causes": []}
            claim_ids = [row[0] for row in conn.execute("SELECT claim_id FROM report_revision_claims WHERE revision_id = ? ORDER BY position, claim_id", (revision["id"],)).fetchall()]
            causes = [
                dict(row)
                for row in conn.execute(
                    f"SELECT * FROM report_revision_causes WHERE revision_id = ? AND {_before('created_at')} ORDER BY created_at, id",
                    (revision["id"], boundary),
                ).fetchall()
            ]
            revision_value = dict(revision)
            revision_value["sections"] = _json(revision_value.pop("sections_json"), {})
            revision_value["propositions"] = _json(revision_value.pop("propositions_json"), [])
            revision_value["audit"] = _json(revision_value.pop("audit_json"), {})
            revision_value["what_changed"] = _json(revision_value.get("what_changed"), revision_value["sections"].get("what_changed", []))
            return {
                "report": historical_report,
                "as_of": boundary,
                "revision": revision_value,
                "claims": self.claims_as_of(boundary, claim_ids=claim_ids),
                "causes": causes,
            }
        finally:
            conn.close()


__all__ = ["TEMPORAL_CLAIM_STATES", "TemporalReadService", "normalize_as_of"]
