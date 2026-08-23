"""Durable jobs, leases, scheduler state, and budget enforcement.

The queue is deliberately small and SQLite-backed. Every state transition is
performed in a short ``BEGIN IMMEDIATE`` transaction; worker code runs outside
that transaction and can therefore be restarted without holding database locks.
"""
from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from . import storage
from .domain import DomainConflict, DomainError, DomainNotFound, DomainValidation, new_id, utc_now


class JobError(DomainError):
    status_code = 409
    code = "job_error"


class JobConflict(DomainConflict):
    code = "job_conflict"


class JobNotFound(DomainNotFound):
    pass


class BudgetExhausted(DomainError):
    status_code = 409
    code = "budget_exhausted"

    def __init__(self, message: str = "job budget is exhausted", *, reason: str = "budget_exhausted"):
        super().__init__(message)
        self.reason = reason


class PaidInvocationBusy(BudgetExhausted):
    """Another worker owns the canonical paid analysis invocation."""

    def __init__(self, message: str = "paid analysis invocation is already active"):
        super().__init__(message, reason="analysis_invocation_active")


class PaidInvocationUncertain(BudgetExhausted):
    """A previous provider call may have been processed remotely."""

    def __init__(self, message: str = "paid analysis invocation has uncertain remote state"):
        super().__init__(message, reason="analysis_invocation_uncertain")


JOB_STATUSES = frozenset({"queued", "running", "succeeded", "partial", "failed", "cancelled"})
TERMINAL_JOB_STATUSES = frozenset({"succeeded", "partial", "failed", "cancelled"})
ATTEMPT_STATUSES = frozenset({"running", "succeeded", "failed", "cancelled"})
RUN_STATUSES = frozenset({"running", "success", "partial", "failed"})
BUDGET_SCOPE_TYPES = frozenset({"global", "policy", "job", "research_question"})
BUDGET_PERIODS = frozenset({"daily", "monthly", "lifetime"})
BUDGET_CAP_TYPES = frozenset({"acquisition_units", "local_model_units", "paid_requests", "usd"})

MONITOR_CHECK_JOB_TYPE = "monitor_check"
RESEARCH_QUESTION_JOB_TYPE = "research_question"
DOCUMENT_VERSION_PROCESS_JOB_TYPE = "document_version_process"
AUTOMATIC_STORY_STAGE_JOB_TYPE = "automatic_story_stage"
AUTOMATIC_REPORT_STAGE_JOB_TYPE = "automatic_report_stage"

RecoveryHook = Callable[[sqlite3.Connection, sqlite3.Row, str], None]
CompletionHook = Callable[[sqlite3.Connection, sqlite3.Row, str, Mapping[str, Any] | None], None]
RerunFactory = Callable[[Path, Mapping[str, Any]], Mapping[str, Any] | None]


def compose_rerun_factories(*factories: RerunFactory | None) -> RerunFactory | None:
    """Compose independent rerun factories into one JobService rerun factory.

    Every factory is asked in registration order and the first non-None rebuilt
    job wins; ``None`` answers fall through so each domain stays optional and
    the generic clone fallback in ``JobService.rerun`` remains the last resort.
    Registering the same factory object twice is rejected, mirroring
    ``compose_completion_hooks`` collision semantics.
    """
    registered: list[RerunFactory] = []
    for factory in factories:
        if factory is None:
            continue
        if not callable(factory):
            raise TypeError("rerun factories must be callable")
        if any(registered_factory is factory for registered_factory in registered):
            raise ValueError("duplicate rerun factory registration")
        registered.append(factory)
    if not registered:
        return None
    if len(registered) == 1:
        return registered[0]

    def composed(db_path: Path, job: Mapping[str, Any]) -> Mapping[str, Any] | None:
        for factory in registered:
            rebuilt = factory(db_path, job)
            if rebuilt is not None:
                return rebuilt
        return None

    return composed


