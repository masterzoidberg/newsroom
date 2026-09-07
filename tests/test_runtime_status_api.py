from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.jobs import JobService
from newsroom.migrations import apply_migrations
from newsroom.runtime_managed import ComponentState
from newsroom.runtime_status import RuntimeControlUnavailable, RuntimeStatusService


PASSWORD = "a-long-test-password-12345"
IDENTITY = {
    "installation_id": "11111111-1111-4111-8111-111111111111",
    "role": "api",
    "release_id": "fixture-release",
    "pid": 1234,
    "process_creation_token": "fixture-token",
}


def _login(client: TestClient) -> str:
    assert client.post("/api/v1/auth/setup", json={"username": "admin", "password": PASSWORD}).status_code == 201
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}).status_code == 200
    csrf = client.cookies.get("newsroom_csrf")
    assert csrf
    return csrf


def _client(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    app = create_app(config=config, frontend_dist=tmp_path / "missing-dist", runtime_identity=IDENTITY)
    return config, TestClient(app)


def test_runtime_status_is_authenticated_bounded_and_not_cached(tmp_path):
    config, client = _client(tmp_path)
    with client:
        assert client.get("/api/v1/runtime/status").status_code == 401
        _login(client)
        response = client.get("/api/v1/runtime/status")

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    payload = response.json()
    assert payload["overall"] == "degraded"
    assert payload["work"] == {"state": "idle", "queued_jobs": 0, "running_jobs": 0}
    assert payload["components"]["worker"]["status"] == "missing"
    assert payload["controls"] == {"available": False, "actions": []}
    assert str(config.root) not in response.text
    assert '"pid"' not in response.text
    assert '"process_creation_token"' not in response.text


def test_runtime_status_distinguishes_queued_and_processing_work(tmp_path):
    config, client = _client(tmp_path)
    with client:
        _login(client)
        jobs = JobService(config.database_path)
        job = jobs.enqueue("fixture", {})
        queued = client.get("/api/v1/runtime/status").json()
        assert queued["work"] == {"state": "queued", "queued_jobs": 1, "running_jobs": 0}

        assert jobs.claim(job["id"], "worker-fixture") is not None
        processing = client.get("/api/v1/runtime/status").json()
        assert processing["work"] == {"state": "processing", "queued_jobs": 0, "running_jobs": 1}


def test_runtime_status_service_distinguishes_idle_from_stale_worker(tmp_path, monkeypatch):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    config.ensure_runtime_dirs()
    apply_migrations(config.database_path)
    managed_owner = SimpleNamespace(supervisor_managed=True)
    states = {
        role: ComponentState(role=role, status="healthy", detail="heartbeat is fresh", owner=managed_owner)
        for role in ("supervisor", "api", "worker", "scheduler")
    }

    def fake_state(_config, role, **_kwargs):
        return states[role]

    monkeypatch.setattr("newsroom.runtime_status.component_state", fake_state)
    service = RuntimeStatusService(config, IDENTITY)
    idle = service.snapshot()
    assert idle["overall"] == "idle"
    assert idle["work"]["state"] == "idle"
    assert idle["controls"]["actions"] == ["stop_newsroom", "restart_api", "restart_worker", "restart_scheduler"]

    states["worker"] = ComponentState(role="worker", status="stale", detail="heartbeat is stale", owner=managed_owner)
    degraded = service.snapshot()
    assert degraded["overall"] == "degraded"
    assert degraded["work"]["state"] == "idle"
    assert degraded["components"]["worker"] == {"status": "stale", "detail": "heartbeat is stale", "managed": True}


def test_runtime_controls_require_auth_csrf_and_strict_allowlist(tmp_path, monkeypatch):
    dispatched: list[object] = []
    target = object()
    monkeypatch.setattr(RuntimeStatusService, "prepare_control", lambda self, action: target)
    monkeypatch.setattr(RuntimeStatusService, "dispatch_control", lambda self, owner: dispatched.append(owner))
    _config, client = _client(tmp_path)

    with client:
        unauthenticated = client.post("/api/v1/runtime/control", json={"action": "restart_worker"})
        csrf = _login(client)
        missing_csrf = client.post("/api/v1/runtime/control", json={"action": "restart_worker"})
        invalid = client.post(
            "/api/v1/runtime/control",
            json={"action": "run_arbitrary_command"},
            headers={"X-CSRF-Token": csrf},
        )
        accepted = client.post(
            "/api/v1/runtime/control",
            json={"action": "restart_worker"},
            headers={"X-CSRF-Token": csrf},
        )
        stop = client.post(
            "/api/v1/runtime/control",
            json={"action": "stop_newsroom"},
            headers={"X-CSRF-Token": csrf},
        )

    assert unauthenticated.status_code == 401
    assert missing_csrf.status_code == 403
    assert invalid.status_code == 422
    assert accepted.status_code == 202
    assert accepted.headers["Cache-Control"] == "no-store"
    assert accepted.json()["transition"] == "restarting"
    assert stop.status_code == 202
    assert stop.json()["transition"] == "stopping"
    assert dispatched == [target, target]


def test_unmanaged_runtime_control_fails_closed(tmp_path):
    _config, client = _client(tmp_path)
    with client:
        csrf = _login(client)
        response = client.post(
            "/api/v1/runtime/control",
            json={"action": "stop_newsroom"},
            headers={"X-CSRF-Token": csrf},
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "http_error"


def test_runtime_status_service_rejects_unavailable_action(tmp_path, monkeypatch):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    config.ensure_runtime_dirs()
    apply_migrations(config.database_path)
    missing = ComponentState(role="worker", status="missing", detail="owner is missing", owner=None)
    monkeypatch.setattr("newsroom.runtime_status.component_state", lambda _config, role, **_kwargs: missing)
    service = RuntimeStatusService(config, IDENTITY)
    with pytest.raises(RuntimeControlUnavailable):
        service.prepare_control("restart_worker")
