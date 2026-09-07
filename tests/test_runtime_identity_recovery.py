from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from newsroom import runtime
from newsroom.config import RuntimeConfig
from newsroom.runtime_identity import ensure_installation_identity


ROOT = Path(__file__).resolve().parents[1]


def _unused_port() -> int:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def test_waiting_launch_takes_released_lock_when_initial_owner_dies(tmp_path, monkeypatch):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    config.ensure_runtime_dirs()
    ensure_installation_identity(config)
    lock_path = config.root / "runtime" / "api.lock"
    code = (
        "import sys,time; from newsroom.runtime_identity import ExclusiveFileLock; "
        "lock=ExclusiveFileLock(sys.argv[1]); assert lock.acquire(); "
        "print('locked', flush=True); time.sleep(0.25)"
    )
    holder = subprocess.Popen(
        [sys.executable, "-c", code, str(lock_path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "locked"
        monkeypatch.setattr(runtime, "resolve_release_id", lambda: "release-test")
        monkeypatch.setattr(runtime, "apply_migrations", lambda _path: None)
        monkeypatch.setattr(runtime, "create_app", lambda **_kwargs: object())
        monkeypatch.setattr(runtime.uvicorn, "run", lambda *_args, **_kwargs: None)

        result = runtime._run_api(
            config,
            SimpleNamespace(host="127.0.0.1", port=_unused_port()),
        )

        assert result == 0
        holder.wait(timeout=2)
        assert holder.returncode == 0
    finally:
        _stop_process(holder)
