from __future__ import annotations

import json
from pathlib import Path

from newsroom.release import (
    build_artifact_manifest,
    build_release_identity,
    verify_artifact_manifest,
)
from newsroom.runtime import build_parser, runtime_config_from_options


def test_artifact_manifest_round_trip_detects_tampering(tmp_path):
    source = tmp_path / "source"
    (source / "newsroom").mkdir(parents=True)
    (source / "frontend" / "dist").mkdir(parents=True)
    (source / "pyproject.toml").write_text("[project]\nname='newsroom'\n", encoding="utf-8")
    (source / "newsroom" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (source / "frontend" / "dist" / "index.html").write_text("<html></html>\n", encoding="utf-8")

    manifest = build_artifact_manifest(source)
    manifest_path = tmp_path / "release-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    install = tmp_path / "install"
    for item in manifest["files"]:
        destination = install / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((source / item["path"]).read_bytes())

    assert verify_artifact_manifest(install, manifest) == []

    (install / "newsroom" / "app.py").write_text("tampered\n", encoding="utf-8")
    assert verify_artifact_manifest(install, manifest) == [
        "hash mismatch: newsroom/app.py"
    ]


def test_artifact_manifest_excludes_runtime_secrets_and_build_inputs(tmp_path):
    source = tmp_path / "source"
    (source / "newsroom").mkdir(parents=True)
    (source / "frontend" / "dist").mkdir(parents=True)
    (source / "node_modules").mkdir()
    (source / ".git").mkdir()
    (source / "newsroom" / "app.py").write_text("app\n", encoding="utf-8")
    (source / "newsroom" / "local.db").write_text("secret\n", encoding="utf-8")
    (source / ".env").write_text("PASSWORD=secret\n", encoding="utf-8")
    (source / "frontend" / "dist" / "index.html").write_text("built\n", encoding="utf-8")
    (source / "node_modules" / "ignored.js").write_text("ignored\n", encoding="utf-8")
    (source / ".git" / "HEAD").write_text("ignored\n", encoding="utf-8")

    manifest = build_artifact_manifest(source)
    paths = {item["path"] for item in manifest["files"]}

    assert paths == {"frontend/dist/index.html", "newsroom/app.py"}


def test_release_identity_records_clean_git_state_and_artifact_digest(tmp_path):
    source = tmp_path / "source"
    (source / "newsroom").mkdir(parents=True)
    (source / "newsroom" / "app.py").write_text("app\n", encoding="utf-8")

    identity = build_release_identity(source)

    assert identity["source_commit"] is None
    assert identity["worktree_clean"] is False
    assert identity["source_tree_sha256"]
    assert identity["artifact_sha256"] == build_artifact_manifest(source)["digest"]


def test_artifact_manifest_verification_rejects_malformed_file_list(tmp_path):
    assert verify_artifact_manifest(tmp_path, {"files": "not-a-list"}) == [
        "invalid manifest files"
    ]
    assert verify_artifact_manifest(tmp_path, {"files": ["not-a-record"]}) == [
        "invalid manifest file record",
        "manifest digest mismatch",
    ]


def test_runtime_commands_require_explicit_prod_root_and_bounded_process_options(tmp_path):
    parser = build_parser()
    args = parser.parse_args(
        [
            "worker",
            "--environment",
            "prod",
            "--root",
            str(tmp_path / "prod"),
            "--interval",
            "5",
        ]
    )

    config = runtime_config_from_options(args)

    assert args.command == "worker"
    assert args.interval == 5.0
    assert config.environment == "prod"
    assert config.root == (tmp_path / "prod").resolve()
