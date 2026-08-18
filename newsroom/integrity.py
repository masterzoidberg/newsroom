"""Database integrity checks, including deliberate polymorphic references."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from . import storage


@dataclass(frozen=True)
class IntegrityIssue:
    code: str
    detail: str


@dataclass(frozen=True)
class IntegrityReport:
    ok: bool
    issues: tuple[IntegrityIssue, ...]


_MONITOR_TARGET_TABLES = {
    "topic": "topics",
    "subject": "subjects",
    "story": "stories",
    "source": "sources",
    "research_question": "research_questions",
}

_QUESTION_ORIGIN_TABLES = {
    "story": "stories",
    "claim": "claims",
    "subject": "subjects",
    "monitor": "monitors",
}


def _table_exists(conn, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        is not None
    )


def check_database(db_path: Optional[str] = None) -> IntegrityReport:
    conn = storage.connect(db_path)
    issues: list[IntegrityIssue] = []
    try:
        if not _table_exists(conn, "schema_migrations"):
            return IntegrityReport(False, (IntegrityIssue("missing_schema", "schema_migrations is absent"),))

        pragma_result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if pragma_result != "ok":
            issues.append(IntegrityIssue("sqlite_integrity", str(pragma_result)))

        for row in conn.execute("PRAGMA foreign_key_check"):
            issues.append(
                IntegrityIssue(
                    "foreign_key_violation",
                    f"table={row[0]} rowid={row[1]} parent={row[2]}",
                )
            )

        if not _table_exists(conn, "monitors"):
            issues.append(IntegrityIssue("missing_schema", "monitors is absent"))
        for target_type, table in _MONITOR_TARGET_TABLES.items():
            if not _table_exists(conn, table):
                continue
            rows = conn.execute(
                f"""
                SELECT m.id, m.target_id
                FROM monitors AS m
                WHERE m.target_type = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM {table} AS target WHERE target.id = m.target_id
                  )
                ORDER BY m.id
                """,
                (target_type,),
            )
            issues.extend(
                IntegrityIssue(
                    "orphan_monitor_target",
                    f"monitor={row[0]} target_type={target_type} target_id={row[1]}",
                )
                for row in rows
            )

        if not _table_exists(conn, "research_questions"):
            issues.append(IntegrityIssue("missing_schema", "research_questions is absent"))
        else:
            for origin_type, table in _QUESTION_ORIGIN_TABLES.items():
                if not _table_exists(conn, table):
                    continue
                rows = conn.execute(
                    f"""
                    SELECT q.id, q.origin_id
                    FROM research_questions AS q
                    WHERE q.origin_type = ?
                      AND (q.origin_id IS NULL OR NOT EXISTS (
                          SELECT 1 FROM {table} AS origin WHERE origin.id = q.origin_id
                      ))
                    ORDER BY q.id
                    """,
                    (origin_type,),
                )
                issues.extend(
                    IntegrityIssue(
                        "orphan_research_question_origin",
                        f"question={row[0]} origin_type={origin_type} origin_id={row[1]}",
                    )
                    for row in rows
                )

        if _table_exists(conn, "story_review") and _table_exists(conn, "story_revisions"):
            rows = conn.execute(
                """
                SELECT review.story_id, review.last_reviewed_revision_id
                FROM story_review AS review
                JOIN story_revisions AS revision
                  ON revision.id = review.last_reviewed_revision_id
                WHERE revision.story_id <> review.story_id
                """
            )
            issues.extend(
                IntegrityIssue(
                    "review_revision_story_mismatch",
                    f"story={row[0]} revision={row[1]}",
                )
                for row in rows
            )

        # Phase 18 — durable normalized content artifacts. Referenced artifacts
        # must exist (FK also guards this) and stored content must still hash to
        # its recorded normalized_content_hash, or the DB cannot be trusted.
        # Pre-Phase-18 versions legitimately have artifact_id = NULL and are not
        # flagged: no content is ever fabricated for historical versions.
        if _table_exists(conn, "content_artifacts") and _table_exists(conn, "document_versions"):
            rows = conn.execute(
                """
                SELECT dv.id, dv.artifact_id
                FROM document_versions AS dv
                WHERE dv.artifact_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM content_artifacts AS ca WHERE ca.id = dv.artifact_id
                  )
                ORDER BY dv.id
                """
            )
            issues.extend(
                IntegrityIssue(
                    "missing_content_artifact",
                    f"document_version={row[0]} artifact={row[1]}",
                )
                for row in rows
            )
            for row in conn.execute(
                """
                SELECT ca.id, ca.normalized_content_hash, ca.normalized_text, ca.text_length
                FROM content_artifacts AS ca
                ORDER BY ca.id
                """
            ):
                recomputed = hashlib.sha256(row[2].encode("utf-8")).hexdigest()
                if recomputed != row[1]:
                    issues.append(
                        IntegrityIssue(
                            "content_artifact_hash_mismatch",
                            f"artifact={row[0]} stored_hash={row[1][:16]}... recomputed={recomputed[:16]}...",
                        )
                    )
                if len(row[2]) != row[3]:
                    issues.append(
                        IntegrityIssue(
                            "content_artifact_length_mismatch",
                            f"artifact={row[0]} stored_length={len(row[2])} recorded={row[3]}",
                        )
                    )
        return IntegrityReport(not issues, tuple(issues))
    finally:
        conn.close()
