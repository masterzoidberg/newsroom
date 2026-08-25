"""Tests for corpus loading, validation, and taxonomy coverage."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from newsroom.evals.corpus import (
    validate_corpus,
    load_all_cases,
    load_case,
    discover_case_files,
)
from newsroom.evals.semantic import SemanticCaseRunner
from newsroom.evals.schema import ValidationError
from newsroom.evals.taxonomy import CASE_TYPES


def test_corpus_discovered_and_valid():
    errors, valid = validate_corpus()
    assert errors == []
    assert len(valid) >= 30


def test_all_taxonomy_types_covered():
    _, valid = validate_corpus()
    present = {c.case_type for c in valid.values()}
    assert present == set(CASE_TYPES)


def test_case_ids_unique_and_stable():
    files = discover_case_files()
    ids = set()
    for f in files:
        c = load_case(f.stem)
        assert c.case_id == f.stem
        ids.add(c.case_id)
    assert len(ids) == len(files)


def test_load_missing_case_raises():
    with pytest.raises(ValidationError, match="case not found"):
        load_case("does-not-exist")


def test_real_v1_cases_present():
    _, valid = validate_corpus()
    for cid in (
        "multi-outlet-hermes-v0200",
        "duplicate-syndication-hermes-v0201",
        "primary-vs-secondary-nous-funding",
        "similar-distinct-hermes-events",
    ):
        assert cid in valid


def test_every_candidate_has_content_hash():
    _, valid = validate_corpus()
    for case in valid.values():
        for c in case.candidates:
            assert c.content_hash, f"{case.case_id}/{c.candidate_id} missing content_hash"


def test_expected_primary_sources_reference_candidates():
    _, valid = validate_corpus()
    for case in valid.values():
        ids = {c.candidate_id for c in case.candidates}
        for pid in case.expected_primary_sources:
            assert pid in ids


def test_duplicate_json_keys_are_rejected(tmp_path, monkeypatch):
    cases = tmp_path / "corpus" / "cases"
    cases.mkdir(parents=True)
    (tmp_path / "fixtures").mkdir()
    (cases / "duplicate.json").write_text(
        '{"schema_version": 1, "schema_version": 1}', encoding="utf-8"
    )
    monkeypatch.setenv("NEWSROOM_EVALS_DIR", str(tmp_path))

    errors, valid = validate_corpus()

    assert valid == {}
    assert errors and "duplicate key 'schema_version'" in errors[0]


def test_silent_edit_case_uses_distinct_content_hashes():
    case = load_case("silent-document-edit-version")
    hashes = {candidate.content_hash for candidate in case.candidates}
    assert len(hashes) == 2


def test_content_hash_must_use_canonical_sha256_shape():
    raw = json.loads(
        (Path(__file__).resolve().parents[1] / "evals" / "corpus" / "cases" / "silent-document-edit-version.json").read_text(
            encoding="utf-8"
        )
    )
    raw["candidates"][0]["content_hash"] = "sha256:placeholder"
    with pytest.raises(ValidationError, match="lowercase SHA-256"):
        from newsroom.evals.schema import validate_case

        validate_case(raw)


def test_phase2875_semantic_cases_are_machine_scored():
    case_ids = (
        "ask-sufficiency-refusal",
        "conservative-absence",
        "late-dependency-discovery",
        "late-story-correction",
        "late-story-split",
        "retracted-evidence",
        "silent-document-edit-version",
        "single-dependency-group-support",
    )
    for case_id in case_ids:
        result = SemanticCaseRunner().run(case_id)
        assert result.assertions, case_id
        assert result.score.semantic.assertion_count == result.score.semantic.passed_count
