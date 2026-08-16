"""Small persistence boundary for transactional application services."""
from __future__ import annotations

import hashlib
from typing import Mapping

from . import storage


class RepositoryIntegrityError(ValueError):
    """Raised when an application-level reference invariant would be broken."""


def evidence_span_hash(
    excerpt: str, locator_type: str | None, locator_value: str | None
) -> str:
    """Hash the evidence text and both locator components deterministically."""
    payload = "\x1f".join(
        (excerpt, locator_type or "", locator_value or "")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class Repository:
    """Boundary for writes that need application-level cross-table checks."""

    def __init__(self, conn):
        self.conn = conn

    def _require_reference(self, table: str, identifier: str, label: str) -> None:
        if self.conn.execute(
            f"SELECT 1 FROM {table} WHERE id = ?", (identifier,)
        ).fetchone() is None:
            raise RepositoryIntegrityError(f"{label} does not exist: {identifier}")

    def create_monitor(self, values: Mapping[str, object]) -> None:
        target_type = str(values["target_type"])
        target_id = str(values["target_id"])
        target_tables = {
            "topic": "topics",
            "subject": "subjects",
            "story": "stories",
            "source": "sources",
            "research_question": "research_questions",
        }
        table = target_tables.get(target_type)
        if table is None:
            raise RepositoryIntegrityError(f"unsupported monitor target type: {target_type}")
        columns = (
            "id", "target_type", "target_id", "policy_id", "enabled",
            "next_check_at", "last_run_at", "last_result", "created_at", "updated_at",
        )
        with storage.write_tx(self.conn):
            self._require_reference(table, target_id, f"monitor target {target_type}")
            self._require_reference("monitoring_policies", str(values["policy_id"]), "monitoring policy")
            self.conn.execute(
                f"INSERT INTO monitors ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                tuple(values.get(column) for column in columns),
            )


__all__ = ["Repository", "RepositoryIntegrityError", "evidence_span_hash"]
