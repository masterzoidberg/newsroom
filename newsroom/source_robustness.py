"""Source dependency, evidence-family, and non-mutating fragility analysis."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from . import storage
from .domain import DomainNotFound, DomainValidation, new_id, utc_now


DEPENDENCY_RELATIONSHIPS = frozenset(
    {"syndicated_from", "wire_propagation", "rewritten_from", "common_primary_document"}
)
FAMILY_ALGORITHM_VERSION = "evidence_family_v1"
EVIDENCE_FAMILY_REBUILD_JOB_TYPE = "evidence_family_rebuild"
FRAGILITY_ANALYSIS_JOB_TYPE = "fragility_analysis"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None


class SourceRobustnessService:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def handlers(self) -> dict[str, Any]:
        return {
            EVIDENCE_FAMILY_REBUILD_JOB_TYPE: self._handle_family_rebuild,
            FRAGILITY_ANALYSIS_JOB_TYPE: self._handle_fragility,
        }

    def _handle_family_rebuild(self, job: dict[str, Any]) -> dict[str, Any]:
        document_ids = (job.get("payload") or {}).get("document_ids") or []
        return {"families": self.rebuild_evidence_families(document_ids)}

    def _handle_fragility(self, job: dict[str, Any]) -> dict[str, Any]:
        payload = job.get("payload") or {}
        return self.analyze_fragility(str(payload.get("target_type") or ""), str(payload.get("target_id") or ""))

    @staticmethod
    def _lineage_group_tx(conn: sqlite3.Connection, document_id: str) -> str:
        seen = {document_id}
        frontier = [document_id]
        while frontier:
            current = frontier.pop()
            rows = conn.execute(
                """
                SELECT parent_document_id AS related FROM document_lineage
                WHERE document_id = ? AND relationship IN ('syndicated_from','wire_propagation','rewritten_from','common_primary_document')
                UNION
                SELECT document_id AS related FROM document_lineage
                WHERE parent_document_id = ? AND relationship IN ('syndicated_from','wire_propagation','rewritten_from','common_primary_document')
                """,
                (current, current),
            ).fetchall()
            for row in rows:
                if row["related"] not in seen:
                    seen.add(row["related"])
                    frontier.append(row["related"])
        return min(seen)

    @staticmethod
    def _component_groups(conn: sqlite3.Connection, document_ids: list[str]) -> list[list[str]]:
        remaining = set(document_ids)
        groups: list[list[str]] = []
        while remaining:
            start = min(remaining)
            component = {start}
            frontier = [start]
            while frontier:
                current = frontier.pop()
                rows = conn.execute(
                    """
                    SELECT parent_document_id AS related FROM document_lineage
                    WHERE document_id = ? AND relationship IN ('syndicated_from','wire_propagation','rewritten_from','common_primary_document')
                    UNION
                    SELECT document_id AS related FROM document_lineage
                    WHERE parent_document_id = ? AND relationship IN ('syndicated_from','wire_propagation','rewritten_from','common_primary_document')
                    """,
                    (current, current),
                ).fetchall()
                for row in rows:
                    related = row["related"]
                    if related in remaining and related not in component:
                        component.add(related)
                        frontier.append(related)
            remaining -= component
            groups.append(sorted(component))
        return sorted(groups, key=lambda group: group[0])

    def rebuild_evidence_families(self, document_ids: Iterable[str]) -> list[dict[str, Any]]:
        requested = sorted(set(str(item).strip() for item in document_ids if str(item).strip()))
        if not requested:
            return []
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                placeholders = ",".join("?" for _ in requested)
                rows = conn.execute(
                    f"SELECT id, source_id FROM documents WHERE id IN ({placeholders})",
                    requested,
                ).fetchall()
                if len(rows) != len(requested):
                    raise DomainNotFound("evidence family document not found")
                conn.execute(
                    f"DELETE FROM evidence_family_members WHERE document_id IN ({placeholders})",
                    requested,
                )
                groups = self._component_groups(conn, requested)
                output: list[dict[str, Any]] = []
                now = utc_now()
                for group in groups:
                    family_key = hashlib.sha256(_json({"algorithm": FAMILY_ALGORITHM_VERSION, "documents": group}).encode()).hexdigest()
                    existing = conn.execute("SELECT * FROM evidence_families WHERE family_key = ?", (family_key,)).fetchone()
                    if existing is None:
                        family_id = new_id("family")
                        conn.execute(
                            "INSERT INTO evidence_families(id, family_key, label, origin, authority, algorithm_version, created_at, updated_at) VALUES (?, ?, ?, 'deterministic', 'derived', ?, ?, ?)",
                            (family_id, family_key, f"Evidence family {group[0]}", FAMILY_ALGORITHM_VERSION, now, now),
                        )
                    else:
                        family_id = existing["id"]
                        conn.execute("UPDATE evidence_families SET updated_at = ? WHERE id = ?", (now, family_id))
                    for document_id in group:
                        source_id = next(row["source_id"] for row in rows if row["id"] == document_id)
                        conn.execute(
                            "INSERT INTO evidence_family_members(family_id, document_id, source_id, relationship, confidence, created_at) VALUES (?, ?, ?, 'member', 1.0, ?)",
                            (family_id, document_id, source_id, now),
                        )
                    output.append({"id": family_id, "family_key": family_key, "document_ids": group})
                conn.execute(
                    "DELETE FROM evidence_families WHERE origin = 'deterministic' AND authority = 'derived' AND NOT EXISTS (SELECT 1 FROM evidence_family_members m WHERE m.family_id = evidence_families.id)"
                )
                return output
        finally:
            conn.close()

    @staticmethod
    def _claim_ids_tx(conn: sqlite3.Connection, target_type: str, target_id: str) -> list[str]:
        if target_type == "claim":
            query, params = "SELECT id FROM claims WHERE id = ?", (target_id,)
        elif target_type == "story":
            query, params = "SELECT id FROM claims WHERE story_id = ?", (target_id,)
        elif target_type == "report":
            query, params = "SELECT claim_id FROM report_revision_claims WHERE revision_id = (SELECT current_revision_id FROM living_reports WHERE id = ?)", (target_id,)
        else:
            return []
        rows = conn.execute(query, params).fetchall()
        if target_type == "claim" and not rows:
            raise DomainNotFound("claim not found")
        return [row[0] for row in rows]

    @staticmethod
    def _claim_paths_tx(conn: sqlite3.Connection, claim_ids: list[str]) -> list[dict[str, Any]]:
        if not claim_ids:
            return []
        placeholders = ",".join("?" for _ in claim_ids)
        rows = conn.execute(
            f"""
            SELECT ce.claim_id, d.id AS document_id, d.source_id
            FROM claim_evidence ce
            JOIN evidence_spans es ON es.id = ce.evidence_span_id
            JOIN document_versions dv ON dv.id = es.document_version_id
            JOIN documents d ON d.id = dv.document_id
            WHERE ce.relationship = 'supports' AND ce.claim_id IN ({placeholders})
            ORDER BY ce.claim_id, d.id
            """,
            claim_ids,
        ).fetchall()
        return [dict(row) for row in rows]

    def evidence_summary(self, target_type: str, target_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            claim_ids = self._claim_ids_tx(conn, target_type, target_id)
            paths = self._claim_paths_tx(conn, claim_ids)
            document_ids = sorted({item["document_id"] for item in paths})
            family_rows = conn.execute(
                f"SELECT m.document_id, m.family_id FROM evidence_family_members m WHERE m.document_id IN ({','.join('?' for _ in document_ids)}) ORDER BY m.document_id, m.family_id",
                document_ids,
            ).fetchall() if document_ids else []
            family_by_document = {row["document_id"]: row["family_id"] for row in family_rows}
            missing = [item for item in document_ids if item not in family_by_document]
        finally:
            conn.close()

        if missing:
            self.rebuild_evidence_families(missing)
            return self.evidence_summary(target_type, target_id)

        conn = storage.connect(self.db_path)
        try:
            family_ids = sorted({family_by_document[item] for item in document_ids})
            lineage_groups = sorted({self._lineage_group_tx(conn, item) for item in document_ids})
            claim_paths: list[dict[str, Any]] = []
            for claim_id in claim_ids:
                claim_docs = sorted({item["document_id"] for item in paths if item["claim_id"] == claim_id})
                claim_sources = sorted({item["source_id"] for item in paths if item["claim_id"] == claim_id})
                claim_families = sorted({family_by_document[item] for item in claim_docs})
                claim_paths.append({"claim_id": claim_id, "document_ids": claim_docs, "source_ids": claim_sources, "family_ids": claim_families})
            return {
                "target_type": target_type,
                "target_id": target_id,
                "claim_ids": claim_ids,
                "document_ids": document_ids,
                "distinct_source_count": len({item["source_id"] for item in paths}),
                "lineage_group_count": len(lineage_groups),
                "evidence_family_count": len(family_ids),
                "family_ids": family_ids,
                "claim_paths": claim_paths,
            }
        finally:
            conn.close()

    def dependency_summary(self, document_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            document = conn.execute("SELECT id, source_id, title, canonical_url FROM documents WHERE id = ?", (document_id,)).fetchone()
            if document is None:
                raise DomainNotFound("document not found")
            outgoing = [dict(row) for row in conn.execute("SELECT * FROM document_lineage WHERE document_id = ? ORDER BY created_at, id", (document_id,)).fetchall()]
            incoming = [dict(row) for row in conn.execute("SELECT * FROM document_lineage WHERE parent_document_id = ? ORDER BY created_at, id", (document_id,)).fetchall()]
            return {
                "document": dict(document),
                "lineage_group": self._lineage_group_tx(conn, document_id),
                "outgoing": outgoing,
                "incoming": incoming,
                "dependency_count": len(outgoing) + len(incoming),
            }
        finally:
            conn.close()

    def source_summary(self, source_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            source = conn.execute("SELECT id, name, slug FROM sources WHERE id = ?", (source_id,)).fetchone()
            if source is None:
                raise DomainNotFound("source not found")
            document_ids = [row[0] for row in conn.execute("SELECT id FROM documents WHERE source_id = ? ORDER BY id", (source_id,))]
            family_rows = conn.execute(
                f"SELECT DISTINCT family_id FROM evidence_family_members WHERE source_id = ?" if _table_exists(conn, "evidence_family_members") else "SELECT NULL WHERE 0",
                (source_id,),
            ).fetchall()
            lineage_groups = sorted({self._lineage_group_tx(conn, document_id) for document_id in document_ids})
            failures = conn.execute("SELECT COUNT(*) FROM acquisition_events WHERE source_id = ? AND outcome IN ('error', 'failed')", (source_id,)).fetchone()[0] if _table_exists(conn, "acquisition_events") else 0
            return {
                "source": dict(source),
                "document_count": len(document_ids),
                "evidence_family_count": len(family_rows),
                "lineage_group_count": len(lineage_groups),
                "acquisition_failure_count": failures,
                "dependency_groups": lineage_groups,
            }
        finally:
            conn.close()
    def analyze_fragility(self, target_type: str, target_id: str) -> dict[str, Any]:
        summary = self.evidence_summary(target_type, target_id)
        paths = summary["claim_paths"]
        scores = [
            1.0 - (len(path["family_ids"]) / max(1, len(path["source_ids"])))
            for path in paths
            if path["source_ids"]
        ]
        score = round(max(scores, default=0.0), 6)
        fingerprint = hashlib.sha256(_json(summary).encode()).hexdigest()
        explanation = {
            "interpretation": "higher means more support traces to fewer evidence families",
            "fragile_claim_ids": [path["claim_id"] for path in paths if len(path["family_ids"]) <= 1 and path["family_ids"]],
        }
        return {
            "id": new_id("fragility"),
            "target_type": target_type,
            "target_id": target_id,
            "input_fingerprint": fingerprint,
            "claim_ids": summary["claim_ids"],
            "distinct_source_count": summary["distinct_source_count"],
            "lineage_group_count": summary["lineage_group_count"],
            "evidence_family_count": summary["evidence_family_count"],
            "fragility_score": score,
            "support_paths": paths,
            "explanation": explanation,
        }

    def counterfactual(self, target_type: str, target_id: str, excluded_family_ids: Iterable[str]) -> dict[str, Any]:
        analysis = self.analyze_fragility(target_type, target_id)
        excluded = set(str(item) for item in excluded_family_ids)
        surviving: list[str] = []
        dropped: list[str] = []
        for path in analysis["support_paths"]:
            remaining = set(path["family_ids"]) - excluded
            if remaining:
                surviving.append(path["claim_id"])
            else:
                dropped.append(path["claim_id"])
        affected = [path["claim_id"] for path in analysis["support_paths"] if set(path["family_ids"]) & excluded]
        return {
            "target_type": target_type,
            "target_id": target_id,
            "input_fingerprint": analysis["input_fingerprint"],
            "excluded_family_ids": sorted(excluded),
            "changed": bool(affected),
            "surviving_claim_ids": sorted(surviving),
            "dropped_claim_ids": sorted(dropped),
            "explanation": "Counterfactual excludes evidence families in memory; canonical Claims and Evidence are unchanged.",
        }


__all__ = ["DEPENDENCY_RELATIONSHIPS", "EVIDENCE_FAMILY_REBUILD_JOB_TYPE", "FAMILY_ALGORITHM_VERSION", "FRAGILITY_ANALYSIS_JOB_TYPE", "SourceRobustnessService"]
