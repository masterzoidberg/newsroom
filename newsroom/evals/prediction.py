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
from typing import Any, Optional

from .schema import ValidationError
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


def _req(obj: dict, key: str) -> Any:
    if key not in obj:
        raise ValidationError(f"missing required field {key!r}")
    return obj[key]


def _opt_str(obj: dict, key: str) -> Optional[str]:
    v = obj.get(key)
    return v if isinstance(v, str) and v.strip() else None


def validate_prediction(data: dict) -> Prediction:
    """Validate a raw prediction dict into a typed :class:`Prediction`."""
    if not isinstance(data, dict):
        raise ValidationError("prediction must be a JSON object")

    case_id = _req(data, "case_id")
    system = _req(data, "system")

    groups = tuple(
        PredictedStoryGroup(
            story_id=_req(g, "story_id"),
            candidate_ids=tuple(g.get("candidate_ids", [])),
        )
        for g in data.get("story_groups", [])
    )

    claims = tuple(
        PredictedClaim(
            claim_id=_req(c, "claim_id"),
            story_id=_req(c, "story_id"),
            text=_req(c, "text"),
            importance=("major" if c.get("importance") in IMPORTANCES and c.get("importance") == "major" else
                        c.get("importance") if c.get("importance") in IMPORTANCES else "relevant"),
            state=c.get("state") if c.get("state") in CLAIM_STATES else "pending",
        )
        for c in data.get("claims", [])
    )

    evidence = tuple(
        PredictedEvidenceLink(
            claim_id=_req(e, "claim_id"),
            candidate_id=_req(e, "candidate_id"),
            excerpt=e.get("excerpt", ""),
            locator=_opt_str(e, "locator"),
            relationship=(e.get("relationship") if e.get("relationship") in EVIDENCE_RELATIONSHIPS else "supports"),
            span_hash=_opt_str(e, "span_hash"),
        )
        for e in data.get("evidence", [])
    )

    contradictions = tuple(
        PredictedContradiction(
            claim_id=_req(c, "claim_id"),
            candidate_id=_req(c, "candidate_id"),
        )
        for c in data.get("contradictions", [])
    )

    propositions = tuple(
        SynthesizedProposition(
            text=_req(p, "text"),
            claim_ids=tuple(p.get("claim_ids", [])),
        )
        for p in data.get("synthesized_propositions", [])
    )

    usage_raw = data.get("usage", {}) or {}
    usage = UsageRecord(
        acquisition_requests=int(usage_raw.get("acquisition_requests", 0) or 0),
        paid_requests=int(usage_raw.get("paid_requests", 0) or 0),
        local_model_calls=int(usage_raw.get("local_model_calls", 0) or 0),
        frontier_calls=int(usage_raw.get("frontier_calls", 0) or 0),
        latency_ms=int(usage_raw.get("latency_ms", 0) or 0),
        cost_usd=float(usage_raw.get("cost_usd", 0.0) or 0.0),
    )

    return Prediction(
        prediction_id=_req(data, "prediction_id"),
        case_id=case_id,
        system=system,
        story_groups=groups,
        claims=claims,
        evidence=evidence,
        contradictions=contradictions,
        primary_sources=tuple(data.get("primary_sources", [])),
        synthesized_propositions=propositions,
        usage=usage,
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
