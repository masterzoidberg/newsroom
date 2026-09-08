from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from newsroom.config import RuntimeConfig
from newsroom.runtime_managed import ManagedRoleContext, _read_json, _write_json_atomic


def test_read_json_treats_permission_error_as_transient_unavailable_state(monkeypatch, tmp_path):
    target = tmp_path / "api-heartbeat.json"
    original_read_bytes = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path == target:
            raise PermissionError(13, "Permission denied", str(path))
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)

    assert _read_json(target) is None


def test_write_json_atomic_retries_transient_permission_error(monkeypatch, tmp_path):
    target = tmp_path / "api-heartbeat.json"
    original_replace = os.replace
    attempts = 0

    def replace(source, destination):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError(13, "Permission denied", str(destination))
        return original_replace(source, destination)

    monkeypatch.setattr(os, "replace", replace)
    monkeypatch.setattr("newsroom.runtime_managed.time.sleep", lambda _seconds: None)

    _write_json_atomic(target, {"ok": True})

    assert attempts == 3
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}


def test_heartbeat_loop_survives_permission_error_and_retries_next_interval(monkeypatch, tmp_path):
    config = RuntimeConfig(environment="prod", root=tmp_path / "prod")
    context = ManagedRoleContext(
        config,
        installation_id="installation",
        release_id="release",
        role="worker",
        stop_event=threading.Event(),
    )
    writes = 0

    class StopSequence:
        def __init__(self) -> None:
            self.calls = 0

        def wait(self, _seconds: float) -> bool:
            self.calls += 1
            return self.calls > 2

    def write_heartbeat() -> None:
        nonlocal writes
        writes += 1
        if writes == 1:
            raise PermissionError(13, "Permission denied")

    context._thread_stop = StopSequence()  # type: ignore[assignment]
    monkeypatch.setattr(context, "_write_heartbeat", write_heartbeat)

    context._heartbeat_loop()

    assert writes == 2
