"""Reproducible evaluation metrics.

Every metric is a pure function over a gold :class:`EvaluationCase` and a
:class:`Prediction`. No network, no database, no randomness. Definitions are
intentionally narrow and are documented in ``docs/EVALUATION.md``.

Event/Story metrics are computed pairwise over candidate documents, which makes
false-merge and false-split symmetric and independent of story identity strings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import combinations
from typing import Iterable, Optional

from .schema import EvaluationCase, content_hash
from .prediction import Prediction, PredictedClaim


def normalize_text(text: str) -> str:
    """Casefold and collapse whitespace for claim/proposition matching."""
    return re.sub(r"\s+", " ", text.casefold()).strip()


# ---------------------------------------------------------------------------
# Event / Story metrics (pairwise over candidate documents)
# ---------------------------------------------------------------------------


def _gold_same_pairs(case: EvaluationCase) -> set[frozenset]:
    """All unordered candidate-id pairs that gold places in the same event."""
    pairs: set[frozenset] = set()
    for group in case.gold_groups:
        for a, b in combinations(group.candidate_ids, 2):
            pairs.add(frozenset((a, b)))
    return pairs


def _pred_same_pairs(pred: Prediction) -> set[frozenset]:
    pairs: set[frozenset] = set()
    for group in pred.story_groups:
        for a, b in combinations(group.candidate_ids, 2):
            pairs.add(frozenset((a, b)))
    return pairs


def _gold_same_map(case: EvaluationCase) -> dict[str, str]:
    """candidate_id -> event_id."""
    m: dict[str, str] = {}
    for group in case.gold_groups:
        for cid in group.candidate_ids:
            m[cid] = group.event_id
    return m


def _pred_same_map(pred: Prediction) -> dict[str, str]:
    m: dict[str, str] = {}
    for group in pred.story_groups:
        for cid in group.candidate_ids:
            m[cid] = group.story_id
    return m


@dataclass(frozen=True)
class EventMetrics:
    precision: float
    recall: float
    f1: float
    false_merge_count: int
    false_split_count: int
    false_merge_rate: float
    false_split_rate: float
    duplicate_rate: float
    gold_event_count: int
    predicted_story_count: int


def event_metrics(case: EvaluationCase, pred: Prediction) -> EventMetrics:
    """Pairwise event clustering metrics plus a per-event duplicate rate."""
    gold_same = _gold_same_pairs(case)
    pred_same = _pred_same_pairs(pred)

    candidate_ids = {c.candidate_id for c in case.candidates}
    all_pairs = {frozenset((a, b)) for a, b in combinations(sorted(candidate_ids), 2)}

    tp = gold_same & pred_same
    fp = pred_same - gold_same  # gold says different, pred says same -> false merge
    fn = gold_same - pred_same  # gold says same, pred says different -> false split

    gold_diff = all_pairs - gold_same
    gold_same_total = len(gold_same)

    # Vacuous truth: when no merges are predicted (or expected), there are no
    # merge errors, so precision/recall are 1.0 rather than undefined/0.0.
    precision = len(tp) / len(pred_same) if pred_same else 1.0
    recall = len(tp) / gold_same_total if gold_same_total else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    false_merge_rate = len(fp) / len(gold_diff) if gold_diff else 0.0
    false_split_rate = len(fn) / gold_same_total if gold_same_total else 0.0

    # Per-event duplicate: a gold event is "duplicated" if more than one
    # predicted story contains >=1 of its candidates.
    gold_map = _gold_same_map(case)
    pred_map = _pred_same_map(pred)
    duplicated = 0
    for group in case.gold_groups:
        story_ids = {pred_map[cid] for cid in group.candidate_ids if cid in pred_map}
        if len(story_ids) > 1:
            duplicated += 1
    duplicate_rate = duplicated / len(case.gold_groups) if case.gold_groups else 0.0

    return EventMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        false_merge_count=len(fp),
        false_split_count=len(fn),
        false_merge_rate=false_merge_rate,
        false_split_rate=false_split_rate,
        duplicate_rate=duplicate_rate,
        gold_event_count=len(case.gold_groups),
        predicted_story_count=len(pred.story_groups),
    )


# ---------------------------------------------------------------------------
# Claim metrics
# ---------------------------------------------------------------------------


def _match_claims(case: EvaluationCase, pred: Prediction) -> tuple[dict[str, Optional[str]], dict[str, Optional[str]]]:
    """Match predicted claims to gold claims by normalized text.

    Returns (gold_claim_id -> matched predicted claim_id or None,
             predicted_claim_id -> matched gold claim_id or None).
    """
    gold_by_norm: dict[str, str] = {}
    for gc in case.gold_claims:
        gold_by_norm.setdefault(normalize_text(gc.proposition), gc.claim_id)

    gold_to_pred: dict[str, Optional[str]] = {}
    pred_to_gold: dict[str, Optional[str]] = {}

    used_gold: set[str] = set()
    for pc in pred.claims:
        norm = normalize_text(pc.text)
        gold_id = gold_by_norm.get(norm)
        if gold_id is not None and gold_id not in used_gold:
            pred_to_gold[pc.claim_id] = gold_id
            gold_to_pred[gold_id] = pc.claim_id
            used_gold.add(gold_id)
        else:
            pred_to_gold[pc.claim_id] = None

    for gc in case.gold_claims:
        gold_to_pred.setdefault(gc.claim_id, None)

    return gold_to_pred, pred_to_gold


@dataclass(frozen=True)
class ClaimMetrics:
    important_claim_recall: float
    all_claim_recall: float
    claim_precision: float
    important_gold_count: int
    gold_claim_count: int
    predicted_claim_count: int


def claim_metrics(case: EvaluationCase, pred: Prediction) -> ClaimMetrics:
    gold_to_pred, pred_to_gold = _match_claims(case, pred)

    important = [gc for gc in case.gold_claims if gc.importance == "major"]
    important_hit = sum(1 for gc in important if gold_to_pred.get(gc.claim_id))
    all_hit = sum(1 for gc in case.gold_claims if gold_to_pred.get(gc.claim_id))

    important_recall = important_hit / len(important) if important else 0.0
    all_recall = all_hit / len(case.gold_claims) if case.gold_claims else 0.0
    precision = (
        sum(1 for gid in pred_to_gold.values() if gid is not None) / len(pred.claims)
        if pred.claims
        else 0.0
    )

    return ClaimMetrics(
        important_claim_recall=important_recall,
        all_claim_recall=all_recall,
        claim_precision=precision,
        important_gold_count=len(important),
        gold_claim_count=len(case.gold_claims),
        predicted_claim_count=len(pred.claims),
    )


# ---------------------------------------------------------------------------
# Evidence metrics
# ---------------------------------------------------------------------------


def _evidence_key(span_hash: Optional[str], candidate_id: str, excerpt: str) -> tuple:
    return (span_hash, candidate_id, normalize_text(excerpt))


@dataclass(frozen=True)
class EvidenceMetrics:
    citation_correctness: float
    evidence_coverage: float
    contradiction_detection: float
    unsupported_proposition_rate: float
    gold_evidence_count: int
    predicted_link_count: int
    gold_contradiction_count: int
    synthesized_proposition_count: int


def evidence_metrics(case: EvaluationCase, pred: Prediction) -> EvidenceMetrics:
    # Map predicted claim -> matched gold claim.
    _, pred_to_gold = _match_claims(case, pred)

    # Index gold evidence by (claim_id, candidate_id, span_hash or excerpt).
    gold_keys: dict[str, set[tuple]] = {}
    for ge in case.gold_evidence:
        keys = gold_keys.setdefault(ge.claim_id, set())
        keys.add(_evidence_key(ge.span_hash, ge.candidate_id, ge.excerpt))

    correct_links = 0
    for link in pred.evidence:
        gold_claim = pred_to_gold.get(link.claim_id)
        if gold_claim is None:
            continue
        keys = gold_keys.get(gold_claim, set())
        if _evidence_key(link.span_hash, link.candidate_id, link.excerpt) in keys:
            correct_links += 1

    citation_correctness = (
        correct_links / len(pred.evidence) if pred.evidence else 0.0
    )

    # Evidence coverage: gold evidence spans matched by at least one correct link.
    matched_gold_evidence: set[str] = set()
    for link in pred.evidence:
        gold_claim = pred_to_gold.get(link.claim_id)
        if gold_claim is None:
            continue
        keys = gold_keys.get(gold_claim, set())
        if _evidence_key(link.span_hash, link.candidate_id, link.excerpt) in keys:
            for ge in case.gold_evidence:
                if ge.claim_id == gold_claim and _evidence_key(ge.span_hash, ge.candidate_id, ge.excerpt) == _evidence_key(link.span_hash, link.candidate_id, link.excerpt):
                    matched_gold_evidence.add(ge.evidence_id)

    evidence_coverage = (
        len(matched_gold_evidence) / len(case.gold_evidence)
        if case.gold_evidence
        else 0.0
    )

    # Contradiction detection: recall of gold contradictions.
    pred_contradictions = {
        (pred_to_gold.get(c.claim_id), c.candidate_id) for c in pred.contradictions
    }
    gold_contradiction_pairs = set()
    for gc in case.contradictions:
        # Resolve evidence -> (claim_id, candidate_id).
        for ge in case.gold_evidence:
            if ge.evidence_id == gc.evidence_id:
                gold_contradiction_pairs.add((gc.claim_id, ge.candidate_id))
                break

    detected = sum(1 for p in gold_contradiction_pairs if p in pred_contradictions)
    contradiction_detection = (
        detected / len(gold_contradiction_pairs) if gold_contradiction_pairs else 0.0
    )

    # Unsupported synthesized proposition rate.
    valid_claim_ids = {pc.claim_id for pc in pred.claims}
    propositions = pred.synthesized_propositions
    unsupported = sum(
        1 for p in propositions if not any(cid in valid_claim_ids for cid in p.claim_ids)
    )
    unsupported_rate = unsupported / len(propositions) if propositions else 0.0

    return EvidenceMetrics(
        citation_correctness=citation_correctness,
        evidence_coverage=evidence_coverage,
        contradiction_detection=contradiction_detection,
        unsupported_proposition_rate=unsupported_rate,
        gold_evidence_count=len(case.gold_evidence),
        predicted_link_count=len(pred.evidence),
        gold_contradiction_count=len(gold_contradiction_pairs),
        synthesized_proposition_count=len(propositions),
    )


# ---------------------------------------------------------------------------
# Primary source discovery
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PrimarySourceMetrics:
    primary_source_recall: float
    primary_source_precision: float
    false_primary_count: int
    expected_count: int
    predicted_count: int


def primary_source_metrics(case: EvaluationCase, pred: Prediction) -> PrimarySourceMetrics:
    expected = set(case.expected_primary_sources)
    predicted = set(pred.primary_sources)
    hit = len(expected & predicted)
    # Vacuous truth: with no expectation (or no prediction) there is no error.
    recall = hit / len(expected) if expected else 1.0
    precision = hit / len(predicted) if predicted else 1.0
    false_primary = len(predicted - expected)
    return PrimarySourceMetrics(
        primary_source_recall=recall,
        primary_source_precision=precision,
        false_primary_count=false_primary,
        expected_count=len(expected),
        predicted_count=len(predicted),
    )


# ---------------------------------------------------------------------------
# Economics / operations
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EconomicsMetrics:
    acquisition_requests: int
    paid_requests: int
    local_model_calls: int
    frontier_calls: int
    latency_ms: int
    cost_usd: float
    useful_story_count: int
    cost_per_useful_story: float


def economics_metrics(case: EvaluationCase, pred: Prediction) -> EconomicsMetrics:
    u = pred.usage
    # A predicted story is "useful" if it contains a candidate that gold groups
    # into some (non-noise) event.
    gold_candidates = {cid for g in case.gold_groups for cid in g.candidate_ids}
    useful = sum(
        1 for g in pred.story_groups if any(cid in gold_candidates for cid in g.candidate_ids)
    )
    cost_per = (u.cost_usd / useful) if useful else 0.0
    return EconomicsMetrics(
        acquisition_requests=u.acquisition_requests,
        paid_requests=u.paid_requests,
        local_model_calls=u.local_model_calls,
        frontier_calls=u.frontier_calls,
        latency_ms=u.latency_ms,
        cost_usd=u.cost_usd,
        useful_story_count=useful,
        cost_per_useful_story=cost_per,
    )


# ---------------------------------------------------------------------------
# Aggregate result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScoreResult:
    case_id: str
    system: str
    event: EventMetrics
    claim: ClaimMetrics
    evidence: EvidenceMetrics
    primary_source: PrimarySourceMetrics
    economics: EconomicsMetrics

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "system": self.system,
            "event": {
                "precision": round(self.event.precision, 4),
                "recall": round(self.event.recall, 4),
                "f1": round(self.event.f1, 4),
                "false_merge_count": self.event.false_merge_count,
                "false_split_count": self.event.false_split_count,
                "false_merge_rate": round(self.event.false_merge_rate, 4),
                "false_split_rate": round(self.event.false_split_rate, 4),
                "duplicate_rate": round(self.event.duplicate_rate, 4),
                "gold_event_count": self.event.gold_event_count,
                "predicted_story_count": self.event.predicted_story_count,
            },
            "claim": {
                "important_claim_recall": round(self.claim.important_claim_recall, 4),
                "all_claim_recall": round(self.claim.all_claim_recall, 4),
                "claim_precision": round(self.claim.claim_precision, 4),
                "important_gold_count": self.claim.important_gold_count,
                "gold_claim_count": self.claim.gold_claim_count,
                "predicted_claim_count": self.claim.predicted_claim_count,
            },
            "evidence": {
                "citation_correctness": round(self.evidence.citation_correctness, 4),
                "evidence_coverage": round(self.evidence.evidence_coverage, 4),
                "contradiction_detection": round(self.evidence.contradiction_detection, 4),
                "unsupported_proposition_rate": round(self.evidence.unsupported_proposition_rate, 4),
                "gold_evidence_count": self.evidence.gold_evidence_count,
                "predicted_link_count": self.evidence.predicted_link_count,
                "gold_contradiction_count": self.evidence.gold_contradiction_count,
                "synthesized_proposition_count": self.evidence.synthesized_proposition_count,
            },
            "primary_source": {
                "primary_source_recall": round(self.primary_source.primary_source_recall, 4),
                "primary_source_precision": round(self.primary_source.primary_source_precision, 4),
                "false_primary_count": self.primary_source.false_primary_count,
                "expected_count": self.primary_source.expected_count,
                "predicted_count": self.primary_source.predicted_count,
            },
            "economics": {
                "acquisition_requests": self.economics.acquisition_requests,
                "paid_requests": self.economics.paid_requests,
                "local_model_calls": self.economics.local_model_calls,
                "frontier_calls": self.economics.frontier_calls,
                "latency_ms": self.economics.latency_ms,
                "cost_usd": round(self.economics.cost_usd, 6),
                "useful_story_count": self.economics.useful_story_count,
                "cost_per_useful_story": round(self.economics.cost_per_useful_story, 6),
            },
        }


def score(case: EvaluationCase, pred: Prediction) -> ScoreResult:
    """Score one prediction against one gold case."""
    return ScoreResult(
        case_id=case.case_id,
        system=pred.system,
        event=event_metrics(case, pred),
        claim=claim_metrics(case, pred),
        evidence=evidence_metrics(case, pred),
        primary_source=primary_source_metrics(case, pred),
        economics=economics_metrics(case, pred),
    )
