"""Explainable coverage analysis over existing observation facts."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import storage
from .domain import DomainConflict, DomainNotFound, DomainValidation, new_id, utc_now


COVERAGE_STATES = frozenset(
    {
        "observed",
        "not_found",
        "not_observed",
        "not_searched",
        "failed_acquisition",
        "out_of_scope",
        "stale",
    }
)
COMPLETE_STATES = frozenset({"observed", "not_found", "not_observed"})
TARGET_TYPES = frozenset({"watch", "research_question", "story", "ask", "source"})
COVERAGE_REFRESH_JOB_TYPE = "coverage_refresh"


def _json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise DomainValidation("coverage value must be JSON serializable") from exc


def _decode(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


class CoverageService:
    """Persist a bounded expected denominator and derive coverage states."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def handlers(self) -> dict[str, Any]:
        return {COVERAGE_REFRESH_JOB_TYPE: self.handle}

    def handle(self, job: Mapping[str, Any]) -> dict[str, Any]:
        run_id = str((job.get("payload") or {}).get("run_id") or "").strip()
        if not run_id:
            raise DomainValidation("coverage refresh Job is missing run_id")
        return {"run_id": run_id, "blind_spots": self.generate_blind_spots(run_id)}

    def create_run(
        self,
        target_type: str,
        target_id: str,
        window_start: str,
        window_end: str,
        *,
        expected_channels: Iterable[Mapping[str, Any]] = (),
        included_sources: Iterable[Mapping[str, Any] | str] = (),
        excluded_sources: Iterable[Mapping[str, Any] | str] = (),
        target_version: str = "",
        policy_version: str = "coverage_v1",
        causing_job_id: str | None = None,
    ) -> dict[str, Any]:
        if target_type not in TARGET_TYPES or not str(target_id).strip():
            raise DomainValidation("coverage target_type and target_id are required")
        if not str(window_start).strip() or not str(window_end).strip():
            raise DomainValidation("coverage observation window is required")
        channels = [dict(item) for item in expected_channels]
        if len(channels) > 500:
            raise DomainValidation("coverage expected denominator is bounded at 500 items")
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in channels:
            key = str(item.get("key") or "").strip()
            channel_type = str(item.get("channel_type") or "").strip()
            if not key or not channel_type or key in seen:
                raise DomainValidation("coverage channel keys must be unique and non-empty")
            seen.add(key)
            source_id = item.get("source_id")
            normalized.append(
                {
                    "key": key,
                    "channel_type": channel_type,
                    "source_id": str(source_id).strip() if source_id else None,
                    "source_class": str(item.get("source_class") or "").strip(),
                    "required": bool(item.get("required", True)),
                }
            )
        identifier = new_id("coverage")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    """
                    INSERT INTO coverage_runs
                        (id, target_type, target_id, target_version, window_start, window_end,
                         policy_version, included_sources_json, excluded_sources_json,
                         status, causing_job_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'running', ?, ?)
                    """,
                    (
                        identifier,
                        target_type,
                        str(target_id).strip(),
                        str(target_version or ""),
                        window_start,
                        window_end,
                        str(policy_version or "coverage_v1"),
                        _json(list(included_sources)),
                        _json(list(excluded_sources)),
                        causing_job_id,
                        now,
                    ),
                )
                for item in normalized:
                    conn.execute(
                        """
                        INSERT INTO coverage_items
                            (id, run_id, item_key, channel_type, source_id, source_class,
                             required, state, observation_refs_json, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'not_searched', '[]', ?, ?)
                        """,
                        (
                            new_id("coverage-item"),
                            identifier,
                            item["key"],
                            item["channel_type"],
                            item["source_id"],
                            item["source_class"],
                            int(item["required"]),
                            now,
                            now,
                        ),
                    )
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("coverage run could not be created") from exc
        finally:
            conn.close()
        return self.get_run(identifier)

    def record_item(
        self,
        run_id: str,
        item_key: str,
        state: str,
        *,
        observation_refs: Iterable[str] = (),
        reason: str = "",
        observed_at: str | None = None,
    ) -> dict[str, Any]:
        if state not in COVERAGE_STATES:
            raise DomainValidation("invalid coverage state")
        references = [str(value).strip() for value in observation_refs if str(value).strip()]
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                run = conn.execute("SELECT status FROM coverage_runs WHERE id = ?", (run_id,)).fetchone()
                if run is None:
                    raise DomainNotFound("coverage run not found")
                if run["status"] in {"completed", "failed"}:
                    raise DomainConflict("completed coverage runs are immutable")
                item = conn.execute(
                    "SELECT * FROM coverage_items WHERE run_id = ? AND item_key = ?",
                    (run_id, item_key),
                ).fetchone()
                if item is None:
                    raise DomainNotFound("coverage item not found")
                observation_tables = {
                    "acquisition_event": "acquisition_events",
                    "monitor_activity": "monitor_activity",
                    "story_evolution_event": "story_evolution_events",
                    "research_question_attempt": "research_question_attempts",
                    "document_version": "document_versions",
                    "evidence_span": "evidence_spans",
                }
                for reference in references:
                    prefix, separator, identifier = reference.partition(":")
                    if not separator or prefix not in observation_tables or not identifier:
                        raise DomainValidation("observation_refs must use a supported canonical observation prefix")
                    if conn.execute(f"SELECT 1 FROM {observation_tables[prefix]} WHERE id = ?", (identifier,)).fetchone() is None:
                        raise DomainNotFound(f"observation fact {reference} not found")
                now = utc_now()
                conn.execute(
                    """
                    UPDATE coverage_items
                    SET state = ?, observation_refs_json = ?, reason = ?, observed_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (state, _json(references), str(reason or "")[:4000], observed_at, now, item["id"]),
                )
        finally:
            conn.close()
        return self.get_run(run_id)

    @staticmethod
    def _summary_rows(rows: list[sqlite3.Row]) -> dict[str, Any]:
        state_counts: dict[str, int] = {}
        for row in rows:
            state_counts[row["state"]] = state_counts.get(row["state"], 0) + 1
        required_rows = [row for row in rows if row["required"] and row["state"] != "out_of_scope"]
        complete_rows = [row for row in required_rows if row["state"] in COMPLETE_STATES]
        required_count = len(required_rows)
        complete_count = len(complete_rows)
        completeness = complete_count / required_count if required_count else 1.0
        blocking = sorted(
            {row["state"] for row in required_rows if row["state"] not in COMPLETE_STATES}
        )
        qualified_negative = bool(
            required_rows
            and not blocking
            and any(row["state"] in {"not_found", "not_observed"} for row in required_rows)
        )
        return {
            "expected_count": len(rows),
            "required_count": required_count,
            "observed_count": state_counts.get("observed", 0),
            "complete_count": complete_count,
            "completeness": round(completeness, 6),
            "qualified_negative": qualified_negative,
            "state_counts": state_counts,
            "blocking_states": blocking,
            "explanation": {
                "denominator": "required coverage items excluding explicit out_of_scope items",
                "blocking_states": blocking,
                "negative_evidence": "qualified" if qualified_negative else "not qualified",
            },
        }

    def complete(self, run_id: str, *, status: str | None = None) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                run = conn.execute("SELECT * FROM coverage_runs WHERE id = ?", (run_id,)).fetchone()
                if run is None:
                    raise DomainNotFound("coverage run not found")
                rows = list(conn.execute("SELECT * FROM coverage_items WHERE run_id = ? ORDER BY item_key, id", (run_id,)))
                summary = self._summary_rows(rows)
                final_status = status or ("completed" if not summary["blocking_states"] else "partial")
                if final_status not in {"completed", "partial", "failed"}:
                    raise DomainValidation("invalid coverage completion status")
                now = utc_now()
                conn.execute(
                    "UPDATE coverage_runs SET status = ?, completed_at = ? WHERE id = ?",
                    (final_status, now, run_id),
                )
                conn.execute(
                    """
                    INSERT INTO coverage_summaries
                        (run_id, expected_count, required_count, observed_count, complete_count,
                         completeness, qualified_negative, state_counts_json, explanation_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        expected_count = excluded.expected_count,
                        required_count = excluded.required_count,
                        observed_count = excluded.observed_count,
                        complete_count = excluded.complete_count,
                        completeness = excluded.completeness,
                        qualified_negative = excluded.qualified_negative,
                        state_counts_json = excluded.state_counts_json,
                        explanation_json = excluded.explanation_json,
                        created_at = excluded.created_at
                    """,
                    (
                        run_id,
                        summary["expected_count"],
                        summary["required_count"],
                        summary["observed_count"],
                        summary["complete_count"],
                        summary["completeness"],
                        int(summary["qualified_negative"]),
                        _json(summary["state_counts"]),
                        _json(summary["explanation"]),
                        now,
                    ),
                )
        finally:
            conn.close()
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            run = conn.execute("SELECT * FROM coverage_runs WHERE id = ?", (run_id,)).fetchone()
            if run is None:
                raise DomainNotFound("coverage run not found")
            result = dict(run)
            result["included_sources"] = _decode(result.pop("included_sources_json"), [])
            result["excluded_sources"] = _decode(result.pop("excluded_sources_json"), [])
            items = []
            for row in conn.execute("SELECT * FROM coverage_items WHERE run_id = ? ORDER BY item_key, id", (run_id,)):
                item = dict(row)
                item["required"] = bool(item["required"])
                item["observation_refs"] = _decode(item.pop("observation_refs_json"), [])
                items.append(item)
            result["items"] = items
            summary_row = conn.execute("SELECT * FROM coverage_summaries WHERE run_id = ?", (run_id,)).fetchone()
            if summary_row is None:
                item_rows = conn.execute("SELECT * FROM coverage_items WHERE run_id = ? ORDER BY item_key, id", (run_id,)).fetchall()
                summary = self._summary_rows(list(item_rows))
            else:
                summary = {
                    "expected_count": summary_row["expected_count"],
                    "required_count": summary_row["required_count"],
                    "observed_count": summary_row["observed_count"],
                    "complete_count": summary_row["complete_count"],
                    "completeness": summary_row["completeness"],
                    "qualified_negative": bool(summary_row["qualified_negative"]),
                    "state_counts": _decode(summary_row["state_counts_json"], {}),
                    "explanation": _decode(summary_row["explanation_json"], {}),
                }
            result["summary"] = summary
            return result
        finally:
            conn.close()

    def list_runs(self, *, target_type: str | None = None, target_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if limit < 1 or limit > 200:
            raise DomainValidation("coverage limit must be between 1 and 200")
        clauses = ["1 = 1"]
        params: list[Any] = []
        if target_type:
            clauses.append("target_type = ?")
            params.append(target_type)
        if target_id:
            clauses.append("target_id = ?")
            params.append(target_id)
        conn = storage.connect(self.db_path)
        try:
            ids = conn.execute(
                f"SELECT id FROM coverage_runs WHERE {' AND '.join(clauses)} ORDER BY created_at DESC, id DESC LIMIT ?",
                [*params, limit],
            ).fetchall()
        finally:
            conn.close()
        return [self.get_run(row[0]) for row in ids]

    def generate_blind_spots(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                for item in run["items"]:
                    if not item["required"] or not item.get("source_class") or item["state"] in COMPLETE_STATES:
                        continue
                    priority = 0.9 if item["state"] == "failed_acquisition" else 0.7
                    reason = item.get("reason") or f"Coverage state is {item['state']} for the expected {item['source_class']} channel."
                    conn.execute(
                        "INSERT OR IGNORE INTO blind_spot_suggestions(id, target_type, target_id, source_class, coverage_run_id, priority, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (new_id("blind-spot"), run["target_type"], run["target_id"], item["source_class"], run_id, priority, reason[:4000], now),
                    )
            return self.list_blind_spots(target_type=run["target_type"], target_id=run["target_id"])
        finally:
            conn.close()

    def list_blind_spots(self, *, target_type: str | None = None, target_id: str | None = None, status: str | None = None, limit: int = 100) -> dict[str, Any]:
        if status is not None and status not in {"pending", "approved", "dismissed", "used"}:
            raise DomainValidation("invalid blind spot status")
        if limit < 1 or limit > 500:
            raise DomainValidation("blind spot limit must be between 1 and 500")
        clauses = ["1 = 1"]
        params: list[Any] = []
        for column, value in (("target_type", target_type), ("target_id", target_id), ("status", status)):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        conn = storage.connect(self.db_path)
        try:
            rows = conn.execute(f"SELECT * FROM blind_spot_suggestions WHERE {' AND '.join(clauses)} ORDER BY priority DESC, created_at DESC, id DESC LIMIT ?", [*params, limit]).fetchall()
            return {"items": [dict(row) for row in rows], "count": len(rows)}
        finally:
            conn.close()

    def review_blind_spot(self, identifier: str, status: str, *, actor: str | None = None) -> dict[str, Any]:
        if status not in {"approved", "dismissed", "used"}:
            raise DomainValidation("invalid blind spot review status")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT id FROM blind_spot_suggestions WHERE id = ?", (identifier,)).fetchone()
                if row is None:
                    raise DomainNotFound("blind spot suggestion not found")
                conn.execute("UPDATE blind_spot_suggestions SET status = ?, reviewed_at = ?, reviewed_by = ? WHERE id = ?", (status, utc_now(), actor, identifier))
                return dict(conn.execute("SELECT * FROM blind_spot_suggestions WHERE id = ?", (identifier,)).fetchone())
        finally:
            conn.close()


__all__ = ["COMPLETE_STATES", "COVERAGE_REFRESH_JOB_TYPE", "COVERAGE_STATES", "CoverageService"]
