"""Prediction contract for scoring.

A "prediction" is the structured output a system-under-test produces for one
evaluation case, expressed in a provider-neutral form. Gold labels live in the
corpus; predictions are compared against them by :mod:`newsroom.evals.metrics`.

The v1 baseline is produced by converting v1 database rows into this same
contract, which is the only way v1 can be meaningfully compared without inventing
claims/evidence it never produced.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Optional

from .schema import EvaluationCase, ValidationError, validate_id
from . import CLAIM_STATES, EVIDENCE_RELATIONSHIPS, IMPORTANCES


@dataclass(frozen=True)
class PredictedStoryGroup:
    story_id: str
    candidate_ids: tuple[str, ...]


@dataclass(frozen=True)
class PredictedClaim:
    claim_id: str
    story_id: str
    text: str
    importance: str = "relevant"
    state: str = "pending"


@dataclass(frozen=True)
class PredictedEvidenceLink:
    claim_id: str
    candidate_id: str
    excerpt: str = ""
    locator: Optional[str] = None
    relationship: str = "supports"
    span_hash: Optional[str] = None


@dataclass(frozen=True)
class PredictedContradiction:
    claim_id: str
    candidate_id: str


@dataclass(frozen=True)
class SynthesizedProposition:
    text: str
    claim_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class UsageRecord:
    acquisition_requests: int = 0
    paid_requests: int = 0
    local_model_calls: int = 0
    frontier_calls: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class Prediction:
    prediction_id: str
    case_id: str
    system: str
    story_groups: tuple[PredictedStoryGroup, ...]
    claims: tuple[PredictedClaim, ...] = ()
    evidence: tuple[PredictedEvidenceLink, ...] = ()
    contradictions: tuple[PredictedContradiction, ...] = ()
    primary_sources: tuple[str, ...] = ()
    synthesized_propositions: tuple[SynthesizedProposition, ...] = ()
    usage: UsageRecord = field(default_factory=UsageRecord)
    semantic_results: dict[str, Any] = field(default_factory=dict)


def _req(obj: dict, key: str) -> Any:
    if not isinstance(obj, dict):
        raise ValidationError("prediction entries must be objects")
    if key not in obj:
        raise ValidationError(f"missing required field {key!r}")
    return obj[key]


def _required_str(obj: dict, key: str) -> str:
    value = _req(obj, key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{key!r} must be a non-empty string")
    return value


def _opt_str(obj: dict, key: str) -> Optional[str]:
    v = obj.get(key)
    if v is None:
        return None
    if not isinstance(v, str):
        raise ValidationError(f"{key!r} must be a string or null")
    return v if v.strip() else None


def _list(obj: dict, key: str, *, default: Optional[list] = None) -> list:
    value = obj[key] if key in obj else (default if default is not None else None)
    if not isinstance(value, list):
        raise ValidationError(f"{key!r} must be a list")
    return value


def _validate_id_list(values: list, name: str) -> tuple[str, ...]:
    result = tuple(
        validate_id(value, f"{name}[{index}]")
        for index, value in enumerate(values)
    )
    if len(set(result)) != len(result):
        raise ValidationError(f"duplicate values in {name}")
    return result


def _validate_usage(raw: Any) -> UsageRecord:
    if raw is None:
        raise ValidationError("usage must be an object")
    if not isinstance(raw, dict):
        raise ValidationError("usage must be an object")

    def nonnegative_int(key: str) -> int:
        value = raw.get(key, 0)
        if type(value) is not int:
            raise ValidationError(f"usage.{key} must be a non-negative integer")
        if value < 0:
            raise ValidationError(f"usage.{key} must be non-negative")
        return value

    cost = raw.get("cost_usd", 0.0)
    if isinstance(cost, bool) or not isinstance(cost, (int, float)):
        raise ValidationError("usage.cost_usd must be a non-negative finite number")
    if not math.isfinite(float(cost)) or cost < 0:
        raise ValidationError("usage.cost_usd must be a non-negative finite number")

    return UsageRecord(
        acquisition_requests=nonnegative_int("acquisition_requests"),
        paid_requests=nonnegative_int("paid_requests"),
        local_model_calls=nonnegative_int("local_model_calls"),
        frontier_calls=nonnegative_int("frontier_calls"),
        latency_ms=nonnegative_int("latency_ms"),
        cost_usd=float(cost),
    )


def validate_prediction(data: dict, case: Optional[EvaluationCase] = None) -> Prediction:
    """Validate a raw prediction dict into a typed :class:`Prediction`."""
    if not isinstance(data, dict):
        raise ValidationError("prediction must be a JSON object")

    prediction_id = validate_id(_req(data, "prediction_id"), "prediction_id")
    case_id = validate_id(_req(data, "case_id"), "case_id")
    system = _required_str(data, "system")
    if case is not None and case_id != case.case_id:
        raise ValidationError(
            f"prediction.case_id {case_id!r} does not match case {case.case_id!r}"
        )

    group_values = _list(data, "story_groups")
    groups_out: list[PredictedStoryGroup] = []
    story_ids: set[str] = set()
    assigned_candidates: dict[str, str] = {}
    case_candidate_ids = {c.candidate_id for c in case.candidates} if case else None
    for index, raw_group in enumerate(group_values):
        if not isinstance(raw_group, dict):
            raise ValidationError(f"story_groups[{index}] must be an object")
        story_id = validate_id(raw_group.get("story_id"), f"story_groups[{index}].story_id")
        if story_id in story_ids:
            raise ValidationError(f"duplicate story_id {story_id!r}")
        story_ids.add(story_id)
        candidate_ids = _validate_id_list(
            _list(raw_group, "candidate_ids", default=[]),
            f"story_groups[{index}].candidate_ids",
        )
        if not candidate_ids:
            raise ValidationError(f"story_groups[{index}].candidate_ids must be non-empty")
        for candidate_id in candidate_ids:
            if case_candidate_ids is not None and candidate_id not in case_candidate_ids:
                raise ValidationError(f"story group references unknown candidate_id {candidate_id!r}")
            previous_story = assigned_candidates.get(candidate_id)
            if previous_story is not None:
                raise ValidationError(
                    f"candidate {candidate_id!r} assigned to multiple predicted groups: "
                    f"{previous_story!r}, {story_id!r}"
                )
            assigned_candidates[candidate_id] = story_id
        groups_out.append(PredictedStoryGroup(story_id=story_id, candidate_ids=candidate_ids))
    groups = tuple(groups_out)

    claims_out: list[PredictedClaim] = []
    claim_ids: set[str] = set()
    for index, raw_claim in enumerate(_list(data, "claims", default=[])):
        if not isinstance(raw_claim, dict):
            raise ValidationError(f"claims[{index}] must be an object")
        claim_id = validate_id(raw_claim.get("claim_id"), f"claims[{index}].claim_id")
        if claim_id in claim_ids:
            raise ValidationError(f"duplicate claim_id {claim_id!r}")
        claim_ids.add(claim_id)
        story_id = validate_id(raw_claim.get("story_id"), f"claims[{index}].story_id")
        if story_id not in story_ids:
            raise ValidationError(f"claims[{index}] references unknown story_id {story_id!r}")
        text = _required_str(raw_claim, "text")
        importance = raw_claim.get("importance", "relevant")
        if not isinstance(importance, str) or importance not in IMPORTANCES:
            raise ValidationError(f"claims[{index}].importance has invalid enum value {importance!r}")
        state = raw_claim.get("state", "pending")
        if not isinstance(state, str) or state not in CLAIM_STATES:
            raise ValidationError(f"claims[{index}].state has invalid enum value {state!r}")
        claims_out.append(
            PredictedClaim(
                claim_id=claim_id,
                story_id=story_id,
                text=text,
                importance=importance,
                state=state,
            )
        )
    claims = tuple(claims_out)

    claim_by_id = {claim.claim_id: claim for claim in claims}
    evidence_out: list[PredictedEvidenceLink] = []
    for index, raw_evidence in enumerate(_list(data, "evidence", default=[])):
        if not isinstance(raw_evidence, dict):
            raise ValidationError(f"evidence[{index}] must be an object")
        claim_id = validate_id(raw_evidence.get("claim_id"), f"evidence[{index}].claim_id")
        if claim_id not in claim_by_id:
            raise ValidationError(f"evidence[{index}] references unknown claim_id {claim_id!r}")
        candidate_id = validate_id(
            raw_evidence.get("candidate_id"), f"evidence[{index}].candidate_id"
        )
        if candidate_id not in assigned_candidates:
            raise ValidationError(f"evidence[{index}] references unknown candidate_id {candidate_id!r}")
        if assigned_candidates[candidate_id] != claim_by_id[claim_id].story_id:
            raise ValidationError(
                f"evidence[{index}] candidate is outside claim story {claim_by_id[claim_id].story_id!r}"
            )
        excerpt = raw_evidence.get("excerpt", "")
        if not isinstance(excerpt, str):
            raise ValidationError(f"evidence[{index}].excerpt must be a string")
        relationship = raw_evidence.get("relationship", "supports")
        if not isinstance(relationship, str) or relationship not in EVIDENCE_RELATIONSHIPS:
            raise ValidationError(
                f"evidence[{index}].relationship has invalid enum value {relationship!r}"
            )
        evidence_out.append(
            PredictedEvidenceLink(
                claim_id=claim_id,
                candidate_id=candidate_id,
                excerpt=excerpt,
                locator=_opt_str(raw_evidence, "locator"),
                relationship=relationship,
                span_hash=_opt_str(raw_evidence, "span_hash"),
            )
        )
    evidence = tuple(evidence_out)

    contradictions_out: list[PredictedContradiction] = []
    for index, raw_contradiction in enumerate(_list(data, "contradictions", default=[])):
        if not isinstance(raw_contradiction, dict):
            raise ValidationError(f"contradictions[{index}] must be an object")
        claim_id = validate_id(raw_contradiction.get("claim_id"), f"contradictions[{index}].claim_id")
        if claim_id not in claim_by_id:
            raise ValidationError(f"contradictions[{index}] references unknown claim_id {claim_id!r}")
        candidate_id = validate_id(
            raw_contradiction.get("candidate_id"), f"contradictions[{index}].candidate_id"
        )
        if candidate_id not in assigned_candidates:
            raise ValidationError(f"contradictions[{index}] references unknown candidate_id {candidate_id!r}")
        if assigned_candidates[candidate_id] != claim_by_id[claim_id].story_id:
            raise ValidationError(
                f"contradictions[{index}] candidate is outside claim story {claim_by_id[claim_id].story_id!r}"
            )
        contradictions_out.append(
            PredictedContradiction(claim_id=claim_id, candidate_id=candidate_id)
        )
    contradictions = tuple(contradictions_out)

    propositions_out: list[SynthesizedProposition] = []
    for index, raw_proposition in enumerate(_list(data, "synthesized_propositions", default=[])):
        if not isinstance(raw_proposition, dict):
            raise ValidationError(f"synthesized_propositions[{index}] must be an object")
        claim_ids_for_prop = _validate_id_list(
            _list(raw_proposition, "claim_ids", default=[]),
            f"synthesized_propositions[{index}].claim_ids",
        )
        unknown_claims = set(claim_ids_for_prop) - claim_ids
        if unknown_claims:
            raise ValidationError(
                f"synthesized_propositions[{index}] references unknown claim_id(s) "
                f"{sorted(unknown_claims)!r}"
            )
        propositions_out.append(
            SynthesizedProposition(
                text=_required_str(raw_proposition, "text"),
                claim_ids=claim_ids_for_prop,
            )
        )
    propositions = tuple(propositions_out)

    predicted_candidate_ids = set(assigned_candidates)
    primary_sources = _validate_id_list(
        _list(data, "primary_sources", default=[]), "primary_sources"
    )
    if not set(primary_sources) <= predicted_candidate_ids:
        raise ValidationError("primary_sources references an unassigned candidate_id")
    usage = _validate_usage(data.get("usage", {}))
    semantic_results = data.get("semantic_results", {})
    if not isinstance(semantic_results, dict):
        raise ValidationError("semantic_results must be an object")
    if any(not isinstance(key, str) or not key.strip() for key in semantic_results):
        raise ValidationError("semantic_results keys must be non-empty strings")

    return Prediction(
        prediction_id=prediction_id,
        case_id=case_id,
        system=system,
        story_groups=groups,
        claims=claims,
        evidence=evidence,
        contradictions=contradictions,
        primary_sources=primary_sources,
        synthesized_propositions=propositions,
        usage=usage,
        semantic_results=dict(semantic_results),
    )


def prediction_to_dict(pred: Prediction) -> dict:
    """Serialize a prediction to a dict (stable field order)."""
    out: dict[str, Any] = {
        "prediction_id": pred.prediction_id,
        "case_id": pred.case_id,
        "system": pred.system,
        "story_groups": [
            {"story_id": g.story_id, "candidate_ids": list(g.candidate_ids)}
            for g in pred.story_groups
        ],
        "claims": [
            {
                "claim_id": c.claim_id,
                "story_id": c.story_id,
                "text": c.text,
                "importance": c.importance,
                "state": c.state,
            }
            for c in pred.claims
        ],
        "evidence": [
            {
                "claim_id": e.claim_id,
                "candidate_id": e.candidate_id,
                "excerpt": e.excerpt,
                "locator": e.locator,
                "relationship": e.relationship,
                "span_hash": e.span_hash,
            }
            for e in pred.evidence
        ],
        "contradictions": [
            {"claim_id": c.claim_id, "candidate_id": c.candidate_id}
            for c in pred.contradictions
        ],
        "primary_sources": list(pred.primary_sources),
        "synthesized_propositions": [
            {"text": p.text, "claim_ids": list(p.claim_ids)}
            for p in pred.synthesized_propositions
        ],
        "semantic_results": dict(pred.semantic_results),
        "usage": {
            "acquisition_requests": pred.usage.acquisition_requests,
            "paid_requests": pred.usage.paid_requests,
            "local_model_calls": pred.usage.local_model_calls,
            "frontier_calls": pred.usage.frontier_calls,
            "latency_ms": pred.usage.latency_ms,
            "cost_usd": pred.usage.cost_usd,
        },
    }
    return out
