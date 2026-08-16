"""Corpus discovery, loading, and validation.

Corpus cases are JSON files under ``evals/corpus/cases/``; replay fixtures live
under ``evals/fixtures/``. The directory is located relative to this package by
default and can be overridden with ``NEWSROOM_EVALS_DIR`` for tests.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from .schema import EvaluationCase, ValidationError, validate_case


def _repo_root() -> Path:
    # package lives at <repo>/newsroom/evals/, so parents[2] is the repo root.
    return Path(__file__).resolve().parents[2]


def evals_dir() -> Path:
    env = os.environ.get("NEWSROOM_EVALS_DIR")
    if env:
        return Path(env)
    return _repo_root() / "evals"


def corpus_dir() -> Path:
    return evals_dir() / "corpus"


def cases_dir() -> Path:
    return corpus_dir() / "cases"


def fixtures_dir() -> Path:
    return evals_dir() / "fixtures"


def discover_case_files() -> list[Path]:
    d = cases_dir()
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.json"))


def load_case(case_id: str) -> EvaluationCase:
    """Load and validate a single case by id (with or without ``.json``)."""
    key = case_id if case_id.endswith(".json") else f"{case_id}.json"
    path = cases_dir() / key
    if not path.is_file():
        raise ValidationError(f"case not found: {case_id}")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return validate_case(data)


def load_all_cases() -> dict[str, EvaluationCase]:
    cases: dict[str, EvaluationCase] = {}
    for path in discover_case_files():
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        case = validate_case(data)
        cases[case.case_id] = case
    return cases


def validate_corpus() -> tuple[list[str], dict[str, EvaluationCase]]:
    """Validate every case file.

    Returns ``(errors, valid_cases)``. Errors are human-readable strings; an
    empty error list means the corpus is valid.
    """
    errors: list[str] = []
    valid: dict[str, EvaluationCase] = {}
    seen_ids: dict[str, str] = {}

    for path in discover_case_files():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: cannot parse JSON: {exc}")
            continue
        try:
            case = validate_case(data)
        except ValidationError as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        if case.case_id in seen_ids:
            errors.append(
                f"{path.name}: duplicate case_id {case.case_id!r} (also in {seen_ids[case.case_id]})"
            )
            continue
        seen_ids[case.case_id] = path.name
        valid[case.case_id] = case

    return errors, valid
