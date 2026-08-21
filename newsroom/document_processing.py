"""Durable changed DocumentVersion processing obligations (Phase 19/20).

Phase 19 introduced the durable orchestration substrate between acquisition
and future intelligence stages. The canonical work item is the persisted
``DocumentVersion``: a successful changed acquisition enqueues exactly one
``document_version_process`` Job transactionally with the version itself, so a
committed changed version can never silently lose its processing obligation.

Phase 20 adds the deterministic automatic relevance stage to that handler:
the worker resolves the canonical version, verifies the Phase 18 normalized
content artifact, evaluates the verified text against the approved scope
snapshot pinned at acquisition (``scope_version``) using the local
``RelevanceCascade``, and persists one canonical relevance decision with full
provenance. A not-relevant or acquisition-only outcome is a successful
processing outcome, and a missing scope/provenance is a truthful terminal
failure (``COULD NOT EVALUATE RELEVANCE``), never a false negative.

Phase 21 adds the structured article-analysis stage to the same handler for
``relevant=true`` decisions only: the exact verified artifact content is sent
through the provider-neutral AIRouter to one opt-in real provider or the
deterministic local provider, and the validated structured output is persisted
as a durable ArticleAnalysis (with provider/model/prompt/schema provenance)
before the job completes. AI analysis is not evidence: candidate
Claims/Excerpts remain proposals inside the analysis record and never reach the
canonical Evidence/Claims tables. No Story, Report, or Alert work happens here;
Phase 23 owns those connections.

Ownership contract:

- ``jobs.document_version_id`` (Migration 0016) is the canonical owner column
  for this Job type. The FK proves the referenced DocumentVersion exists at
  insert time, so no enqueue path can reference a nonexistent version.
- The payload carries only canonical IDs for provenance: document_id,
  source_id, the originating monitor_id, and the acquisition-pinned
  ``scope_version`` (the approved ``monitor_scope_history`` version in effect
  when the version was acquired). Mutable Source/Monitor metadata is never
  duplicated into the payload; handlers resolve persisted rows through
  services.
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
- The persisted relevance identity is
  ``(document_version_id, monitor_id, scope_version)``: retries, lease
  recovery, and explicit reruns all reference the one canonical decision.
- Explicit rerun creates a new obligation with a fresh ``rerun:`` key. It is
  refused while an active obligation exists and requires an existing
  DocumentVersion; the rerun preserves the acquisition-pinned scope version.
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

    When the originating Monitor carries an approved information need, the
    obligation additionally pins the monitor's current approved scope history
    version (``scope_version``) in the payload. That pin makes the later
    relevance evaluation deterministic and historical: the processing worker
    evaluates against the exact approved scope snapshot that existed at
    acquisition time, never a later mutable scope.
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
            "SELECT target_type, target_id, need_type, need_id FROM monitors WHERE id = ?",
            (monitor_id,),
        ).fetchone()
        if monitor is None or monitor["target_type"] != "source" or monitor["target_id"] != version["source_id"]:
            raise DomainValidation("monitor does not own this document version's source")
    canonical_scope_version: int | None = None
    if monitor_id is not None and monitor["need_type"] is not None and monitor["need_id"] is not None:
        from .monitoring import current_information_need_status

        available, _status = current_information_need_status(
            conn,
            monitor["need_type"],
            monitor["need_id"],
        )
        if available:
            scope_version = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM monitor_scope_history WHERE monitor_id = ?",
                (monitor_id,),
            ).fetchone()[0]
            if not scope_version:
                raise DomainValidation(
                    f"monitor '{monitor_id}' has an approved information need but no scope snapshot"
                )
            canonical_scope_version = int(scope_version)

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
    if canonical_scope_version is not None:
        payload["scope_version"] = canonical_scope_version
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
    """Allow-listed worker handler for the deterministic Phase-20 processor.

    The handler resolves the canonical DocumentVersion, verifies its persisted
    ownership IDs, loads the hash-verified Phase 18 artifact, and — when the
    originating Monitor carries an approved semantic information need —
    evaluates the verified content against the approved scope snapshot pinned
    at acquisition (``scope_version``) using the deterministic local
    ``RelevanceCascade``, persists one canonical decision, and only then
    returns a bounded deterministic result. It never invokes semantic
    extraction, Story evolution, Reports, or Alerts, never accepts
    caller-supplied text or relevance terms, and never re-fetches remote
    content.

    Phase 21 (article analysis): when the persisted decision is
    ``relevant=true``, the handler additionally runs the structured
    article-analysis stage against the exact verified artifact and persists a
    durable ArticleAnalysis before completing. Phase 22 then validates the
    full analysis provenance and promotes only uniquely matched excerpts into
    canonical Evidence/Claims tables. Non-relevant, not-applicable, and
    relevance-failure outcomes complete without any analysis provider call.

    Outcome semantics are explicit:

    - ``evaluated`` (relevant true/false): a real deterministic decision was
      persisted; both outcomes are successful processing.
    - ``not_applicable``: the obligation has no approved semantic scope
      provenance (no originating Monitor, or an acquisition-only Monitor with
      no information need, or no acquisition-time scope pin). Processing
      succeeds truthfully without a relevance decision — never a false
      relevant/not-relevant.
    - terminal failure: anything that prevents evaluation (missing scope,
      malformed scope, invalid provenance, corrupt/legacy artifact) is
      ``COULD NOT EVALUATE RELEVANCE``, never ``relevant=false``.
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        artifacts: ContentArtifactService | None = None,
        analysis_service: Any | None = None,
        promotion_service: Any | None = None,
    ):
        self.db_path = Path(db_path)
        self.artifacts = artifacts or ContentArtifactService(db_path)
        self.analysis_service = analysis_service
        self.promotion_service = promotion_service

    def _analysis(self) -> Any:
        if self.analysis_service is None:
            from .article_analysis import ArticleAnalysisService  # noqa: PLC0415

            self.analysis_service = ArticleAnalysisService(self.db_path)
        return self.analysis_service

    def _promotion(self) -> Any:
        if self.promotion_service is None:
            from .evidence_promotion import ArticleAnalysisPromotionService  # noqa: PLC0415

            self.promotion_service = ArticleAnalysisPromotionService(self.db_path)
        return self.promotion_service

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
        monitor_id = None
        payload_monitor_id = payload.get("monitor_id")
        if payload_monitor_id is not None:
            monitor_id = str(payload_monitor_id).strip()
            conn = storage.connect(self.db_path)
            try:
                monitor = conn.execute(
                    "SELECT target_type, target_id FROM monitors WHERE id = ?",
                    (monitor_id,),
                ).fetchone()
            except sqlite3.OperationalError as exc:
                raise RetryableJobFailure(f"transient database error resolving monitor provenance: {exc}") from exc
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

        relevance = self._evaluate_relevance(job, payload, monitor_id, row, content)
        analysis = None
        if relevance.get("status") == "evaluated" and relevance.get("relevant") is True:
            analysis = self._run_article_analysis(job, row, content, relevance)
            promotion = self._promotion().promote(analysis["id"])
            if promotion["outcomes"] and not any(
                item["code"] == "verified" for item in promotion["outcomes"]
            ):
                raise DomainValidation("article analysis promotion produced no verified evidence")
        result: dict[str, Any] = {
            "document_version_id": version_id,
            "document_id": row["document_id"],
            "source_id": row["source_id"],
            "artifact_id": content["artifact_id"],
            "content_hash": row["content_hash"],
            "normalized_content_hash": content["normalized_content_hash"],
            "content_kind": content["content_kind"],
            "norm_version": content["norm_version"],
            "content_length": content["text_length"],
            "relevance": relevance,
            "processing_status": "completed",
        }
        if analysis is not None:
            result["analysis"] = analysis
            result["promotion"] = {
                "article_analysis_id": promotion["article_analysis_id"],
                "outcomes": [
                    {
                        "code": item["code"],
                        "claim_id": item["claim_id"],
                        "evidence_span_ids": item["evidence_span_ids"],
                    }
                    for item in promotion["outcomes"]
                ],
            }
        return result

    def _run_article_analysis(
        self,
        job: Mapping[str, Any],
        version_row: sqlite3.Row,
        content: Mapping[str, Any],
        relevance: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Run the Phase-21 structured analysis stage for a relevant version.

        The relevance decision has already been durably persisted in its own
        short write transaction before this stage, so no database write
        transaction is held while the analysis provider is called. The durable
        ArticleAnalysis (with its telemetry) is persisted before the handler
        returns; a provider failure therefore never falsely records processing
        success. Phase 22 promotion runs immediately afterward.
        The job outcome carries bounded analysis metadata; the full validated
        structured result lives only in ``article_analyses.result_json``.
        """
        record = self._analysis().analyze(
            document_version_id=str(version_row["id"]),
            relevance=relevance,
            content=content,
            # The canonical processing Job is owned by the durable relevance
            # decision (the Job that persisted it). On explicit rerun or lease
            # recovery the current Job may differ; the analysis is always
            # recorded under the decision's canonical Job so the
            # ArticleAnalysis → relevance → Job chain stays consistent.
            job_id=relevance.get("job_id") or job.get("id"),
        )
        return {key: value for key, value in record.items() if key != "result"}

    def _evaluate_relevance(
        self,
        job: Mapping[str, Any],
        payload: Mapping[str, Any],
        monitor_id: str | None,
        version_row: sqlite3.Row,
        content: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Evaluate verified normalized content against the pinned approved scope.

        Local imports keep the module import graph acyclic (monitoring imports
        acquisition which imports this module). No caller-supplied relevance
        terms or article text ever reach this path.
        """
        from .monitoring import (  # noqa: PLC0415
            DocumentVersionRelevanceService,
            MonitorService,
            RelevanceCascade,
        )

        monitored = monitor_id is not None
        scope_version_raw = payload.get("scope_version") if isinstance(payload, Mapping) else None
        if not monitored:
            return {
                "status": "not_applicable",
                "reason": "no originating monitor provenance was recorded for this processing obligation",
                "paid_used": False,
            }
        if scope_version_raw is None:
            return {
                "status": "not_applicable",
                "reason": "no approved scope version was pinned at acquisition (monitor had no approved information need then)",
                "paid_used": False,
            }
        try:
            scope_version = int(scope_version_raw)
        except (TypeError, ValueError) as exc:
            raise DomainValidation(f"invalid pinned scope version: {scope_version_raw!r}") from exc
        scope = MonitorService(self.db_path).scope_at_version(monitor_id, scope_version)
        if not scope.all_terms():
            raise DomainValidation(
                f"monitor '{monitor_id}' approved scope snapshot {scope_version} has no positive terms; "
                "cannot evaluate relevance"
            )
        text = _relevance_text(content)
        if not str(text).strip():
            raise DomainValidation("cannot evaluate relevance: verified artifact text is empty")
        result = RelevanceCascade().evaluate(text, scope)
        record = DocumentVersionRelevanceService(self.db_path).persist_decision(
            job_id=job.get("id"),
            document_version_id=str(version_row["id"]),
            monitor_id=monitor_id,
            scope_version=scope_version,
            scope=scope,
            result=result,
            observed_at=job.get("updated_at"),
        )
        return {
            "status": "evaluated",
            "relevant": result.relevant,
            "relevance_id": record["id"],
            "job_id": record["job_id"],
            "monitor_id": monitor_id,
            "scope_version": scope_version,
            "stage": result.stage,
            "score": result.score,
            "matched_terms": list(result.matched_terms),
            "scope_terms": list(scope.all_terms())[:200],
            "reason": result.reason,
            "algorithm": "deterministic_relevance_cascade_v1",
            "paid_used": False,
        }


def _relevance_text(content: Mapping[str, Any]) -> str:
    """Derive the bounded evaluation text for the verified artifact.

    HTML/text artifacts evaluate their exact normalized visible text. Feed
    metadata artifacts evaluate the entry title and summary extracted from the
    exact persisted metadata JSON (URLs and raw JSON structure never
    participate in term matching); if a feed entry has no title/summary the
    exact metadata text is used rather than fabricating content.
    """
    if content.get("content_kind") != "feed_metadata":
        return str(content.get("normalized_text") or "")
    raw = content.get("normalized_text") or ""
    try:
        metadata = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise DomainValidation("cannot evaluate relevance: feed metadata artifact is corrupted") from exc
    if not isinstance(metadata, Mapping):
        raise DomainValidation("cannot evaluate relevance: feed metadata artifact is corrupted")
    parts = [str(metadata.get("title") or ""), str(metadata.get("summary") or "")]
    text = "\n".join(part.strip() for part in parts if part.strip())
    return text or raw


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
            "scope_version": payload.get("scope_version"),
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
