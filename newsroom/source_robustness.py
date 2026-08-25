"""On-demand source dependency summaries and non-mutating counterfactuals."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from . import storage
from .domain import DomainNotFound, DomainValidation


DEPENDENCY_RELATIONSHIPS = frozenset(
    {"syndicated_from", "wire_propagation", "rewritten_from", "common_primary_document"}
)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class SourceRobustnessService:
    """Compute current dependency groups directly from document lineage."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

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

    @classmethod
    def _component_groups(cls, conn: sqlite3.Connection, document_ids: list[str]) -> list[list[str]]:
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
                    if related not in component:
                        component.add(related)
                        frontier.append(related)
            remaining -= component
            groups.append(sorted(component))
        return sorted(groups, key=lambda group: group[0])

    @staticmethod
    def _claim_ids_tx(conn: sqlite3.Connection, target_type: str, target_id: str) -> list[str]:
        if target_type == "claim":
            query, params = "SELECT id FROM claims WHERE id = ?", (target_id,)
        elif target_type == "story":
            if conn.execute("SELECT 1 FROM stories WHERE id = ?", (target_id,)).fetchone() is None:
                raise DomainNotFound("story not found")
            query, params = "SELECT id FROM claims WHERE story_id = ?", (target_id,)
        elif target_type == "report":
            if conn.execute("SELECT 1 FROM living_reports WHERE id = ?", (target_id,)).fetchone() is None:
                raise DomainNotFound("report not found")
            query, params = (
                "SELECT claim_id FROM report_revision_claims WHERE revision_id = "
                "(SELECT current_revision_id FROM living_reports WHERE id = ?)",
                (target_id,),
            )
        else:
            raise DomainValidation("unsupported dependency target type")
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
            groups = self._component_groups(conn, document_ids)
            group_by_document = {document_id: group[0] for group in groups for document_id in group}
            component_document_ids = sorted({item for group in groups for item in group})
            source_by_document = {
                row["id"]: row["source_id"]
                for row in conn.execute(
                    "SELECT id, source_id FROM documents WHERE id IN ({})".format(",".join("?" for _ in component_document_ids)),
                    component_document_ids,
                ).fetchall()
            } if component_document_ids else {}
            group_summaries = [
                {
                    "id": group[0],
                    "document_ids": group,
                    "source_ids": sorted({source_by_document[item] for item in group if item in source_by_document}),
                    "support_document_count": len(set(group) & set(document_ids)),
                }
                for group in groups
            ]
            claim_paths: list[dict[str, Any]] = []
            for claim_id in claim_ids:
                claim_rows = [item for item in paths if item["claim_id"] == claim_id]
                claim_docs = sorted({item["document_id"] for item in claim_rows})
                claim_sources = sorted({item["source_id"] for item in claim_rows})
                claim_groups = sorted({group_by_document[item] for item in claim_docs})
                claim_paths.append({"claim_id": claim_id, "document_ids": claim_docs, "source_ids": claim_sources, "dependency_group_ids": claim_groups})
            supported_claim_ids = {item["claim_id"] for item in claim_paths if item["document_ids"]}
            support_count = len(document_ids)
            largest_group_share = round(max((item["support_document_count"] for item in group_summaries), default=0) / max(1, support_count), 6)
            return {
                "target_type": target_type,
                "target_id": target_id,
                "claim_ids": claim_ids,
                "document_ids": document_ids,
                "document_source_ids": {item["document_id"]: item["source_id"] for item in paths},
                "distinct_source_count": len({item["source_id"] for item in paths}),
                "dependency_group_count": len(group_summaries),
                "dependency_groups": group_summaries,
                "largest_group_share": largest_group_share,
                "single_group_claim_ids": sorted(item["claim_id"] for item in claim_paths if len(item["dependency_group_ids"]) == 1),
                "unsupported_claim_ids": sorted(set(claim_ids) - supported_claim_ids),
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
            return {"document": dict(document), "dependency_group": self._lineage_group_tx(conn, document_id), "outgoing": outgoing, "incoming": incoming, "dependency_count": len(outgoing) + len(incoming)}
        finally:
            conn.close()

    def source_summary(self, source_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            source = conn.execute("SELECT id, name, slug FROM sources WHERE id = ?", (source_id,)).fetchone()
            if source is None:
                raise DomainNotFound("source not found")
            document_ids = [row[0] for row in conn.execute("SELECT id FROM documents WHERE source_id = ? ORDER BY id", (source_id,))]
            groups = self._component_groups(conn, document_ids)
            failures = conn.execute("SELECT COUNT(*) FROM acquisition_events WHERE source_id = ? AND outcome IN ('failed', 'blocked')", (source_id,)).fetchone()[0]
            return {"source": dict(source), "document_count": len(document_ids), "dependency_group_count": len(groups), "dependency_groups": [{"id": group[0], "document_ids": group} for group in groups], "acquisition_failure_count": failures}
        finally:
            conn.close()

    def counterfactual(self, target_type: str, target_id: str, *, exclude_document_ids: Iterable[str] = (), exclude_source_ids: Iterable[str] = ()) -> dict[str, Any]:
        summary = self.evidence_summary(target_type, target_id)
        excluded_documents = {str(item) for item in exclude_document_ids if str(item)}
        excluded_sources = {str(item) for item in exclude_source_ids if str(item)}
        anchor_documents = set(excluded_documents)
        supporting_documents = set(summary["document_ids"])
        for source_id in excluded_sources:
            anchor_documents.update(
                document_id
                for document_id in supporting_documents
                if summary["document_source_ids"].get(document_id) == source_id
            )
        resolved_groups: list[list[str]] = []
        resolved_excluded_documents: set[str] = set()
        if anchor_documents:
            conn = storage.connect(self.db_path)
            try:
                resolved_groups = self._component_groups(conn, sorted(anchor_documents))
            finally:
                conn.close()
            resolved_excluded_documents = {
                document_id for group in resolved_groups for document_id in group
            }
        source_by_document = summary.get("document_source_ids", {})
        surviving_claim_ids: list[str] = []
        dropped_claim_ids: list[str] = []
        affected_claim_ids: set[str] = set()
        for path in summary["claim_paths"]:
            remaining = [
                document_id
                for document_id in path["document_ids"]
                if document_id not in resolved_excluded_documents
                and source_by_document.get(document_id) not in excluded_sources
            ]
            if remaining:
                surviving_claim_ids.append(path["claim_id"])
            else:
                dropped_claim_ids.append(path["claim_id"])
            if len(remaining) != len(path["document_ids"]):
                affected_claim_ids.add(path["claim_id"])
        input_fingerprint = hashlib.sha256(_json(summary).encode("utf-8")).hexdigest()
        return {
            "target_type": target_type,
            "target_id": target_id,
            "input_fingerprint": input_fingerprint,
            "excluded_document_ids": sorted(excluded_documents),
            "excluded_source_ids": sorted(excluded_sources),
            "resolved_excluded_document_ids": sorted(resolved_excluded_documents),
            "resolved_dependency_groups": resolved_groups,
            "changed": bool(affected_claim_ids),
            "surviving_claim_ids": sorted(surviving_claim_ids),
            "dropped_claim_ids": sorted(dropped_claim_ids),
            "affected_claim_ids": sorted(affected_claim_ids),
            "explanation": "Counterfactual excludes current Documents or Sources in memory; canonical Claims, Evidence, and lineage are unchanged.",
        }


__all__ = ["DEPENDENCY_RELATIONSHIPS", "SourceRobustnessService"]
