"""Regression tests for the Phase 01 evaluation and dedupe repairs."""
from __future__ import annotations

import pytest

from newsroom.dedupe import CandidateStory, merge_decision
from newsroom.evals.metrics import claim_metrics, event_metrics, evidence_metrics
from newsroom.evals.prediction import validate_prediction
from newsroom.evals.schema import ValidationError, content_hash, validate_case
from newsroom.evals.replay import validate_fixture
from newsroom.url_norm import normalize_url, url_fingerprint


def _case(**overrides):
    case = {
        "schema_version": 1,
        "case_id": "phase01-case",
        "title": "Phase 01 case",
        "description": "A case for hardening tests",
        "case_type": "official_announcement",
        "monitored_targets": [{"kind": "topic", "ref": "demo"}],
        "observation_window": {
            "start": "2026-08-15T00:00:00Z",
            "end": "2026-08-16T00:00:00Z",
        },
        "provenance": {"source": "synthetic"},
        "reviewer_notes": "",
        "candidates": [
            {
                "candidate_id": "a",
                "canonical_url": "https://example.test/a",
                "title": "A",
                "content_type": "metadata",
            },
            {
                "candidate_id": "b",
                "canonical_url": "https://example.test/b",
                "title": "B",
                "content_type": "metadata",
            },
            {
                "candidate_id": "c",
                "canonical_url": "https://example.test/c",
                "title": "C",
                "content_type": "metadata",
            },
        ],
        "gold_groups": [
            {"event_id": "e1", "candidate_ids": ["a", "b"]},
            {"event_id": "e2", "candidate_ids": ["c"]},
        ],
        "gold_claims": [],
        "gold_evidence": [],
        "expected_primary_sources": [],
        "noise_candidates": [],
        "contradictions": [],
        "material_changes": [],
    }
    case.update(overrides)
    return case


def _prediction(**overrides):
    prediction = {
        "prediction_id": "prediction-1",
        "case_id": "phase01-case",
        "system": "test",
        "story_groups": [
            {"story_id": "s1", "candidate_ids": ["a", "b"]},
            {"story_id": "s2", "candidate_ids": ["c"]},
        ],
    }
    prediction.update(overrides)
    return prediction


def _fixture(**overrides):
    fixture = {
        "schema_version": 1,
        "fixture_id": "fixture-1",
        "case_id": "phase01-case",
        "channel": "simulated",
        "query": {"text": "demo"},
        "captured_at": "2026-08-15T00:00:00Z",
        "documents": [
            {
                "candidate_id": "a",
                "canonical_url": "https://example.test/a",
                "title": "A",
                "source": "synthetic",
                "publisher": "Example",
                "published_at": "2026-08-15T00:00:00Z",
                "retrieved_at": "2026-08-15T00:01:00Z",
                "content_type": "metadata",
                "excerpt": "A",
            }
        ],
    }
    fixture["content_hash"] = content_hash(fixture["documents"])
    fixture.update(overrides)
    return fixture


def test_case_rejects_duplicate_claim_ids_and_cross_group_candidate_assignment():
    duplicate_claims = _case(
        gold_claims=[
            {
                "claim_id": "claim-1",
                "event_id": "e1",
                "proposition": "A",
                "importance": "major",
                "expected_state": "supported",
            },
            {
                "claim_id": "claim-1",
                "event_id": "e2",
                "proposition": "B",
                "importance": "major",
                "expected_state": "supported",
            },
        ]
    )
    with pytest.raises(ValidationError, match="duplicate.*claim_id"):
        validate_case(duplicate_claims)

    duplicate_assignment = _case(
        gold_groups=[
            {"event_id": "e1", "candidate_ids": ["a", "b"]},
            {"event_id": "e2", "candidate_ids": ["b", "c"]},
        ]
    )
    with pytest.raises(ValidationError, match="assigned to multiple"):
        validate_case(duplicate_assignment)


@pytest.mark.parametrize(
    "mutator, message",
    [
        (lambda c: c["candidates"][0].update({"published_at": "2026-08-15"}), "timestamp"),
        (lambda c: c["candidates"][0].update({"canonical_url": "https:///missing-host"}), "host"),
        (lambda c: c["monitored_targets"].__setitem__(0, "topic"), "object"),
    ],
)
def test_case_rejects_malformed_nested_values(mutator, message):
    case = _case()
    mutator(case)
    with pytest.raises(ValidationError, match=message):
        validate_case(case)


def test_fixture_rejects_bad_types_and_timestamps():
    fixture = _fixture()
    fixture["query"] = ["not", "an", "object"]
    with pytest.raises(ValidationError, match="query"):
        validate_fixture(fixture)

    fixture = _fixture()
    fixture["documents"][0]["retrieved_at"] = "yesterday"
    fixture["content_hash"] = content_hash(fixture["documents"])
    with pytest.raises(ValidationError, match="timestamp"):
        validate_fixture(fixture)


