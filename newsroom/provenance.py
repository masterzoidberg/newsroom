"""Fail-closed provenance validation for the pre-evidence pipeline."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from . import storage
from .domain import DomainNotFound, DomainValidation


class ProvenanceValidationError(DomainValidation):
    """The complete ArticleAnalysis provenance chain is not trustworthy."""

    code = "invalid_analysis_provenance"

    def __init__(self, message: str, *, issues: tuple[str, ...] = ()):
        super().__init__(message)
        self.issues = issues or (message,)


_NEED_TABLES = {
    "topic": "topics",
    "subject": "subjects",
    "story": "stories",
    "research_question": "research_questions",
}


def _json(value: Any, *, label: str) -> Any:
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ProvenanceValidationError(f"{label} is not valid JSON") from exc


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _issue(issues: list[str], code: str, detail: str) -> None:
    issues.append(f"{code}: {detail}")


def validate_analysis_provenance(db_path: str | Path, analysis_id: str) -> dict[str, Any]:
    """Return a verified ArticleAnalysis provenance bundle or fail closed.

    This function is intentionally read-only. It never re-runs relevance,
    models, acquisition, or any future evidence automation.
    """
    conn = storage.connect(db_path)
    issues: list[str] = []
    try:
        analysis = conn.execute("SELECT * FROM article_analyses WHERE id = ?", (analysis_id,)).fetchone()
        if analysis is None:
            raise DomainNotFound("article analysis not found")
        relevance = conn.execute(
            "SELECT * FROM document_version_relevance WHERE id = ?",
            (analysis["relevance_id"],),
        ).fetchone()
        if relevance is None:
            _issue(issues, "orphan_analysis_relevance", f"relevance={analysis['relevance_id']}")
        version = conn.execute(
            """
            SELECT dv.*, d.source_id, d.canonical_url, d.title AS document_title,
                   s.name AS source_name, s.slug AS source_slug
            FROM document_versions AS dv
            JOIN documents AS d ON d.id = dv.document_id
            JOIN sources AS s ON s.id = d.source_id
            WHERE dv.id = ?
            """,
            (analysis["document_version_id"],),
        ).fetchone()
        if version is None:
            _issue(issues, "orphan_analysis_version", f"document_version={analysis['document_version_id']}")
        monitor = conn.execute("SELECT * FROM monitors WHERE id = ?", (analysis["monitor_id"],)).fetchone()
        if monitor is None:
            _issue(issues, "orphan_analysis_monitor", f"monitor={analysis['monitor_id']}")
        artifact = None
        if version is not None and version["artifact_id"]:
            artifact = conn.execute(
                "SELECT * FROM content_artifacts WHERE id = ?", (version["artifact_id"],)
            ).fetchone()
        if artifact is None:
            _issue(issues, "missing_analysis_artifact", f"artifact={analysis['artifact_id']}")

        if relevance is not None:
            if relevance["relevant"] != 1 or relevance["stage"] == "not_applicable":
                _issue(issues, "analysis_relevance_not_confirmed", "analysis is not anchored to a relevant=true decision")
            if not str(relevance["algorithm"] or "").strip():
                _issue(issues, "missing_relevance_algorithm", "relevance algorithm provenance is empty")
            if analysis["document_version_id"] != relevance["document_version_id"]:
                _issue(issues, "analysis_relevance_document_version_mismatch", "analysis and relevance point to different versions")
            if analysis["monitor_id"] != relevance["monitor_id"]:
                _issue(issues, "analysis_relevance_monitor_mismatch", "analysis and relevance point to different monitors")
            if int(analysis["scope_version"]) != int(relevance["scope_version"]):
                _issue(issues, "analysis_relevance_scope_mismatch", "analysis and relevance use different scope versions")

        if version is not None:
            if analysis["artifact_id"] != version["artifact_id"]:
                _issue(issues, "analysis_artifact_mismatch", "analysis artifact differs from the DocumentVersion artifact")
            if artifact is not None:
                recomputed = hashlib.sha256(artifact["normalized_text"].encode("utf-8")).hexdigest()
                if recomputed != artifact["normalized_content_hash"]:
                    _issue(issues, "analysis_artifact_hash_corrupt", "artifact content does not match its stored hash")
                if analysis["normalized_content_hash"] != artifact["normalized_content_hash"]:
                    _issue(issues, "analysis_normalized_hash_mismatch", "analysis hash differs from the verified artifact hash")
                if int(artifact["text_length"]) != len(artifact["normalized_text"]):
                    _issue(issues, "analysis_artifact_length_corrupt", "artifact length does not match its content")

        if monitor is not None and version is not None:
            if monitor["target_type"] != "source" or monitor["target_id"] != version["source_id"]:
                _issue(issues, "relevance_monitor_source_mismatch", "monitor provenance does not own the DocumentVersion source")
            need_type, need_id = monitor["need_type"], monitor["need_id"]
            if (need_type is None) != (need_id is None):
                _issue(issues, "invalid_monitor_need_reference", "monitor need_type and need_id must be supplied together")
            elif need_type is None:
                _issue(issues, "invalid_monitor_need_reference", "relevant analysis monitor has no information need")
            elif need_type not in _NEED_TABLES:
                _issue(issues, "invalid_monitor_need_reference", f"unsupported need_type={need_type}")
            else:
                target = conn.execute(
                    f"SELECT * FROM {_NEED_TABLES[need_type]} WHERE id = ?", (need_id,)
                ).fetchone()
                if target is None or ("deleted_at" in target.keys() and target["deleted_at"] is not None):
                    _issue(issues, "invalid_monitor_need_reference", f"missing {need_type} need={need_id}")

            scope_history = conn.execute(
                "SELECT * FROM monitor_scope_history WHERE monitor_id = ? AND version = ?",
                (analysis["monitor_id"], analysis["scope_version"]),
            ).fetchone()
            if scope_history is None:
                _issue(issues, "scope_version_wrong_monitor", "analysis scope version is not owned by its monitor")
            elif relevance is not None:
                try:
                    history_scope = _json(scope_history["scope_json"], label="monitor scope snapshot")
                    relevance_scope = _json(relevance["scope_json"], label="relevance scope snapshot")
                    if _canonical(history_scope) != _canonical(relevance_scope):
                        _issue(issues, "relevance_scope_snapshot_mismatch", "relevance scope is not the monitor-owned pinned snapshot")
                except ProvenanceValidationError as exc:
                    _issue(issues, "malformed_relevance_scope", str(exc))
        else:
            scope_history = None

        job = None
        if relevance is not None and relevance["job_id"]:
            job = conn.execute("SELECT * FROM jobs WHERE id = ?", (relevance["job_id"],)).fetchone()
            if job is None:
                _issue(issues, "orphan_relevance_job", f"job={relevance['job_id']}")
            else:
                if job["job_type"] != "document_version_process":
                    _issue(issues, "relevance_job_type_mismatch", "relevance is not owned by a document processing job")
                if job["document_version_id"] != relevance["document_version_id"]:
                    _issue(issues, "relevance_job_document_version_mismatch", "processing job owns a different version")
                payload = _json(job["payload_json"], label="processing job payload")
                if not isinstance(payload, dict):
                    _issue(issues, "malformed_processing_payload", "processing job payload is not an object")
                else:
                    if payload.get("monitor_id") != relevance["monitor_id"]:
                        _issue(issues, "relevance_job_monitor_mismatch", "processing job monitor differs from relevance monitor")
                    if int(payload.get("scope_version", -1)) != int(relevance["scope_version"]):
                        _issue(issues, "relevance_job_scope_mismatch", "processing job scope differs from relevance scope")
        if analysis["job_id"] and relevance is not None and analysis["job_id"] != relevance["job_id"]:
            _issue(issues, "analysis_job_mismatch", "analysis and relevance belong to different jobs")

        try:
            result = _json(analysis["result_json"], label="analysis result")
            from .ai import ArticleAnalysisOutput  # noqa: PLC0415

            ArticleAnalysisOutput.model_validate(result)
        except Exception as exc:
            _issue(issues, "malformed_analysis_result", str(exc))

        from .article_analysis import analysis_identity_hash  # noqa: PLC0415

        expected_identity = analysis_identity_hash(
            document_version_id=analysis["document_version_id"],
            relevance_id=analysis["relevance_id"],
            scope_version=int(analysis["scope_version"]),
            schema_version=analysis["schema_version"],
            prompt_version=analysis["prompt_version"],
            provider=analysis["provider"],
            model=analysis["model"],
        )
        if expected_identity != analysis["identity_hash"]:
            _issue(issues, "analysis_identity_mismatch", "analysis identity hash does not match its canonical fields")

        if issues:
            raise ProvenanceValidationError("; ".join(issues), issues=tuple(issues))
        return {
            "analysis": dict(analysis),
            "relevance": dict(relevance),
            "document_version": dict(version),
            "document": {
                "id": version["document_id"],
                "source_id": version["source_id"],
                "canonical_url": version["canonical_url"],
                "title": version["document_title"],
            },
            "source": {
                "id": version["source_id"],
                "name": version["source_name"],
                "slug": version["source_slug"],
            },
            "monitor": dict(monitor),
            "scope_history": dict(scope_history),
            "job": dict(job) if job is not None else None,
            "artifact": {
                "id": artifact["id"],
                "normalized_content_hash": artifact["normalized_content_hash"],
                "content_kind": artifact["content_kind"],
                "norm_version": artifact["norm_version"],
                "text_length": artifact["text_length"],
            },
        }
    finally:
        conn.close()


__all__ = ["ProvenanceValidationError", "validate_analysis_provenance"]