def compose_completion_hooks(*hooks: CompletionHook | None) -> CompletionHook | None:
    """Compose independent completion hooks into one JobService completion hook.

    Every hook receives the same completion event and is responsible for
    ignoring job types it does not own (each domain hook filters by its own
    ``job_type``). None entries are skipped so individual domains can stay
    optional. Registering the same hook object twice is rejected: a hook must
    never run twice for a single event, mirroring ``merge_handlers`` collision
    semantics.
    """
    registered: list[CompletionHook] = []
    for hook in hooks:
        if hook is None:
            continue
        if not callable(hook):
            raise TypeError("completion hooks must be callable")
        if any(registered_hook is hook for registered_hook in registered):
            raise ValueError("duplicate completion hook registration")
        registered.append(hook)
    if not registered:
        return None
    if len(registered) == 1:
        return registered[0]

    def composed(
        conn: sqlite3.Connection,
        job_row: sqlite3.Row,
        job_status: str,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        for hook in registered:
            hook(conn, job_row, job_status, context)

    return composed


def _resolve_monitor_check_monitor_id(
    job_type: str,
    monitor_id: str | None,
    payload: Mapping[str, Any],
) -> str:
    """Validate canonical Monitor ownership for a monitor_check enqueue.

    Returns the canonical ``monitor_id`` when the job is a ``monitor_check``.
    Returns an empty string for any other job type so callers can skip the
    active-work check. Raises ``DomainValidation`` when a monitor_check job is
    missing its canonical ``monitor_id`` or when its payload carries a
    conflicting ``monitor_id``.
    """
    if job_type != MONITOR_CHECK_JOB_TYPE:
        return ""
    canonical = str(monitor_id or "").strip()
    if not canonical:
        raise DomainValidation("monitor_check jobs require a canonical monitor_id")
    payload_mid = payload.get("monitor_id") if isinstance(payload, Mapping) else None
    if payload_mid is not None and str(payload_mid).strip() != canonical:
        raise DomainValidation("monitor_check payload monitor_id conflicts with job monitor_id")
    return canonical


def _active_monitor_check_id_tx(conn: sqlite3.Connection, monitor_id: str) -> str | None:
    """Return the job id of any active monitor_check for ``monitor_id``.

    Active means ``status IN ('queued', 'running')`` — the same definition the
    scheduler uses. Runs inside the caller's write transaction so that
    ``BEGIN IMMEDIATE`` serializes concurrent producers.
    """
    row = conn.execute(
        """
        SELECT id FROM jobs
        WHERE monitor_id = ? AND job_type = ?
          AND status IN ('queued', 'running')
        LIMIT 1
        """,
        (monitor_id, MONITOR_CHECK_JOB_TYPE),
    ).fetchone()
    return row[0] if row is not None else None


def _resolve_document_version_process_version_id(
    job_type: str,
    document_version_id: str | None,
    payload: Mapping[str, Any],
) -> str:
    """Validate canonical DocumentVersion ownership for a processing enqueue.

    Returns the canonical ``document_version_id`` when the job is a
    ``document_version_process``. Returns an empty string for any other job
    type so callers can skip the active-work check. Raises
    ``DomainValidation`` when a document_version_process job is missing its
    canonical ``document_version_id`` or when its payload carries a
    conflicting ``document_version_id``.
    """
    if job_type != DOCUMENT_VERSION_PROCESS_JOB_TYPE:
        return ""
    canonical = str(document_version_id or "").strip()
    if not canonical:
        raise DomainValidation("document_version_process jobs require a canonical document_version_id")
    payload_id = payload.get("document_version_id") if isinstance(payload, Mapping) else None
    if payload_id is not None and str(payload_id).strip() != canonical:
        raise DomainValidation("document_version_process payload document_version_id conflicts with job document_version_id")
    return canonical


def _active_document_version_process_id_tx(conn: sqlite3.Connection, document_version_id: str) -> str | None:
    """Return the job id of any active document_version_process for a version.

    Active means ``status IN ('queued', 'running')`` — the same definition
    used for monitor_check obligations. Runs inside the caller's write
    transaction so that ``BEGIN IMMEDIATE`` serializes concurrent producers.
    """
    row = conn.execute(
        """
        SELECT id FROM jobs
        WHERE document_version_id = ? AND job_type = ?
          AND status IN ('queued', 'running')
        LIMIT 1
        """,
        (document_version_id, DOCUMENT_VERSION_PROCESS_JOB_TYPE),
    ).fetchone()
    return row[0] if row is not None else None


def _timestamp(value: str | datetime | None = None) -> str:
    if value is None:
        return utc_now()
    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DomainValidation("timestamp must be an ISO-8601 value") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _plus_seconds(value: str, seconds: int) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _timestamp(parsed + timedelta(seconds=seconds))


def _json_object(value: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        raise DomainValidation("job payload must be an object")
    try:
        encoded = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise DomainValidation("job payload must be JSON serializable") from exc
    if len(encoded.encode("utf-8")) > 100_000:
        raise DomainValidation("job payload exceeds the 100KB limit")
    return encoded, dict(value)


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DomainValidation(f"{field} must be a nonnegative integer")
    return value


def _cap_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise DomainValidation(f"{field} must be a nonnegative integer")
    if float(value) < 0 or not float(value).is_integer():
        raise DomainValidation(f"{field} must be a nonnegative integer")
    return int(value)


def _nonnegative_float(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
        raise DomainValidation(f"{field} must be a finite nonnegative number")
    return float(value)


def _budget_plan(payload: Mapping[str, Any]) -> dict[str, int | float]:
    raw = payload.get("budget", {})
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise DomainValidation("job budget must be an object")
    return {
        "acquisition_units": _nonnegative_int(raw.get("acquisition_units", 0), "acquisition_units"),
        "local_model_units": _nonnegative_int(raw.get("local_model_units", 0), "local_model_units"),
        "paid_requests": _nonnegative_int(raw.get("paid_requests", 0), "paid_requests"),
        "usd": _nonnegative_float(raw.get("usd", 0.0), "usd"),
    }


def _decode(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _job_dict(row: sqlite3.Row, attempts: list[sqlite3.Row] | None = None, reservation: sqlite3.Row | None = None) -> dict[str, Any]:
    result = dict(row)
    result["payload"] = _decode(result.pop("payload_json"), {})
    result["result"] = _decode(result.pop("result_json"), None) if "result_json" in result else None
    result["attempts_detail"] = [dict(item) for item in (attempts or [])]
    if reservation is not None:
        result["budget_reservation"] = dict(reservation)
    else:
        result["budget_reservation"] = None
    return result


class BudgetService:
    """Atomically check and reserve configured global/work budgets."""

    paid_enabled_key = "budget.paid_enabled"

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def set_paid_enabled(self, enabled: bool) -> dict[str, Any]:
        value = "1" if enabled else "0"
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    """
                    INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                    """,
                    (self.paid_enabled_key, value, now),
                )
        finally:
            conn.close()
        return {"enabled": enabled, "updated_at": now}

    def paid_enabled(self) -> bool:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (self.paid_enabled_key,)).fetchone()
            return bool(row and row[0] == "1")
        finally:
            conn.close()

    def configure_limit(
        self,
        scope_type: str,
        scope_id: str | None,
        period: str,
        cap_type: str,
        cap_value: int | float,
        *,
        enabled: bool = True,
    ) -> dict[str, Any]:
        scope_type = str(scope_type).strip()
        period = str(period).strip()
        cap_type = str(cap_type).strip()
        if scope_type not in BUDGET_SCOPE_TYPES:
            raise DomainValidation("invalid budget scope")
        if period not in BUDGET_PERIODS:
            raise DomainValidation("invalid budget period")
        if cap_type not in BUDGET_CAP_TYPES:
            raise DomainValidation("invalid budget cap type")
        normalized_scope_id = "" if scope_type == "global" else str(scope_id or "").strip()
        if scope_type != "global" and not normalized_scope_id:
            raise DomainValidation("non-global budget scope requires scope_id")
        normalized_cap = _nonnegative_float(cap_value, "cap_value") if cap_type == "usd" else _cap_integer(cap_value, "cap_value")
        now = utc_now()
        identifier = new_id("budget")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if scope_type != "global":
                    table = {
                        "policy": "monitoring_policies",
                        "job": "jobs",
                        "research_question": "research_questions",
                    }[scope_type]
                    if conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (normalized_scope_id,)).fetchone() is None:
                        raise DomainNotFound(f"{scope_type} not found")
                existing = conn.execute(
                    """
                    SELECT id FROM budget_limits
                    WHERE scope_type = ? AND scope_id = ? AND period = ? AND cap_type = ?
                    """,
                    (scope_type, normalized_scope_id, period, cap_type),
                ).fetchone()
                if existing:
                    identifier = existing[0]
                    conn.execute(
                        """
                        UPDATE budget_limits
                        SET cap_value = ?, enabled = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (normalized_cap, int(enabled), now, identifier),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO budget_limits
                            (id, scope_type, scope_id, period, cap_type, cap_value,
                             enabled, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (identifier, scope_type, normalized_scope_id, period, cap_type, normalized_cap, int(enabled), now, now),
                    )
        finally:
            conn.close()
        return self.get_limit(identifier)

    def get_limit(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM budget_limits WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("budget limit not found")
            return dict(row)
        finally:
            conn.close()

    def list_limits(self) -> list[dict[str, Any]]:
        conn = storage.connect(self.db_path)
        try:
            return [dict(row) for row in conn.execute("SELECT * FROM budget_limits ORDER BY scope_type, scope_id, period, cap_type")]
        finally:
            conn.close()

    def record_usage(
        self,
        *,
        capability: str,
        provider: str | None,
        request_type: str,
        acquisition_units: int = 0,
        local_model_units: int = 0,
        paid_requests: int = 0,
        estimated_cost_usd: float = 0.0,
        job_id: str | None = None,
        monitor_id: str | None = None,
        research_question_id: str | None = None,
        outcome: str | None = None,
    ) -> dict[str, Any]:
        if not str(capability).strip() or not str(request_type).strip():
            raise DomainValidation("usage capability and request_type are required")
        acquisition_units = _nonnegative_int(acquisition_units, "acquisition_units")
        local_model_units = _nonnegative_int(local_model_units, "local_model_units")
        paid_requests = _nonnegative_int(paid_requests, "paid_requests")
        estimated_cost_usd = _nonnegative_float(estimated_cost_usd, "estimated_cost_usd")
        identifier = new_id("usage")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    """
                    INSERT INTO provider_usage
                        (id, job_id, monitor_id, research_question_id, capability,
                         provider, request_type, query_units, token_units,
                         estimated_cost_usd, latency_ms, outcome, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                    """,
                    (
                        identifier, job_id, monitor_id, research_question_id,
                        str(capability).strip(), provider, str(request_type).strip(),
                        acquisition_units, local_model_units, estimated_cost_usd,
                        json.dumps({"paid_requests": paid_requests, "status": outcome}, sort_keys=True) if paid_requests else outcome,
                        utc_now(),
                    ),
                )
        finally:
            conn.close()
        return self.get_usage(identifier)

    def get_usage(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM provider_usage WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("provider usage not found")
            return dict(row)
        finally:
            conn.close()

    def list_usage(self, *, job_id: str | None = None, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        if page < 1 or page_size < 1 or page_size > 200:
            raise DomainValidation("invalid usage page")
        where = "WHERE job_id = ?" if job_id else ""
        params: list[Any] = [job_id] if job_id else []
        conn = storage.connect(self.db_path)
        try:
            total = conn.execute(f"SELECT COUNT(*) FROM provider_usage {where}", params).fetchone()[0]
            params.extend([page_size, (page - 1) * page_size])
            rows = conn.execute(
                f"SELECT * FROM provider_usage {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
            return {"items": [dict(row) for row in rows], "page": page, "page_size": page_size, "total": total}
        finally:
            conn.close()

    @staticmethod
    def _scope_specs(job: sqlite3.Row) -> list[tuple[str, str]]:
        specs = [("global", "")]
        if job["monitor_id"]:
            specs.append(("policy", "__from_monitor__"))
        if job["research_question_id"]:
            specs.append(("research_question", job["research_question_id"]))
        specs.append(("job", job["id"]))
        return specs

    @staticmethod
    def _period_start(period: str, now: str) -> str | None:
        if period == "lifetime":
            return None
        parsed = datetime.fromisoformat(now.replace("Z", "+00:00"))
        if period == "daily":
            parsed = parsed.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            parsed = parsed.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return _timestamp(parsed)

    @staticmethod
    def _usage_rows(conn: sqlite3.Connection, job: sqlite3.Row, period: str, now: str) -> list[sqlite3.Row]:
        start = BudgetService._period_start(period, now)
        joins = "LEFT JOIN monitors AS m ON m.id = u.monitor_id"
        where = "WHERE u.created_at >= ?" if start else ""
        params: list[Any] = [start] if start else []
        rows = conn.execute(
            f"SELECT u.*, m.policy_id AS usage_policy_id, NULL AS invocation_policy_id FROM provider_usage AS u {joins} {where}",
            params,
        ).fetchall()
        return list(rows)

    @staticmethod
    def _row_in_scope(row: sqlite3.Row, scope_type: str, scope_id: str, job: sqlite3.Row) -> bool:
        if scope_type == "global":
            return True
        if scope_type == "job":
            return row["job_id"] == scope_id
        if scope_type == "research_question":
            return row["research_question_id"] == scope_id
        policy_id = scope_id
        return (row["usage_policy_id"] or row["invocation_policy_id"]) == policy_id

    @staticmethod
    def _usage_value(row: sqlite3.Row, cap_type: str) -> float:
        # A linked article-analysis usage row is already represented by its
        # durable invocation reservation. Counting it again would make a
        # configured budget appear to consume two requests for one call.
        if row["invocation_id"] is not None:
            return 0.0
        if cap_type == "acquisition_units":
            return float(row["query_units"] or 0)
        if cap_type == "local_model_units":
            return float(row["token_units"] or 0)
        if cap_type == "usd":
            return float(row["estimated_cost_usd"] or 0.0)
        if str(row["request_type"] or "").casefold().find("paid") >= 0:
            return 1.0
        try:
            outcome = json.loads(row["outcome"] or "{}")
            return float(outcome.get("paid_requests", 0)) if isinstance(outcome, Mapping) else 0.0
        except (TypeError, ValueError, json.JSONDecodeError):
            return 0.0

    @staticmethod
    def _reservation_value(row: sqlite3.Row, cap_type: str) -> float:
        return float(row["estimated_cost_usd"] if cap_type == "usd" else row[cap_type])

    @staticmethod
    def _analysis_invocation_rows(conn: sqlite3.Connection, *, period: str, now: str) -> list[sqlite3.Row]:
        start = BudgetService._period_start(period, now)
        predicate = "ai.state <> 'retryable'"
        params: list[Any] = []
        if start:
            predicate += " AND ai.created_at >= ?"
            params.append(start)
        return list(
            conn.execute(
                """
                SELECT ai.*, m.policy_id AS invocation_policy_id
                FROM analysis_invocations AS ai
                LEFT JOIN monitors AS m ON m.id = ai.monitor_id
                WHERE """ + predicate,
                params,
            ).fetchall()
        )

    @staticmethod
    def _analysis_invocation_value(row: sqlite3.Row, cap_type: str) -> float:
        return float(row["reserved_cost_usd"] or 0.0) if cap_type == "usd" else float(row["reserved_requests"] or 0)

    @staticmethod
    def _analysis_scope_match(row: sqlite3.Row, scope_type: str, scope_id: str) -> bool:
        if scope_type == "global":
            return True
        if scope_type == "job":
            return row["job_id"] == scope_id
        if scope_type == "research_question":
            return "research_question_id" in row.keys() and row["research_question_id"] == scope_id
        usage_policy = row["usage_policy_id"] if "usage_policy_id" in row.keys() else None
        invocation_policy = row["invocation_policy_id"] if "invocation_policy_id" in row.keys() else None
        return (usage_policy or invocation_policy) == scope_id

    @staticmethod
    def _legacy_paid_analysis_usage(conn: sqlite3.Connection) -> tuple[float, float]:
        row = conn.execute(
            """
            SELECT COUNT(*) AS requests, COALESCE(SUM(estimated_cost_usd), 0.0) AS cost
            FROM provider_usage
            WHERE capability = 'article_analysis'
              AND request_type = 'ai:paid'
              AND invocation_id IS NULL
            """
        ).fetchone()
        return float(row["requests"] or 0), float(row["cost"] or 0.0)

    def _analysis_usage_totals_tx(self, conn: sqlite3.Connection) -> tuple[float, float]:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(reserved_requests), 0) AS requests,
                   COALESCE(SUM(reserved_cost_usd), 0.0) AS cost
            FROM analysis_invocations
            WHERE state <> 'retryable'
            """
        ).fetchone()
        legacy_requests, legacy_cost = self._legacy_paid_analysis_usage(conn)
        return (
            float(row["requests"] or 0) + legacy_requests,
            float(row["cost"] or 0.0) + legacy_cost,
        )

    def _authorize_paid_analysis_tx(
        self,
        conn: sqlite3.Connection,
        *,
        monitor_id: str,
        job_id: str | None,
        estimated_cost_usd: float,
        max_paid_calls: int,
        max_paid_cost_usd: float,
        now: str,
    ) -> None:
        """Authorize a paid analysis against current durable state."""
        if not self._paid_enabled_tx(conn):
            raise BudgetExhausted("paid dispatch is disabled", reason="paid_disabled")
        used_requests, used_cost = self._analysis_usage_totals_tx(conn)
        if used_requests + 1 > max_paid_calls:
            raise BudgetExhausted(
                "configured paid analysis request limit exhausted",
                reason="paid_budget_exhausted",
            )
        if used_cost + estimated_cost_usd > max_paid_cost_usd + 1e-12:
            raise BudgetExhausted(
                "configured paid analysis USD limit exhausted",
                reason="paid_budget_exhausted",
            )
        self._check_analysis_budget_limits_tx(
            conn,
            monitor_id=monitor_id,
            job_id=job_id,
            request_cost_usd=estimated_cost_usd,
            now=now,
        )

    def _check_analysis_budget_limits_tx(
        self,
        conn: sqlite3.Connection,
        *,
        monitor_id: str,
        job_id: str | None,
        request_cost_usd: float,
        now: str,
    ) -> None:
        monitor = conn.execute("SELECT policy_id FROM monitors WHERE id = ?", (monitor_id,)).fetchone()
        specs = [("global", "")]
        if monitor is not None and monitor["policy_id"]:
            specs.append(("policy", monitor["policy_id"]))
        if job_id:
            specs.append(("job", job_id))
        for scope_type, scope_id in specs:
            limits = conn.execute(
                """
                SELECT * FROM budget_limits
                WHERE scope_type = ? AND scope_id = ? AND enabled = 1
                  AND cap_type IN ('paid_requests', 'usd')
                """,
                (scope_type, scope_id),
            ).fetchall()
            if not limits:
                continue
            usage_rows = self._usage_rows(
                conn,
                conn.execute(
                    "SELECT ? AS id, ? AS monitor_id, ? AS research_question_id",
                    (job_id, monitor_id, None),
                ).fetchone(),
                "lifetime",
                now,
            )
            invocation_rows = self._analysis_invocation_rows(conn, period="lifetime", now=now)
            for limit in limits:
                start = self._period_start(limit["period"], now)
                usage = 0.0
                for row in usage_rows:
                    if start and row["created_at"] < start:
                        continue
                    if self._analysis_scope_match(row, limit["scope_type"], limit["scope_id"]):
                        usage += self._usage_value(row, limit["cap_type"])
                for row in invocation_rows:
                    if start and row["created_at"] < start:
                        continue
                    if self._analysis_scope_match(row, limit["scope_type"], limit["scope_id"]):
                        usage += self._analysis_invocation_value(row, limit["cap_type"])
                for reservation in conn.execute(
                    "SELECT * FROM budget_reservations WHERE status = 'reserved'"
                ).fetchall():
                    if self._reservation_in_scope(conn, reservation, limit["scope_type"], limit["scope_id"]):
                        usage += self._reservation_value(reservation, limit["cap_type"])
                requested = 1.0 if limit["cap_type"] == "paid_requests" else request_cost_usd
                if usage + requested > float(limit["cap_value"]) + 1e-12:
                    raise BudgetExhausted(
                        f"{scope_type} {limit['cap_type']} budget exhausted",
                        reason="budget_exhausted",
                    )

    @staticmethod
    def _reservation_in_scope(
        conn: sqlite3.Connection,
        reservation: sqlite3.Row,
        scope_type: str,
        scope_id: str,
    ) -> bool:
        job = conn.execute(
            "SELECT id, monitor_id, research_question_id FROM jobs WHERE id = ?",
            (reservation["job_id"],),
        ).fetchone()
        if job is None:
            return False
        if scope_type == "global":
            return True
        if scope_type == "job":
            return job["id"] == scope_id
        if scope_type == "research_question":
            return job["research_question_id"] == scope_id
        monitor = conn.execute("SELECT policy_id FROM monitors WHERE id = ?", (job["monitor_id"],)).fetchone()
        return monitor is not None and monitor["policy_id"] == scope_id

    def reserve_paid_analysis(
        self,
        *,
        identity_hash: str,
        document_version_id: str,
        relevance_id: str,
        monitor_id: str,
        job_id: str | None,
        estimated_cost_usd: float,
        max_paid_calls: int,
        max_paid_cost_usd: float,
        lease_seconds: int = 300,
    ) -> dict[str, Any]:
        """Atomically authorize one automatic paid analysis invocation."""
        if not str(identity_hash).strip():
            raise DomainValidation("paid analysis identity_hash is required")
        estimated_cost_usd = _nonnegative_float(estimated_cost_usd, "estimated_cost_usd")
        max_paid_calls = _nonnegative_int(max_paid_calls, "max_paid_calls")
        max_paid_cost_usd = _nonnegative_float(max_paid_cost_usd, "max_paid_cost_usd")
        if lease_seconds < 1:
            raise DomainValidation("paid analysis invocation lease must be positive")
        now = utc_now()
        owner_token = new_id("inv-owner")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                existing = conn.execute(
                    "SELECT * FROM analysis_invocations WHERE identity_hash = ?",
                    (identity_hash,),
                ).fetchone()
                if existing is not None:
                    state = existing["state"]
                    if state == "succeeded":
                        return {"state": state, "id": existing["id"], "identity_hash": identity_hash}
                    if state in {"reserved", "running"}:
                        raise PaidInvocationBusy()
                    if state == "uncertain":
                        raise PaidInvocationUncertain()
                    if state == "failed_terminal":
                        raise BudgetExhausted(
                            "paid analysis invocation is terminally failed",
                            reason="analysis_invocation_terminal",
                        )
                    if (
                        existing["document_version_id"] != document_version_id
                        or existing["relevance_id"] != relevance_id
                        or existing["monitor_id"] != monitor_id
                        or existing["job_id"] != job_id
                    ):
                        raise DomainConflict("paid analysis invocation provenance does not match the retry")
                    if int(existing["paid"] or 0) != 1 or int(existing["reserved_requests"] or 0) != 1:
                        raise DomainConflict("paid analysis invocation reservation is invalid")
                    self._authorize_paid_analysis_tx(
                        conn,
                        monitor_id=monitor_id,
                        job_id=job_id,
                        estimated_cost_usd=estimated_cost_usd,
                        max_paid_calls=max_paid_calls,
                        max_paid_cost_usd=max_paid_cost_usd,
                        now=now,
                    )
                    conn.execute(
                        """
                        UPDATE analysis_invocations
                        SET state = 'running', owner_token = ?,
                            lease_expires_at = ?, started_at = ?,
                            completed_at = NULL, failure_code = NULL,
                            reserved_requests = 1, reserved_cost_usd = ?, updated_at = ?
                        WHERE id = ? AND state = 'retryable'
                        """,
                        (
                            owner_token,
                            _plus_seconds(now, lease_seconds),
                            now,
                            estimated_cost_usd,
                            now,
                            existing["id"],
                        ),
                    )
                    return {
                        "state": "running",
                        "id": existing["id"],
                        "identity_hash": identity_hash,
                        "owner_token": owner_token,
                    }
                self._authorize_paid_analysis_tx(
                    conn,
                    monitor_id=monitor_id,
                    job_id=job_id,
                    estimated_cost_usd=estimated_cost_usd,
                    max_paid_calls=max_paid_calls,
                    max_paid_cost_usd=max_paid_cost_usd,
                    now=now,
                )
                identifier = new_id("inv")
                conn.execute(
                    """
                    INSERT INTO analysis_invocations
                        (id, identity_hash, document_version_id, relevance_id,
                         monitor_id, job_id, state, paid, reserved_requests,
                         reserved_cost_usd, owner_token, lease_expires_at,
                         started_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'running', 1, 1, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        identifier,
                        identity_hash,
                        document_version_id,
                        relevance_id,
                        monitor_id,
                        job_id,
                        estimated_cost_usd,
                        owner_token,
                        _plus_seconds(now, lease_seconds),
                        now,
                        now,
                        now,
                    ),
                )
                return {
                    "state": "running",
                    "id": identifier,
                    "identity_hash": identity_hash,
                    "owner_token": owner_token,
                }
        finally:
            conn.close()

    def complete_paid_analysis(self, invocation_id: str, owner_token: str) -> None:
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                result = conn.execute(
                    """
                    UPDATE analysis_invocations
                    SET state = 'succeeded', owner_token = NULL,
                        lease_expires_at = NULL, completed_at = ?, updated_at = ?
                    WHERE id = ? AND state = 'running' AND owner_token = ?
                    """,
                    (now, now, invocation_id, owner_token),
                )
                if result.rowcount != 1:
                    raise DomainConflict("paid analysis invocation ownership was lost")
        finally:
            conn.close()

    def fail_paid_analysis(
        self,
        invocation_id: str,
        owner_token: str,
        *,
        state: str,
        failure_code: str,
    ) -> None:
        if state not in {"failed_terminal", "uncertain", "retryable"}:
            raise DomainValidation("invalid paid analysis invocation failure state")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    """
                    UPDATE analysis_invocations
                    SET state = ?, owner_token = NULL, lease_expires_at = NULL,
                        completed_at = ?, failure_code = ?, updated_at = ?
                    WHERE id = ? AND state = 'running' AND owner_token = ?
                    """,
                    (state, now, str(failure_code)[:120], now, invocation_id, owner_token),
                )
        finally:
            conn.close()

    def release_paid_analysis_if_not_started(
        self,
        identity_hash: str,
        *,
        reason: str = "operator_confirmed_not_started",
    ) -> None:
        """Explicitly release a reservation only after no request began."""
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                result = conn.execute(
                    """
                    UPDATE analysis_invocations
                    SET state = 'retryable', owner_token = NULL,
                        lease_expires_at = NULL, failure_code = ?, updated_at = ?
                    WHERE identity_hash = ? AND state IN ('running', 'uncertain')
                    """,
                    (str(reason)[:120], now, identity_hash),
                )
                if result.rowcount != 1:
                    raise DomainConflict("paid analysis invocation is not releasable")
        finally:
            conn.close()

    def _reserve_tx(self, conn: sqlite3.Connection, job: sqlite3.Row, now: str) -> None:
        plan = _budget_plan(_decode(job["payload_json"], {}))
        if plan["paid_requests"] and not self._paid_enabled_tx(conn):
            raise BudgetExhausted("paid dispatch is disabled", reason="paid_disabled")

        rows = self._usage_rows(conn, job, "lifetime", now)
        policy_id = None
        if job["monitor_id"]:
            monitor = conn.execute("SELECT policy_id FROM monitors WHERE id = ?", (job["monitor_id"],)).fetchone()
            policy_id = monitor[0] if monitor else None
        specs = [("global", "")]
        if policy_id:
            specs.append(("policy", policy_id))
        if job["research_question_id"]:
            specs.append(("research_question", job["research_question_id"]))
        specs.append(("job", job["id"]))

        limits = []
        for scope_type, scope_id in specs:
            limits.extend(
                conn.execute(
                    """
                    SELECT * FROM budget_limits
                    WHERE scope_type = ? AND scope_id = ? AND enabled = 1
                    """,
                    (scope_type, scope_id),
                ).fetchall()
            )
        for limit in limits:
            value = float(plan[limit["cap_type"]])
            start = self._period_start(limit["period"], now)
            usage = 0.0
            for row in rows:
                if start and row["created_at"] < start:
                    continue
                if self._row_in_scope(row, limit["scope_type"], limit["scope_id"], job):
                    usage += self._usage_value(row, limit["cap_type"])
            reservations = conn.execute(
                """
                SELECT br.* FROM budget_reservations AS br
                JOIN jobs AS j ON j.id = br.job_id
                LEFT JOIN monitors AS m ON m.id = j.monitor_id
                WHERE br.status = 'reserved'
                  AND (? IS NULL OR br.reserved_at >= ?)
                  AND (? = 'global' OR (? = 'job' AND j.id = ?) OR
                       (? = 'research_question' AND j.research_question_id = ?) OR
                       (? = 'policy' AND m.policy_id = ?))
                """,
                (
                    start, start, limit["scope_type"], limit["scope_type"], limit["scope_id"],
                    limit["scope_type"], limit["scope_id"], limit["scope_type"], limit["scope_id"],
                ),
            ).fetchall()
            reserved = sum(self._reservation_value(row, limit["cap_type"]) for row in reservations)
            if usage + reserved + value > float(limit["cap_value"]) + 1e-12:
                raise BudgetExhausted(
                    f"{limit['scope_type']} {limit['cap_type']} budget exhausted",
                    reason="budget_exhausted",
                )

        conn.execute(
            """
            INSERT INTO budget_reservations
                (id, job_id, acquisition_units, local_model_units, paid_requests,
                 estimated_cost_usd, status, reserved_at)
            VALUES (?, ?, ?, ?, ?, ?, 'reserved', ?)
            ON CONFLICT(job_id) DO UPDATE SET
                acquisition_units = excluded.acquisition_units,
                local_model_units = excluded.local_model_units,
                paid_requests = excluded.paid_requests,
                estimated_cost_usd = excluded.estimated_cost_usd,
                status = 'reserved', reserved_at = excluded.reserved_at,
                released_at = NULL
            """,
            (new_id("reservation"), job["id"], plan["acquisition_units"], plan["local_model_units"], plan["paid_requests"], plan["usd"], now),
        )

    @staticmethod
    def _paid_enabled_tx(conn: sqlite3.Connection) -> bool:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (BudgetService.paid_enabled_key,)).fetchone()
        return bool(row and row[0] == "1")

    @staticmethod
    def _release_tx(conn: sqlite3.Connection, job_id: str, now: str) -> None:
        conn.execute(
            """
            UPDATE budget_reservations
            SET status = 'released', released_at = ?
            WHERE job_id = ? AND status = 'reserved'
            """,
            (now, job_id),
        )


class JobService:
    """Durable queue state machine with atomic claims and bounded retries."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        lease_seconds: int = 120,
        backoff_base_seconds: int = 30,
        backoff_max_seconds: int = 3600,
        budget_service: BudgetService | None = None,
        recovery_hook: RecoveryHook | None = None,
        completion_hook: CompletionHook | None = None,
        rerun_factory: RerunFactory | None = None,
    ):
        if lease_seconds < 1 or backoff_base_seconds < 1 or backoff_max_seconds < backoff_base_seconds:
            raise ValueError("invalid job timing configuration")
        self.db_path = Path(db_path)
        self.lease_seconds = lease_seconds
        self.backoff_base_seconds = backoff_base_seconds
        self.backoff_max_seconds = backoff_max_seconds
        self.budgets = budget_service or BudgetService(db_path)
        self.recovery_hook = recovery_hook
        self.completion_hook = completion_hook
        self.rerun_factory = rerun_factory

    def enqueue(
        self,
        job_type: str,
        payload: Mapping[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
        monitor_id: str | None = None,
        research_question_id: str | None = None,
        document_version_id: str | None = None,
        priority: int = 0,
        max_attempts: int = 3,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        job_type = str(job_type).strip()
        if not job_type or len(job_type) > 120:
            raise DomainValidation("job_type must be 1-120 characters")
        if idempotency_key is not None:
            idempotency_key = str(idempotency_key).strip()
            if not idempotency_key or len(idempotency_key) > 300:
                raise DomainValidation("idempotency_key must be 1-300 characters")
        if isinstance(priority, bool) or not isinstance(priority, int) or priority < -1000 or priority > 1000:
            raise DomainValidation("priority must be between -1000 and 1000")
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or not 1 <= max_attempts <= 10:
            raise DomainValidation("max_attempts must be between 1 and 10")
        encoded, decoded = _json_object(payload or {})
        _budget_plan(decoded)
        identifier = new_id("job")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if idempotency_key:
                    existing = conn.execute("SELECT id FROM jobs WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
                    if existing:
                        identifier = existing[0]
                    else:
                        self._enqueue_check_tx(conn, job_type, monitor_id, document_version_id, decoded)
                        conn.execute(
                            """
                            INSERT INTO jobs
                                (id, job_type, payload_json, idempotency_key, monitor_id,
                                 research_question_id, document_version_id, priority,
                                 max_attempts, run_id, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (identifier, job_type, encoded, idempotency_key, monitor_id, research_question_id, document_version_id, priority, max_attempts, run_id, now, now),
                        )
                else:
                    self._enqueue_check_tx(conn, job_type, monitor_id, document_version_id, decoded)
                    conn.execute(
                        """
                        INSERT INTO jobs
                            (id, job_type, payload_json, idempotency_key, monitor_id,
                             research_question_id, document_version_id, priority,
                             max_attempts, run_id, created_at, updated_at)
                        VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (identifier, job_type, encoded, monitor_id, research_question_id, document_version_id, priority, max_attempts, run_id, now, now),
                    )
        except sqlite3.IntegrityError as exc:
            if idempotency_key:
                return self.get_by_idempotency(idempotency_key)
            raise JobConflict("job parent reference or idempotency constraint failed") from exc
        finally:
            conn.close()
        return self.get(identifier)

    def _enqueue_check_tx(
        self,
        conn: sqlite3.Connection,
        job_type: str,
        monitor_id: str | None,
        document_version_id: str | None,
        payload: Mapping[str, Any],
    ) -> None:
        """Enforce canonical ownership and active-work coalescing before insert.

        Runs inside the caller's write transaction. A monitor_check job must
        carry exactly one canonical ``monitor_id`` and a
        ``document_version_process`` job must carry exactly one canonical
        ``document_version_id`` (whose FK guarantees the version exists).
        Active obligations reject duplicates regardless of the idempotency key
        so no enqueue path (API, rerun, backfill) can bypass coalescing.
        """
        canonical = _resolve_monitor_check_monitor_id(job_type, monitor_id, payload)
        if canonical:
            active_id = _active_monitor_check_id_tx(conn, canonical)
            if active_id is not None:
                raise JobConflict(
                    f"monitor {canonical} already has an active monitor_check obligation ({active_id})"
                )
        canonical_dv = _resolve_document_version_process_version_id(job_type, document_version_id, payload)
        if canonical_dv:
            active_id = _active_document_version_process_id_tx(conn, canonical_dv)
            if active_id is not None:
                raise JobConflict(
                    f"document version {canonical_dv} already has an active processing obligation ({active_id})"
                )

    def get_by_idempotency(self, idempotency_key: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT id FROM jobs WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
            if row is None:
                raise JobNotFound("job not found")
            return self._get_tx(conn, row[0])
        finally:
            conn.close()

    def get(self, job_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return self._get_tx(conn, job_id)
        finally:
            conn.close()

    @staticmethod
    def _get_tx(conn: sqlite3.Connection, job_id: str) -> dict[str, Any]:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFound("job not found")
        attempts = conn.execute("SELECT * FROM job_attempts WHERE job_id = ? ORDER BY attempt_no", (job_id,)).fetchall()
        reservation = conn.execute("SELECT * FROM budget_reservations WHERE job_id = ?", (job_id,)).fetchone()
        return _job_dict(row, attempts, reservation)

    def list(self, *, status: str | None = None, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        if status is not None and status not in JOB_STATUSES:
            raise DomainValidation("invalid job status")
        if page < 1 or page_size < 1 or page_size > 200:
            raise DomainValidation("invalid job page")
        where = "WHERE status = ?" if status else ""
        params: list[Any] = [status] if status else []
        conn = storage.connect(self.db_path)
        try:
            total = conn.execute(f"SELECT COUNT(*) FROM jobs {where}", params).fetchone()[0]
            params.extend([page_size, (page - 1) * page_size])
            rows = conn.execute(
                f"SELECT * FROM jobs {where} ORDER BY priority DESC, created_at, id LIMIT ? OFFSET ?",
                params,
            ).fetchall()
            return {"items": [_job_dict(row) for row in rows], "page": page, "page_size": page_size, "total": total}
        finally:
            conn.close()

    def claim(self, job_id: str, worker_id: str, *, now: str | datetime | None = None) -> dict[str, Any] | None:
        worker_id = self._worker_id(worker_id)
        timestamp = _timestamp(now)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._recover_expired_tx(conn, timestamp)
                row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
                if row is None:
                    raise JobNotFound("job not found")
                if row["status"] != "queued" or (row["next_attempt_at"] and row["next_attempt_at"] > timestamp):
                    return None
                try:
                    self._claim_tx(conn, row, worker_id, timestamp)
                except BudgetExhausted as exc:
                    self._mark_budget_failed_tx(conn, row, timestamp, exc.reason)
                    return None
                return self._get_tx(conn, job_id)
        finally:
            conn.close()

    def claim_next(self, worker_id: str, *, now: str | datetime | None = None) -> dict[str, Any] | None:
        worker_id = self._worker_id(worker_id)
        timestamp = _timestamp(now)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._recover_expired_tx(conn, timestamp)
                while True:
                    row = conn.execute(
                        """
                        SELECT * FROM jobs
                        WHERE status = 'queued' AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
                        ORDER BY priority DESC, created_at, id
                        LIMIT 1
                        """,
                        (timestamp,),
                    ).fetchone()
                    if row is None:
                        return None
                    try:
                        self._claim_tx(conn, row, worker_id, timestamp)
                    except BudgetExhausted as exc:
                        self._mark_budget_failed_tx(conn, row, timestamp, exc.reason)
                        continue
                    return self._get_tx(conn, row["id"])
        finally:
            conn.close()

    def recover_expired(self, *, now: str | datetime | None = None) -> int:
        timestamp = _timestamp(now)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                return self._recover_expired_tx(conn, timestamp)
        finally:
            conn.close()

    def complete(
        self,
        job_id: str,
        worker_id: str,
        status: str,
        *,
        error_code: str | None = None,
        error_detail: str | None = None,
        retryable: bool = True,
        now: str | datetime | None = None,
        outcome: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if status not in {"succeeded", "partial", "failed", "cancelled"}:
            raise DomainValidation("invalid completion status")
        if outcome is not None and not isinstance(outcome, Mapping):
            raise DomainValidation("completion outcome must be an object")
        timestamp = _timestamp(now)
        worker_id = self._worker_id(worker_id)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
                if row is None:
                    raise JobNotFound("job not found")
                if row["status"] != "running" or row["lease_owner"] != worker_id:
                    raise JobConflict("job is not leased by this worker")
                attempt = conn.execute(
                    "SELECT * FROM job_attempts WHERE job_id = ? AND status = 'running' ORDER BY attempt_no DESC LIMIT 1",
                    (job_id,),
                ).fetchone()
                if attempt is None:
                    raise JobConflict("job has no running attempt")
                final_status = "cancelled" if row["cancel_requested_at"] else status
                bounded_code = (error_code or ("cancelled" if final_status == "cancelled" else None))
                bounded_detail = (error_detail or "")[:1000] if error_detail else None
                conn.execute(
                    """
                    UPDATE job_attempts
                    SET status = ?, finished_at = ?, error_code = ?, error_detail = ?
                    WHERE id = ?
                    """,
                    (final_status if final_status in ATTEMPT_STATUSES else "failed", timestamp, bounded_code, bounded_detail, attempt["id"]),
                )
                self.budgets._release_tx(conn, job_id, timestamp)
                encoded_result = None
                if outcome is not None and final_status in {"succeeded", "partial"}:
                    try:
                        encoded_result = json.dumps(dict(outcome), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                    except (TypeError, ValueError):
                        encoded_result = None
                retrying = final_status == "failed" and retryable and row["attempts"] < row["max_attempts"]
                if retrying:
                    next_at = _plus_seconds(timestamp, self._backoff_seconds(row["attempts"]))
                    conn.execute(
                        """
                        UPDATE jobs
                        SET status = 'queued', lease_owner = NULL, lease_expires_at = NULL,
                            cancel_requested_at = NULL, next_attempt_at = ?,
                            failure_cause = ?, result_json = NULL, updated_at = ?
                        WHERE id = ?
                        """,
                        (next_at, bounded_code or "failed", timestamp, job_id),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE jobs
                        SET status = ?, lease_owner = NULL, lease_expires_at = NULL,
                            cancel_requested_at = NULL, next_attempt_at = NULL,
                            failure_cause = ?, result_json = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (final_status, bounded_code, encoded_result, timestamp, job_id),
                    )
                if self.completion_hook is not None:
                    self.completion_hook(
                        conn,
                        row,
                        "queued" if retrying else final_status,
                        {
                            "trigger": "complete",
                            "error_code": bounded_code,
                            "error_detail": bounded_detail,
                            "outcome": dict(outcome) if outcome is not None else None,
                        },
                    )
                self._maybe_finish_run_tx(conn, row["run_id"], timestamp)
                return self._get_tx(conn, job_id)
        finally:
            conn.close()

    def cancel(self, job_id: str, *, reason: str = "cancelled_by_user", now: str | datetime | None = None) -> dict[str, Any]:
        timestamp = _timestamp(now)
        reason = str(reason).strip()[:500] or "cancelled_by_user"
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
                if row is None:
                    raise JobNotFound("job not found")
                if row["status"] in TERMINAL_JOB_STATUSES:
                    return self._get_tx(conn, job_id)
                if row["status"] == "running":
                    conn.execute(
                        "UPDATE jobs SET cancel_requested_at = ?, failure_cause = ?, updated_at = ? WHERE id = ?",
                        (timestamp, reason, timestamp, job_id),
                    )
                else:
                    conn.execute(
                        "UPDATE jobs SET status = 'cancelled', failure_cause = ?, next_attempt_at = NULL, updated_at = ? WHERE id = ?",
                        (reason, timestamp, job_id),
                    )
                    self.budgets._release_tx(conn, job_id, timestamp)
                    if self.completion_hook is not None:
                        self.completion_hook(
                            conn,
                            row,
                            "cancelled",
                            {"trigger": "cancel", "error_code": reason},
                        )
                    self._maybe_finish_run_tx(conn, row["run_id"], timestamp)
                return self._get_tx(conn, job_id)
        finally:
            conn.close()

    def rerun(self, job_id: str) -> dict[str, Any]:
        old = self.get(job_id)
        if old["status"] not in TERMINAL_JOB_STATUSES:
            raise JobConflict("only terminal jobs may be rerun")
        if old["job_type"] == MONITOR_CHECK_JOB_TYPE:
            self._guard_monitor_check_rerun(old)
        if self.rerun_factory is not None:
            try:
                rebuilt = self.rerun_factory(self.db_path, old)
            except sqlite3.IntegrityError as exc:
                raise JobConflict("rerun raced with another attempt creation for the same job") from exc
            if rebuilt is not None:
                return rebuilt
        return self.enqueue(
            old["job_type"],
            old["payload"],
            idempotency_key=f"rerun:{job_id}:{new_id('request')}",
            monitor_id=old["monitor_id"],
            research_question_id=old["research_question_id"],
            document_version_id=old.get("document_version_id"),
            priority=old["priority"],
            max_attempts=old["max_attempts"],
        )

    def _guard_monitor_check_rerun(self, old: Mapping[str, Any]) -> None:
        """Reject a monitor_check rerun while the Monitor already has an active
        monitor_check obligation.

        Rerunning would otherwise clone a fresh job into the queue under a new
        ``rerun:`` idempotency key, bypassing the scheduler's active-work check
        and producing two simultaneous obligations. The Monitor's adaptive
        ``next_check_at`` is deliberately left untouched so the scheduler
        resumes cadence from the active job's eventual ``record_activity``
        outcome rather than the rerun request.
        """
        canonical = str(old.get("monitor_id") or "").strip()
        payload = old.get("payload") or {}
        if isinstance(payload, Mapping) and payload.get("monitor_id") is not None and str(payload["monitor_id"]).strip() != canonical:
            raise DomainValidation("historical monitor_check has conflicting monitor_id ownership")
        if not canonical:
            raise DomainValidation("historical monitor_check has no canonical monitor_id")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                active_id = _active_monitor_check_id_tx(conn, canonical)
        finally:
            conn.close()
        if active_id is not None:
            raise JobConflict(
                f"rerun refused: monitor {canonical} already has an active monitor_check obligation ({active_id})"
            )

    def create_run(self, trigger_type: str, *, summary: Mapping[str, Any] | None = None, now: str | datetime | None = None) -> dict[str, Any]:
        if trigger_type not in {"cron", "manual", "test"}:
            raise DomainValidation("invalid run trigger")
        timestamp = _timestamp(now)
        identifier = new_id("run")
        encoded = json.dumps(dict(summary or {}), sort_keys=True, separators=(",", ":"))
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    "INSERT INTO runs(id, trigger_type, status, started_at, summary_json) VALUES (?, ?, 'running', ?, ?)",
                    (identifier, trigger_type, timestamp, encoded),
                )
        finally:
            conn.close()
        return self.get_run(identifier)

    def get_run(self, run_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise DomainNotFound("run not found")
            result = dict(row)
            result["summary"] = _decode(result.pop("summary_json"), {})
            result["jobs"] = [dict(job) for job in conn.execute("SELECT id, status, job_type, failure_cause FROM jobs WHERE run_id = ? ORDER BY created_at, id", (run_id,))]
            return result
        finally:
            conn.close()

    def list_runs(self, *, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        if page < 1 or page_size < 1 or page_size > 200:
            raise DomainValidation("invalid run page")
        conn = storage.connect(self.db_path)
        try:
            total = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY started_at DESC, id DESC LIMIT ? OFFSET ?",
                (page_size, (page - 1) * page_size),
            ).fetchall()
            items = []
            for row in rows:
                result = dict(row)
                result["summary"] = _decode(result.pop("summary_json"), {})
                items.append(result)
            return {"items": items, "page": page, "page_size": page_size, "total": total}
        finally:
            conn.close()

    def finish_run(self, run_id: str, *, now: str | datetime | None = None) -> dict[str, Any]:
        timestamp = _timestamp(now)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
                if run is None:
                    raise DomainNotFound("run not found")
                jobs = conn.execute("SELECT status FROM jobs WHERE run_id = ?", (run_id,)).fetchall()
                if any(job[0] in {"queued", "running"} for job in jobs):
                    raise JobConflict("run still has active jobs")
                if not jobs or all(job[0] == "succeeded" for job in jobs):
                    status = "success"
                elif all(job[0] == "failed" for job in jobs):
                    status = "failed"
                else:
                    status = "partial"
                conn.execute("UPDATE runs SET status = ?, completed_at = ? WHERE id = ?", (status, timestamp, run_id))
        finally:
            conn.close()
        return self.get_run(run_id)

    @staticmethod
    def _maybe_finish_run_tx(conn: sqlite3.Connection, run_id: str | None, now: str) -> None:
        if not run_id:
            return
        run = conn.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
        if run is None or run[0] != "running":
            return
        statuses = [row[0] for row in conn.execute("SELECT status FROM jobs WHERE run_id = ?", (run_id,)).fetchall()]
        if not statuses or any(status in {"queued", "running"} for status in statuses):
            return
        if all(status == "succeeded" for status in statuses):
            status = "success"
        elif all(status == "failed" for status in statuses):
            status = "failed"
        else:
            status = "partial"
        conn.execute("UPDATE runs SET status = ?, completed_at = ? WHERE id = ?", (status, now, run_id))

    def _claim_tx(self, conn: sqlite3.Connection, row: sqlite3.Row, worker_id: str, now: str) -> None:
        self.budgets._reserve_tx(conn, row, now)
        attempt_no = row["attempts"] + 1
        expires = _plus_seconds(now, self.lease_seconds)
        conn.execute(
            """
            UPDATE jobs
            SET status = 'running', lease_owner = ?, lease_expires_at = ?,
                attempts = ?, updated_at = ?
            WHERE id = ? AND status = 'queued'
            """,
            (worker_id, expires, attempt_no, now, row["id"]),
        )
        conn.execute(
            """
            INSERT INTO job_attempts(id, job_id, attempt_no, started_at, status)
            VALUES (?, ?, ?, ?, 'running')
            """,
            (new_id("attempt"), row["id"], attempt_no, now),
        )

    def _mark_budget_failed_tx(self, conn: sqlite3.Connection, row: sqlite3.Row, now: str, reason: str) -> None:
        conn.execute(
            "UPDATE jobs SET status = 'failed', failure_cause = ?, updated_at = ? WHERE id = ? AND status = 'queued'",
            (reason, now, row["id"]),
        )
        if self.completion_hook is not None:
            self.completion_hook(conn, row, "failed", {"trigger": "budget", "error_code": reason})
        self._maybe_finish_run_tx(conn, row["run_id"], now)

    def _recover_expired_tx(self, conn: sqlite3.Connection, now: str) -> int:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?",
            (now,),
        ).fetchall()
        for row in rows:
            attempt = conn.execute(
                "SELECT id FROM job_attempts WHERE job_id = ? AND status = 'running' ORDER BY attempt_no DESC LIMIT 1",
                (row["id"],),
            ).fetchone()
            if attempt:
                conn.execute(
                    "UPDATE job_attempts SET status = 'failed', finished_at = ?, error_code = 'lease_expired', error_detail = 'worker lease expired' WHERE id = ?",
                    (now, attempt[0]),
                )
            self.budgets._release_tx(conn, row["id"], now)
            if row["cancel_requested_at"]:
                status, next_attempt, failure = "cancelled", None, row["failure_cause"] or "cancelled_by_user"
            elif row["attempts"] >= row["max_attempts"]:
                status, next_attempt, failure = "failed", None, "lease_expired"
            else:
                status, next_attempt, failure = "queued", _plus_seconds(now, self._backoff_seconds(row["attempts"])), "lease_expired"
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, lease_owner = NULL, lease_expires_at = NULL,
                    cancel_requested_at = NULL, next_attempt_at = ?,
                    failure_cause = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, next_attempt, failure, now, row["id"]),
            )
            if self.recovery_hook is not None:
                self.recovery_hook(conn, row, status)
            self._maybe_finish_run_tx(conn, row["run_id"], now)
        return len(rows)

    def _backoff_seconds(self, attempt_no: int) -> int:
        return min(self.backoff_max_seconds, self.backoff_base_seconds * (2 ** max(0, attempt_no - 1)))

    @staticmethod
    def _worker_id(worker_id: str) -> str:
        value = str(worker_id).strip()
        if not value or len(value) > 200:
            raise DomainValidation("worker_id must be 1-200 characters")
        return value


class SchedulerService:
    """Select due monitors and enqueue at most one job per due schedule.

    The tick only advances scheduling state (``next_check_at`` and
    ``updated_at``). It never writes ``last_result`` or ``last_run_at``:
    those fields describe the most recent ACTUAL Monitor execution, and
    queue state is not an execution result.
    """

    job_type = MONITOR_CHECK_JOB_TYPE

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def tick(self, *, now: str | datetime | None = None, limit: int = 100) -> dict[str, Any]:
        timestamp = _timestamp(now)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise DomainValidation("scheduler limit must be between 1 and 500")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                due = conn.execute(
                    """
                    SELECT m.*, p.priority AS policy_priority,
                           p.base_cadence_seconds, p.min_cadence_seconds, p.max_cadence_seconds,
                           p.query_budget, p.local_model_budget, p.paid_budget_usd
                    FROM monitors AS m
                    JOIN monitoring_policies AS p ON p.id = m.policy_id
                    WHERE m.enabled = 1 AND m.next_check_at IS NOT NULL AND m.next_check_at <= ?
                    ORDER BY CASE p.priority WHEN 'urgent' THEN 3 WHEN 'high' THEN 2 WHEN 'normal' THEN 1 ELSE 0 END DESC,
                             m.next_check_at, m.id
                    LIMIT ?
                    """,
                    (timestamp, limit),
                ).fetchall()
                target_tables = {
                    "topic": "topics",
                    "subject": "subjects",
                    "story": "stories",
                    "source": "sources",
                    "research_question": "research_questions",
                }
                eligible = []
                for monitor in due:
                    table = target_tables[monitor["target_type"]]
                    target = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (monitor["target_id"],)).fetchone()
                    unavailable = target is None
                    if target is not None:
                        columns = set(target.keys())
                        unavailable = ("deleted_at" in columns and target["deleted_at"] is not None) or (
                            "enabled" in columns and target["enabled"] == 0
                        ) or ("status" in columns and target["status"] == "abandoned")
                    if unavailable:
                        conn.execute(
                            "UPDATE monitors SET enabled = 0, next_check_at = NULL, updated_at = ? WHERE id = ?",
                            (timestamp, monitor["id"]),
                        )
                        continue
                    eligible.append(monitor)
                due = eligible
                conn.execute(
                    """
                    INSERT INTO scheduler_state(id, last_tick_at, updated_at) VALUES (1, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET last_tick_at = excluded.last_tick_at, updated_at = excluded.updated_at
                    """,
                    (timestamp, timestamp),
                )
                if not due:
                    return {
                        "run_id": None,
                        "job_ids": [],
                        "due_count": 0,
                        "eligible_count": 0,
                        "enqueued": 0,
                        "coalesced_skipped_active": 0,
                        "auto_disabled": 0,
                        "scheduled_at": timestamp,
                    }
                job_ids: list[str] = []
                coalesced = 0
                for monitor in due:
                    active = conn.execute(
                        """
                        SELECT 1 FROM jobs
                        WHERE monitor_id = ?
                          AND job_type = ?
                          AND status IN ('queued', 'running')
                        LIMIT 1
                        """,
                        (monitor["id"], self.job_type),
                    ).fetchone()
                    if active is not None:
                        coalesced += 1
                        continue
                    schedule_key = monitor["next_check_at"] or timestamp
                    idempotency_key = f"monitor:{monitor['id']}:{schedule_key}"
                    existing = conn.execute(
                        "SELECT id FROM jobs WHERE idempotency_key = ?", (idempotency_key,)
                    ).fetchone()
                    if existing:
                        job_ids.append(existing[0])
                    else:
                        job_id = new_id("job")
                        payload = json.dumps(
                            {
                                "monitor_id": monitor["id"],
                                "target_type": monitor["target_type"],
                                "target_id": monitor["target_id"],
                                "budget": {
                                    "acquisition_units": max(0, int(monitor["query_budget"] or 0)),
                                    "local_model_units": max(0, int(monitor["local_model_budget"] or 0)),
                                    "usd": max(0.0, float(monitor["paid_budget_usd"] or 0.0)),
                                },
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        priority = {"urgent": 30, "high": 20, "normal": 10, "low": 0}.get(
                            monitor["policy_priority"], 0
                        )
                        conn.execute(
                            """
                            INSERT INTO jobs
                                (id, job_type, status, payload_json, idempotency_key,
                                 monitor_id, priority, max_attempts, created_at, updated_at)
                            VALUES (?, ?, 'queued', ?, ?, ?, ?, 3, ?, ?)
                            """,
                            (job_id, self.job_type, payload, idempotency_key, monitor["id"], priority, timestamp, timestamp),
                        )
                        job_ids.append(job_id)
                    base = max(1, int(monitor["base_cadence_seconds"] or 1))
                    minimum = max(1, int(monitor["min_cadence_seconds"] or 1))
                    maximum = max(minimum, int(monitor["max_cadence_seconds"] or minimum))
                    cadence = max(minimum, min(maximum, base))
                    next_check = _plus_seconds(timestamp, cadence)
                    conn.execute(
                        "UPDATE monitors SET next_check_at = ?, updated_at = ? WHERE id = ?",
                        (next_check, timestamp, monitor["id"]),
                    )
                run_id: str | None = None
                if job_ids:
                    run_id = new_id("run")
                    conn.execute(
                        "INSERT INTO runs(id, trigger_type, status, started_at, summary_json) VALUES (?, 'cron', 'running', ?, ?)",
                        (run_id, timestamp, json.dumps(
                            {"scheduled_count": len(job_ids), "coalesced": coalesced},
                            sort_keys=True,
                        )),
                    )
                    for job_id in job_ids:
                        conn.execute(
                            "UPDATE jobs SET run_id = ? WHERE id = ?",
                            (run_id, job_id),
                        )
                return {
                    "run_id": run_id,
                    "job_ids": job_ids,
                    "due_count": len(due),
                    "eligible_count": len(due),
                    "enqueued": len(job_ids),
                    "coalesced_skipped_active": coalesced,
                    "auto_disabled": 0,
                    "scheduled_at": timestamp,
                }
        finally:
            conn.close()


__all__ = [
    "BudgetExhausted",
    "BudgetService",
    "CompletionHook",
    "AUTOMATIC_STORY_STAGE_JOB_TYPE",
    "AUTOMATIC_REPORT_STAGE_JOB_TYPE",
    "DOCUMENT_VERSION_PROCESS_JOB_TYPE",
    "JobConflict",
    "JobError",
    "JobNotFound",
    "JobService",
    "MONITOR_CHECK_JOB_TYPE",
    "RecoveryHook",
    "RerunFactory",
    "RESEARCH_QUESTION_JOB_TYPE",
    "SchedulerService",
    "compose_completion_hooks",
    "compose_rerun_factories",
]
