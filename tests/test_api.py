from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient

from newsroom.app import create_app
from newsroom.config import RuntimeConfig


def test_health_and_readiness_expose_request_id_and_database_state(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    app = create_app(config=config, frontend_dist=tmp_path / "missing-dist")

    with TestClient(app) as client:
        health = client.get("/api/v1/health", headers={"X-Request-ID": "req-test-1"})
        readiness = client.get("/api/v1/readiness")

    assert health.status_code == 200
    assert health.headers["X-Request-ID"] == "req-test-1"
    assert health.json()["status"] == "ok"
    assert health.json()["request_id"] == "req-test-1"
    assert readiness.status_code == 200
    assert readiness.json() == {
        "database": "ok",
        "request_id": readiness.headers["X-Request-ID"],
        "status": "ready",
    }


def test_api_errors_use_canonical_envelope(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    app = create_app(config=config, frontend_dist=tmp_path / "missing-dist")

    with TestClient(app) as client:
        response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["request_id"] == response.headers["X-Request-ID"]
    assert payload["error"]["message"]


def test_api_logs_structured_request_record(tmp_path, caplog):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    app = create_app(config=config, frontend_dist=tmp_path / "missing-dist")

    with caplog.at_level(logging.INFO, logger="newsroom.api"):
        with TestClient(app) as client:
            response = client.get("/api/v1/health")

    records = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "newsroom.api"
    ]
    assert response.status_code == 200
    assert any(
        record["event"] == "http_request"
        and record["request_id"] == response.headers["X-Request-ID"]
        for record in records
    )


def test_production_frontend_dist_is_served_from_same_origin(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        "<!doctype html><html><body><div id='root'>shell</div></body></html>",
        encoding="utf-8",
    )

    app = create_app(config=config, frontend_dist=dist)
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "id='root'" in response.text
