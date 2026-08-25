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
            return {row["id"]: self._evidence_row(row) for row in rows}
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
            if story is None:
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
            return {
                "story": dict(story),
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

    def report_as_of(self, report_id: str, as_of: str | datetime) -> dict[str, Any]:
        boundary = normalize_as_of(as_of)
        conn = storage.connect(self.db_path)
        try:
            report = conn.execute("SELECT * FROM living_reports WHERE id = ?", (report_id,)).fetchone()
            if report is None:
                raise DomainNotFound("living report not found")
            revision = conn.execute(
                f"SELECT * FROM report_revisions WHERE report_id = ? AND {_before('generated_at')} ORDER BY revision_number DESC, id DESC LIMIT 1",
                (report_id, boundary),
            ).fetchone()
            if revision is None:
                return {"report": dict(report), "as_of": boundary, "revision": None, "claims": [], "causes": []}
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
                "report": dict(report),
                "as_of": boundary,
                "revision": revision_value,
                "claims": self.claims_as_of(boundary, claim_ids=claim_ids),
                "causes": causes,
            }
        finally:
            conn.close()


__all__ = ["TEMPORAL_CLAIM_STATES", "TemporalReadService", "normalize_as_of"]
