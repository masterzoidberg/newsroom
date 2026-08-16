from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from newsroom.app import create_app
from newsroom.config import RuntimeConfig


PASSWORD = "a-long-test-password-12345"


def _client(tmp_path, environment: str = "dev"):
    config = RuntimeConfig.for_environment(environment, root=tmp_path / environment)
    return TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))


def test_setup_stores_argon2id_hash_and_never_returns_password(tmp_path):
    with _client(tmp_path) as client:
        response = client.post(
            "/api/v1/auth/setup",
            json={"username": "admin", "password": PASSWORD},
        )
        repeated = client.post(
            "/api/v1/auth/setup",
            json={"username": "second", "password": PASSWORD},
        )

    assert response.status_code == 201
    assert response.json() == {"username": "admin"}
    assert PASSWORD not in response.text
    assert repeated.status_code == 409

    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    from newsroom import storage

    conn = storage.connect(config.database_path)
    try:
        row = conn.execute(
            "SELECT password_hash, password_algo FROM users WHERE username = 'admin'"
        ).fetchone()
    finally:
        conn.close()
    assert row[0].startswith("$argon2id$")
    assert row[1] == "argon2id"


def test_login_sets_http_only_session_and_csrf_cookies(tmp_path):
    with _client(tmp_path) as client:
        client.post(
            "/api/v1/auth/setup",
            json={"username": "admin", "password": PASSWORD},
        )
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": PASSWORD},
        )
        me = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json() == {"username": "admin"}
    assert "newsroom_session=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert client.cookies.get("newsroom_csrf")
    assert me.status_code == 200
    assert me.json() == {"username": "admin"}


def test_logout_requires_csrf_and_revokes_session(tmp_path):
    with _client(tmp_path) as client:
        client.post(
            "/api/v1/auth/setup",
            json={"username": "admin", "password": PASSWORD},
        )
        client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": PASSWORD},
        )
        invalid = client.post(
            "/api/v1/auth/logout", headers={"X-CSRF-Token": "wrong"}
        )
        still_authenticated = client.get("/api/v1/auth/me")
        csrf = client.cookies.get("newsroom_csrf")
        valid = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
        revoked = client.get("/api/v1/auth/me")

    assert invalid.status_code == 403
    assert still_authenticated.status_code == 200
    assert valid.status_code == 204
    assert revoked.status_code == 401


def test_invalid_login_is_throttled_without_disclosing_account_state(tmp_path):
    with _client(tmp_path) as client:
        client.post(
            "/api/v1/auth/setup",
            json={"username": "admin", "password": PASSWORD},
        )
        responses = [
            client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "wrong-password"},
            )
            for _ in range(6)
        ]

    assert all(response.status_code in {401, 429} for response in responses)
    assert responses[-1].status_code == 429
    assert responses[0].json()["error"]["message"] == "invalid credentials"
    assert responses[-1].json()["error"]["message"] == "too many login attempts"


def test_security_headers_and_logs_exclude_password_material(tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger="newsroom.api"):
        with _client(tmp_path) as client:
            response = client.post(
                "/api/v1/auth/setup",
                json={"username": "admin", "password": PASSWORD},
            )

    assert response.status_code == 201
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Content-Security-Policy"]
    assert PASSWORD not in caplog.text


def test_validation_errors_do_not_echo_password_material(tmp_path):
    with _client(tmp_path) as client:
        response = client.post(
            "/api/v1/auth/setup",
            json={"username": "admin", "password": "short-pass"},
        )

    assert response.status_code == 422
    assert "short-pass" not in response.text


def test_production_session_cookie_is_secure(tmp_path):
    with _client(tmp_path, environment="prod") as client:
        response = client.post(
            "/api/v1/auth/setup",
            json={"username": "admin", "password": PASSWORD},
        )
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": PASSWORD},
        )

    assert response.status_code == 201
    assert "Secure" in login.headers["set-cookie"]
    assert "Strict-Transport-Security" in login.headers