def test_prediction_rejects_duplicate_assignments_unknown_references_and_negative_usage():
    duplicate = _prediction(
        story_groups=[
            {"story_id": "s1", "candidate_ids": ["a", "b"]},
            {"story_id": "s2", "candidate_ids": ["b", "c"]},
        ]
    )
    with pytest.raises(ValidationError, match="assigned to multiple"):
        validate_prediction(duplicate)

    invalid_enum = _prediction(
        claims=[
            {
                "claim_id": "claim-1",
                "story_id": "s1",
                "text": "A",
                "importance": "important",
                "state": "supported",
            }
        ]
    )
    with pytest.raises(ValidationError, match="importance"):
        validate_prediction(invalid_enum)

    negative_usage = _prediction(usage={"cost_usd": -0.01})
    with pytest.raises(ValidationError, match="non-negative"):
        validate_prediction(negative_usage)


def test_prediction_case_references_are_checked():
    case = validate_case(_case())
    prediction = _prediction(
        claims=[
            {"claim_id": "claim-1", "story_id": "missing-story", "text": "A"}
        ]
    )
    with pytest.raises(ValidationError, match="unknown story_id"):
        validate_prediction(prediction, case=case)


def test_empty_and_incomplete_predictions_are_not_perfect_event_scores():
    case = validate_case(_case(gold_groups=[
        {"event_id": "e1", "candidate_ids": ["a"]},
        {"event_id": "e2", "candidate_ids": ["b"]},
        {"event_id": "e3", "candidate_ids": ["c"]},
    ]))
    empty = validate_prediction(_prediction(story_groups=[]), case=case)
    empty_metrics = event_metrics(case, empty)
    assert empty_metrics.candidate_coverage == 0.0
    assert empty_metrics.precision == 0.0
    assert empty_metrics.recall == 0.0
    assert empty_metrics.important_story_recall == 0.0

    partial = validate_prediction(
        _prediction(story_groups=[{"story_id": "s1", "candidate_ids": ["a"]}]),
        case=case,
    )
    assert event_metrics(case, partial).candidate_coverage == pytest.approx(1 / 3)


def test_important_story_recall_uses_major_gold_claims():
    case = validate_case(
        _case(
            gold_claims=[
                {
                    "claim_id": "important-1",
                    "event_id": "e1",
                    "proposition": "A happened",
                    "importance": "major",
                    "expected_state": "supported",
                }
            ]
        )
    )
    prediction = validate_prediction(
        _prediction(story_groups=[{"story_id": "s1", "candidate_ids": ["c"]}]),
        case=case,
    )
    assert event_metrics(case, prediction).important_story_recall == 0.0


def test_claims_match_only_within_event_and_state_is_evaluated():
    case = validate_case(
        _case(
            gold_claims=[
                {
                    "claim_id": "claim-e1",
                    "event_id": "e1",
                    "proposition": "The result was announced",
                    "importance": "major",
                    "expected_state": "supported",
                },
                {
                    "claim_id": "claim-e2",
                    "event_id": "e2",
                    "proposition": "The result was announced",
                    "importance": "major",
                    "expected_state": "disputed",
                },
            ]
        )
    )
    prediction = validate_prediction(
        _prediction(
            claims=[
                {
                    "claim_id": "pred-1",
                    "story_id": "s2",
                    "text": "The result was announced",
                    "importance": "major",
                    "state": "supported",
                }
            ]
        ),
        case=case,
    )
    metrics = claim_metrics(case, prediction)
    assert metrics.all_claim_recall == 0.5
    assert metrics.expected_state_accuracy == 0.0


def test_closed_world_synthesis_requires_accepted_claims():
    case = validate_case(_case())
    prediction = validate_prediction(
        _prediction(
            claims=[
                {
                    "claim_id": "pending-1",
                    "story_id": "s1",
                    "text": "A",
                    "state": "pending",
                }
            ],
            synthesized_propositions=[
                {"text": "A", "claim_ids": ["pending-1"]}
            ],
        ),
        case=case,
    )
    assert evidence_metrics(case, prediction).unsupported_proposition_rate == 1.0


def test_url_identity_includes_scheme_and_non_default_port_and_rejects_missing_host():
    assert url_fingerprint("http://example.test/article") != url_fingerprint(
        "https://example.test/article"
    )
    assert url_fingerprint("https://example.test:8443/article") != url_fingerprint(
        "https://example.test/article"
    )
    with pytest.raises(ValueError, match="host"):
        normalize_url("https:///article")


def test_dedupe_chooses_strongest_eligible_candidate_not_input_order():
    candidates = [
        CandidateStory(
            id="weak",
            headline="Valve releases SteamOS update",
            normalized_headline="valve releases steamos update",
            event_key="valve-steamos-3-9-release",
            published_at=None,
            created_at="2026-08-15T00:00:00Z",
            topic_ids=["topic"],
            source_canonical_urls={"https://weak.test/article"},
        ),
        CandidateStory(
            id="strong",
            headline="Valve releases SteamOS 3.9 beta update",
            normalized_headline="valve releases steamos 3.9 beta update",
            event_key="valve-steamos-3-9-beta-release",
            published_at=None,
            created_at="2026-08-15T00:00:00Z",
            topic_ids=["topic"],
            source_canonical_urls={"https://strong.test/article"},
        ),
    ]
    decision = merge_decision(
        candidates,
        "Valve releases SteamOS 3.9 beta update",
        "valve releases steamos 3.9 beta update",
        [{"canonical_url": "https://new.test/article"}],
        ["topic"],
        "valve-steamos-3-9-beta-release",
        None,
    )
    assert decision["action"] == "merge"
    assert decision["story_id"] == "strong"
