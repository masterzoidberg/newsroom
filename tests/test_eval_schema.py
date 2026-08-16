"""Tests for the evaluation data contract (schema validation)."""
from __future__ import annotations

import pytest

from newsroom.evals.schema import (
    ValidationError,
    validate_case,
    content_hash,
    canonical_json,
)
from newsroom.evals.corpus import load_case


def _minimal_case(**overrides):
    case = {
        "schema_version": 1,
        "case_id": "test-case-001",
        "title": "Test case",
        "description": "A minimal valid case",
        "case_type": "official_announcement",
        "monitored_targets": [{"kind": "topic", "ref": "demo"}],
        "observation_window": {"start": None, "end": None},
        "provenance": {"source": "synthetic", "note": "test"},
        "reviewer_notes": "",
        "candidates": [
            {
                "candidate_id": "cand-1",
                "canonical_url": "https://corp-official.test/press/1",
                "title": "Acme announcement",
                "content_type": "metadata",
                "content_hash": "abc",
            }
        ],
        "gold_groups": [{"event_id": "evt-1", "candidate_ids": ["cand-1"]}],
        "gold_claims": [],
        "gold_evidence": [],
        "expected_primary_sources": [],
        "noise_candidates": [],
        "contradictions": [],
        "material_changes": [],
    }
    case.update(overrides)
    return case


def test_valid_minimal_case():
    case = validate_case(_minimal_case())
    assert case.case_id == "test-case-001"
    assert case.case_type == "official_announcement"
    assert len(case.candidates) == 1


def test_rejects_unknown_schema_version():
    with pytest.raises(ValidationError, match="schema_version"):
        validate_case(_minimal_case(schema_version=2))


def test_rejects_invalid_case_type():
    with pytest.raises(ValidationError, match="case_type"):
        validate_case(_minimal_case(case_type="not_a_type"))


def test_rejects_invalid_case_id():
    with pytest.raises(ValidationError, match="case_id"):
        validate_case(_minimal_case(case_id="has spaces!"))


def test_rejects_missing_monitored_targets():
    with pytest.raises(ValidationError, match="monitored_targets"):
        validate_case(_minimal_case(monitored_targets=[]))


def test_rejects_duplicate_candidate_ids():
    dup = _minimal_case()
    dup["candidates"].append(dict(dup["candidates"][0]))
    with pytest.raises(ValidationError, match="duplicate candidate_id"):
        validate_case(dup)


def test_rejects_unknown_candidate_in_group():
    case = _minimal_case()
    case["gold_groups"][0]["candidate_ids"] = ["cand-1", "missing"]
    with pytest.raises(ValidationError, match="unknown candidate"):
        validate_case(case)


def test_rejects_claim_with_unknown_event():
    case = _minimal_case()
    case["gold_claims"] = [
        {"claim_id": "cl-1", "event_id": "evt-nope", "proposition": "X",
         "importance": "major", "expected_state": "supported"}
    ]
    with pytest.raises(ValidationError, match="unknown event"):
        validate_case(case)


def test_rejects_invalid_claim_state():
    case = _minimal_case()
    case["gold_claims"] = [
        {"claim_id": "cl-1", "event_id": "evt-1", "proposition": "X",
         "importance": "major", "expected_state": "true"}
    ]
    with pytest.raises(ValidationError, match="expected_state"):
        validate_case(case)


def test_rejects_evidence_with_unknown_claim():
    case = _minimal_case()
    case["gold_evidence"] = [
        {"evidence_id": "ev-1", "claim_id": "cl-nope", "candidate_id": "cand-1",
         "excerpt": "x", "relationship": "supports"}
    ]
    with pytest.raises(ValidationError, match="unknown claim"):
        validate_case(case)


def test_rejects_contradiction_with_unknown_evidence():
    case = _minimal_case()
    case["gold_claims"] = [
        {"claim_id": "cl-1", "event_id": "evt-1", "proposition": "X",
         "importance": "major", "expected_state": "supported"}
    ]
    case["gold_evidence"] = [
        {"evidence_id": "ev-1", "claim_id": "cl-1", "candidate_id": "cand-1",
         "excerpt": "x", "relationship": "contradicts"}
    ]
    case["contradictions"] = [{"claim_id": "cl-1", "evidence_id": "ev-missing"}]
    with pytest.raises(ValidationError, match="unknown evidence"):
        validate_case(case)


def test_canonical_json_is_stable_and_sorted():
    # Deterministic: same input -> same output.
    a = {"b": 1, "a": [2, 1]}
    assert canonical_json(a) == canonical_json(a)
    # Dict key order must not matter (keys are sorted).
    assert canonical_json({"b": 1, "a": [2, 1]}) == canonical_json({"a": [2, 1], "b": 1})
    assert content_hash(a) == content_hash({"a": [2, 1], "b": 1})
    assert len(content_hash(a)) == 64


def test_canonical_json_preserves_list_order():
    # List order is meaningful and is preserved (canonical != sorted-list).
    assert canonical_json({"x": [2, 1]}) == '{"x":[2,1]}'


def test_loaded_corpus_case_validates():
    case = load_case("multi-outlet-hermes-v0200")
    assert case.case_id == "multi-outlet-hermes-v0200"
    assert len(case.candidates) == 2
