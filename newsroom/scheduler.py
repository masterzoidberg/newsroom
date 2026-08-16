"""Restart-safe scheduler process wrapper."""
from __future__ import annotations

import threading
from pathlib import Path

from .jobs import SchedulerService


class SchedulerProcess:
    """Run one persisted scheduler tick at a time."""

    def __init__(self, db_path: str | Path, *, scheduler: SchedulerService | None = None):
        self.scheduler = scheduler or SchedulerService(db_path)

    def run_once(self) -> dict:
        return self.scheduler.tick()

    def run_forever(self, stop_event: threading.Event, *, interval_seconds: float = 30.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        while not stop_event.is_set():
            self.run_once()
            stop_event.wait(interval_seconds)


__all__ = ["SchedulerProcess"]
