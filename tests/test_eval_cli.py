"""Tests for the evaluation CLI."""
from __future__ import annotations

import json

from newsroom.evals.cli import main
from newsroom.evals.corpus import evals_dir


def test_cli_validate(capsys):
    assert main(["validate"]) == 0
    out = capsys.readouterr().out
    assert "VALID" in out


def test_cli_list(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "multi-outlet-hermes-v0200" in out


def test_cli_summary(capsys):
    assert main(["summary"]) == 0
    out = capsys.readouterr().out
    assert "taxonomy distribution" in out


def test_cli_replay(capsys):
    assert main(["replay", "multi-outlet-hermes-v0200"]) == 0
    out = capsys.readouterr().out
    assert "deterministic" in out


def test_cli_replay_missing_fixture(capsys):
    assert main(["replay", "does-not-exist"]) == 1


def test_cli_baseline_json(capsys):
    assert main(["baseline", "--json"]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["system"] == "hermes-v1"
    assert len(data["results"]) == 4


def test_cli_score(capsys, tmp_path):
    _, valid = __import__("newsroom.evals.corpus", fromlist=["validate_corpus"]).validate_corpus()
    pred_file = tmp_path / "pred.json"
    pred_file.write_text(
        json.dumps(
            {
                "prediction_id": "p",
                "case_id": "multi-outlet-hermes-v0200",
                "system": "test",
                "story_groups": [
                    {"story_id": "s1", "candidate_ids": ["github-v0200", "hermesatlas-guide"]}
                ],
            }
        ),
        encoding="utf-8",
    )
    assert main(["score", "multi-outlet-hermes-v0200", "--prediction", str(pred_file)]) == 0
    out = capsys.readouterr().out
    assert "event.precision=1.000" in out
