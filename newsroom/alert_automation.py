"""Phase 23D exact-cause Alert automation and durable in-app delivery."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from . import storage
from .domain import DomainNotFound, DomainValidation, new_id, utc_now
from .evidence import ACCEPTED_STATES, claim_set_hash
from .jobs import (
    AUTOMATIC_ALERT_STAGE_JOB_TYPE,
    AUTOMATIC_REPORT_STAGE_JOB_TYPE,
    JobService,
)
from .report_automation import REPORT_COMPLETED
from .reports import CAUSE_TYPES, AlertService, LivingReportService
from .worker import RetryableJobFailure


AUTOMATIC_ALERT_STAGE_IDEMPOTENCY_PREFIX = "automatic_alert_stage:"
ALERT_COMPLETED = "completed"
ALERT_NO_ALERT = "no_alert"
ALERT_DEFERRED = "deferred"
ALERT_TERMINAL = "terminal"
_ALERT_STATUSES = frozenset(
    {ALERT_COMPLETED, ALERT_NO_ALERT, ALERT_DEFERRED, ALERT_TERMINAL}
)


def alert_stage_idempotency_key(report_stage_job_id: str) -> str:
    identifier = str(report_stage_job_id or "").strip()
    if not identifier:
        raise DomainValidation("report_stage_job_id is required")
    return f"{AUTOMATIC_ALERT_STAGE_IDEMPOTENCY_PREFIX}{identifier}"


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


def _checkpoint(value: Any) -> dict[str, Any] | None:
    result = _decode(value)
    if result and result.get("stage_status") in _ALERT_STATUSES:
        return result
    return None


def enqueue_alert_stage_tx(
    conn: sqlite3.Connection,
    report_stage_job_id: str,
    *,
    report_result: Mapping[str, Any] | None = None,
    now: str | None = None,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Create/reuse the one Alert obligation for a material Report result."""

    if isinstance(max_attempts, bool) or not 1 <= max_attempts <= 10:
        raise DomainValidation("max_attempts must be between 1 and 10")
    report_job = conn.execute(
        "SELECT * FROM jobs WHERE id = ?", (str(report_stage_job_id).strip(),)
    ).fetchone()
    if report_job is None or report_job["job_type"] != AUTOMATIC_REPORT_STAGE_JOB_TYPE:
        raise DomainValidation("Alert-stage work requires an automatic Report-stage Job")
    result = (
        dict(report_result)
        if isinstance(report_result, Mapping)
        else _decode(report_job["result_json"])
    )
    if (
        report_job["status"] not in {"succeeded", "partial"}
        or not result
        or result.get("stage_status") != REPORT_COMPLETED
    ):
        raise DomainValidation("Alert-stage work requires a completed material Report result")
    required = ("report_id", "revision_id")
    if any(not str(result.get(field) or "").strip() for field in required):
        raise DomainValidation("completed Report-stage result is incomplete")

    key = alert_stage_idempotency_key(report_job["id"])
    existing = conn.execute(
        "SELECT id, status FROM jobs WHERE idempotency_key = ?", (key,)
    ).fetchone()
    if existing is not None:
        return {"id": existing["id"], "status": existing["status"], "coalesced": True}

    identifier = new_id("job")
    timestamp = now or utc_now()
    payload = json.dumps(
        {
            "report_stage_job_id": report_job["id"],
            "report_id": result["report_id"],
            "report_revision_id": result["revision_id"],
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
                AUTOMATIC_ALERT_STAGE_JOB_TYPE,
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


def enqueue_alert_stage(
    db_path: str | Path,
    report_stage_job_id: str,
    *,
    max_attempts: int = 3,
) -> dict[str, Any]:
    conn = storage.connect(db_path)
    try:
        with storage.write_tx(conn):
            result = enqueue_alert_stage_tx(
                conn, report_stage_job_id, max_attempts=max_attempts
            )
    finally:
        conn.close()
    return JobService(db_path).get(result["id"])


def automatic_alert_stage_completion_hook():
    """Enqueue Alert work only after a newly material Report-stage result."""

    def hook(
        conn: sqlite3.Connection,
        job_row: sqlite3.Row,
        job_status: str,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        if job_row["job_type"] != AUTOMATIC_REPORT_STAGE_JOB_TYPE:
            return
        if job_status not in {"succeeded", "partial"} or not isinstance(
            context, Mapping
        ):
            return
        outcome = context.get("outcome")
        if not isinstance(outcome, Mapping) or outcome.get("stage_status") != REPORT_COMPLETED:
            return
        enqueue_alert_stage_tx(conn, job_row["id"], report_result=outcome)

    return hook


def automatic_alert_stage_rerun_factory(
    db_path: str | Path, job: Mapping[str, Any]
) -> Mapping[str, Any] | None:
    if job.get("job_type") != AUTOMATIC_ALERT_STAGE_JOB_TYPE:
        return None
    payload = job.get("payload")
    if not isinstance(payload, Mapping):
        raise DomainValidation("Alert-stage Job payload must be an object")
    return enqueue_alert_stage(
        db_path, str(payload.get("report_stage_job_id") or "")
    )


class AutomaticAlertStageExecutionService:
    """Revalidate one material ReportRevision and deliver exact-cause Alerts."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.alerts = AlertService(db_path)

    def handlers(self) -> dict[str, Any]:
        return {AUTOMATIC_ALERT_STAGE_JOB_TYPE: self.handle}

    def handle(self, job: Mapping[str, Any]) -> dict[str, Any]:
        checkpoint = _checkpoint(job.get("result"))
        if checkpoint is not None:
            return checkpoint
        payload = job.get("payload")
        if not isinstance(payload, Mapping):
            raise DomainValidation("Alert-stage Job payload must be an object")
        job_id = str(job.get("id") or "").strip()
        if not job_id:
            raise DomainValidation("Alert-stage Job is missing canonical identity")
        try:
            conn = storage.connect(self.db_path)
            try:
                with storage.write_tx(conn):
                    existing = self._checkpoint_tx(conn, job_id)
                    if existing is not None:
                        return existing
                    reason = self._validate_report_tx(conn, job_id, payload)
                    if reason:
                        result = self._result(
                            job_id,
                            ALERT_TERMINAL,
                            reason,
                            report_id=payload.get("report_id"),
                            report_revision_id=payload.get("report_revision_id"),
                        )
                        self._save_checkpoint_tx(conn, job_id, result)
                        return result
                    emitted = self.alerts.emit_for_report_revision_tx(
                        conn,
                        str(payload["report_id"]),
                        str(payload["report_revision_id"]),
                        in_app_only=True,
                        suppress_equivalent=False,
                    )
                    stage_status = (
                        ALERT_COMPLETED if emitted["alert_ids"] else ALERT_NO_ALERT
                    )
                    result = self._result(
                        job_id,
                        stage_status,
                        "alerts_delivered"
                        if stage_status == ALERT_COMPLETED
                        else "no_active_rule_matched",
                        report_id=payload["report_id"],
                        report_revision_id=payload["report_revision_id"],
                        evaluated_rule_ids=emitted["evaluated_rule_ids"],
                        alert_ids=emitted["alert_ids"],
                        delivery_ids=emitted["delivery_ids"],
                    )
                    self._save_checkpoint_tx(conn, job_id, result)
                    return result
            finally:
                conn.close()
        except sqlite3.OperationalError as exc:
            raise RetryableJobFailure(
                f"transient database error executing Alert stage: {exc}"
            ) from exc

    @staticmethod
    def _result(
        job_id: str, status: str, reason_code: str, **values: Any
    ) -> dict[str, Any]:
        return {
            "job_id": job_id,
            "stage_status": status,
            "reason_code": reason_code,
            "report_id": values.get("report_id"),
            "report_revision_id": values.get("report_revision_id"),
            "evaluated_rule_ids": sorted(values.get("evaluated_rule_ids", [])),
            "alert_ids": sorted(values.get("alert_ids", [])),
            "delivery_ids": sorted(values.get("delivery_ids", [])),
        }

    @staticmethod
    def _checkpoint_tx(
        conn: sqlite3.Connection, job_id: str
    ) -> dict[str, Any] | None:
        row = conn.execute(
            "SELECT result_json FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None:
            raise DomainNotFound("Alert-stage Job not found")
        return _checkpoint(row["result_json"])

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
            raise DomainNotFound("Alert-stage Job not found")

    @staticmethod
    def _validate_report_tx(
        conn: sqlite3.Connection, job_id: str, payload: Mapping[str, Any]
    ) -> str | None:
        alert_job = conn.execute(
            "SELECT job_type FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if alert_job is None or alert_job["job_type"] != AUTOMATIC_ALERT_STAGE_JOB_TYPE:
            return "alert_job_identity_mismatch"
        report_job = conn.execute(
            "SELECT * FROM jobs WHERE id = ? AND job_type = ?",
            (payload.get("report_stage_job_id"), AUTOMATIC_REPORT_STAGE_JOB_TYPE),
        ).fetchone()
        if report_job is None or report_job["status"] not in {"succeeded", "partial"}:
            return "report_stage_not_completed"
        report_result = _decode(report_job["result_json"])
        expected = {
            "stage_status": REPORT_COMPLETED,
            "report_id": payload.get("report_id"),
            "revision_id": payload.get("report_revision_id"),
        }
        if not report_result or any(
            report_result.get(key) != value for key, value in expected.items()
        ):
            return "report_stage_result_mismatch"
        report = conn.execute(
            "SELECT * FROM living_reports WHERE id = ?", (payload.get("report_id"),)
        ).fetchone()
        revision = conn.execute(
            "SELECT * FROM report_revisions WHERE id = ? AND report_id = ?",
            (payload.get("report_revision_id"), payload.get("report_id")),
        ).fetchone()
        if report is None or revision is None or not revision["material_change"]:
            return "report_revision_mismatch"
        if report["current_revision_id"] is not None:
            current = conn.execute(
                "SELECT 1 FROM report_revisions WHERE id = ? AND report_id = ?",
                (report["current_revision_id"], report["id"]),
            ).fetchone()
            if current is None:
                return "report_current_revision_mismatch"
        try:
            audit = json.loads(revision["audit_json"])
            propositions = json.loads(revision["propositions_json"])
            changes = json.loads(revision["what_changed"] or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            return "report_revision_json_invalid"
        if (
            not isinstance(audit, dict)
            or audit.get("passed") is not True
            or audit.get("input_identity") != report_result.get("input_identity")
        ):
            return "report_revision_audit_mismatch"
        claim_rows = conn.execute(
            """
            SELECT c.*
            FROM report_revision_claims rrc
            JOIN claims c ON c.id = rrc.claim_id
            WHERE rrc.revision_id = ?
            ORDER BY rrc.position, c.id
            """,
            (revision["id"],),
        ).fetchall()
        claim_ids = [row["id"] for row in claim_rows]
        claim_id_set = set(claim_ids)
        if (
            not claim_ids
            or revision["claim_set_hash"] != claim_set_hash(claim_ids)
            or any(
                row["accepted_at"] is None or row["state"] not in ACCEPTED_STATES
                for row in claim_rows
            )
        ):
            return "report_claim_set_invalid"
        if not isinstance(propositions, list) or any(
            not isinstance(item, dict)
            or not item.get("claim_ids")
            or not set(item["claim_ids"]) <= claim_id_set
            for item in propositions
        ):
            return "report_propositions_invalid"
        causes = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM report_revision_causes WHERE revision_id = ? ORDER BY id",
                (revision["id"],),
            ).fetchall()
        ]
        cause_ids = {cause["id"] for cause in causes}
        if not causes or not isinstance(changes, list):
            return "report_causes_invalid"
        referenced_cause_ids: set[str] = set()
        for change in changes:
            if not isinstance(change, dict) or not change.get("cause_ids"):
                return "report_change_causes_invalid"
            selected = set(change["cause_ids"])
            if not selected <= cause_ids:
                return "report_change_causes_invalid"
            referenced_cause_ids.update(selected)
        if referenced_cause_ids != cause_ids:
            return "report_change_causes_invalid"
        for cause in causes:
            if (
                cause.get("cause_type") not in CAUSE_TYPES
                or cause.get("claim_id") not in claim_id_set
                or not LivingReportService._validate_cause_tx(
                    conn, cause, claim_id_set
                )
            ):
                return "report_cause_chain_invalid"
            live = conn.execute(
                """
                SELECT c.story_id, d.id AS document_id,
                       s.deleted_at AS source_deleted_at
                FROM claims c
                JOIN claim_evidence ce
                  ON ce.claim_id = c.id AND ce.relationship = 'supports'
                JOIN evidence_spans es ON es.id = ce.evidence_span_id
                JOIN document_versions dv ON dv.id = es.document_version_id
                JOIN documents d ON d.id = dv.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE c.id = ? AND es.id = ?
                """,
                (cause.get("claim_id"), cause.get("evidence_span_id")),
            ).fetchone()
            if (
                live is None
                or live["story_id"] != cause.get("story_id")
                or live["document_id"] != cause.get("document_id")
                or live["source_deleted_at"] is not None
            ):
                return "report_cause_chain_invalid"
        return None


__all__ = [
    "ALERT_COMPLETED",
    "ALERT_DEFERRED",
    "ALERT_NO_ALERT",
    "ALERT_TERMINAL",
    "AUTOMATIC_ALERT_STAGE_IDEMPOTENCY_PREFIX",
    "AUTOMATIC_ALERT_STAGE_JOB_TYPE",
    "AutomaticAlertStageExecutionService",
    "alert_stage_idempotency_key",
    "automatic_alert_stage_completion_hook",
    "automatic_alert_stage_rerun_factory",
    "enqueue_alert_stage",
    "enqueue_alert_stage_tx",
]
