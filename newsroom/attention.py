"""Read-time Attention ranking with append-only human decisions."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from . import storage
from .domain import DomainConflict, DomainNotFound, DomainValidation, new_id, utc_now
from .temporal import TemporalReadService, normalize_as_of


ATTENTION_ACTIONS = frozenset({"seen", "snoozed", "not_useful"})
REVIEW_CURSOR_SETTING_PREFIX = "review_boundary:"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class AttentionService:
    """Rank current operational causes; persist only explicit human actions."""

    def __init__(self, db_path: str | Path, *, clock: Callable[[], str] | None = None):
        self.db_path = Path(db_path)
        self._clock = clock or utc_now

    @staticmethod
    def _basis_fingerprint(fields: dict[str, Any]) -> str:
        return hashlib.sha256(_json(fields).encode("utf-8")).hexdigest()

    @staticmethod
    def _candidate_id(candidate: dict[str, Any]) -> str:
        return "attention:{}:{}:{}:{}".format(
            candidate["object_type"],
            candidate["object_id"],
            candidate["reason_code"],
            candidate["basis_fingerprint"],
        )

    def _candidates(self) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        conn = storage.connect(self.db_path)
        try:
            for row in conn.execute(
                "SELECT id, story_id, event_type, title, body, importance_score, cause_json, created_at FROM alerts WHERE status = 'unread' ORDER BY importance_score DESC, created_at DESC, id DESC LIMIT 100"
            ):
                reason_code = {
                    "contradiction": "new_contradiction",
                    "correction": "correction",
                    "new_primary_evidence": "new_primary_source",
                    "material_update": "material_change",
                }.get(row["event_type"], "alert_followup")
                try:
                    cause = json.loads(row["cause_json"] or "{}") if row["cause_json"] else {}
                except (TypeError, ValueError):
                    cause = {}
                candidate = {
                    "object_type": "alert",
                    "object_id": row["id"],
                    "reason_code": reason_code,
                    "importance_score": max(0.0, min(1.0, float(row["importance_score"]))),
                    "explanation": {"title": row["title"], "body": row["body"], "story_id": row["story_id"], "created_at": row["created_at"]},
                    "basis_fingerprint": self._basis_fingerprint({"event_type": row["event_type"], "story_id": row["story_id"], "cause": cause}),
                }
                candidate["id"] = self._candidate_id(candidate)
                candidates.append(candidate)
            for row in conn.execute(
                "SELECT id, operation_type, reason, reason_code, cause_class, caused_by_type, caused_by_id, occurred_at FROM story_corrections ORDER BY occurred_at DESC, id DESC LIMIT 50"
            ):
                candidate = {
                    "object_type": "story_correction",
                    "object_id": row["id"],
                    "reason_code": "correction",
                    "importance_score": 0.8,
                    "explanation": {"operation_type": row["operation_type"], "reason": row["reason"], "reason_code": row["reason_code"], "cause_class": row["cause_class"], "occurred_at": row["occurred_at"]},
                    "basis_fingerprint": self._basis_fingerprint({"operation_type": row["operation_type"], "reason_code": row["reason_code"], "cause_class": row["cause_class"], "caused_by_type": row["caused_by_type"], "caused_by_id": row["caused_by_id"], "occurred_at": row["occurred_at"]}),
                }
                candidate["id"] = self._candidate_id(candidate)
                candidates.append(candidate)
        finally:
            conn.close()
        return candidates

    @staticmethod
    def _decision_keys(
        conn: sqlite3.Connection, *, now: str
    ) -> set[tuple[str, str, str, str]]:
        rows = conn.execute(
            """
            SELECT object_type, object_id, reason_code, basis_fingerprint,
                   action, snoozed_until
            FROM attention_decisions
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
        suppressed: set[tuple[str, str, str, str]] = set()
        decided: set[tuple[str, str, str, str]] = set()
        for row in rows:
            key = (row[0], row[1], row[2], row[3])
            if key in decided:
                continue
            decided.add(key)
            if row[4] == "snoozed" and row[5] and row[5] <= now:
                continue
            suppressed.add(key)
        return suppressed

    def list(self, *, limit: int = 100) -> dict[str, Any]:
        if limit < 1 or limit > 500:
            raise DomainValidation("attention limit must be between 1 and 500")
        conn = storage.connect(self.db_path)
        try:
            suppressed = self._decision_keys(conn, now=self._clock())
        finally:
            conn.close()
        candidates = [
            item for item in self._candidates()
            if (item["object_type"], item["object_id"], item["reason_code"], item["basis_fingerprint"]) not in suppressed
        ]
        candidates.sort(key=lambda item: (-item["importance_score"], item["object_type"], item["object_id"]))
        return {"items": candidates[:limit], "count": min(limit, len(candidates))}

    def get(self, identifier: str) -> dict[str, Any]:
        for item in self._candidates():
            if item["id"] == identifier:
                return item
        raise DomainNotFound("attention item not found")

    def decide(
        self,
        identifier: str,
        action: str,
        *,
        actor: str | None = None,
        snooze_days: int = 7,
    ) -> dict[str, Any]:
        if action not in ATTENTION_ACTIONS:
            raise DomainValidation("invalid attention action")
        if isinstance(snooze_days, bool) or not isinstance(snooze_days, int) or not 1 <= snooze_days <= 30:
            raise DomainValidation("snooze_days must be between 1 and 30")
        candidate = self.get(identifier)
        created_at = self._clock()
        snoozed_until = None
        if action == "snoozed":
            try:
                parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise DomainValidation("attention clock must return an ISO-8601 timestamp") from exc
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            snoozed_until = (
                parsed.astimezone(timezone.utc) + timedelta(days=snooze_days)
            ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    """
                    INSERT INTO attention_decisions
                        (id, object_type, object_id, reason_code, basis_fingerprint,
                         action, actor, created_at, snoozed_until)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (new_id("attention-decision"), candidate["object_type"], candidate["object_id"], candidate["reason_code"], candidate["basis_fingerprint"], action, actor, created_at, snoozed_until),
                )
                if candidate["object_type"] == "alert" and action in {"seen", "not_useful"}:
                    conn.execute(
                        """
                        UPDATE alerts
                        SET status = 'acknowledged', acknowledged_at = ?, acknowledged_by = ?
                        WHERE id = ? AND status = 'unread'
                        """,
                        (created_at, actor, candidate["object_id"]),
                    )
        finally:
            conn.close()
        decision = {"action": action, "actor": actor}
        if snoozed_until is not None:
            decision["snoozed_until"] = snoozed_until
        return {**candidate, "decision": decision}

    @staticmethod
    def _review_cursor_key(user_id: str) -> str:
        identifier = str(user_id or "").strip()
        if not identifier:
            raise DomainValidation("user_id is required")
        return f"{REVIEW_CURSOR_SETTING_PREFIX}{identifier}"

    def _require_review_user(self, conn: sqlite3.Connection, user_id: str) -> str:
        identifier = str(user_id or "").strip()
        if not identifier:
            raise DomainValidation("user_id is required")
        if conn.execute("SELECT 1 FROM users WHERE id = ? AND disabled_at IS NULL", (identifier,)).fetchone() is None:
            raise DomainNotFound("review user not found")
        return identifier

    def review_cursor(self, user_id: str) -> dict[str, Any]:
        """Read the explicit owner boundary without changing any state."""

        key = self._review_cursor_key(user_id)
        conn = storage.connect(self.db_path)
        try:
            self._require_review_user(conn, user_id)
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return {"cursor": row["value"] if row is not None else None}
        finally:
            conn.close()

    def advance_review_cursor(self, user_id: str, boundary: str | datetime | None = None) -> dict[str, Any]:
        """Advance the explicit review boundary monotonically in UTC.

        A missing boundary means the server's current UTC time at the explicit
        mutation. Client-provided future boundaries are rejected so they cannot
        hide later knowledge.
        """

        now = normalize_as_of(self._clock())
        normalized = normalize_as_of(boundary if boundary is not None else now)
        if normalized > now:
            raise DomainValidation("review cursor cannot be in the future")
        key = self._review_cursor_key(user_id)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_review_user(conn, user_id)
                row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
                current = row["value"] if row is not None else None
                if current is not None:
                    current = normalize_as_of(current)
                    if normalized < current:
                        raise DomainConflict("review cursor cannot move backward")
                    if normalized == current:
                        return {"cursor": current}
                conn.execute(
                    """
                    INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                    """,
                    (key, normalized, now),
                )
                return {"cursor": normalized}
        finally:
            conn.close()

    def changes_since(
        self,
        user_id: str,
        *,
        since: str | datetime | None = None,
        limit: int = 25,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """Return bounded, replayable material changes without advancing review."""

        current = self.review_cursor(user_id)["cursor"]
        # A page token carries the original boundary and high-water mark. Do
        # not replace it with a cursor advanced by a concurrent explicit read.
        effective_since = since if since is not None or page_token else current
        result = TemporalReadService(self.db_path, clock=self._clock).meaningful_changes_since(
            effective_since,
            limit=limit,
            page_token=page_token,
        )
        result["cursor"] = current
        return result


__all__ = ["ATTENTION_ACTIONS", "AttentionService", "REVIEW_CURSOR_SETTING_PREFIX"]
