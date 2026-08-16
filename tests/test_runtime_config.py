from __future__ import annotations

from pathlib import Path

import pytest

from newsroom.config import RuntimeConfig, load_runtime_config


def test_explicit_dev_and_prod_roots_are_distinct_and_outside_source(tmp_path):
    dev = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    prod = RuntimeConfig.for_environment("prod", root=tmp_path / "prod")

    assert dev.environment == "dev"
    assert prod.environment == "prod"
    assert dev.root != prod.root
    assert dev.database_path == dev.root / "data" / "newsroom.db"
    assert prod.database_path == prod.root / "data" / "newsroom.db"
    assert Path(__file__).resolve().parents[1] not in dev.root.parents


def test_environment_name_guards_against_cross_environment_root(tmp_path):
    with pytest.raises(ValueError, match="must end with 'prod'"):
        RuntimeConfig.for_environment("prod", root=tmp_path / "dev")


def test_runtime_root_cannot_be_inside_source_tree():
    source_root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="source repository"):
        RuntimeConfig.for_environment("dev", root=source_root / "runtime" / "dev")


def test_explicit_environment_wins_over_environment_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWSROOM_ENV", "prod")
    monkeypatch.setenv("NEWSROOM_HOME", str(tmp_path / "wrong"))

    config = load_runtime_config(
        environment="dev", root=tmp_path / "dev", environ=None
    )

    assert config.environment == "dev"
    assert config.root == (tmp_path / "dev").resolve()


def test_missing_environment_is_rejected_for_operator_configuration(monkeypatch):
    monkeypatch.delenv("NEWSROOM_ENV", raising=False)
    with pytest.raises(ValueError, match="explicit environment"):
        load_runtime_config(environment=None, environ={})
