"""Tests for corpus loading, validation, and taxonomy coverage."""
from __future__ import annotations

import pytest

from newsroom.evals.corpus import (
    validate_corpus,
    load_all_cases,
    load_case,
    discover_case_files,
)
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
