from __future__ import annotations

from pathlib import Path

from newsroom.runtime_managed import _read_json


def test_read_json_treats_permission_error_as_transient_unavailable_state(monkeypatch, tmp_path):
    target = tmp_path / "api-heartbeat.json"
    original_read_bytes = Path.read_bytes

    def read_bytes(path: Path) -> bytes:
        if path == target:
            raise PermissionError(13, "Permission denied", str(path))
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)

    assert _read_json(target) is None
