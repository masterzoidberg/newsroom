"""In-process, privacy-preserving operational telemetry."""
from __future__ import annotations

import threading
import time
from collections import Counter
from typing import Any

from .security import subsystem_for_path


class OperationalTelemetry:
    """Keep only bounded counters and latency aggregates; never store payloads."""

    def __init__(self) -> None:
        self.started_at = time.time()
        self._lock = threading.Lock()
        self._requests = 0
        self._status_counts: Counter[str] = Counter()
        self._failure_counts: Counter[str] = Counter()
        self._latency_count = 0
        self._latency_total_ms = 0.0
        self._latency_max_ms = 0.0

    def observe(self, *, method: str, path: str, status_code: int, duration_ms: float) -> None:
        subsystem = subsystem_for_path(path)
        bounded_status = str(int(status_code)) if isinstance(status_code, int) else "unknown"
        safe_duration = max(0.0, min(float(duration_ms), 86_400_000.0))
        with self._lock:
            self._requests += 1
            self._status_counts[bounded_status] += 1
            self._latency_count += 1
            self._latency_total_ms += safe_duration
            self._latency_max_ms = max(self._latency_max_ms, safe_duration)
            if status_code >= 500:
                self._failure_counts[subsystem] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            count = self._latency_count
            return {
                "service": "newsroom",
                "uptime_seconds": max(0, int(time.time() - self.started_at)),
                "requests_total": self._requests,
                "status_counts": dict(sorted(self._status_counts.items())),
                "failure_counts_by_subsystem": dict(sorted(self._failure_counts.items())),
                "latency_ms": {
                    "count": count,
                    "average": round(self._latency_total_ms / count, 2) if count else 0.0,
                    "maximum": round(self._latency_max_ms, 2),
                },
                "privacy": {
                    "request_bodies": False,
                    "query_strings": False,
                    "article_bodies": False,
                    "prompt_content": False,
                    "secrets": False,
                },
            }


__all__ = ["OperationalTelemetry"]
