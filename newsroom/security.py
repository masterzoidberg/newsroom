"""Small, dependency-free request-boundary controls for the local API."""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RequestLimiter:
    """Bounded fixed-window limiter suitable for the single local web process."""

    def __init__(self, *, window_seconds: float = 60.0, max_keys: int = 2048):
        if window_seconds <= 0 or max_keys < 1:
            raise ValueError("request limiter bounds must be positive")
        self.window_seconds = float(window_seconds)
        self.max_keys = int(max_keys)
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, *, now: float | None = None) -> RateLimitDecision:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("rate limit must be a positive integer")
        current = time.monotonic() if now is None else float(now)
        normalized_key = str(key).strip()[:200] or "unknown"
        cutoff = current - self.window_seconds
        with self._lock:
            if normalized_key not in self._buckets and len(self._buckets) >= self.max_keys:
                oldest_key = min(
                    self._buckets,
                    key=lambda item: self._buckets[item][0] if self._buckets[item] else current,
                )
                self._buckets.pop(oldest_key, None)
            bucket = self._buckets.setdefault(normalized_key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry = max(1, int(bucket[0] + self.window_seconds - current + 0.999))
                return RateLimitDecision(False, 0, retry)
            bucket.append(current)
            return RateLimitDecision(True, max(0, limit - len(bucket)), 0)


def subsystem_for_path(path: str) -> str:
    """Map a request path to a low-cardinality telemetry subsystem."""
    normalized = str(path).lower()
    if "/auth" in normalized:
        return "auth"
    if "/ask" in normalized:
        return "ask"
    if "/search" in normalized or "/compar" in normalized or "/workbench" in normalized:
        return "research"
    if "/jobs" in normalized or "/runs" in normalized or "/scheduler" in normalized:
        return "jobs"
    if "/sources" in normalized or "/documents" in normalized or "/acquisition" in normalized:
        return "acquisition"
    if "/health" in normalized or "/readiness" in normalized or "/metrics" in normalized:
        return "runtime"
    return "domain"


__all__ = ["RateLimitDecision", "RequestLimiter", "subsystem_for_path"]
