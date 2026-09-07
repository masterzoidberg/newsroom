"""Narrow running-job lease renewal used by the supervised worker."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import storage
from .domain import utc_now


def _plus_seconds(value: str, seconds: int) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (
        (parsed + timedelta(seconds=seconds))
        .astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def renew_running_job_lease(
    db_path: str | Path,
    *,
    job_id: str,
    worker_id: str,
    lease_seconds: int,
) -> bool:
    """Extend the lease only while the same worker still owns the running job."""
    if lease_seconds < 1:
        raise ValueError("lease_seconds must be positive")
    now = utc_now()
    expires = _plus_seconds(now, lease_seconds)
    conn = storage.connect(db_path)
    try:
        with storage.write_tx(conn):
            cursor = conn.execute(
                """
                UPDATE jobs
                SET lease_expires_at = ?, updated_at = ?
                WHERE id = ? AND status = 'running' AND lease_owner = ?
                """,
                (expires, now, job_id, worker_id),
            )
            return cursor.rowcount == 1
    finally:
        conn.close()


__all__ = ["renew_running_job_lease"]
