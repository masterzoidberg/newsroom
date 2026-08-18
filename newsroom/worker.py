"""Restart-safe single-worker process wrapper for durable Jobs."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping

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
        try:
            result = handler(job)
        except RetryableJobFailure as exc:
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
            return self.queue.complete(
                job["id"],
                self.worker_id,
                "failed",
                error_code=type(exc).__name__,
                error_detail=str(exc),
                retryable=False,
                now=now,
            )
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
