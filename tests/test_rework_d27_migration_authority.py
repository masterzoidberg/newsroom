from __future__ import annotations

import sqlite3

import pytest

from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.migrations import CURRENT_SCHEMA_VERSION, apply_migrations
from newsroom.runtime_identity import ExclusiveFileLock
from newsroom.runtime_managed import RUNTIME_ROLES, component_lock_path
from newsroom.runtime_supervisor import RuntimeSupervisor
from newsroom.schema_authority import SchemaNotReady, schema_versions_readonly


def _config(tmp_path) -> RuntimeConfig:
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    config.ensure_runtime_dirs()
    return config


def _make_pending_schema(config: RuntimeConfig) -> None:
    apply_migrations(config.database_path)
    conn = sqlite3.connect(config.database_path)
    try:
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = ?",
            (CURRENT_SCHEMA_VERSION,),
        )
        conn.execute(
            "UPDATE app_meta SET value = ? WHERE key = 'schema_version'",
            (str(CURRENT_SCHEMA_VERSION - 1),),
        )
        conn.commit()
    finally:
        conn.close()


def test_schema_readiness_is_read_only_for_missing_database(tmp_path) -> None:
    config = _config(tmp_path)
    assert not config.database_path.exists()

    with pytest.raises(SchemaNotReady, match="database is missing"):
        schema_versions_readonly(config.database_path)

    assert not config.database_path.exists()


def test_create_app_verify_mode_refuses_pending_schema_without_migrating(tmp_path) -> None:
    config = _config(tmp_path)
    _make_pending_schema(config)

    with pytest.raises(SchemaNotReady, match="schema is not ready"):
        create_app(config=config, schema_mode="verify")

    assert schema_versions_readonly(config.database_path)[-1] == CURRENT_SCHEMA_VERSION - 1


def test_create_app_default_keeps_disposable_dev_initialization(tmp_path) -> None:
    config = _config(tmp_path)

    app = create_app(config=config)

    assert app.state.runtime_config == config
    assert schema_versions_readonly(config.database_path)[-1] == CURRENT_SCHEMA_VERSION


def test_supervisor_holds_all_component_locks_during_migration(tmp_path, monkeypatch) -> None:
    config = _config(tmp_path)
    supervisor = RuntimeSupervisor(
        config,
        installation_id="test-installation",
        release_id="test-release",
        host="127.0.0.1",
        port=8127,
    )
    real_apply = apply_migrations
    observed: list[str] = []

    def guarded_apply(path):
        for role in RUNTIME_ROLES:
            probe = ExclusiveFileLock(component_lock_path(config, role))
            assert probe.acquire() is False
            observed.append(role)
        return real_apply(path)

    monkeypatch.setattr("newsroom.runtime_supervisor.apply_migrations", guarded_apply)

    supervisor.prepare()

    assert observed == list(RUNTIME_ROLES)
    assert schema_versions_readonly(config.database_path)[-1] == CURRENT_SCHEMA_VERSION


def test_supervisor_does_not_migrate_when_managed_writer_is_active(tmp_path) -> None:
    config = _config(tmp_path)
    _make_pending_schema(config)
    held = ExclusiveFileLock(component_lock_path(config, "worker"))
    assert held.acquire() is True
    try:
        supervisor = RuntimeSupervisor(
            config,
            installation_id="test-installation",
            release_id="test-release",
            host="127.0.0.1",
            port=8127,
        )
        with pytest.raises(SchemaNotReady, match="schema is not ready"):
            supervisor.prepare()
    finally:
        held.release()

    assert schema_versions_readonly(config.database_path)[-1] == CURRENT_SCHEMA_VERSION - 1
