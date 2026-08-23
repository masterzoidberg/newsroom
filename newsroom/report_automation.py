"""Phase 23C automatic Claim acceptance and idempotent Living Reports."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from . import storage
from .domain import DomainConflict, DomainNotFound, DomainValidation, new_id, utc_now
from .evidence import EvidenceService
from .evidence_promotion import AutomaticPromotionIntegrityError, verify_automatic_promotion
from .jobs import (
    AUTOMATIC_REPORT_STAGE_JOB_TYPE,
    AUTOMATIC_STORY_STAGE_JOB_TYPE,
    JobService,
)
from .reports import LivingReportService
from .story_automation import STAGE_COMPLETED
from .worker import RetryableJobFailure


AUTOMATIC_REPORT_STAGE_IDEMPOTENCY_PREFIX = "automatic_report_stage:"
AUTOMATIC_ACCEPTANCE_REASON_PREFIX = "automatic_report_acceptance:"
REPORT_COMPLETED = "completed"
REPORT_NO_CHANGE = "no_change"
REPORT_DEFERRED = "deferred"
REPORT_TERMINAL = "terminal"
_REPORT_STATUSES = frozenset(
    {REPORT_COMPLETED, REPORT_NO_CHANGE, REPORT_DEFERRED, REPORT_TERMINAL}
)


def report_stage_idempotency_key(story_stage_job_id: str) -> str:
    identifier = str(story_stage_job_id or "").strip()
    if not identifier:
        raise DomainValidation("story_stage_job_id is required")
    return f"{AUTOMATIC_REPORT_STAGE_IDEMPOTENCY_PREFIX}{identifier}"


def _decode(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        result = dict(value)
    elif isinstance(value, str):
        try:
            result = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
    else:
        return None
    return result if isinstance(result, dict) else None


def _report_checkpoint(value: Any) -> dict[str, Any] | None:
    result = _decode(value)
    if result and result.get("stage_status") in _REPORT_STATUSES:
        return result
    return None


def enqueue_report_stage_tx(
    conn: sqlite3.Connection,
    story_stage_job_id: str,
    *,
    story_result: Mapping[str, Any] | None = None,
    now: str | None = None,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Create/reuse the one Report-stage obligation for a completed Story Job."""

    if isinstance(max_attempts, bool) or not 1 <= max_attempts <= 10:
        raise DomainValidation("max_attempts must be between 1 and 10")
    story_job = conn.execute(
        "SELECT * FROM jobs WHERE id = ?", (str(story_stage_job_id).strip(),)
    ).fetchone()
    if story_job is None or story_job["job_type"] != AUTOMATIC_STORY_STAGE_JOB_TYPE:
        raise DomainValidation("Report-stage work requires an automatic Story-stage Job")
    result = dict(story_result) if isinstance(story_result, Mapping) else _decode(story_job["result_json"])
    if not result or result.get("stage_status") != STAGE_COMPLETED:
        raise DomainValidation("Report-stage work requires a completed Story-stage result")
    required = ("promotion_id", "claim_id", "story_id", "event_id", "revision_id")
    if any(not str(result.get(field) or "").strip() for field in required):
        raise DomainValidation("completed Story-stage result is incomplete")

    key = report_stage_idempotency_key(story_job["id"])
    existing = conn.execute(
        "SELECT id, status FROM jobs WHERE idempotency_key = ?", (key,)
    ).fetchone()
    if existing is not None:
        return {"id": existing["id"], "status": existing["status"], "coalesced": True}

    identifier = new_id("job")
    timestamp = now or utc_now()
    payload = json.dumps(
        {
            "story_stage_job_id": story_job["id"],
            "promotion_id": result["promotion_id"],
            "claim_id": result["claim_id"],
            "story_id": result["story_id"],
            "story_event_id": result["event_id"],
            "story_revision_id": result["revision_id"],
        },
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
                AUTOMATIC_REPORT_STAGE_JOB_TYPE,
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


def enqueue_report_stage(
    db_path: str | Path,
    story_stage_job_id: str,
    *,
    max_attempts: int = 3,
) -> dict[str, Any]:
    conn = storage.connect(db_path)
    try:
        with storage.write_tx(conn):
            result = enqueue_report_stage_tx(
                conn, story_stage_job_id, max_attempts=max_attempts
            )
    finally:
        conn.close()
    return JobService(db_path).get(result["id"])


def automatic_report_stage_completion_hook():
    """Enqueue Report work only after a successful completed Story-stage Job."""

    def hook(
        conn: sqlite3.Connection,
        job_row: sqlite3.Row,
        job_status: str,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        if job_row["job_type"] != AUTOMATIC_STORY_STAGE_JOB_TYPE:
            return
        if job_status not in {"succeeded", "partial"} or not isinstance(context, Mapping):
            return
        outcome = context.get("outcome")
        if not isinstance(outcome, Mapping) or outcome.get("stage_status") != STAGE_COMPLETED:
            return
        enqueue_report_stage_tx(conn, job_row["id"], story_result=outcome)

    return hook


def automatic_report_stage_rerun_factory(
    db_path: str | Path, job: Mapping[str, Any]
) -> Mapping[str, Any] | None:
    if job.get("job_type") != AUTOMATIC_REPORT_STAGE_JOB_TYPE:
        return None
    payload = job.get("payload")
    if not isinstance(payload, Mapping):
        raise DomainValidation("Report-stage Job payload must be an object")
    return enqueue_report_stage(db_path, str(payload.get("story_stage_job_id") or ""))


class AutomaticReportStageExecutionService:
    """Accept one proven Claim and update its Story-scoped Living Report once."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.evidence = EvidenceService(db_path)
        self.reports = LivingReportService(db_path)

    def handlers(self) -> dict[str, Any]:
        return {AUTOMATIC_REPORT_STAGE_JOB_TYPE: self.handle}

    def handle(self, job: Mapping[str, Any]) -> dict[str, Any]:
        checkpoint = _report_checkpoint(job.get("result"))
        if checkpoint is not None:
            return checkpoint
        payload = job.get("payload")
        if not isinstance(payload, Mapping):
            raise DomainValidation("Report-stage Job payload must be an object")
        job_id = str(job.get("id") or "").strip()
        promotion_id = str(payload.get("promotion_id") or "").strip()
        if not job_id or not promotion_id:
            raise DomainValidation("Report-stage Job is missing canonical identity")
        try:
            graph = verify_automatic_promotion(self.db_path, promotion_id)
        except AutomaticPromotionIntegrityError as exc:
            return self._persist_simple(
                job_id,
                REPORT_TERMINAL,
                exc.issues[0].split(":", 1)[0] if exc.issues else "invalid_verified_promotion",
            )
        except sqlite3.OperationalError as exc:
            raise RetryableJobFailure(
                f"transient database error verifying report inputs: {exc}"
            ) from exc

        try:
            conn = storage.connect(self.db_path)
            try:
                with storage.write_tx(conn):
                    existing = self._checkpoint_tx(conn, job_id)
                    if existing is not None:
                        return existing
                    reason = self._validate_story_result_tx(conn, payload, graph)
                    if reason:
                        status = REPORT_DEFERRED if reason in {
                            "claim_human_override",
                            "story_not_reportable",
                        } else REPORT_TERMINAL
                        result = self._result(job_id, status, reason)
                        self._save_checkpoint_tx(conn, job_id, result)
                        return result
                    acceptance_reason = (
                        f"{AUTOMATIC_ACCEPTANCE_REASON_PREFIX}{payload['story_stage_job_id']}"
                    )
                    acceptance_error = self._accept_claim_tx(
                        conn, graph, str(payload["story_id"]), acceptance_reason
                    )
                    if acceptance_error:
                        result = self._result(
                            job_id, REPORT_DEFERRED, acceptance_error
                        )
                        self._save_checkpoint_tx(conn, job_id, result)
                        return result
                    report_id = self._ensure_report_tx(conn, str(payload["story_id"]), graph)
                    generation = self.reports.generate_tx(conn, report_id)
                    stage_status = (
                        REPORT_NO_CHANGE
                        if generation["status"] == "no_change"
                        else REPORT_COMPLETED
                    )
                    result = self._result(
                        job_id,
                        stage_status,
                        "report_inputs_unchanged"
                        if stage_status == REPORT_NO_CHANGE
                        else "report_revision_created",
                        report_id=report_id,
                        revision_id=generation["revision_id"],
                        input_identity=generation["input_identity"],
                        story_id=str(payload["story_id"]),
                        claim_id=str(payload["claim_id"]),
                        promotion_id=promotion_id,
                    )
                    self._save_checkpoint_tx(conn, job_id, result)
                    return result
            finally:
                conn.close()
        except sqlite3.OperationalError as exc:
            raise RetryableJobFailure(
                f"transient database error executing Report stage: {exc}"
            ) from exc
        except DomainConflict as exc:
            return self._persist_simple(
                job_id, REPORT_DEFERRED, "report_materiality_unproven", detail=str(exc)
            )
        except (DomainNotFound, DomainValidation) as exc:
            return self._persist_simple(
                job_id, REPORT_TERMINAL, "report_integrity_failure", detail=str(exc)
            )

    @staticmethod
    def _result(
        job_id: str,
        status: str,
        reason_code: str,
        **values: Any,
    ) -> dict[str, Any]:
        return {
            "job_id": job_id,
            "stage_status": status,
            "reason_code": reason_code,
            "report_id": values.get("report_id"),
            "revision_id": values.get("revision_id"),
            "input_identity": values.get("input_identity"),
            "story_id": values.get("story_id"),
            "claim_id": values.get("claim_id"),
            "promotion_id": values.get("promotion_id"),
            **({"detail": values["detail"][:500]} if values.get("detail") else {}),
        }

    @staticmethod
    def _checkpoint_tx(conn: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
        row = conn.execute("SELECT result_json FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise DomainNotFound("Report-stage Job not found")
        return _report_checkpoint(row["result_json"])

    @staticmethod
    def _save_checkpoint_tx(
        conn: sqlite3.Connection, job_id: str, result: Mapping[str, Any]
    ) -> None:
        changed = conn.execute(
            "UPDATE jobs SET result_json = ?, updated_at = ? WHERE id = ?",
            (
                json.dumps(dict(result), sort_keys=True, separators=(",", ":")),
                utc_now(),
                job_id,
            ),
        )
        if changed.rowcount != 1:
            raise DomainNotFound("Report-stage Job not found")

    def _persist_simple(
        self, job_id: str, status: str, reason_code: str, *, detail: str = ""
    ) -> dict[str, Any]:
        result = self._result(job_id, status, reason_code, detail=detail)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                existing = self._checkpoint_tx(conn, job_id)
                if existing is not None:
                    return existing
                self._save_checkpoint_tx(conn, job_id, result)
        finally:
            conn.close()
        return result

    @staticmethod
    def _validate_story_result_tx(
        conn: sqlite3.Connection,
        payload: Mapping[str, Any],
        graph: Mapping[str, Any],
    ) -> str | None:
        required = {
            "promotion_id": graph["promotion"]["id"],
            "claim_id": graph["claim"]["id"],
        }
        if any(str(payload.get(key) or "") != str(value) for key, value in required.items()):
            return "report_payload_mismatch"
        story_job = conn.execute(
            "SELECT * FROM jobs WHERE id = ? AND job_type = ?",
            (payload.get("story_stage_job_id"), AUTOMATIC_STORY_STAGE_JOB_TYPE),
        ).fetchone()
        if story_job is None or story_job["status"] not in {"succeeded", "partial"}:
            return "story_stage_not_completed"
        story_result = _decode(story_job["result_json"])
        expected = {
            "stage_status": STAGE_COMPLETED,
            "promotion_id": payload.get("promotion_id"),
            "claim_id": payload.get("claim_id"),
            "story_id": payload.get("story_id"),
            "event_id": payload.get("story_event_id"),
            "revision_id": payload.get("story_revision_id"),
        }
        if not story_result or any(story_result.get(key) != value for key, value in expected.items()):
            return "story_stage_result_mismatch"
        story = conn.execute(
            "SELECT lifecycle, deleted_at FROM stories WHERE id = ?",
            (payload.get("story_id"),),
        ).fetchone()
        if story is None or story["deleted_at"] is not None or story["lifecycle"] == "archived":
            return "story_not_reportable"
        claim = conn.execute(
            "SELECT story_id, article_analysis_id, candidate_claim_index, proposition FROM claims WHERE id = ?",
            (payload.get("claim_id"),),
        ).fetchone()
        verified_claim = graph["claim"]
        if (
            claim is None
            or claim["story_id"] != payload.get("story_id")
            or claim["article_analysis_id"] != verified_claim["article_analysis_id"]
            or claim["candidate_claim_index"] != verified_claim["candidate_claim_index"]
            or claim["proposition"] != verified_claim["proposition"]
        ):
            return "claim_story_mismatch"
        document = conn.execute(
            """
            SELECT d.id, s.id AS source_id, s.deleted_at AS source_deleted_at
            FROM documents d
            JOIN sources s ON s.id = d.source_id
            WHERE d.id = ?
            """,
            (graph["document"]["id"],),
        ).fetchone()
        if (
            document is None
            or document["source_deleted_at"] is not None
            or document["source_id"] != graph["source"]["id"]
        ):
            return "source_document_provenance_invalid"
        monitor = conn.execute(
            "SELECT enabled FROM monitors WHERE id = ?",
            (graph["monitor"]["id"],),
        ).fetchone()
        if monitor is None or monitor["enabled"] != 1:
            return "monitor_inactive"
        persisted_links = tuple(
            sorted(
                (row["evidence_span_id"], row["relationship"])
                for row in conn.execute(
                    "SELECT evidence_span_id, relationship FROM claim_evidence WHERE claim_id = ?",
                    (payload.get("claim_id"),),
                ).fetchall()
            )
        )
        verified_links = tuple(
            sorted(
                (str(item["evidence_span_id"]), str(item["relationship"]))
                for item in graph["claim_evidence"]
            )
        )
        if persisted_links != verified_links:
            return "claim_evidence_changed"
        revision = conn.execute(
            """
            SELECT 1
            FROM story_revisions sr
            JOIN story_revision_claims src
              ON src.revision_id = sr.id AND src.claim_id = ?
            WHERE sr.id = ? AND sr.story_id = ?
            """,
            (
                payload.get("claim_id"),
                payload.get("story_revision_id"),
                payload.get("story_id"),
            ),
        ).fetchone()
        event = conn.execute(
            "SELECT document_id, decision_json FROM story_evolution_events WHERE id = ? AND story_id = ?",
            (payload.get("story_event_id"), payload.get("story_id")),
        ).fetchone()
        if (
            revision is None
            or event is None
            or event["document_id"] != graph["document"]["id"]
        ):
            return "story_stage_artifact_mismatch"
        decision = _decode(event["decision_json"])
        automatic = decision.get("automatic_story_stage") if decision else None
        if not isinstance(automatic, Mapping) or any(
            automatic.get(key) != value
            for key, value in {
                "job_id": payload.get("story_stage_job_id"),
                "promotion_id": payload.get("promotion_id"),
                "claim_id": payload.get("claim_id"),
            }.items()
        ):
            return "story_stage_event_mismatch"
        return None

    def _accept_claim_tx(
        self,
        conn: sqlite3.Connection,
        graph: Mapping[str, Any],
        story_id: str,
        acceptance_reason: str,
    ) -> str | None:
        claim_id = str(graph["claim"]["id"])
        claim = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
        if claim is None or claim["story_id"] != story_id:
            return "claim_story_mismatch"
        history = conn.execute(
            "SELECT * FROM claim_state_history WHERE claim_id = ? ORDER BY rowid",
            (claim_id,),
        ).fetchall()
        automatic = [
            row
            for row in history
            if row["from_state"] == "pending"
            and row["to_state"] == "supported"
            and row["reason"] == acceptance_reason
        ]
        if claim["state"] == "supported" and claim["accepted_at"] is not None:
            return None if len(automatic) == 1 else "claim_human_override"
        if claim["state"] != "pending" or claim["accepted_at"] is not None:
            return "claim_human_override"
        links = list(graph["claim_evidence"])
        if not any(item["relationship"] == "supports" for item in links):
            return "claim_support_insufficient"
        if any(item["relationship"] == "contradicts" for item in links):
            return "claim_contradicted"
        self.evidence._set_claim_state_tx(
            conn, claim_id, "supported", acceptance_reason
        )
        self.evidence._accept_claim_tx(conn, claim_id)
        return None

    @staticmethod
    def _ensure_report_tx(
        conn: sqlite3.Connection, story_id: str, graph: Mapping[str, Any]
    ) -> str:
        existing = conn.execute(
            "SELECT id, status FROM living_reports WHERE target_type = 'story' AND target_id = ?",
            (story_id,),
        ).fetchone()
        if existing is not None:
            if existing["status"] != "active":
                raise DomainConflict("Story Living Report is archived")
            return str(existing["id"])
        identifier = new_id("report")
        now = utc_now()
        name = f"{str(graph['claim']['proposition']).strip()[:180]} report"
        try:
            conn.execute(
                "INSERT INTO living_reports(id, name, target_type, target_id, timezone_name, created_at, updated_at) VALUES (?, ?, 'story', ?, 'UTC', ?, ?)",
                (identifier, name, story_id, now, now),
            )
        except sqlite3.IntegrityError:
            winner = conn.execute(
                "SELECT id, status FROM living_reports WHERE target_type = 'story' AND target_id = ?",
                (story_id,),
            ).fetchone()
            if winner is None or winner["status"] != "active":
                raise
            return str(winner["id"])
        return identifier


__all__ = [
    "AUTOMATIC_ACCEPTANCE_REASON_PREFIX",
    "AUTOMATIC_REPORT_STAGE_IDEMPOTENCY_PREFIX",
    "AUTOMATIC_REPORT_STAGE_JOB_TYPE",
    "REPORT_COMPLETED",
    "REPORT_DEFERRED",
    "REPORT_NO_CHANGE",
    "REPORT_TERMINAL",
    "AutomaticReportStageExecutionService",
    "automatic_report_stage_completion_hook",
    "automatic_report_stage_rerun_factory",
    "enqueue_report_stage",
    "enqueue_report_stage_tx",
    "report_stage_idempotency_key",
]
