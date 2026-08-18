"""Durable changed DocumentVersion processing obligations (Phase 19).

Phase 19 introduces the durable orchestration substrate between acquisition
and future intelligence stages. The canonical work item is the persisted
``DocumentVersion``: a successful changed acquisition enqueues exactly one
``document_version_process`` Job transactionally with the version itself, so a
committed changed version can never silently lose its processing obligation.
No relevance, AI, Evidence/Claims, Story, Report, or Alert work happens here:
the Phase-19 handler resolves the canonical version, verifies the Phase 18
normalized content artifact, and returns a deterministic lifecycle result.

Ownership contract:

- ``jobs.document_version_id`` (Migration 0016) is the canonical owner column
  for this Job type. The FK proves the referenced DocumentVersion exists at
  insert time, so no enqueue path can reference a nonexistent version.
- The payload carries only canonical IDs for provenance: document_id,
  source_id, and the originating monitor_id. Mutable Source/Monitor metadata
  is never duplicated into the payload; handlers resolve persisted rows
  through services.
- ``jobs.monitor_id`` is deliberately NOT overloaded: it remains the
  monitor_check execution ownership column (coalescing, policy budgets, and
  monitor completion hooks all key off it). A processing job shares no
  monitor_check semantics and therefore keeps monitor provenance in its
  payload JSON.
- The payload's IDs must agree with the persisted DocumentVersion/Document/
  Source/Monitor rows; the handler rejects conflicting caller-supplied IDs.

Idempotency / coalescing
- The automatic scheduling key is ``document:{version_id}`` (UNIQUE). An
  existing row for the key — queued, running, succeeded, failed, or
  cancelled — means no second automatic obligation is ever created for that
  version.
- ``_active_document_version_process_id_tx`` additionally rejects any second
  ACTIVE (queued/running) obligation in ``JobService.enqueue``, so rerun and
  direct-API enqueue paths cannot create concurrent duplicate work either.
- Explicit rerun creates a new obligation with a fresh ``rerun:`` key. It is
  refused while an active obligation exists and requires an existing
  DocumentVersion.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from . import storage
from .content_artifacts import (
    ArtifactHashMismatch,
    ArtifactLengthMismatch,
    ArtifactNotFound,
    ContentArtifactService,
    LegacyVersionWithoutArtifact,
)
from .domain import DomainConflict, DomainNotFound, DomainValidation, new_id, utc_now
from .jobs import DOCUMENT_VERSION_PROCESS_JOB_TYPE
from .worker import RetryableJobFailure


def enqueue_document_version_processing_tx(
    conn: sqlite3.Connection,
    *,
    version_id: str,
    monitor_id: str | None = None,
) -> dict[str, Any]:
    """Create at most one durable processing obligation inside the caller's tx.

    Designed to run inside the same ``BEGIN IMMEDIATE`` write transaction that
    commits the new DocumentVersion (and its Phase 18 artifact), so a crash
    between version commit and obligation commit is impossible: both commit or
    neither commits. The stable idempotency key coalesces concurrent producers
    and the active-obligation lookup rejects duplicates regardless of key.
    """
    version_id = str(version_id).strip()
    if not version_id:
        raise DomainValidation("document_version_id is required")
    version = conn.execute(
        """
        SELECT dv.id AS version_id, dv.document_id, dv.content_hash, d.source_id
        FROM document_versions AS dv
        JOIN documents AS d ON d.id = dv.document_id
        WHERE dv.id = ?
        """,
        (version_id,),
    ).fetchone()
    if version is None:
        raise DomainValidation("document version does not exist")
    monitor_id = str(monitor_id or "").strip() or None
    if monitor_id is not None:
        monitor = conn.execute(
            "SELECT target_type, target_id FROM monitors WHERE id = ?",
            (monitor_id,),
        ).fetchone()
        if monitor is None or monitor["target_type"] != "source" or monitor["target_id"] != version["source_id"]:
            raise DomainValidation("monitor does not own this document version's source")

    key = f"document:{version_id}"
    existing = conn.execute("SELECT id, status FROM jobs WHERE idempotency_key = ?", (key,)).fetchone()
    if existing is not None:
        return {"id": existing[0], "status": existing[1], "coalesced": True}
    active = conn.execute(
        """
        SELECT id FROM jobs
        WHERE document_version_id = ? AND job_type = ?
          AND status IN ('queued', 'running')
        LIMIT 1
        """,
        (version_id, DOCUMENT_VERSION_PROCESS_JOB_TYPE),
    ).fetchone()
    if active is not None:
        return {"id": active[0], "status": "queued", "coalesced": True}

    job_id = new_id("job")
    now = utc_now()
    payload = {
        "document_version_id": version_id,
        "document_id": version["document_id"],
        "source_id": version["source_id"],
        "monitor_id": monitor_id,
    }
    conn.execute(
        """
        INSERT INTO jobs
            (id, job_type, status, payload_json, idempotency_key,
             document_version_id, priority, max_attempts, created_at, updated_at)
        VALUES (?, ?, 'queued', ?, ?, ?, 0, 3, ?, ?)
        """,
        (
            job_id,
            DOCUMENT_VERSION_PROCESS_JOB_TYPE,
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            key,
            version_id,
            now,
            now,
        ),
    )
    return {"id": job_id, "status": "queued", "coalesced": False}


class DocumentProcessingExecutionService:
    """Allow-listed worker handler for the deterministic Phase-19 processor.

    The handler resolves the canonical DocumentVersion, verifies its persisted
    ownership IDs, loads the hash-verified Phase 18 artifact, and returns a
    bounded deterministic result. It never invokes relevance cascade, AI
    providers, semantic extraction, Evidence/Claims, Story evolution, Reports,
    or Alerts, and it never re-fetches remote content.
    """

    def __init__(self, db_path: str | Path, *, artifacts: ContentArtifactService | None = None):
        self.db_path = Path(db_path)
        self.artifacts = artifacts or ContentArtifactService(db_path)

    def handlers(self) -> dict[str, Any]:
        return {DOCUMENT_VERSION_PROCESS_JOB_TYPE: self.handle}

    def handle(self, job: Mapping[str, Any]) -> dict[str, Any]:
        payload = job.get("payload")
        if not isinstance(payload, Mapping):
            raise DomainValidation("document processing job payload must be an object")
        job_version_id = str(job.get("document_version_id") or "").strip()
        payload_version_id = payload.get("document_version_id")
        version_id = str(payload_version_id or "").strip() or job_version_id
        if not version_id:
            raise DomainValidation("document processing job is missing document_version_id")
        if job_version_id and payload_version_id is not None and str(payload_version_id).strip() != job_version_id:
            raise DomainValidation(
                "document processing payload document_version_id conflicts with job ownership"
            )

        conn = storage.connect(self.db_path)
        try:
            row = conn.execute(
                """
                SELECT dv.*, d.source_id, d.canonical_url
                FROM document_versions AS dv
                JOIN documents AS d ON d.id = dv.document_id
                WHERE dv.id = ?
                """,
                (version_id,),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            raise RetryableJobFailure(f"transient database error resolving document version: {exc}") from exc
        finally:
            conn.close()
        if row is None:
            raise DomainNotFound(f"document version {version_id} not found")

        payload_document_id = payload.get("document_id")
        if payload_document_id is not None and str(payload_document_id).strip() != row["document_id"]:
            raise DomainValidation("document processing payload document_id conflicts with persisted version")
        payload_source_id = payload.get("source_id")
        if payload_source_id is not None and str(payload_source_id).strip() != row["source_id"]:
            raise DomainValidation("document processing payload source_id conflicts with persisted version")
        payload_monitor_id = payload.get("monitor_id")
        if payload_monitor_id is not None:
            monitor_id = str(payload_monitor_id).strip()
            conn = storage.connect(self.db_path)
            try:
                monitor = conn.execute(
                    "SELECT target_type, target_id FROM monitors WHERE id = ?",
                    (monitor_id,),
                ).fetchone()
            finally:
                conn.close()
            if monitor is None or monitor["target_type"] != "source" or monitor["target_id"] != row["source_id"]:
                raise DomainValidation("monitor provenance does not own this document version")

        try:
            content = self.artifacts.load_normalized_content(version_id)
        except sqlite3.OperationalError as exc:
            raise RetryableJobFailure(f"transient database error loading artifact: {exc}") from exc
        if not content["available"]:
            raise LegacyVersionWithoutArtifact(
                f"document version {version_id} has no durable content artifact ({content['reason']})"
            )
        return {
            "document_version_id": version_id,
            "document_id": row["document_id"],
            "source_id": row["source_id"],
            "artifact_id": content["artifact_id"],
            "content_hash": row["content_hash"],
            "normalized_content_hash": content["normalized_content_hash"],
            "content_kind": content["content_kind"],
            "norm_version": content["norm_version"],
            "content_length": content["text_length"],
            "processing_status": "completed",
        }


def document_version_processing_rerun_factory(
    db_path: str | Path,
    job: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    """Rebuild a terminal document_version_process Job as fresh owned work.

    Returns ``None`` for any other job type so JobService falls back to its
    generic clone semantics. For a document_version_process job it refuses
    with a clear diagnostic when the rerun would be invalid: no canonical
    ownership, conflicting payload IDs, or a missing DocumentVersion. The
    enqueue path itself rejects reruns while an active processing obligation
    exists for the same version (``JobService._enqueue_check_tx``), so rerun
    can never duplicate active work. The historical terminal job and its
    attempts are never mutated.
    """
    if job.get("job_type") != DOCUMENT_VERSION_PROCESS_JOB_TYPE:
        return None
    payload = job.get("payload")
    if not isinstance(payload, Mapping):
        raise DomainValidation("document processing job payload must be an object")
    canonical = str(job.get("document_version_id") or "").strip()
    if not canonical:
        raise DomainConflict("document processing job payload has no canonical document_version_id; cannot rerun")
    payload_version_id = payload.get("document_version_id")
    if payload_version_id is not None and str(payload_version_id).strip() != canonical:
        raise DomainValidation("document processing payload document_version_id conflicts with owned job; cannot rerun")
    conn = storage.connect(db_path)
    try:
        row = conn.execute("SELECT 1 FROM document_versions WHERE id = ?", (canonical,)).fetchone()
        if row is None:
            raise DomainNotFound("document version not found; cannot rerun")
    finally:
        conn.close()
    from .jobs import JobService

    return JobService(db_path).enqueue(
        DOCUMENT_VERSION_PROCESS_JOB_TYPE,
        {
            "document_version_id": canonical,
            "document_id": payload.get("document_id"),
            "source_id": payload.get("source_id"),
            "monitor_id": payload.get("monitor_id"),
        },
        idempotency_key=f"rerun:{canonical}:{new_id('request')}",
        document_version_id=canonical,
        priority=int(job.get("priority") or 0),
        max_attempts=int(job.get("max_attempts") or 3),
    )


__all__ = [
    "DOCUMENT_VERSION_PROCESS_JOB_TYPE",
    "DocumentProcessingExecutionService",
    "document_version_processing_rerun_factory",
    "enqueue_document_version_processing_tx",
]