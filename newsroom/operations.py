"""Verified local backup, export, retention, and upgrade operations.

Operator workflows are deliberately file-scoped and SQLite-native.  Logical
exports use an allow-list instead of dumping arbitrary columns so password
hashes, session material, prompts, note bodies, article-derived text, and
provider payloads cannot accidentally leave the runtime root.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import storage
from .integrity import check_database
from .migrations import apply_migrations


class OperationsError(RuntimeError):
    """Base class for operator workflow failures."""


class ExportLimitExceeded(OperationsError):
    """A logical export exceeded its configured row bound."""


_EXPORT_COLUMNS: dict[str, tuple[str, ...]] = {
    "schema_migrations": ("version", "applied_at"),
    "app_meta": ("key", "value"),
    "categories": ("id", "slug", "name", "created_at", "updated_at", "deleted_at"),
    "topics": ("id", "category_id", "slug", "name", "created_at", "updated_at", "deleted_at"),
    "topic_terms": ("id", "topic_id", "term", "term_type", "created_at"),
    "subjects": ("id", "canonical_name", "canonical_id", "subject_type", "description", "created_at", "updated_at", "deleted_at"),
    "subject_aliases": ("id", "subject_id", "alias", "alias_type", "created_at"),
    "entities": ("id", "canonical_name", "normalized_name", "entity_type", "description", "status", "merged_into_id", "created_at", "updated_at"),
    "entity_aliases": ("id", "entity_id", "alias", "normalized_alias", "alias_type", "origin", "status", "created_at"),
    "entity_mentions": ("id", "entity_id", "mention_text", "normalized_mention", "source_type", "source_id", "article_analysis_id", "document_version_id", "resolution_status", "resolution_method", "confidence", "context_json", "created_at"),
    "topic_subjects": ("topic_id", "subject_id", "created_at"),
    "sources": ("id", "slug", "name", "domain", "homepage_url", "feed_url", "source_kind", "default_quality", "created_at", "updated_at", "deleted_at"),
    "documents": ("id", "source_id", "canonical_url", "canonical_url_hash", "title", "title_normalized", "published_at", "first_seen_at", "created_at", "updated_at", "deleted_at"),
    "document_versions": ("id", "document_id", "retrieved_at", "content_hash", "content_kind", "artifact_id", "etag", "last_modified", "created_at"),
    "stories": ("id", "current_revision_id", "lifecycle", "review_status", "created_at", "updated_at", "deleted_at"),
    "story_revisions": ("id", "story_id", "revision_number", "headline", "material_change", "created_at"),
    "story_revision_claims": ("revision_id", "claim_id", "position"),
    "story_revision_documents": ("revision_id", "document_id", "role", "created_at"),
    "story_evolution_events": ("id", "story_id", "document_id", "update_class", "material_change", "decision_json", "created_at"),
    "story_topics": ("story_id", "topic_id", "created_at"),
    "story_subjects": ("story_id", "subject_id", "created_at"),
    "claims": ("id", "story_id", "proposition", "proposition_hash", "importance", "state", "accepted_at", "article_analysis_id", "candidate_claim_index", "created_at"),
    "claim_state_history": ("id", "claim_id", "from_state", "to_state", "reason", "created_at"),
    "claim_story_assignment_history": ("id", "claim_id", "from_story_id", "to_story_id", "correction_id", "origin", "reason_code", "reason", "occurred_at", "created_at"),
    "evidence_spans": ("id", "document_version_id", "locator_type", "locator_value", "span_hash", "article_analysis_id", "artifact_id", "artifact_content_hash", "view_content_hash", "view_kind", "view_version", "field_path", "start_offset", "end_offset", "verification_method", "provenance_json", "created_at"),
    "claim_evidence": ("id", "claim_id", "evidence_span_id", "relationship", "created_at"),
    "claim_entities": ("claim_id", "entity_id", "role", "origin", "mention_id", "created_at"),
    "story_entities": ("story_id", "entity_id", "origin", "authority", "created_at"),
    "story_corrections": ("id", "operation_type", "origin", "actor", "reason_code", "reason", "cause_class", "caused_by_type", "caused_by_id", "occurred_at", "metadata_json"),
    "story_lineage": ("id", "source_story_id", "target_story_id", "relationship", "correction_id", "created_at"),
    "story_duplicate_decisions": ("id", "source_story_id", "destination_story_id", "evidence_hash", "decision", "correction_id", "reason", "created_at"),
    "story_duplicate_suggestions": ("id", "source_story_id", "destination_story_id", "evidence_hash", "score", "explanation_json", "resolver_version", "created_at"),
    "research_questions": ("id", "question", "origin_type", "origin_id", "status", "priority", "assessment_state", "assessment_hash", "assessment_explanation", "assessment_at", "criteria_json", "pursuit_policy", "pursuit_cooldown_seconds", "created_at", "updated_at", "deleted_at"),
    "research_question_history": ("id", "question_id", "from_status", "to_status", "reason", "actor", "created_at"),
    "research_question_claims": ("question_id", "claim_id", "relationship", "created_at", "origin", "confidence", "rationale", "actor"),
    "research_question_evidence": ("question_id", "evidence_span_id", "relationship", "created_at"),
    "research_question_notes": ("id", "question_id", "note_type", "body", "created_at"),
    "research_question_attempts": ("id", "question_id", "job_id", "attempt_no", "mode", "status", "query_units", "local_model_units", "estimated_cost_usd", "query", "outcome_note", "task_id", "gap_id", "started_at", "completed_at", "created_at"),
    "research_question_assessments": ("id", "question_id", "snapshot_hash", "state", "explanation", "supporting_claim_count", "contradicting_claim_count", "contextual_claim_count", "qualifying_evidence_count", "open_gap_count", "origin", "created_at"),
    "research_question_assessment_history": ("id", "question_id", "assessment_id", "from_state", "to_state", "reason_code", "claim_ids_json", "origin", "created_at"),
    "research_question_claim_overrides": ("id", "question_id", "claim_id", "relationship", "action", "reason", "actor", "created_at"),
    "research_question_gaps": ("id", "question_id", "gap_key", "gap_type", "description", "rationale", "condition_json", "status", "origin", "origin_hypothesis_id", "assessment_hash", "first_seen_at", "last_evaluated_at", "satisfied_at", "dismissed_at", "dismissed_by", "dismissal_reason", "created_at", "updated_at"),
    "research_question_gap_history": ("id", "gap_id", "from_status", "to_status", "reason_code", "assessment_hash", "task_id", "actor", "created_at"),
    "research_tasks": ("id", "question_id", "gap_id", "task_no", "mode", "status", "job_id", "attempt_id", "snapshot_hash", "plan_json", "limits_json", "outcome_json", "error_code", "error_detail", "next_attempt_at", "started_at", "completed_at", "created_at", "updated_at"),
    "research_question_entities": ("question_id", "entity_id", "origin", "created_at"),
    "research_gap_entities": ("gap_id", "entity_id", "origin", "created_at"),
    "research_task_entities": ("task_id", "entity_id", "origin", "created_at"),
    "research_task_queries": ("id", "task_id", "query", "query_hash", "strategy", "ordinal", "created_at"),
    "research_task_findings": ("id", "task_id", "finding_type", "identity_key", "status", "source_id", "document_id", "document_version_id", "claim_id", "evidence_span_id", "rank", "metadata_json", "created_at", "updated_at"),
    "monitoring_policies": ("id", "name", "allowed_channels", "priority", "base_cadence_seconds", "min_cadence_seconds", "max_cadence_seconds", "query_budget", "paid_budget_usd", "local_model_budget", "escalation_rules", "backoff_rules", "retirement_criteria", "created_at", "updated_at"),
    "monitors": ("id", "target_type", "target_id", "historical_target_id", "resolution_state", "resolution_options_json", "policy_id", "enabled", "next_check_at", "last_run_at", "last_result", "need_type", "need_id", "created_at", "updated_at"),
    "monitor_scope_history": ("id", "monitor_id", "version", "scope_json", "change_type", "changed_by", "created_at"),
    "watches": ("id", "name", "target_type", "target_id", "historical_target_id", "resolution_state", "resolution_options_json", "policy_id", "status", "priority", "discovery_enabled", "last_discovery_at", "discovery_error", "created_at", "updated_at"),
    "watch_vocabulary": ("id", "watch_id", "term", "term_normalized", "kind", "origin", "status", "enabled", "expansion_of", "rationale", "created_at", "reviewed_at", "reviewed_by"),
    "source_candidates": ("id", "watch_id", "source_id", "name", "homepage_url", "normalized_url", "feed_url", "discovery_method", "rationale", "authority_context", "limitations", "provenance_json", "status", "created_at", "reviewed_at", "reviewed_by"),
    "watch_sources": ("watch_id", "source_id", "monitor_id", "created_at"),
    "watch_entities": ("watch_id", "entity_id", "origin", "created_at"),
    "jobs": ("id", "job_type", "status", "priority", "attempts", "max_attempts", "created_at", "updated_at", "completed_at"),
    "job_attempts": ("id", "job_id", "attempt_no", "started_at", "finished_at", "status", "error_code"),
    "runs": ("id", "trigger_type", "status", "started_at", "completed_at"),
    "provider_usage": ("id", "job_id", "provider", "capability", "request_type", "estimated_cost_usd", "actual_cost_usd", "latency_ms", "outcome", "created_at"),
    "acquisition_events": ("id", "source_id", "document_id", "document_version_id", "channel", "request_url", "final_url", "outcome", "status_code", "content_type", "response_bytes", "error_code", "observed_at", "created_at"),
    "source_profiles": ("source_id", "source_type", "updated_at"),
    "living_reports": ("id", "name", "target_type", "target_id", "status", "current_revision_id", "created_at", "updated_at"),
    "report_revisions": ("id", "report_id", "revision_number", "claim_set_hash", "material_change", "generated_at", "created_at"),
    "report_revision_claims": ("revision_id", "claim_id", "position", "created_at"),
    "report_revision_causes": ("id", "revision_id", "cause_type", "cause_id", "story_id", "claim_id", "evidence_span_id", "document_id", "rationale", "created_at"),
    "briefings": ("id", "period_type", "period_key", "timezone", "created_at"),
    "alert_rules": ("id", "name", "target_type", "target_id", "event_types_json", "min_importance", "browser_enabled", "enabled", "dedupe_window_seconds", "timezone_name", "created_at", "updated_at"),
    "alerts": ("id", "rule_id", "report_id", "report_revision_id", "story_id", "event_type", "title", "body", "importance_score", "dedupe_key", "cause_json", "status", "created_at", "acknowledged_at", "acknowledged_by"),
    "alert_deliveries": ("id", "alert_id", "channel", "status", "attempt_count", "error_detail", "delivered_at", "created_at", "updated_at"),
    "tags": ("id", "name", "normalized_name", "namespace", "tag_type", "created_at", "updated_at"),
    "story_tags": ("story_id", "tag_id", "created_at"),
    "tag_assignments": ("id", "tag_id", "object_type", "object_id", "origin", "confidence", "reason", "created_at"),
    "knowledge_backfills": ("id", "kind", "status", "cursor", "processed", "row_limit", "batch_size", "error_code", "error_detail", "created_at", "updated_at", "completed_at"),
    "ask_conversations": ("id", "scope_type", "scope_id", "created_at", "updated_at"),
    "ask_runs": ("id", "conversation_id", "turn_number", "status", "retrieval_json", "citations_json", "refusal_code", "context_units", "provider_route", "estimated_cost_usd", "created_at", "completed_at"),
    "article_analyses": ("id", "document_version_id", "relevance_id", "monitor_id", "job_id", "scope_version", "artifact_id", "normalized_content_hash", "schema_version", "prompt_version", "provider", "model", "paid", "confidence", "input_char_count", "analyzed_char_count", "truncated", "input_view_version", "input_content_hash", "analyzed_content_hash", "invocation_id", "created_at"),
    "article_analysis_promotions": ("id", "promotion_identity", "article_analysis_id", "candidate_claim_index", "outcome_code", "claim_id", "evidence_span_ids_json", "created_at"),
    "story_target_resolution_history": ("id", "target_kind", "target_id", "historical_story_id", "selected_story_ids_json", "resolution", "actor", "created_at"),
    "blind_spot_review_history": ("id", "source_id", "target_type", "target_id", "source_class", "coverage_run_id", "priority", "review_status", "reviewer", "reviewed_at", "reason", "original_created_at", "preserved_at"),
    "attention_decisions": ("id", "object_type", "object_id", "reason_code", "basis_fingerprint", "action", "actor", "created_at", "snoozed_until", "legacy_action", "note"),
    "hypotheses": ("id", "question_id", "statement", "status", "origin", "provider_route", "created_at", "updated_at", "approved_at", "approved_by"),
    "hypothesis_claim_links": ("id", "hypothesis_id", "claim_id", "relationship", "created_at"),
    "hypothesis_history": ("id", "hypothesis_id", "from_status", "to_status", "actor", "reason", "created_at"),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def _database_versions(db_path: Path) -> tuple[int, ...]:
    if not db_path.is_file():
        return ()
    conn = sqlite3.connect(str(db_path))
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
        ).fetchone()
        if not exists:
            return ()
        return tuple(row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version"))
    finally:
        conn.close()


def verify_database(db_path: str | Path) -> dict[str, Any]:
    """Return a safe, machine-readable integrity and schema report."""
    path = _path(db_path)
    issues: list[dict[str, str]] = []
    try:
        sqlite_result = storage.integrity_check(path)
    except (OSError, sqlite3.DatabaseError) as exc:
        sqlite_result = "error"
        issues.append({"code": "sqlite_open", "detail": type(exc).__name__})
    report = check_database(path) if path.is_file() else None
    if report is None:
        issues.append({"code": "missing_database", "detail": "database file is absent"})
    else:
        issues.extend({"code": issue.code, "detail": issue.detail} for issue in report.issues)
    if sqlite_result != "ok":
        issues.append({"code": "sqlite_integrity", "detail": sqlite_result})
    versions = _database_versions(path)
    if versions and versions != tuple(range(1, max(versions) + 1)):
        issues.append({"code": "migration_gap", "detail": "schema migration versions are not contiguous"})
    return {
        "path": path,
        "ok": not issues,
        "integrity": sqlite_result,
        "schema_versions": versions,
        "schema_version": max(versions, default=0),
        "issues": issues,
    }


def _verified_or_raise(path: Path) -> dict[str, Any]:
    result = verify_database(path)
    if not result["ok"]:
        raise OperationsError("database verification failed")
    return result


def backup_database(
    source_path: str | Path,
    destination_dir: str | Path,
    *,
    label: str = "scheduled",
) -> dict[str, Any]:
    """Create an online SQLite backup and verify it before publication."""
    source = _path(source_path)
    if not source.is_file():
        raise FileNotFoundError(source)
    destination = _path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    safe_label = re.sub(r"[^A-Za-z0-9_-]+", "-", str(label).strip()).strip("-") or "scheduled"
    stamp = _utc_now().strftime("%Y%m%dT%H%M%SZ")
    final_path = destination / f"newsroom-{stamp}-{safe_label}-{uuid.uuid4().hex[:8]}.db"
    temporary = final_path.with_suffix(".tmp")
    try:
        storage.online_backup(temporary, source_path=source)
        verification = _verified_or_raise(temporary)
        temporary.replace(final_path)
    finally:
        for candidate in (temporary, Path(f"{temporary}-wal"), Path(f"{temporary}-shm")):
            if candidate.exists():
                candidate.unlink()
    verification["path"] = final_path
    verification["verified"] = True
    return verification


def restore_database(backup_path: str | Path, destination_path: str | Path) -> dict[str, Any]:
    """Restore only a verified backup, then verify the restored destination."""
    backup = _path(backup_path)
    destination = _path(destination_path)
    if backup == destination:
        raise OperationsError("backup and destination must be different files")
    _verified_or_raise(backup)
    storage.restore_backup(backup, destination)
    verification = _verified_or_raise(destination)
    verification["path"] = destination
    verification["verified"] = True
    return verification


def upgrade_database(db_path: str | Path) -> dict[str, Any]:
    """Apply pending migrations atomically, then run integrity verification."""
    path = _path(db_path)
    result = apply_migrations(path)
    verification = _verified_or_raise(path)
    verification["applied_versions"] = result.applied_versions
    verification["verified"] = True
    return verification


def _table_columns(conn: sqlite3.Connection, table: str) -> tuple[str, ...]:
    return tuple(row[1] for row in conn.execute(f'PRAGMA table_info("{table}")'))


def export_logical(
    db_path: str | Path,
    destination: str | Path,
    *,
    max_rows: int = 100_000,
) -> Path:
    """Write a bounded JSONL export from an explicit non-secret column allow-list."""
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows < 1:
        raise ValueError("max_rows must be a positive integer")
    source = _path(db_path)
    target = _path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    rows_written = 0
    try:
        conn = storage.connect(source)
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                header = {
                    "format": "newsroom-logical-export-v1",
                    "schema_versions": list(_database_versions(source)),
                    "exported_at": _timestamp(_utc_now()),
                }
                stream.write(json.dumps(header, sort_keys=True, separators=(",", ":")) + "\n")
                for table, requested_columns in _EXPORT_COLUMNS.items():
                    exists = conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
                    ).fetchone()
                    if not exists:
                        continue
                    columns = tuple(column for column in requested_columns if column in _table_columns(conn, table))
                    if not columns:
                        continue
                    quoted = ", ".join(f'"{column}"' for column in columns)
                    for row in conn.execute(f'SELECT {quoted} FROM "{table}" ORDER BY rowid'):
                        data = {column: row[index] for index, column in enumerate(columns)}
                        if table == "app_meta" and re.search(r"password|secret|token|key|credential", str(data.get("key", "")), re.IGNORECASE):
                            continue
                        if rows_written >= max_rows:
                            raise ExportLimitExceeded("logical export row limit exceeded")
                        stream.write(json.dumps({"table": table, "data": data}, sort_keys=True, default=str, separators=(",", ":")) + "\n")
                        rows_written += 1
                stream.write(json.dumps({"format": "newsroom-logical-export-end", "rows": rows_written}, sort_keys=True, separators=(",", ":")) + "\n")
        finally:
            conn.close()
        os.replace(temporary, target)
        return target
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def import_logical(
    source: str | Path,
    destination: str | Path,
    *,
    max_rows: int = 100_000,
) -> dict[str, Any]:
    """Import an allow-listed Class A/B JSONL export into a fresh database."""
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows < 1:
        raise ValueError("max_rows must be a positive integer")
    source_path = _path(source)
    destination_path = _path(destination)
    if destination_path.exists() and destination_path.stat().st_size:
        raise OperationsError("logical import destination must be a fresh or empty file")
    records: list[tuple[str, dict[str, Any]]] = []
    header: dict[str, Any] | None = None
    ended = False
    with source_path.open("r", encoding="utf-8") as stream:
        for line in stream:
            payload = json.loads(line)
            if isinstance(payload, dict) and payload.get("format") == "newsroom-logical-export-v1":
                if header is not None or records:
                    raise OperationsError("logical export has an invalid header")
                header = payload
                continue
            if isinstance(payload, dict) and payload.get("format") == "newsroom-logical-export-end":
                if ended or int(payload.get("rows", -1)) != len(records):
                    raise OperationsError("logical export has an invalid terminator")
                ended = True
                continue
            if ended or not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
                raise OperationsError("logical export contains an invalid record")
            table = payload.get("table")
            if table not in _EXPORT_COLUMNS:
                raise OperationsError(f"logical export table is not allow-listed: {table}")
            records.append((str(table), payload["data"]))
            if len(records) > max_rows:
                raise ExportLimitExceeded("logical import row limit exceeded")
    if header is None or not ended:
        raise OperationsError("logical export is incomplete")

    apply_migrations(destination_path)
    conn = storage.connect(destination_path)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        with storage.write_tx(conn):
            for table, data in records:
                columns = tuple(column for column in _EXPORT_COLUMNS[table] if column in data and column in _table_columns(conn, table))
                if not columns:
                    continue
                quoted = ", ".join(f'"{column}"' for column in columns)
                placeholders = ", ".join("?" for _ in columns)
                conn.execute(
                    f'INSERT OR IGNORE INTO "{table}" ({quoted}) VALUES ({placeholders})',
                    tuple(data[column] for column in columns),
                )
        conn.execute("PRAGMA foreign_keys = ON")
        foreign_key_errors = [tuple(row) for row in conn.execute("PRAGMA foreign_key_check")]
        if foreign_key_errors:
            raise OperationsError("logical import failed foreign-key validation")
        integrity = check_database(destination_path)
        if not integrity.ok:
            raise OperationsError("logical import failed authority integrity validation")
        return {"rows_imported": len(records), "tables": sorted({table for table, _ in records}), "verified": True}
    finally:
        conn.close()


def retain_backups(
    backup_dir: str | Path,
    *,
    keep: int = 7,
    older_than_days: int = 30,
) -> dict[str, Any]:
    """Remove only Newsroom backup files, retaining the newest ``keep`` files."""
    if isinstance(keep, bool) or not isinstance(keep, int) or keep < 1:
        raise ValueError("keep must be a positive integer")
    if isinstance(older_than_days, bool) or not isinstance(older_than_days, int) or older_than_days < 0:
        raise ValueError("older_than_days must be a nonnegative integer")
    directory = _path(backup_dir)
    if not directory.is_dir():
        return {"deleted": 0, "retained": 0, "directory": directory}
    backups = sorted(
        (item for item in directory.iterdir() if item.is_file() and item.name.startswith("newsroom-") and item.suffix == ".db"),
        key=lambda item: (item.stat().st_mtime, item.name),
        reverse=True,
    )
    protected = {item for item in backups[:keep]}
    cutoff = datetime.now(timezone.utc).timestamp() - (older_than_days * 86400)
    deleted = 0
    for item in backups:
        if item in protected or (older_than_days > 0 and item.stat().st_mtime > cutoff):
            continue
        item.unlink()
        deleted += 1
    return {"deleted": deleted, "retained": len(backups) - deleted, "directory": directory}


def purge_expired_sessions(
    db_path: str | Path,
    *,
    now: str | None = None,
    revoked_retention_days: int = 30,
) -> int:
    """Delete expired sessions and old revoked sessions without touching active sessions."""
    if isinstance(revoked_retention_days, bool) or not isinstance(revoked_retention_days, int) or revoked_retention_days < 0:
        raise ValueError("revoked_retention_days must be a nonnegative integer")
    current = datetime.fromisoformat((now or _timestamp(_utc_now())).replace("Z", "+00:00"))
    current = current.astimezone(timezone.utc).replace(microsecond=0)
    cutoff = _timestamp(current - timedelta(days=revoked_retention_days))
    conn = storage.connect(db_path)
    try:
        with storage.write_tx(conn):
            result = conn.execute(
                "DELETE FROM sessions WHERE expires_at <= ? OR (revoked_at IS NOT NULL AND revoked_at <= ?)",
                (_timestamp(current), cutoff),
            )
            return result.rowcount
    finally:
        conn.close()


__all__ = [
    "ExportLimitExceeded",
    "OperationsError",
    "backup_database",
    "export_logical",
    "import_logical",
    "purge_expired_sessions",
    "restore_database",
    "retain_backups",
    "upgrade_database",
    "verify_database",
]
