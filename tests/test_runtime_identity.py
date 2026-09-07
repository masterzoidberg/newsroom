from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from newsroom import runtime
from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.runtime_identity import (
    EndpointDiagnosis,
    EndpointStatus,
    ExclusiveFileLock,
    build_process_identity,
    diagnose_endpoint,
    ensure_installation_identity,
    process_creation_token,
    verify_api_owner,
)


ROOT = Path(__file__).resolve().parents[1]


def _wait_for_managed_identity(port: int, *, timeout: float = 8.0) -> dict:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.25)
        try:
            connection.request("GET", "/api/v1/runtime/identity")
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            if response.status == 200 and payload.get("managed") is True:
                return payload
        except Exception as exc:  # pragma: no cover - only retained for timeout diagnostics
            last_error = exc
        finally:
            connection.close()
        time.sleep(0.05)
    raise AssertionError(f"managed API did not become ready: {last_error}")


def _start_api(root: Path, port: int) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "newsroom.runtime",
            "api",
            "--environment",
            "dev",
            "--root",
            str(root),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


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


def test_installation_identity_is_stable_and_lock_is_exclusive(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    config.ensure_runtime_dirs()

    first = ensure_installation_identity(config)
    second = ensure_installation_identity(config)

    assert first == second
    assert first.root == str(config.root)

    lock_path = config.root / "runtime" / "api.lock"
    first_lock = ExclusiveFileLock(lock_path)
    second_lock = ExclusiveFileLock(lock_path)
    assert first_lock.acquire()
    assert second_lock.acquire() is False
    first_lock.release()
    assert second_lock.acquire()
    second_lock.release()


def test_pid_creation_time_and_release_are_required_for_owner_verification(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    config.ensure_runtime_dirs()
    installation = ensure_installation_identity(config)
    token = process_creation_token(os.getpid())
    assert token is not None
    owner = build_process_identity(
        config,
        installation,
        role="api",
        release_id="release-a",
        host="127.0.0.1",
        port=18127,
    )

    verified, _ = verify_api_owner(
        config,
        owner,
        installation=installation,
        release_id="release-a",
        host="127.0.0.1",
        port=18127,
    )
    assert verified is True

    stale = replace(owner, process_creation_token=owner.process_creation_token + "-stale")
    verified, reason = verify_api_owner(
        config,
        stale,
        installation=installation,
        release_id="release-a",
        host="127.0.0.1",
        port=18127,
    )
    assert verified is False
    assert "PID may have been reused" in reason

    wrong_release = replace(owner, release_id="release-b")
    verified, reason = verify_api_owner(
        config,
        wrong_release,
        installation=installation,
        release_id="release-a",
        host="127.0.0.1",
        port=18127,
    )
    assert verified is False
    assert "release identity" in reason


def test_runtime_identity_endpoint_is_bounded_and_does_not_expose_root(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    identity = {
        "installation_id": "11111111-1111-4111-8111-111111111111",
        "role": "api",
        "release_id": "git:abc123",
        "pid": 123,
        "process_creation_token": "linux-startticks:456",
    }
    with TestClient(create_app(config=config, runtime_identity=identity)) as client:
        response = client.get("/api/v1/runtime/identity")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["managed"] is True
    assert response.json()["installation_id"] == identity["installation_id"]
    assert "root" not in response.json()


def test_concurrent_same_root_launches_converge_on_one_verified_api(tmp_path):
    port = _unused_port()
    runtime_root = tmp_path / "same" / "dev"
    first = _start_api(runtime_root, port)
    second = _start_api(runtime_root, port)
    processes = [first, second]
    try:
        identity = _wait_for_managed_identity(port)
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline and sum(p.poll() is None for p in processes) != 1:
            time.sleep(0.05)

        running = [p for p in processes if p.poll() is None]
        exited = [p for p in processes if p.poll() is not None]
        assert len(running) == 1
        assert len(exited) == 1
        assert exited[0].returncode == 0
        stderr = exited[0].stderr.read() if exited[0].stderr is not None else ""
        assert "reusing it" in stderr
        assert running[0].poll() is None
        assert identity["installation_id"]

        duplicate = subprocess.run(
            [
                sys.executable,
                "-m",
                "newsroom.runtime",
                "api",
                "--environment",
                "dev",
                "--root",
                str(runtime_root),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=8,
        )
        assert duplicate.returncode == 0
        assert "reusing it" in duplicate.stderr
        assert running[0].poll() is None
    finally:
        for process in processes:
            _stop_process(process)


def test_different_root_on_same_port_is_diagnosed_without_stopping_owner(tmp_path):
    port = _unused_port()
    owner_root = tmp_path / "owner" / "dev"
    other_root = tmp_path / "other" / "dev"
    owner = _start_api(owner_root, port)
    try:
        _wait_for_managed_identity(port)
        conflicting = subprocess.run(
            [
                sys.executable,
                "-m",
                "newsroom.runtime",
                "api",
                "--environment",
                "dev",
                "--root",
                str(other_root),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=8,
        )

        assert conflicting.returncode == 3
        assert "different Newsroom installation or release" in conflicting.stderr
        assert "No process was stopped" in conflicting.stderr
        assert owner.poll() is None
        _wait_for_managed_identity(port)
    finally:
        _stop_process(owner)


class _ForeignHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib handler contract
        body = b'{"service":"other","status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args) -> None:
        return


def test_foreign_listener_is_actionable_and_is_not_killed(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ForeignHandler)
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
        installation = ensure_installation_identity(config)
        diagnosis = diagnose_endpoint(
            "127.0.0.1",
            port,
            expected_installation_id=installation.installation_id,
            expected_release_id="release-a",
        )
        assert diagnosis.status is EndpointStatus.FOREIGN

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "newsroom.runtime",
                "api",
                "--environment",
                "dev",
                "--root",
                str(tmp_path / "launch" / "dev"),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=8,
        )
        assert result.returncode == 3
        assert "occupied by another application" in result.stderr
        assert "did not stop it or choose another port" in result.stderr

        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
        connection.request("GET", "/still-running")
        response = connection.getresponse()
        assert response.status == 200
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_bind_race_uses_same_diagnostic_path(tmp_path, monkeypatch, capsys):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    config.ensure_runtime_dirs()
    options = SimpleNamespace(host="127.0.0.1", port=18129)
    diagnoses = iter(
        [
            EndpointDiagnosis(EndpointStatus.AVAILABLE, "available"),
            EndpointDiagnosis(EndpointStatus.FOREIGN, "foreign"),
        ]
    )

    monkeypatch.setattr(runtime, "resolve_release_id", lambda: "release-test")
    monkeypatch.setattr(runtime, "diagnose_endpoint", lambda *_args, **_kwargs: next(diagnoses))

    def fail_bind(*_args, **_kwargs):
        raise SystemExit(1)

    monkeypatch.setattr(runtime.uvicorn, "run", fail_bind)

    result = runtime._run_api(config, options)
    captured = capsys.readouterr()

    assert result == 3
    assert "API bind failed after preflight" in captured.err
    assert "occupied by another application" in captured.err


class _UnmanagedNewsroomHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib handler contract
        if self.path == "/api/v1/runtime/identity":
            body = b'{"service":"newsroom","managed":false,"version":"0.1.0-dev"}'
        else:
            body = b'{"service":"newsroom","status":"ok","version":"0.1.0-dev"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args) -> None:
        return


def test_unmanaged_newsroom_listener_is_distinguished_from_matching_owner(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _UnmanagedNewsroomHandler)
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
        installation = ensure_installation_identity(config)
        diagnosis = diagnose_endpoint(
            "127.0.0.1",
            port,
            expected_installation_id=installation.installation_id,
            expected_release_id="release-a",
        )
        assert diagnosis.status is EndpointStatus.UNMANAGED
        assert "without managed runtime identity" in diagnosis.detail
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_non_http_listener_with_unverifiable_owner_is_unknown(tmp_path):
    import socketserver

    class SilentHandler(socketserver.BaseRequestHandler):
        def handle(self):
            time.sleep(0.15)

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), SilentHandler)
    server.daemon_threads = True
    port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
        installation = ensure_installation_identity(config)
        diagnosis = diagnose_endpoint(
            "127.0.0.1",
            port,
            expected_installation_id=installation.installation_id,
            expected_release_id="release-a",
            timeout_seconds=0.05,
        )
        assert diagnosis.status is EndpointStatus.UNKNOWN
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_release_identity_reads_large_installed_manifest(tmp_path):
    from newsroom.runtime_identity import resolve_release_id

    code_root = tmp_path / "install"
    (code_root / "newsroom").mkdir(parents=True)
    (code_root / "newsroom" / "placeholder.py").write_text("VALUE = 1\n", encoding="utf-8")
    manifest = {
        "installed_artifact_sha256": "a" * 64,
        "artifact_files": [{"path": f"docs/{i}.md", "sha256": "b" * 64, "size": 1} for i in range(200)],
    }
    (code_root / "release-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert resolve_release_id(code_root) == "manifest:" + ("a" * 64)


def test_corrupt_stale_owner_metadata_is_not_trusted(tmp_path):
    from newsroom.runtime_identity import api_owner_path, read_api_owner

    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    config.ensure_runtime_dirs()
    ensure_installation_identity(config)
    path = api_owner_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    assert read_api_owner(config) is None
