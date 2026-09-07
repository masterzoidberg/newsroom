"""Restart-safe single-worker process wrapper for durable Jobs."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from .job_lease import renew_running_job_lease
from .jobs import JobService


class RetryableJobFailure(RuntimeError):
    """A handler failure that should consume a bounded retry."""


def merge_handlers(*registries: Mapping[str, Callable[[dict[str, Any]], Any]]) -> dict[str, Callable[[dict[str, Any]], Any]]:
    """Compose handler registries while rejecting silent job-type collisions."""
    merged: dict[str, Callable[[dict[str, Any]], Any]] = {}
    for registry in registries:
        for name, handler in registry.items():
            if name in merged:
                raise ValueError(f"duplicate handler registration for job_type {name!r}")
            merged[name] = handler
    return merged


class WorkerProcess:
    """Claim one job, execute a registered handler, and persist its outcome."""

    def __init__(
        self,
        db_path: str | Path,
        handlers: Mapping[str, Callable[[dict[str, Any]], Any]],
        *,
        worker_id: str,
        queue: JobService | None = None,
    ):
        self.queue = queue or JobService(db_path)
        self.handlers = dict(handlers)
        self.worker_id = worker_id

    def run_once(self, *, now: str | None = None) -> dict[str, Any] | None:
        job = self.queue.claim_next(self.worker_id, now=now)
        if job is None:
            return None
        handler = self.handlers.get(job["job_type"])
        if handler is None:
            return self.queue.complete(
                job["id"],
                self.worker_id,
                "failed",
                error_code="unknown_job_type",
                error_detail=job["job_type"],
                retryable=False,
                now=now,
            )
        lease_stop = threading.Event()
        lease_lost = threading.Event()

        def renew_lease() -> None:
            interval = max(0.5, min(30.0, float(self.queue.lease_seconds) / 3.0))
            while not lease_stop.wait(interval):
                try:
                    renewed = renew_running_job_lease(
                        self.queue.db_path,
                        job_id=job["id"],
                        worker_id=self.worker_id,
                        lease_seconds=self.queue.lease_seconds,
                    )
                except Exception:
                    # Transient SQLite/IO failures get another bounded renewal
                    # interval rather than ending a valid lease early.
                    continue
                if not renewed:
                    lease_lost.set()
                    return

        renewal = threading.Thread(
            target=renew_lease,
            name=f"newsroom-lease-{job['id']}",
            daemon=True,
        )
        renewal.start()
        try:
            result = handler(job)
        except RetryableJobFailure as exc:
            lease_stop.set()
            renewal.join(timeout=1.0)
            if lease_lost.is_set():
                return self.queue.get(job["id"])
            return self.queue.complete(
                job["id"],
                self.worker_id,
                "failed",
                error_code="retryable_handler_failure",
                error_detail=str(exc),
                retryable=True,
                now=now,
            )
        except Exception as exc:  # handlers are an internal allow-listed boundary
            lease_stop.set()
            renewal.join(timeout=1.0)
            if lease_lost.is_set():
                return self.queue.get(job["id"])
            return self.queue.complete(
                job["id"],
                self.worker_id,
                "failed",
                error_code=type(exc).__name__,
                error_detail=str(exc),
                retryable=False,
                now=now,
            )
        lease_stop.set()
        renewal.join(timeout=1.0)
        if lease_lost.is_set():
            return self.queue.get(job["id"])
        return self.queue.complete(
            job["id"],
            self.worker_id,
            "succeeded",
            outcome=result if isinstance(result, Mapping) else None,
            now=now,
        )

    def run_forever(self, stop_event: threading.Event, *, interval_seconds: float = 1.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        while not stop_event.is_set():
            if self.run_once() is None:
                stop_event.wait(interval_seconds)


__all__ = ["RetryableJobFailure", "WorkerProcess", "merge_handlers"]
