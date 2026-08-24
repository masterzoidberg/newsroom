"""Evidence-bound Living Reports, briefings, and durable alerts."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import storage
from .domain import DomainConflict, DomainNotFound, DomainValidation, new_id, utc_now
from .evidence import ACCEPTED_STATES, claim_set_hash


REPORT_TARGET_TYPES = frozenset({"monitor", "story", "topic", "subject", "source", "research_question"})
REPORT_STATUSES = frozenset({"active", "archived"})
BRIEFING_PERIODS = frozenset({"daily", "weekly"})
CAUSE_TYPES = frozenset({"new_primary_evidence", "contradiction", "correction", "corroboration", "material_update"})
ALERT_TARGET_TYPES = frozenset({"all", "report", "monitor", "story"})
ALERT_STATUSES = frozenset({"unread", "acknowledged"})
DELIVERY_STATUSES = frozenset({"pending", "sent", "failed", "denied", "offline", "skipped"})

CAUSE_WEIGHTS = {
    "new_primary_evidence": 1.0,
    "contradiction": 1.0,
    "correction": 0.95,
    "material_update": 0.9,
    "corroboration": 0.45,
}


def _decode(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None


def _encode(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise DomainValidation("report content must be JSON serializable") from exc


def _timestamp(value: str | datetime | None = None) -> str:
    if value is None:
        return utc_now()
    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise DomainValidation("timestamp must be an ISO-8601 value") from exc
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timezone(name: str) -> ZoneInfo:
    value = str(name or "UTC").strip()
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise DomainValidation("timezone is invalid") from exc


def _validate_name(value: Any, label: str = "name", maximum: int = 200) -> str:
    result = str(value or "").strip()
    if not result or len(result) > maximum:
        raise DomainValidation(f"{label} must be 1-{maximum} characters")
    return result


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _cause_event_type(update_class: str) -> str:
    return {
        "contradiction": "contradiction",
        "correction": "correction",
        "corroboration": "corroboration",
        "material_update": "material_update",
        "duplicate": "corroboration",
        "qualification": "material_update",
        "new_story": "material_update",
    }.get(update_class, "material_update")


def _report_input_identity(sections: Mapping[str, Any], propositions: list[dict[str, Any]]) -> str:
    """Hash exactly the deterministic persisted inputs rendered by a revision."""

    material_sections = dict(sections)
    material_sections["what_changed"] = []
    encoded = _encode(
        {"sections": material_sections, "propositions": propositions}
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class LivingReportService:
    """Create immutable, accepted-Claim-bound report revisions."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @staticmethod
    def _require(conn: sqlite3.Connection, identifier: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM living_reports WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise DomainNotFound("living report not found")
        return row

    @staticmethod
    def _require_target(conn: sqlite3.Connection, target_type: str, target_id: str) -> None:
        tables = {
            "monitor": "monitors",
            "story": "stories",
            "topic": "topics",
            "subject": "subjects",
            "source": "sources",
            "research_question": "research_questions",
        }
        row = conn.execute(f"SELECT * FROM {tables[target_type]} WHERE id = ?", (target_id,)).fetchone()
        if row is None or ("deleted_at" in row.keys() and row["deleted_at"] is not None):
            raise DomainNotFound(f"{target_type} report target not found")

    def create(self, data: Mapping[str, Any]) -> dict[str, Any]:
        name = _validate_name(data.get("name"))
        target_type = str(data.get("target_type", "")).strip()
        target_id = str(data.get("target_id", "")).strip()
        timezone_name = str(data.get("timezone_name", "UTC")).strip() or "UTC"
        if target_type not in REPORT_TARGET_TYPES:
            raise DomainValidation("invalid living report target type")
        if not target_id:
            raise DomainValidation("living report target_id is required")
        _timezone(timezone_name)
        identifier = new_id("report")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_target(conn, target_type, target_id)
                try:
                    conn.execute(
                        "INSERT INTO living_reports(id, name, target_type, target_id, timezone_name, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (identifier, name, target_type, target_id, timezone_name, now, now),
                    )
                except sqlite3.IntegrityError as exc:
                    raise DomainConflict("a living report already exists for this target") from exc
        finally:
            conn.close()
        return self.get(identifier)

    def list(self, *, status: str | None = None, target_type: str | None = None, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        if status is not None and status not in REPORT_STATUSES:
            raise DomainValidation("invalid living report status")
        if target_type is not None and target_type not in REPORT_TARGET_TYPES:
            raise DomainValidation("invalid living report target type")
        if page < 1 or page_size < 1 or page_size > 100:
            raise DomainValidation("invalid living report page")
        clauses = ["1 = 1"]
        params: list[Any] = []
        for field, value in (("status", status), ("target_type", target_type)):
            if value is not None:
                clauses.append(f"{field} = ?")
                params.append(value)
        where = " AND ".join(clauses)
        conn = storage.connect(self.db_path)
        try:
            total = conn.execute(f"SELECT COUNT(*) FROM living_reports WHERE {where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM living_reports WHERE {where} ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
            return {"items": [dict(item) for item in rows], "page": page, "page_size": page_size, "total": total}
        finally:
            conn.close()

    def get(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            report = self._require(conn, identifier)
            result = dict(report)
            result["current_revision"] = None
            if report["current_revision_id"]:
                row = conn.execute("SELECT * FROM report_revisions WHERE id = ?", (report["current_revision_id"],)).fetchone()
                result["current_revision"] = self._revision_result(conn, row)
            result["revisions"] = [
                self._revision_result(conn, row)
                for row in conn.execute(
                    "SELECT * FROM report_revisions WHERE report_id = ? ORDER BY revision_number DESC, id DESC",
                    (identifier,),
                ).fetchall()
            ]
            return result
        finally:
            conn.close()

    def archive(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, identifier)
                conn.execute("UPDATE living_reports SET status = 'archived', updated_at = ? WHERE id = ?", (utc_now(), identifier))
        finally:
            conn.close()
        return self.get(identifier)

    @staticmethod
    def _revision_result(conn: sqlite3.Connection, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        result["sections"] = _decode(result.pop("sections_json"), {})
        result["propositions"] = _decode(result.pop("propositions_json"), [])
        result["audit"] = _decode(result.pop("audit_json"), {})
        result["claim_ids"] = [
            item[0]
            for item in conn.execute(
                "SELECT claim_id FROM report_revision_claims WHERE revision_id = ? ORDER BY position, claim_id",
                (result["id"],),
            ).fetchall()
        ]
        result["change_causes"] = [
            dict(item)
            for item in conn.execute(
                "SELECT * FROM report_revision_causes WHERE revision_id = ? ORDER BY created_at, id",
                (result["id"],),
            ).fetchall()
        ]
        result["what_changed"] = _decode(result.get("what_changed"), result["sections"].get("what_changed", []))
        return result

    def _story_ids(self, conn: sqlite3.Connection, report: sqlite3.Row) -> list[str]:
        target_type, target_id = report["target_type"], report["target_id"]
        if target_type == "story":
            return [target_id]
        if target_type == "monitor":
            monitor = conn.execute("SELECT target_type, target_id FROM monitors WHERE id = ?", (target_id,)).fetchone()
            if monitor is None:
                return []
            target_type, target_id = monitor["target_type"], monitor["target_id"]
        if target_type == "story":
            return [target_id]
        queries = {
            "topic": ("SELECT story_id FROM story_topics WHERE topic_id = ?", target_id),
            "subject": ("SELECT story_id FROM story_subjects WHERE subject_id = ?", target_id),
            "source": ("""
                SELECT DISTINCT c.story_id
                FROM claims c
                JOIN claim_evidence ce ON ce.claim_id = c.id
                JOIN evidence_spans es ON es.id = ce.evidence_span_id
                JOIN document_versions dv ON dv.id = es.document_version_id
                JOIN documents d ON d.id = dv.document_id
                WHERE d.source_id = ? AND c.story_id IS NOT NULL
            """, target_id),
            "research_question": ("SELECT DISTINCT c.story_id FROM research_question_claims rqc JOIN claims c ON c.id = rqc.claim_id JOIN research_questions rq ON rq.id = rqc.question_id WHERE rq.id = ? AND c.story_id IS NOT NULL", target_id),
        }
        if target_type not in queries:
            return []
        return sorted(
            row[0]
            for row in conn.execute(
                f"{queries[target_type][0]} LIMIT 100", (queries[target_type][1],)
            ).fetchall()
        )

    def _accepted_claims(self, conn: sqlite3.Connection, story_ids: list[str]) -> list[sqlite3.Row]:
        if not story_ids:
            return []
        placeholders = ",".join("?" for _ in story_ids)
        return conn.execute(
            f"SELECT * FROM claims WHERE story_id IN ({placeholders}) AND accepted_at IS NOT NULL AND state IN ('supported', 'partially_supported') ORDER BY story_id, created_at, id LIMIT 500",
            story_ids,
        ).fetchall()

    def _claim_evidence(self, conn: sqlite3.Connection, claim_id: str) -> list[sqlite3.Row]:
        return conn.execute(
            """
            SELECT ce.relationship, ce.evidence_span_id, es.document_version_id,
                   dv.document_id, d.source_id, s.default_quality, s.source_kind
            FROM claim_evidence ce
            JOIN evidence_spans es ON es.id = ce.evidence_span_id
            JOIN document_versions dv ON dv.id = es.document_version_id
            JOIN documents d ON d.id = dv.document_id
            JOIN sources s ON s.id = d.source_id
            WHERE ce.claim_id = ? ORDER BY ce.created_at, ce.id
            """,
            (claim_id,),
        ).fetchall()

    def _previous_claim_ids(self, conn: sqlite3.Connection, report_id: str) -> set[str]:
        row = conn.execute("SELECT current_revision_id FROM living_reports WHERE id = ?", (report_id,)).fetchone()
        if row is None or row[0] is None:
            return set()
        return {item[0] for item in conn.execute("SELECT claim_id FROM report_revision_claims WHERE revision_id = ?", (row[0],)).fetchall()}

    def _previous_cause_ids(self, conn: sqlite3.Connection, report_id: str) -> set[str]:
        return {
            item[0]
            for item in conn.execute(
                "SELECT rrc.cause_id FROM report_revision_causes rrc JOIN report_revisions rr ON rr.id = rrc.revision_id WHERE rr.report_id = ?",
                (report_id,),
            ).fetchall()
        }

    def _previous_evidence_ids(self, conn: sqlite3.Connection, report_id: str) -> set[str]:
        return {
            item[0]
            for item in conn.execute(
                """
                SELECT rrc.evidence_span_id
                FROM report_revision_causes rrc
                JOIN report_revisions rr ON rr.id = rrc.revision_id
                WHERE rr.report_id = ? AND rrc.evidence_span_id IS NOT NULL
                """,
                (report_id,),
            ).fetchall()
        }

    def _collect_sections(
        self,
        conn: sqlite3.Connection,
        story_ids: list[str],
        claims: list[sqlite3.Row],
        coverage_target_id: str | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        claim_ids = [claim["id"] for claim in claims]
        claim_id_set = set(claim_ids)
        active_stories = []
        for story_id in story_ids:
            story = conn.execute(
                """
                SELECT s.id, s.lifecycle, sr.id AS revision_id, sr.headline
                FROM stories s
                LEFT JOIN story_revisions sr
                  ON sr.story_id = s.id
                 AND sr.revision_number = (
                     SELECT MAX(latest.revision_number)
                     FROM story_revisions latest
                     WHERE latest.story_id = s.id
                 )
                WHERE s.id = ? AND s.deleted_at IS NULL
                """,
                (story_id,),
            ).fetchone()
            if story is None:
                continue
            story_claims = [claim["id"] for claim in claims if claim["story_id"] == story_id]
            if story["lifecycle"] != "archived":
                active_stories.append({"story_id": story_id, "headline": story["headline"], "lifecycle": story["lifecycle"], "revision_id": story["revision_id"], "claim_ids": story_claims})
        strength = []
        contradictions = []
        evidence_by_claim: dict[str, list[sqlite3.Row]] = {}
        for claim in claims:
            evidence = self._claim_evidence(conn, claim["id"])
            evidence_by_claim[claim["id"]] = evidence
            support = [item for item in evidence if item["relationship"] == "supports"]
            conflict = [item for item in evidence if item["relationship"] == "contradicts"]
            source_ids = _unique([item["source_id"] for item in support])
            family_count = conn.execute(
                """
                SELECT COUNT(DISTINCT efm.family_id)
                FROM claim_evidence ce
                JOIN evidence_spans es ON es.id = ce.evidence_span_id
                JOIN document_versions dv ON dv.id = es.document_version_id
                JOIN evidence_family_members efm ON efm.document_id = dv.document_id
                WHERE ce.claim_id = ? AND ce.relationship = 'supports'
                """,
                (claim["id"],),
            ).fetchone()[0] if _table_exists(conn, "evidence_family_members") else 0
            strength.append({"story_id": claim["story_id"], "claim_id": claim["id"], "supporting_evidence_count": len(support), "contradicting_evidence_count": len(conflict), "distinct_source_count": len(source_ids), "evidence_family_count": family_count, "state": claim["state"]})
            if claim["state"] == "disputed" or conflict:
                contradictions.append({"claim_id": claim["id"], "proposition": claim["proposition"], "evidence_span_ids": [item["evidence_span_id"] for item in conflict]})
        question_params: list[Any] = []
        question_clauses: list[str] = []
        for story_id in story_ids:
            question_clauses.append("(rq.origin_type = 'story' AND rq.origin_id = ?)")
            question_params.append(story_id)
        for claim_id in claim_ids:
            question_clauses.append("(rq.origin_type = 'claim' AND rq.origin_id = ?)")
            question_params.append(claim_id)
        unresolved = []
        if question_clauses:
            unresolved = [dict(item) for item in conn.execute(f"SELECT rq.id, rq.question, rq.priority, rq.origin_type, rq.origin_id FROM research_questions rq WHERE rq.status = 'open' AND ({' OR '.join(question_clauses)}) ORDER BY CASE rq.priority WHEN 'urgent' THEN 3 WHEN 'high' THEN 2 WHEN 'normal' THEN 1 ELSE 0 END DESC, rq.created_at, rq.id LIMIT 100", question_params).fetchall()]
        suggestions = []
        if question_clauses:
            suggestions = [dict(item) for item in conn.execute(f"SELECT rgs.id, rgs.suggestion, rgs.rationale, rgs.expected_information_value, rgs.suggestion_type, rgs.origin_type, rgs.origin_id FROM research_gap_suggestions rgs WHERE rgs.status = 'pending' AND ({' OR '.join('(' + clause.replace('rq.', 'rgs.') + ')' for clause in question_clauses)}) ORDER BY rgs.expected_information_value DESC, rgs.created_at, rgs.id LIMIT 100", question_params).fetchall()]
        coverage_gaps = []
        if _table_exists(conn, "coverage_runs"):
            coverage_targets = story_ids or ([coverage_target_id] if coverage_target_id else [])
            if coverage_targets:
                placeholders = ",".join("?" for _ in coverage_targets)
                coverage_gaps = [dict(item) for item in conn.execute(
                    f"SELECT id, target_type, target_id, status, window_start, window_end FROM coverage_runs WHERE target_id IN ({placeholders}) AND status <> 'completed' ORDER BY created_at DESC, id DESC LIMIT 10",
                    coverage_targets,
                ).fetchall()]
        sections = {
            "current_status": f"{len(active_stories)} active Story record(s) with {len(claim_ids)} accepted Claim(s).",
            "what_changed": [],
            "active_stories": active_stories,
            "evidence_strength": strength,
            "contradictions": contradictions,
            "unresolved_questions": unresolved,
            "recommended_investigations": suggestions,
            "coverage_gaps": coverage_gaps,
        }
        return sections, [{"text": claim["proposition"], "claim_ids": [claim["id"]]} for claim in claims if claim["id"] in claim_id_set]

    @staticmethod
    def _stored_input_identity(row: sqlite3.Row) -> str:
        audit = _decode(row["audit_json"], {})
        identity = audit.get("input_identity") if isinstance(audit, dict) else None
        if isinstance(identity, str) and identity:
            return identity
        return _report_input_identity(
            _decode(row["sections_json"], {}),
            _decode(row["propositions_json"], []),
        )

    @staticmethod
    def _validate_cause_tx(
        conn: sqlite3.Connection,
        cause: Mapping[str, Any],
        accepted_ids: set[str],
    ) -> bool:
        if cause.get("cause_type") not in CAUSE_TYPES or cause.get("claim_id") not in accepted_ids:
            return False
        chain = conn.execute(
            """
            SELECT c.story_id, dv.document_id
            FROM claims c
            JOIN claim_evidence ce ON ce.claim_id = c.id AND ce.relationship = 'supports'
            JOIN evidence_spans es ON es.id = ce.evidence_span_id
            JOIN document_versions dv ON dv.id = es.document_version_id
            JOIN documents d ON d.id = dv.document_id
            JOIN sources s ON s.id = d.source_id
            WHERE c.id = ? AND es.id = ?
            """,
            (cause.get("claim_id"), cause.get("evidence_span_id")),
        ).fetchone()
        if chain is None:
            return False
        if chain["story_id"] != cause.get("story_id") or chain["document_id"] != cause.get("document_id"):
            return False
        if cause.get("cause_id") == cause.get("claim_id"):
            return True
        if cause.get("cause_type") == "correction":
            correction = conn.execute(
                """
                SELECT 1
                FROM story_corrections sc
                JOIN claim_story_assignment_history h ON h.correction_id = sc.id
                WHERE sc.id = ? AND h.claim_id = ? AND h.to_story_id = ?
                """,
                (cause.get("cause_id"), cause.get("claim_id"), cause.get("story_id")),
            ).fetchone()
            return correction is not None
        event = conn.execute(
            "SELECT story_id, document_id FROM story_evolution_events WHERE id = ?",
            (cause.get("cause_id"),),
        ).fetchone()
        return bool(
            event
            and event["story_id"] == cause.get("story_id")
            and event["document_id"] == cause.get("document_id")
        )

    def generate_tx(
        self,
        conn: sqlite3.Connection,
        identifier: str,
        *,
        generated_at: str | datetime | None = None,
    ) -> dict[str, Any]:
        """Generate once for the exact current input inside a caller mutation transaction."""

        generated = _timestamp(generated_at)
        report = self._require(conn, identifier)
        if report["status"] != "active":
            raise DomainConflict("archived living reports cannot be generated")
        story_ids = self._story_ids(conn, report)
        claims = self._accepted_claims(conn, story_ids)
        sections, propositions = self._collect_sections(
            conn, story_ids, claims, report["target_id"]
        )
        current_claim_ids = [claim["id"] for claim in claims]
        current_hash = claim_set_hash(current_claim_ids)
        input_identity = _report_input_identity(sections, propositions)
        previous_revision_id = report["current_revision_id"]
        previous_revision = None
        if previous_revision_id:
            previous_revision = conn.execute(
                "SELECT * FROM report_revisions WHERE id = ? AND report_id = ?",
                (previous_revision_id, identifier),
            ).fetchone()
            if previous_revision is None:
                raise DomainConflict("living report current revision does not belong to the report")

        previous_claim_ids = self._previous_claim_ids(conn, identifier)
        previous_cause_ids = self._previous_cause_ids(conn, identifier)
        previous_evidence_ids = self._previous_evidence_ids(conn, identifier)
        causes: list[dict[str, Any]] = []
        for claim in claims:
            for item in self._claim_evidence(conn, claim["id"]):
                if item["relationship"] != "supports" or (
                    claim["id"] in previous_claim_ids
                    and item["evidence_span_id"] in previous_evidence_ids
                ):
                    continue
                correction = conn.execute(
                    """
                    SELECT sc.id
                    FROM story_corrections sc
                    JOIN claim_story_assignment_history h ON h.correction_id = sc.id
                    WHERE h.claim_id = ? AND h.to_story_id = ?
                    ORDER BY h.occurred_at DESC, h.id DESC
                    LIMIT 1
                    """,
                    (claim["id"], claim["story_id"]),
                ).fetchone()
                cause_type = "correction" if correction is not None and claim["id"] not in previous_claim_ids else (
                    "new_primary_evidence"
                    if item["default_quality"] == "primary" or item["source_kind"] == "official"
                    else "material_update"
                )
                causes.append(
                    {
                        "id": new_id("cause"),
                        "cause_type": cause_type,
                        "cause_id": correction["id"] if cause_type == "correction" else claim["id"],
                        "story_id": claim["story_id"],
                        "claim_id": claim["id"],
                        "evidence_span_id": item["evidence_span_id"],
                        "document_id": item["document_id"],
                        "rationale": "Story organization changed; this report revision reflects a corrected Claim membership." if cause_type == "correction" else "Accepted Claim entered the report evidence set.",
                    }
                )
        event_rows = []
        if story_ids:
            placeholders = ",".join("?" for _ in story_ids)
            event_rows = conn.execute(
                f"SELECT * FROM story_evolution_events WHERE story_id IN ({placeholders}) ORDER BY created_at, id LIMIT 200",
                story_ids,
            ).fetchall()
        for event in event_rows:
            if event["id"] in previous_cause_ids or not event["material_change"]:
                continue
            linked_evidence = [
                (claim["id"], item)
                for claim in claims
                for item in self._claim_evidence(conn, claim["id"])
                if item["document_id"] == event["document_id"]
                and item["relationship"] == "supports"
            ]
            if linked_evidence:
                claim_id, evidence = linked_evidence[0]
                causes.append(
                    {
                        "id": new_id("cause"),
                        "cause_type": _cause_event_type(event["update_class"]),
                        "cause_id": event["id"],
                        "story_id": event["story_id"],
                        "claim_id": claim_id,
                        "evidence_span_id": evidence["evidence_span_id"],
                        "document_id": event["document_id"],
                        "rationale": f"Story evolution recorded {event['update_class']} against accepted evidence.",
                    }
                )
        unique_causes: list[dict[str, Any]] = []
        seen_causes: set[tuple[str, str, str]] = set()
        for cause in causes:
            key = (cause["cause_type"], cause["cause_id"], cause["evidence_span_id"])
            if key not in seen_causes:
                seen_causes.add(key)
                unique_causes.append(cause)
        causes = unique_causes

        if previous_revision is not None and not causes and self._stored_input_identity(previous_revision) == input_identity:
            return {
                "status": "no_change",
                "report_id": identifier,
                "revision_id": previous_revision["id"],
                "input_identity": input_identity,
            }
        if previous_revision is not None and not causes:
            raise DomainConflict("material report input changed without an exact persisted cause")

        accepted_ids = {claim["id"] for claim in claims}
        unsupported_propositions = []
        for proposition in propositions:
            proposition_claim_ids = set(proposition.get("claim_ids", []))
            supported_claim_ids = {
                claim_id
                for claim_id in proposition_claim_ids & accepted_ids
                if any(
                    item["relationship"] == "supports"
                    for item in self._claim_evidence(conn, claim_id)
                )
            }
            if not proposition_claim_ids or supported_claim_ids != proposition_claim_ids:
                unsupported_propositions.append(proposition.get("text", ""))
        unsupported_changes = [
            cause["rationale"]
            for cause in causes
            if not self._validate_cause_tx(conn, cause, accepted_ids)
        ]
        audit = {
            "passed": not unsupported_propositions and not unsupported_changes,
            "unsupported_propositions": unsupported_propositions,
            "unsupported_changes": unsupported_changes,
            "claim_set_hash": current_hash,
            "input_identity": input_identity,
        }
        if not audit["passed"]:
            raise DomainConflict("report generation produced unsupported closed-world content")
        sections["what_changed"] = [
            {
                "text": cause["rationale"],
                "cause_type": cause["cause_type"],
                "cause_ids": [cause["id"]],
                "claim_ids": [cause["claim_id"]],
                "evidence_span_ids": [cause["evidence_span_id"]],
            }
            for cause in causes
        ]
        revision_number = conn.execute(
            "SELECT COALESCE(MAX(revision_number), 0) + 1 FROM report_revisions WHERE report_id = ?",
            (identifier,),
        ).fetchone()[0]
        revision_id = new_id("rptrev")
        conn.execute(
            """
            INSERT INTO report_revisions
                (id, report_id, revision_number, claim_set_hash, material_change,
                 current_status, what_changed, sections_json, propositions_json,
                 audit_json, generated_at, created_at)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                revision_id,
                identifier,
                revision_number,
                current_hash,
                sections["current_status"],
                _encode(sections["what_changed"]),
                _encode(sections),
                _encode(propositions),
                _encode(audit),
                generated,
                generated,
            ),
        )
        for position, claim_id in enumerate(current_claim_ids):
            conn.execute(
                "INSERT INTO report_revision_claims(revision_id, claim_id, position, created_at) VALUES (?, ?, ?, ?)",
                (revision_id, claim_id, position, generated),
            )
        for cause in causes:
            conn.execute(
                "INSERT INTO report_revision_causes(id, revision_id, cause_type, cause_id, story_id, claim_id, evidence_span_id, document_id, rationale, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cause["id"],
                    revision_id,
                    cause["cause_type"],
                    cause["cause_id"],
                    cause["story_id"],
                    cause["claim_id"],
                    cause["evidence_span_id"],
                    cause["document_id"],
                    cause["rationale"],
                    generated,
                ),
            )
        changed = conn.execute(
            "UPDATE living_reports SET current_revision_id = ?, updated_at = ? WHERE id = ?",
            (revision_id, generated, identifier),
        )
        if changed.rowcount != 1:
            raise DomainNotFound("living report not found")
        return {
            "status": "material",
            "report_id": identifier,
            "revision_id": revision_id,
            "input_identity": input_identity,
        }

    def generate(self, identifier: str, *, generated_at: str | datetime | None = None) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                generation = self.generate_tx(conn, identifier, generated_at=generated_at)
        finally:
            conn.close()
        result = self.get(identifier)
        result["generation"] = generation
        return result


class BriefingService:
    """Build deterministic daily or weekly briefings from material report revisions."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @staticmethod
    def _window(period: str, timezone_name: str, now: str | datetime | None = None) -> tuple[str, str]:
        if period not in BRIEFING_PERIODS:
            raise DomainValidation("briefing period must be daily or weekly")
        zone = _timezone(timezone_name)
        current = datetime.fromisoformat(_timestamp(now).replace("Z", "+00:00")).astimezone(zone)
        start = current.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "weekly":
            start -= timedelta(days=start.weekday())
            end = start + timedelta(days=7)
        else:
            end = start + timedelta(days=1)
        return _timestamp(start), _timestamp(end)

    @staticmethod
    def _result(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["monitor_ids"] = [
            item[0]
            for item in conn.execute(
                "SELECT monitor_id FROM briefing_monitors WHERE briefing_id = ? ORDER BY monitor_id",
                (row["id"],),
            ).fetchall()
        ]
        result["items"] = []
        for item in conn.execute(
            "SELECT * FROM briefing_items WHERE briefing_id = ? ORDER BY rank, id",
            (row["id"],),
        ).fetchall():
            parsed = dict(item)
            parsed["claim_ids"] = _decode(parsed.pop("claim_ids_json"), [])
            parsed["evidence_span_ids"] = _decode(parsed.pop("evidence_span_ids_json"), [])
            result["items"].append(parsed)
        return result

    def get(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM briefings WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("briefing not found")
            return self._result(conn, row)
        finally:
            conn.close()

    def generate(
        self,
        period: str,
        *,
        monitor_ids: list[str] | None = None,
        period_start: str | datetime | None = None,
        period_end: str | datetime | None = None,
        timezone_name: str = "UTC",
        generated_at: str | datetime | None = None,
    ) -> dict[str, Any]:
        if period not in BRIEFING_PERIODS:
            raise DomainValidation("briefing period must be daily or weekly")
        _timezone(timezone_name)
        selected_monitors = _unique(monitor_ids or [])
        if len(selected_monitors) > 100:
            raise DomainValidation("briefing monitor_ids cannot exceed 100 items")
        if period_start is None and period_end is None:
            start, end = self._window(period, timezone_name, generated_at)
        elif period_start is None or period_end is None:
            raise DomainValidation("period_start and period_end must be supplied together")
        else:
            start, end = _timestamp(period_start), _timestamp(period_end)
            if start >= end:
                raise DomainValidation("briefing period_start must precede period_end")
        identifier = new_id("briefing")
        now = _timestamp(generated_at)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                for monitor_id in selected_monitors:
                    if conn.execute("SELECT 1 FROM monitors WHERE id = ?", (monitor_id,)).fetchone() is None:
                        raise DomainNotFound("briefing monitor not found")
                conn.execute(
                    "INSERT OR IGNORE INTO briefings(id, period, timezone_name, period_start, period_end, status, created_at) VALUES (?, ?, ?, ?, ?, 'published', ?)",
                    (identifier, period, timezone_name, start, end, now),
                )
                row = conn.execute(
                    "SELECT * FROM briefings WHERE period = ? AND timezone_name = ? AND period_start = ? AND period_end = ?",
                    (period, timezone_name, start, end),
                ).fetchone()
                assert row is not None
                identifier = row["id"]
                for monitor_id in selected_monitors:
                    conn.execute("INSERT OR IGNORE INTO briefing_monitors(briefing_id, monitor_id, created_at) VALUES (?, ?, ?)", (identifier, monitor_id, now))
                params: list[Any] = [start, end]
                monitor_clause = ""
                if selected_monitors:
                    placeholders = ",".join("?" for _ in selected_monitors)
                    monitor_clause = f" AND lr.target_type = 'monitor' AND lr.target_id IN ({placeholders})"
                    params.extend(selected_monitors)
                else:
                    monitor_clause = " AND lr.target_type = 'monitor'"
                revisions = conn.execute(
                    f"""
                    SELECT lr.*, rr.id AS revision_id, rr.revision_number, rr.material_change,
                           rr.claim_set_hash, rr.sections_json, rr.generated_at
                    FROM living_reports lr
                    JOIN report_revisions rr ON rr.id = lr.current_revision_id
                    WHERE lr.status = 'active' AND rr.material_change = 1
                      AND rr.generated_at >= ? AND rr.generated_at < ?{monitor_clause}
                    ORDER BY rr.generated_at DESC, rr.id DESC
                    """,
                    params,
                ).fetchall()
                scored: list[dict[str, Any]] = []
                for revision in revisions:
                    causes = [
                        dict(cause)
                        for cause in conn.execute(
                            "SELECT * FROM report_revision_causes WHERE revision_id = ? ORDER BY created_at, id",
                            (revision["revision_id"],),
                        ).fetchall()
                    ]
                    if not causes:
                        continue
                    score = min(1.0, max(CAUSE_WEIGHTS.get(cause["cause_type"], 0.0) for cause in causes) + max(0, len({cause["cause_type"] for cause in causes}) - 1) * 0.02)
                    sections = _decode(revision["sections_json"], {})
                    story_id = next((cause.get("story_id") for cause in causes if cause.get("story_id")), None)
                    if story_id is None:
                        active_stories = sections.get("active_stories", []) if isinstance(sections, dict) else []
                        story_id = active_stories[0].get("story_id") if active_stories else None
                    claim_ids = [item[0] for item in conn.execute("SELECT claim_id FROM report_revision_claims WHERE revision_id = ? ORDER BY position", (revision["revision_id"],)).fetchall()]
                    evidence_ids = _unique([cause.get("evidence_span_id") for cause in causes])
                    reason = "; ".join(_unique([cause["rationale"] for cause in causes]))
                    scored.append({"report": revision, "story_id": story_id, "claim_ids": claim_ids, "evidence_span_ids": evidence_ids, "score": score, "reason": reason})
                scored.sort(key=lambda item: (-item["score"], item["report"]["generated_at"], item["report"]["revision_id"]))
                for rank, item in enumerate(scored, start=1):
                    exists = conn.execute(
                        "SELECT 1 FROM briefing_items WHERE briefing_id = ? AND report_revision_id = ? AND (story_id = ? OR (story_id IS NULL AND ? IS NULL))",
                        (identifier, item["report"]["revision_id"], item["story_id"], item["story_id"]),
                    ).fetchone()
                    if exists is not None:
                        continue
                    conn.execute(
                        "INSERT INTO briefing_items(id, briefing_id, report_id, report_revision_id, story_id, rank, importance_score, reason, claim_ids_json, evidence_span_ids_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (new_id("briefitem"), identifier, item["report"]["id"], item["report"]["revision_id"], item["story_id"], rank, item["score"], item["reason"], _encode(item["claim_ids"]), _encode(item["evidence_span_ids"]), now),
                    )
        finally:
            conn.close()
        return self.get(identifier)


class AlertService:
    """Persist user rules, material alerts, delivery state, and acknowledgement."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @staticmethod
    def _rule_result(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["event_types"] = _decode(result.pop("event_types_json"), [])
        result["browser_enabled"] = bool(result["browser_enabled"])
        result["enabled"] = bool(result["enabled"])
        return result

    @staticmethod
    def _validate_rule(data: Mapping[str, Any], *, partial: bool = False) -> dict[str, Any]:
        allowed = {"name", "target_type", "target_id", "event_types", "min_importance", "browser_enabled", "enabled", "dedupe_window_seconds", "timezone_name"}
        unknown = set(data) - allowed
        if unknown:
            raise DomainValidation("unknown alert rule field")
        result = dict(data)
        if not partial or "name" in result:
            result["name"] = _validate_name(result.get("name"), "alert rule name")
        if not partial or "target_type" in result:
            result["target_type"] = str(result.get("target_type", "all"))
            if result["target_type"] not in ALERT_TARGET_TYPES:
                raise DomainValidation("invalid alert rule target type")
        if not partial or "event_types" in result:
            event_types = result.get("event_types", [])
            if not isinstance(event_types, list) or any(item not in CAUSE_TYPES for item in event_types):
                raise DomainValidation("invalid alert rule event types")
            result["event_types"] = _unique(event_types)
        if not partial or "min_importance" in result:
            try:
                result["min_importance"] = float(result.get("min_importance", 0.0))
            except (TypeError, ValueError) as exc:
                raise DomainValidation("min_importance must be numeric") from exc
            if not 0.0 <= result["min_importance"] <= 1.0:
                raise DomainValidation("min_importance must be between 0 and 1")
        if not partial or "dedupe_window_seconds" in result:
            result["dedupe_window_seconds"] = int(result.get("dedupe_window_seconds", 86400))
            if not 0 <= result["dedupe_window_seconds"] <= 2_592_000:
                raise DomainValidation("dedupe_window_seconds is out of range")
        if "timezone_name" in result or not partial:
            result["timezone_name"] = str(result.get("timezone_name", "UTC"))
            _timezone(result["timezone_name"])
        if "target_id" in result:
            result["target_id"] = None if result["target_id"] is None else str(result["target_id"]).strip() or None
        for field in ("browser_enabled", "enabled"):
            if field in result:
                result[field] = bool(result[field])
        return result

    def _require_rule(self, conn: sqlite3.Connection, identifier: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM alert_rules WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise DomainNotFound("alert rule not found")
        return row

    def create_rule(self, data: Mapping[str, Any]) -> dict[str, Any]:
        values = self._validate_rule(data)
        if values["target_type"] != "all" and not values.get("target_id"):
            raise DomainValidation("target_id is required for targeted alert rules")
        identifier, now = new_id("alertrule"), utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if values["target_type"] == "report" and conn.execute("SELECT 1 FROM living_reports WHERE id = ?", (values["target_id"],)).fetchone() is None:
                    raise DomainNotFound("alert report target not found")
                if values["target_type"] == "monitor" and conn.execute("SELECT 1 FROM monitors WHERE id = ?", (values["target_id"],)).fetchone() is None:
                    raise DomainNotFound("alert monitor target not found")
                if values["target_type"] == "story" and conn.execute("SELECT 1 FROM stories WHERE id = ?", (values["target_id"],)).fetchone() is None:
                    raise DomainNotFound("alert story target not found")
                conn.execute(
                    "INSERT INTO alert_rules(id, name, target_type, target_id, event_types_json, min_importance, browser_enabled, enabled, dedupe_window_seconds, timezone_name, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (identifier, values["name"], values["target_type"], values.get("target_id"), _encode(values["event_types"]), values["min_importance"], int(values.get("browser_enabled", False)), int(values.get("enabled", True)), values["dedupe_window_seconds"], values["timezone_name"], now, now),
                )
        finally:
            conn.close()
        return self.get_rule(identifier)

    def get_rule(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return self._rule_result(self._require_rule(conn, identifier))
        finally:
            conn.close()

    def list_rules(self, *, enabled: bool | None = None) -> list[dict[str, Any]]:
        conn = storage.connect(self.db_path)
        try:
            if enabled is None:
                rows = conn.execute("SELECT * FROM alert_rules ORDER BY created_at, id").fetchall()
            else:
                rows = conn.execute("SELECT * FROM alert_rules WHERE enabled = ? ORDER BY created_at, id", (int(enabled),)).fetchall()
            return [self._rule_result(row) for row in rows]
        finally:
            conn.close()

    def update_rule(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        values = self._validate_rule(data, partial=True)
        if "target_type" in values and values["target_type"] != "all" and not values.get("target_id", self.get_rule(identifier).get("target_id")):
            raise DomainValidation("target_id is required for targeted alert rules")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                current = self._require_rule(conn, identifier)
                current_values = self._rule_result(current)
                merged = self._validate_rule({field: current_values[field] for field in ("name", "target_type", "target_id", "event_types", "min_importance", "browser_enabled", "enabled", "dedupe_window_seconds", "timezone_name")} | values)
                if merged["target_type"] != "all" and not merged.get("target_id"):
                    raise DomainValidation("target_id is required for targeted alert rules")
                target_table = {"report": "living_reports", "monitor": "monitors", "story": "stories"}.get(merged["target_type"])
                if target_table and conn.execute(f"SELECT 1 FROM {target_table} WHERE id = ?", (merged["target_id"],)).fetchone() is None:
                    raise DomainNotFound("alert target not found")
                conn.execute(
                    "UPDATE alert_rules SET name = ?, target_type = ?, target_id = ?, event_types_json = ?, min_importance = ?, browser_enabled = ?, enabled = ?, dedupe_window_seconds = ?, timezone_name = ?, updated_at = ? WHERE id = ?",
                    (merged["name"], merged["target_type"], merged.get("target_id"), _encode(merged["event_types"]), merged["min_importance"], int(merged["browser_enabled"]), int(merged["enabled"]), merged["dedupe_window_seconds"], merged["timezone_name"], utc_now(), identifier),
                )
        finally:
            conn.close()
        return self.get_rule(identifier)

    def get_notification_preferences(self) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM notification_preferences WHERE id = 1").fetchone()
            assert row is not None
            result = dict(row)
            for field in ("browser_enabled", "online"):
                result[field] = bool(result[field])
            return result
        finally:
            conn.close()

    def set_notification_preferences(
        self,
        data: Mapping[str, Any] | None = None,
        *,
        browser_enabled: bool | None = None,
        permission_state: str | None = None,
        online: bool | None = None,
    ) -> dict[str, Any]:
        values = dict(data or {})
        if browser_enabled is not None:
            values["browser_enabled"] = browser_enabled
        if permission_state is not None:
            values["permission_state"] = permission_state
        if online is not None:
            values["online"] = online
        permission_state = str(values.get("permission_state", "default"))
        if permission_state not in {"default", "granted", "denied"}:
            raise DomainValidation("invalid browser permission state")
        browser_enabled, online = bool(values.get("browser_enabled", False)), bool(values.get("online", True))
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute("UPDATE notification_preferences SET browser_enabled = ?, permission_state = ?, online = ?, updated_at = ? WHERE id = 1", (int(browser_enabled), permission_state, int(online), utc_now()))
        finally:
            conn.close()
        return self.get_notification_preferences()

    @staticmethod
    def _alert_result(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["cause"] = _decode(result.pop("cause_json"), [])
        result["deliveries"] = [dict(item) for item in conn.execute("SELECT * FROM alert_deliveries WHERE alert_id = ? ORDER BY channel", (row["id"],)).fetchall()]
        return result

    def get_alert(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM alerts WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("alert not found")
            return self._alert_result(conn, row)
        finally:
            conn.close()

    def list_alerts(self, *, status: str | None = None, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        if status is not None and status not in ALERT_STATUSES:
            raise DomainValidation("invalid alert status")
        if page < 1 or page_size < 1 or page_size > 100:
            raise DomainValidation("invalid alert page")
        conn = storage.connect(self.db_path)
        try:
            clause, params = ("status = ?", [status]) if status else ("1 = 1", [])
            total = conn.execute(f"SELECT COUNT(*) FROM alerts WHERE {clause}", params).fetchone()[0]
            rows = conn.execute(f"SELECT * FROM alerts WHERE {clause} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()
            return {"items": [self._alert_result(conn, row) for row in rows], "page": page, "page_size": page_size, "total": total}
        finally:
            conn.close()

    @staticmethod
    def _matching_causes(
        rule: sqlite3.Row,
        report: sqlite3.Row,
        causes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not rule["enabled"]:
            return []
        configured_events = _decode(rule["event_types_json"], [])
        matching = [
            cause
            for cause in causes
            if not configured_events or cause["cause_type"] in configured_events
        ]
        target_type = rule["target_type"]
        target_id = rule["target_id"]
        if target_type == "all":
            return matching
        if target_type == "report":
            return matching if target_id == report["id"] else []
        if target_type == "monitor":
            return (
                matching
                if report["target_type"] == "monitor" and target_id == report["target_id"]
                else []
            )
        return [cause for cause in matching if cause.get("story_id") == target_id]

    def emit_for_report_revision_tx(
        self,
        conn: sqlite3.Connection,
        report_id: str,
        revision_id: str | None = None,
        *,
        in_app_only: bool = False,
        suppress_equivalent: bool = True,
    ) -> dict[str, Any]:
        """Persist exact-cause Alerts inside an existing write transaction."""

        created: list[str] = []
        alert_ids: list[str] = []
        delivery_ids: list[str] = []
        report = conn.execute(
            "SELECT * FROM living_reports WHERE id = ?", (report_id,)
        ).fetchone()
        if report is None:
            raise DomainNotFound("living report not found")
        revision_id = revision_id or report["current_revision_id"]
        revision = conn.execute(
            "SELECT * FROM report_revisions WHERE id = ? AND report_id = ?",
            (revision_id, report_id),
        ).fetchone()
        if revision is None:
            raise DomainNotFound("report revision not found")
        causes = [
            dict(item)
            for item in conn.execute(
                "SELECT * FROM report_revision_causes WHERE revision_id = ? ORDER BY id",
                (revision_id,),
            ).fetchall()
        ]
        rules = conn.execute(
            "SELECT * FROM alert_rules WHERE enabled = 1 ORDER BY created_at, id"
        ).fetchall()
        evaluated_rule_ids = [rule["id"] for rule in rules]
        if not revision["material_change"] or not causes:
            return {
                "created_count": 0,
                "items": [],
                "alert_ids": [],
                "delivery_ids": [],
                "evaluated_rule_ids": evaluated_rule_ids,
            }
        prefs = conn.execute(
            "SELECT * FROM notification_preferences WHERE id = 1"
        ).fetchone()
        for rule in rules:
            configured_events = _decode(rule["event_types_json"], [])
            matching_causes = sorted(
                self._matching_causes(rule, report, causes), key=lambda cause: cause["id"]
            )
            if not matching_causes:
                continue
            importance = min(
                1.0,
                max(
                    CAUSE_WEIGHTS.get(cause["cause_type"], 0.0)
                    for cause in matching_causes
                )
                + max(0, len({cause["cause_type"] for cause in matching_causes}) - 1)
                * 0.02,
            )
            if importance < rule["min_importance"]:
                continue
            event_type = max(
                matching_causes,
                key=lambda cause: (
                    CAUSE_WEIGHTS.get(cause["cause_type"], 0.0),
                    cause["id"],
                ),
            )["cause_type"]
            matching_cause_keys = sorted(
                (cause["id"], cause.get("evidence_span_id"), cause.get("claim_id"))
                for cause in matching_causes
            )
            semantic_cause_keys = sorted(
                (
                    cause["cause_type"],
                    cause.get("story_id"),
                    cause.get("claim_id"),
                    cause.get("evidence_span_id"),
                    cause.get("document_id"),
                )
                for cause in matching_causes
            )
            dedupe_window = int(rule["dedupe_window_seconds"])
            if suppress_equivalent and dedupe_window > 0:
                threshold = _timestamp(
                    datetime.fromisoformat(utc_now().replace("Z", "+00:00"))
                    - timedelta(seconds=dedupe_window)
                )
                recent = conn.execute(
                    "SELECT cause_json FROM alerts WHERE rule_id = ? AND report_id = ? AND created_at >= ? ORDER BY created_at DESC LIMIT 1000",
                    (rule["id"], report_id, threshold),
                ).fetchall()
                duplicate = False
                for prior in recent:
                    prior_causes = [
                        cause
                        for cause in _decode(prior["cause_json"], [])
                        if not configured_events
                        or cause["cause_type"] in configured_events
                    ]
                    prior_semantic_keys = sorted(
                        (
                            cause["cause_type"],
                            cause.get("story_id"),
                            cause.get("claim_id"),
                            cause.get("evidence_span_id"),
                            cause.get("document_id"),
                        )
                        for cause in prior_causes
                    )
                    if prior_semantic_keys == semantic_cause_keys:
                        duplicate = True
                        break
                if duplicate:
                    continue
            dedupe_key = hashlib.sha256(
                _encode(
                    {
                        "rule_id": rule["id"],
                        "report_revision_id": revision_id,
                        "causes": matching_cause_keys,
                    }
                ).encode("utf-8")
            ).hexdigest()
            existing = conn.execute(
                "SELECT id FROM alerts WHERE dedupe_key = ?", (dedupe_key,)
            ).fetchone()
            now = utc_now()
            if existing is None:
                alert_id = new_id("alert")
                story_id = (
                    report["target_id"]
                    if report["target_type"] == "story"
                    else next(
                        (
                            cause.get("story_id")
                            for cause in matching_causes
                            if cause.get("story_id")
                        ),
                        None,
                    )
                )
                body = "; ".join(
                    _unique([cause["rationale"] for cause in matching_causes])
                )
                conn.execute(
                    "INSERT INTO alerts(id, rule_id, report_id, report_revision_id, story_id, event_type, title, body, importance_score, dedupe_key, cause_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        alert_id,
                        rule["id"],
                        report_id,
                        revision_id,
                        story_id,
                        event_type,
                        f"{event_type.replace('_', ' ').capitalize()}: {report['name']}",
                        body,
                        importance,
                        dedupe_key,
                        _encode(matching_causes),
                        now,
                    ),
                )
                created.append(alert_id)
            else:
                alert_id = existing["id"]
            conn.execute(
                "INSERT OR IGNORE INTO alert_deliveries(id, alert_id, channel, status, attempt_count, delivered_at, created_at, updated_at) VALUES (?, ?, 'in_app', 'sent', 1, ?, ?, ?)",
                (new_id("delivery"), alert_id, now, now, now),
            )
            delivery = conn.execute(
                "SELECT id FROM alert_deliveries WHERE alert_id = ? AND channel = 'in_app'",
                (alert_id,),
            ).fetchone()
            if delivery is None:
                raise DomainConflict("in-app Alert delivery was not persisted")
            if not in_app_only and rule["browser_enabled"]:
                if not prefs["browser_enabled"]:
                    browser_status, error = "skipped", "browser notifications disabled"
                elif prefs["permission_state"] == "denied":
                    browser_status, error = "denied", "browser notification permission denied"
                elif not prefs["online"]:
                    browser_status, error = (
                        "offline",
                        "browser notification delivery deferred while offline",
                    )
                else:
                    browser_status, error = "pending", None
                conn.execute(
                    "INSERT OR IGNORE INTO alert_deliveries(id, alert_id, channel, status, attempt_count, error_detail, created_at, updated_at) VALUES (?, ?, 'browser', ?, 0, ?, ?, ?)",
                    (new_id("delivery"), alert_id, browser_status, error, now, now),
                )
            alert_ids.append(alert_id)
            delivery_ids.append(delivery["id"])
        return {
            "created_count": len(created),
            "items": [
                self._alert_result(
                    conn,
                    conn.execute("SELECT * FROM alerts WHERE id = ?", (identifier,)).fetchone(),
                )
                for identifier in created
            ],
            "alert_ids": alert_ids,
            "delivery_ids": delivery_ids,
            "evaluated_rule_ids": evaluated_rule_ids,
        }

    def emit_for_report_revision(
        self, report_id: str, revision_id: str | None = None
    ) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                return self.emit_for_report_revision_tx(conn, report_id, revision_id)
        finally:
            conn.close()

    def acknowledge(self, identifier: str, acknowledged_by: str | None = None) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT id FROM alerts WHERE id = ?", (identifier,)).fetchone()
                if row is None:
                    raise DomainNotFound("alert not found")
                conn.execute("UPDATE alerts SET status = 'acknowledged', acknowledged_at = ?, acknowledged_by = ? WHERE id = ? AND status = 'unread'", (utc_now(), acknowledged_by, identifier))
        finally:
            conn.close()
        return self.get_alert(identifier)

    def record_delivery(self, identifier: str, status: str, error_detail: str | None = None) -> dict[str, Any]:
        if status not in DELIVERY_STATUSES:
            raise DomainValidation("invalid alert delivery status")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT id FROM alert_deliveries WHERE id = ?", (identifier,)).fetchone()
                if row is None:
                    raise DomainNotFound("alert delivery not found")
                conn.execute("UPDATE alert_deliveries SET status = ?, attempt_count = attempt_count + 1, error_detail = ?, delivered_at = ?, updated_at = ? WHERE id = ?", (status, error_detail, utc_now() if status == "sent" else None, utc_now(), identifier))
                result = conn.execute("SELECT * FROM alert_deliveries WHERE id = ?", (identifier,)).fetchone()
                return dict(result)
        finally:
            conn.close()

    def emit(self, report_id: str, revision_id: str | None = None) -> dict[str, Any]:
        return self.emit_for_report_revision(report_id, revision_id)


ReportService = LivingReportService


__all__ = ["AlertService", "BriefingService", "LivingReportService", "ReportService"]
