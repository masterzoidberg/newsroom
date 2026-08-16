"""Tests for reproducible evaluation metrics."""
from __future__ import annotations

from newsroom.evals.schema import validate_case
from newsroom.evals.prediction import (
    Prediction,
    PredictedStoryGroup,
    PredictedClaim,
    PredictedEvidenceLink,
    PredictedContradiction,
    SynthesizedProposition,
    validate_prediction,
)
from newsroom.evals.metrics import (
    event_metrics,
    claim_metrics,
    evidence_metrics,
    score,
    normalize_text,
)


def _case(**overrides):
    case = {
        "schema_version": 1,
        "case_id": "metric-case",
        "title": "t",
        "description": "d",
        "case_type": "similar_distinct_events",
        "monitored_targets": [{"kind": "topic", "ref": "demo"}],
        "observation_window": {"start": None, "end": None},
        "provenance": {"source": "synthetic"},
        "reviewer_notes": "",
        "candidates": [
            {"candidate_id": "a", "canonical_url": "https://x.test/a", "title": "A", "content_type": "metadata"},
            {"candidate_id": "b", "canonical_url": "https://x.test/b", "title": "B", "content_type": "metadata"},
            {"candidate_id": "c", "canonical_url": "https://x.test/c", "title": "C", "content_type": "metadata"},
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
    return validate_case(case)


def _pred(groups, **kw):
    base = {
        "prediction_id": "p1",
        "case_id": "metric-case",
        "system": "test",
        "story_groups": groups,
    }
    base.update(kw)
    return validate_prediction(base)


# --- Event / story metrics -------------------------------------------------


def test_event_perfect_merge():
    case = _case()
    pred = _pred([{"story_id": "s1", "candidate_ids": ["a", "b"]},
                  {"story_id": "s2", "candidate_ids": ["c"]}])
    m = event_metrics(case, pred)
    assert m.precision == 1.0
    assert m.recall == 1.0
    assert m.false_merge_count == 0
    assert m.false_split_count == 0


def test_event_false_merge():
    case = _case()
    # Predicted all three in one story -> a,b are correct, c wrongly merged.
    pred = _pred([{"story_id": "s1", "candidate_ids": ["a", "b", "c"]}])
    m = event_metrics(case, pred)
    assert m.false_merge_count == 2  # (a,c) and (b,c) wrongly merged
    assert m.false_split_count == 0
    assert m.precision < 1.0


def test_event_false_split():
    case = _case()
    # Predicted every candidate as its own story -> a,b wrongly split.
    pred = _pred([{"story_id": "s1", "candidate_ids": ["a"]},
                  {"story_id": "s2", "candidate_ids": ["b"]},
                  {"story_id": "s3", "candidate_ids": ["c"]}])
    m = event_metrics(case, pred)
    assert m.false_split_count == 1  # (a,b) wrongly split
    assert m.false_merge_count == 0
    assert m.recall == 0.0


def test_event_all_singletons_vacuous_truth():
    case = _case(gold_groups=[
        {"event_id": "e1", "candidate_ids": ["a"]},
        {"event_id": "e2", "candidate_ids": ["b"]},
        {"event_id": "e3", "candidate_ids": ["c"]},
    ])
    pred = _pred([{"story_id": "s1", "candidate_ids": ["a"]},
                  {"story_id": "s2", "candidate_ids": ["b"]},
                  {"story_id": "s3", "candidate_ids": ["c"]}])
    m = event_metrics(case, pred)
    assert m.precision == 1.0
    assert m.recall == 1.0
    assert m.duplicate_rate == 0.0


def test_duplicate_rate():
    case = _case()
    # a,b should be one event, but predicted in two stories -> duplicated event.
    pred = _pred([{"story_id": "s1", "candidate_ids": ["a"]},
                  {"story_id": "s2", "candidate_ids": ["b"]},
                  {"story_id": "s3", "candidate_ids": ["c"]}])
    m = event_metrics(case, pred)
    assert m.duplicate_rate == 0.5  # e1 duplicated, e2 not


# --- Claim metrics ----------------------------------------------------------


def test_claim_recall_and_precision():
    case = _case(gold_claims=[
        {"claim_id": "g1", "event_id": "e1", "proposition": "Acme launched X",
         "importance": "major", "expected_state": "supported"},
        {"claim_id": "g2", "event_id": "e1", "proposition": "Acme has 1M users",
         "importance": "relevant", "expected_state": "supported"},
    ])
    pred = _pred(
        [{"story_id": "s1", "candidate_ids": ["a", "b"]}],
        claims=[
            {"claim_id": "p1", "story_id": "s1", "text": "Acme launched X",
             "importance": "major", "state": "supported"},
            {"claim_id": "p2", "story_id": "s1", "text": "Unrelated claim",
             "importance": "major", "state": "supported"},
        ],
    )
    m = claim_metrics(case, pred)
    assert m.important_claim_recall == 1.0  # g1 matched (major)
    assert m.all_claim_recall == 0.5  # only g1 matched
    assert m.claim_precision == 0.5  # p1 matched, p2 not


def test_claim_match_normalizes_text():
    assert normalize_text("  Acme   Launched X ") == "acme launched x"
    assert normalize_text("Acme-Launched X") == "acme-launched x"


# --- Evidence metrics -------------------------------------------------------


def test_evidence_correctness_and_coverage():
    case = _case(gold_claims=[
        {"claim_id": "g1", "event_id": "e1", "proposition": "Acme launched X",
         "importance": "major", "expected_state": "supported"},
    ], gold_evidence=[
        {"evidence_id": "ev1", "claim_id": "g1", "candidate_id": "a",
         "excerpt": "Acme launched X today", "relationship": "supports"},
    ])
    pred = _pred(
        [{"story_id": "s1", "candidate_ids": ["a", "b"]}],
        claims=[
            {"claim_id": "p1", "story_id": "s1", "text": "Acme launched X",
             "importance": "major", "state": "supported"},
        ],
        evidence=[
            {"claim_id": "p1", "candidate_id": "a", "excerpt": "Acme launched X today"},
        ],
    )
    m = evidence_metrics(case, pred)
    assert m.citation_correctness == 1.0
    assert m.evidence_coverage == 1.0


def test_evidence_wrong_candidate_is_incorrect():
    case = _case(gold_claims=[
        {"claim_id": "g1", "event_id": "e1", "proposition": "Acme launched X",
         "importance": "major", "expected_state": "supported"},
    ], gold_evidence=[
        {"evidence_id": "ev1", "claim_id": "g1", "candidate_id": "a",
         "excerpt": "Acme launched X today", "relationship": "supports"},
    ])
    pred = _pred(
        [{"story_id": "s1", "candidate_ids": ["a", "b"]}],
        claims=[
            {"claim_id": "p1", "story_id": "s1", "text": "Acme launched X",
             "importance": "major", "state": "supported"},
        ],
        evidence=[
            {"claim_id": "p1", "candidate_id": "b", "excerpt": "Acme launched X today"},
        ],
    )
    m = evidence_metrics(case, pred)
    assert m.citation_correctness == 0.0


def test_unsupported_proposition_rate():
    case = _case()
    pred = _pred(
        [{"story_id": "s1", "candidate_ids": ["a", "b"]}],
        claims=[
            {"claim_id": "p1", "story_id": "s1", "text": "X", "importance": "major", "state": "supported"},
        ],
        synthesized_propositions=[
            {"text": "supported proposition", "claim_ids": ["p1"]},
            {"text": "unsupported proposition", "claim_ids": []},
        ],
    )
    m = evidence_metrics(case, pred)
    assert m.unsupported_proposition_rate == 0.5


def test_contradiction_detection_recall():
    case = _case(gold_claims=[
        {"claim_id": "g1", "event_id": "e1", "proposition": "12 injured",
         "importance": "major", "expected_state": "disputed"},
        {"claim_id": "g2", "event_id": "e1", "proposition": "30 injured",
         "importance": "major", "expected_state": "disputed"},
    ], gold_evidence=[
        {"evidence_id": "ev1", "claim_id": "g1", "candidate_id": "a",
         "excerpt": "12 injured", "relationship": "supports"},
        {"evidence_id": "ev2", "claim_id": "g2", "candidate_id": "b",
         "excerpt": "30 injured", "relationship": "supports"},
    ], contradictions=[
        {"claim_id": "g1", "evidence_id": "ev2"},
        {"claim_id": "g2", "evidence_id": "ev1"},
    ])
    pred = _pred(
        [{"story_id": "s1", "candidate_ids": ["a", "b"]}],
        claims=[
            {"claim_id": "p1", "story_id": "s1", "text": "12 injured", "importance": "major"},
            {"claim_id": "p2", "story_id": "s1", "text": "30 injured", "importance": "major"},
        ],
        contradictions=[
            {"claim_id": "p1", "candidate_id": "b"},
        ],
    )
    m = evidence_metrics(case, pred)
    assert m.contradiction_detection == 0.5  # one of two detected


def test_score_result_is_serializable():
    case = _case()
    pred = _pred([{"story_id": "s1", "candidate_ids": ["a", "b"]},
                  {"story_id": "s2", "candidate_ids": ["c"]}])
    r = score(case, pred)
    d = r.as_dict()
    assert d["case_id"] == "metric-case"
    assert d["event"]["precision"] == 1.0
