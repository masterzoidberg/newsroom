"""Durable Phase 23B Story-stage automation.

The existing Job table is the durable obligation and checkpoint store. A
stable idempotency key creates one logical Story-stage job per verified
promotion. Story mutation, the evidence-bound revision, the evolution event,
and the in-progress Job checkpoint commit in one short SQLite write
transaction. No provider or model call is made here.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from . import storage
from .automatic_story_resolution import (
    AMBIGUOUS,
    DEFERRED,
    MATCHED_EXISTING,
    NO_MATCH,
    QUALIFIED,
    AutomaticStoryResolutionResult,
    AutomaticStoryResolutionService,
)
from .domain import DomainConflict, DomainNotFound, DomainValidation, new_id, utc_now
from .evidence import EvidenceService
from .evidence_promotion import (
    AutomaticPromotionIntegrityError,
    verify_automatic_promotion,
)
from .jobs import (
    AUTOMATIC_STORY_STAGE_JOB_TYPE,
    DOCUMENT_VERSION_PROCESS_JOB_TYPE,
    JobService,
)
from .story_evolution import StoryCandidate, StoryEvolutionService
from .worker import RetryableJobFailure


AUTOMATIC_STORY_STAGE_IDEMPOTENCY_PREFIX = "automatic_story_stage:"
STAGE_COMPLETED = "completed"
STAGE_DEFERRED = "deferred"
STAGE_TERMINAL = "terminal"
_STAGE_STATUSES = frozenset({STAGE_COMPLETED, STAGE_DEFERRED, STAGE_TERMINAL})


def story_stage_idempotency_key(promotion_id: str) -> str:
    promotion_id = str(promotion_id).strip()
    if not promotion_id:
        raise DomainValidation("promotion_id is required")
    return f"{AUTOMATIC_STORY_STAGE_IDEMPOTENCY_PREFIX}{promotion_id}"


def enqueue_story_stage_tx(
    conn: sqlite3.Connection,
    promotion_id: str,
    *,
    now: str | None = None,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Enqueue or reuse one Story-stage Job inside a caller transaction."""

    promotion_id = str(promotion_id).strip()
    if not promotion_id:
        raise DomainValidation("promotion_id is required")
    if isinstance(max_attempts, bool) or not 1 <= max_attempts <= 10:
        raise DomainValidation("max_attempts must be between 1 and 10")
    promotion = conn.execute(
        """
        SELECT id, claim_id, outcome_code
        FROM article_analysis_promotions
        WHERE id = ?
        """,
        (promotion_id,),
    ).fetchone()
    if promotion is None or promotion["outcome_code"] != "verified" or not promotion["claim_id"]:
        raise DomainValidation("Story-stage work requires a verified promotion")

    key = story_stage_idempotency_key(promotion_id)
    existing = conn.execute(
        "SELECT id, status FROM jobs WHERE idempotency_key = ?", (key,)
    ).fetchone()
    if existing is not None:
        return {"id": existing["id"], "status": existing["status"], "coalesced": True}

    identifier = new_id("job")
    timestamp = now or utc_now()
    payload = json.dumps(
        {"promotion_id": promotion_id, "claim_id": promotion["claim_id"]},
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        conn.execute(
            """
            INSERT INTO jobs
                (id, job_type, status, payload_json, idempotency_key,
                 priority, max_attempts, created_at, updated_at)
            VALUES (?, ?, 'queued', ?, ?, 0, ?, ?, ?)
            """,
            (
                identifier,
                AUTOMATIC_STORY_STAGE_JOB_TYPE,
                payload,
                key,
                max_attempts,
                timestamp,
                timestamp,
            ),
        )
    except sqlite3.IntegrityError:
        existing = conn.execute(
            "SELECT id, status FROM jobs WHERE idempotency_key = ?", (key,)
        ).fetchone()
        if existing is None:
            raise
        return {"id": existing["id"], "status": existing["status"], "coalesced": True}
    return {"id": identifier, "status": "queued", "coalesced": False}


def enqueue_story_stage(
    db_path: str | Path,
    promotion_id: str,
    *,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Verify a promotion and create/reuse its durable Story-stage Job."""

    verify_automatic_promotion(db_path, promotion_id)
    conn = storage.connect(db_path)
    try:
        with storage.write_tx(conn):
            result = enqueue_story_stage_tx(
                conn,
                promotion_id,
                max_attempts=max_attempts,
            )
    finally:
        conn.close()
    return JobService(db_path).get(result["id"])


def automatic_story_stage_completion_hook(db_path: str | Path):
    """Return the Phase 22 completion hook that only enqueues Story work."""

    path = Path(db_path)

    def hook(
        conn: sqlite3.Connection,
        job_row: sqlite3.Row,
        job_status: str,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        if job_row["job_type"] != DOCUMENT_VERSION_PROCESS_JOB_TYPE:
            return
        if job_status not in {"succeeded", "partial"} or not isinstance(context, Mapping):
            return
        outcome = context.get("outcome")
        if not isinstance(outcome, Mapping):
            return
        promotion = outcome.get("promotion")
        if not isinstance(promotion, Mapping):
            return
        outcomes = promotion.get("outcomes")
        if not isinstance(outcomes, list):
            return
        for item in outcomes:
            if not isinstance(item, Mapping) or item.get("code") != "verified":
                continue
            promotion_id = str(item.get("promotion_id") or "").strip()
            if not promotion_id:
                continue
            try:
                verify_automatic_promotion(path, promotion_id)
            except (AutomaticPromotionIntegrityError, DomainNotFound):
                continue
            enqueue_story_stage_tx(conn, promotion_id)

    return hook


def automatic_story_stage_rerun_factory(
    db_path: str | Path,
    job: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    """Reuse the stable obligation identity for explicit stage reruns."""

    if job.get("job_type") != AUTOMATIC_STORY_STAGE_JOB_TYPE:
        return None
    payload = job.get("payload")
    if not isinstance(payload, Mapping):
        raise DomainValidation("Story-stage Job payload must be an object")
    promotion_id = str(payload.get("promotion_id") or "").strip()
    if not promotion_id:
        raise DomainValidation("Story-stage Job payload is missing promotion_id")
    return enqueue_story_stage(db_path, promotion_id)


def _decode_result(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        result = dict(value)
    elif isinstance(value, str):
        try:
            result = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
    else:
        return None
    return result if isinstance(result, dict) and result.get("stage_status") in _STAGE_STATUSES else None


def _resolution_payload(result: AutomaticStoryResolutionResult) -> dict[str, Any]:
    return {
        "promotion_id": result.promotion_id,
        "claim_id": result.claim_id,
        "qualification": result.qualification,
        "qualification_reason_code": result.qualification_reason_code,
        "story_resolution": result.story_resolution,
        "story_resolution_reason_code": result.story_resolution_reason_code,
        "candidate_story_ids": list(result.candidate_story_ids),
        "selected_story_id": result.selected_story_id,
        "candidate_saturated": result.candidate_saturated,
        "match_signals": [
            {
                "story_id": signal.story_id,
                "strength": signal.strength,
                "signals": signal.signals,
            }
            for signal in result.match_signals
        ],
    }


def _checkpoint_result(
    result: AutomaticStoryResolutionResult,
    *,
    job_id: str,
    status: str,
    reason_code: str,
    story_id: str | None = None,
    event_id: str | None = None,
    revision_id: str | None = None,
) -> dict[str, Any]:
    payload = _resolution_payload(result)
    payload.update(
        {
            "job_id": job_id,
            "stage_status": status,
            "reason_code": reason_code,
            "story_id": story_id,
            "event_id": event_id,
            "revision_id": revision_id,
        }
    )
    return payload


class AutomaticStoryStageExecutionService:
    """Execute one durable Story-stage obligation without provider calls."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.resolver = AutomaticStoryResolutionService(db_path)
        self.evidence = EvidenceService(db_path)
        self.evolution = StoryEvolutionService(db_path)

    def handlers(self) -> dict[str, Any]:
        return {AUTOMATIC_STORY_STAGE_JOB_TYPE: self.handle}

    def handle(self, job: Mapping[str, Any]) -> dict[str, Any]:
        payload = job.get("payload")
        if not isinstance(payload, Mapping):
            raise DomainValidation("Story-stage Job payload must be an object")
        promotion_id = str(payload.get("promotion_id") or "").strip()
        if not promotion_id:
            raise DomainValidation("Story-stage Job is missing promotion_id")
        job_id = str(job.get("id") or "").strip()
        if not job_id:
            raise DomainValidation("Story-stage Job is missing id")

        checkpoint = _decode_result(job.get("result"))
        if checkpoint is not None:
            return checkpoint

        try:
            graph = verify_automatic_promotion(self.db_path, promotion_id)
            initial = self.resolver.resolve_verified_graph(promotion_id, graph)
        except AutomaticPromotionIntegrityError as exc:
            return self._persist_terminal(
                job_id,
                promotion_id,
                _issue_code(exc),
            )
        except DomainNotFound:
            return self._persist_terminal(job_id, promotion_id, "promotion_missing")
        except sqlite3.OperationalError as exc:
            raise RetryableJobFailure(f"transient database error verifying promotion: {exc}") from exc

        if initial.qualification != QUALIFIED or initial.story_resolution in {AMBIGUOUS, DEFERRED}:
            reason = (
                initial.qualification_reason_code
                if initial.qualification != QUALIFIED
                else initial.story_resolution_reason_code
            )
            return self._persist_resolution(
                job_id,
                initial,
                reason,
            )
        if initial.story_resolution not in {MATCHED_EXISTING, NO_MATCH}:
            return self._persist_resolution(job_id, initial, "unsupported_resolution")

        try:
            mutation_graph = verify_automatic_promotion(self.db_path, promotion_id)
            conn = storage.connect(self.db_path)
            try:
                with storage.write_tx(conn):
                    existing = self._checkpoint_in_tx(conn, job_id)
                    if existing is not None:
                        return existing
                    current = self.resolver.resolve_verified_graph(
                        promotion_id,
                        mutation_graph,
                        conn=conn,
                    )
                    if current.qualification != QUALIFIED or current.story_resolution in {AMBIGUOUS, DEFERRED}:
                        reason = (
                            current.qualification_reason_code
                            if current.qualification != QUALIFIED
                            else current.story_resolution_reason_code
                        )
                        result = _checkpoint_result(
                            current,
                            job_id=job_id,
                            status=STAGE_DEFERRED,
                            reason_code=reason,
                        )
                        self._save_checkpoint_tx(conn, job_id, result)
                        return result
                    if current.story_resolution not in {MATCHED_EXISTING, NO_MATCH}:
                        result = _checkpoint_result(
                            current,
                            job_id=job_id,
                            status=STAGE_DEFERRED,
                            reason_code="unsupported_resolution",
                        )
                        self._save_checkpoint_tx(conn, job_id, result)
                        return result
                    result = self._apply_mutation_tx(conn, job_id, mutation_graph, current)
                    self._save_checkpoint_tx(conn, job_id, result)
                    return result
            finally:
                conn.close()
        except RetryableJobFailure:
            raise
        except sqlite3.OperationalError as exc:
            raise RetryableJobFailure(f"transient database error executing Story stage: {exc}") from exc
        except (DomainConflict, DomainNotFound, DomainValidation) as exc:
            return self._persist_terminal(job_id, promotion_id, _exception_code(exc))

    @staticmethod
    def _checkpoint_in_tx(conn: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
        row = conn.execute("SELECT result_json FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise DomainNotFound("Story-stage Job not found")
        return _decode_result(row["result_json"])

    @staticmethod
    def _save_checkpoint_tx(conn: sqlite3.Connection, job_id: str, result: Mapping[str, Any]) -> None:
        encoded = json.dumps(dict(result), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        changed = conn.execute(
            "UPDATE jobs SET result_json = ?, updated_at = ? WHERE id = ?",
            (encoded, utc_now(), job_id),
        )
        if changed.rowcount != 1:
            raise DomainNotFound("Story-stage Job not found")

    def _persist_resolution(
        self,
        job_id: str,
        result: AutomaticStoryResolutionResult,
        reason_code: str,
    ) -> dict[str, Any]:
        checkpoint = _checkpoint_result(
            result,
            job_id=job_id,
            status=STAGE_DEFERRED,
            reason_code=reason_code,
        )
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                existing = self._checkpoint_in_tx(conn, job_id)
                if existing is not None:
                    return existing
                self._save_checkpoint_tx(conn, job_id, checkpoint)
        finally:
            conn.close()
        return checkpoint

    def _persist_terminal(self, job_id: str, promotion_id: str, reason_code: str) -> dict[str, Any]:
        result = AutomaticStoryResolutionResult(
            promotion_id=promotion_id,
            claim_id=None,
            qualification=DEFERRED,
            qualification_reason_code="promotion_verification_failed",
            story_resolution=DEFERRED,
            story_resolution_reason_code=reason_code,
        )
        checkpoint = _checkpoint_result(
            result,
            job_id=job_id,
            status=STAGE_TERMINAL,
            reason_code=reason_code,
        )
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                existing = self._checkpoint_in_tx(conn, job_id)
                if existing is not None:
                    return existing
                self._save_checkpoint_tx(conn, job_id, checkpoint)
        finally:
            conn.close()
        return checkpoint

    def _apply_mutation_tx(
        self,
        conn: sqlite3.Connection,
        job_id: str,
        graph: Mapping[str, Any],
        resolution: AutomaticStoryResolutionResult,
    ) -> dict[str, Any]:
        claim_id = str(graph["claim"]["id"])
        document_id = str(graph["document"]["id"])
        incoming = self.resolver._incoming_candidate(graph)
        story_id = resolution.selected_story_id
        if resolution.story_resolution == NO_MATCH:
            story_id = self._create_story_tx(conn, graph, incoming)
        if not story_id:
            raise DomainValidation("automatic Story resolution selected no Story")

        story = conn.execute(
            "SELECT * FROM stories WHERE id = ? AND deleted_at IS NULL AND lifecycle <> 'archived'",
            (story_id,),
        ).fetchone()
        if story is None:
            raise DomainConflict("selected Story is no longer eligible for automatic assignment")
        claim = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        if claim is None:
            raise DomainNotFound("automatic Claim not found")
        verified_claim = graph["claim"]
        if (
            claim["article_analysis_id"] != verified_claim["article_analysis_id"]
            or claim["candidate_claim_index"] != verified_claim["candidate_claim_index"]
            or claim["proposition"] != verified_claim["proposition"]
        ):
            raise DomainConflict("automatic Claim changed after verification")
        if claim["story_id"] is not None:
            raise DomainConflict("Claim Story association cannot be reassigned")
        self.evidence._assign_claim_to_story_tx(conn, claim_id, story_id)
        self._ensure_story_document_tx(conn, story_id, document_id, incoming)

        verified_evidence = tuple(
            sorted(
                (str(item["evidence_span_id"]), str(item["relationship"]))
                for item in graph["claim_evidence"]
            )
        )
        revision_id, _ = self.evidence._create_automatic_revision_tx(
            conn,
            story_id,
            {
                "headline": graph["claim"]["proposition"],
                "summary": "",
                "why_it_matters": "",
                "material_change": resolution.story_resolution == NO_MATCH,
                "claim_ids": [claim_id],
                "propositions": [
                    {"text": graph["claim"]["proposition"], "claim_ids": [claim_id]}
                ],
            },
            verified_evidence=verified_evidence,
        )
        event_id = self.evolution.record_automatic_observation_tx(
            conn,
            story_id,
            document_id,
            claim_id,
            resolution.promotion_id,
            job_id,
            "new_story" if resolution.story_resolution == NO_MATCH else "qualification",
            candidate=incoming,
            decision={"resolution": _resolution_payload(resolution)},
            revision_id=revision_id,
            material_change=resolution.story_resolution == NO_MATCH,
        )
        return _checkpoint_result(
            resolution,
            job_id=job_id,
            status=STAGE_COMPLETED,
            reason_code="story_stage_completed",
            story_id=story_id,
            event_id=event_id,
            revision_id=revision_id,
        )

    @staticmethod
    def _ensure_story_document_tx(
        conn: sqlite3.Connection,
        story_id: str,
        document_id: str,
        incoming: StoryCandidate,
    ) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO story_documents
                (story_id, document_id, event_key, entities_json, locations_json, linked_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                story_id,
                document_id,
                incoming.event_key,
                json.dumps(sorted(incoming.entities), separators=(",", ":")),
                json.dumps(sorted(incoming.locations), separators=(",", ":")),
                utc_now(),
            ),
        )

    @staticmethod
    def _create_story_tx(
        conn: sqlite3.Connection,
        graph: Mapping[str, Any],
        incoming: StoryCandidate,
    ) -> str:
        headline = str(graph["claim"]["proposition"]).strip()
        if not headline:
            raise DomainValidation("automatic Story headline must not be empty")
        story_id = new_id("st")
        now = utc_now()
        conn.execute(
            "INSERT INTO stories (id, lifecycle, created_at, updated_at) VALUES (?, 'developing', ?, ?)",
            (story_id, now, now),
        )
        conn.execute(
            "INSERT INTO story_review (story_id, updated_at) VALUES (?, ?)",
            (story_id, now),
        )
        monitor = graph.get("monitor") or {}
        need_type = monitor.get("need_type")
        need_id = monitor.get("need_id")
        if need_type == "topic" and need_id and conn.execute(
            "SELECT 1 FROM topics WHERE id = ? AND deleted_at IS NULL", (need_id,)
        ).fetchone():
            conn.execute(
                "INSERT INTO story_topics (story_id, topic_id) VALUES (?, ?)",
                (story_id, need_id),
            )
        if need_type == "subject" and need_id and conn.execute(
            "SELECT 1 FROM subjects WHERE id = ? AND deleted_at IS NULL", (need_id,)
        ).fetchone():
            conn.execute(
                "INSERT INTO story_subjects (story_id, subject_id) VALUES (?, ?)",
                (story_id, need_id),
            )
        return story_id


def _issue_code(exc: AutomaticPromotionIntegrityError) -> str:
    issue = exc.issues[0] if exc.issues else "invalid_verified_promotion"
    return issue.split(":", 1)[0]


def _exception_code(exc: Exception) -> str:
    if isinstance(exc, DomainConflict):
        return "domain_conflict"
    if isinstance(exc, DomainNotFound):
        return "domain_not_found"
    return "domain_validation_failed"


__all__ = [
    "AUTOMATIC_STORY_STAGE_IDEMPOTENCY_PREFIX",
    "AUTOMATIC_STORY_STAGE_JOB_TYPE",
    "STAGE_COMPLETED",
    "STAGE_DEFERRED",
    "STAGE_TERMINAL",
    "AutomaticStoryStageExecutionService",
    "automatic_story_stage_completion_hook",
    "automatic_story_stage_rerun_factory",
    "enqueue_story_stage",
    "enqueue_story_stage_tx",
    "story_stage_idempotency_key",
]
