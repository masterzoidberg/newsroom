"""Evaluation data contract: versioned, machine-validatable case model.

The corpus is stored as JSON on disk and validated into dataclasses here. The
validation is hand-rolled (no external schema dependency) so that the contract is
explicit, stable, and testable in any environment. Every field is described by
the mapping in :data:`CASE_FIELD_SPEC` and enforced by :func:`validate_case`.

Referential integrity rules enforced here:

- every ``gold_group`` references only known candidate ids;
- every ``gold_claim`` references a known gold group (``event_id``);
- every ``gold_evidence`` references a known claim id and a known candidate id;
- every ``contradiction`` references a known claim id and a known evidence id;
- ``noise_candidates`` and ``expected_primary_sources`` reference known ids;
- candidate ids are unique within a case.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from . import (
    SCHEMA_VERSION,
    CASE_TYPES,
    CLAIM_STATES,
    EVIDENCE_RELATIONSHIPS,
    IMPORTANCES,
    MONITOR_TARGET_KINDS,
)

_CASE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class ValidationError(ValueError):
    """Raised when a corpus or fixture document fails the data contract."""


# ---------------------------------------------------------------------------
# Enums (canonical truth for the evaluation contract)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MonitoredTarget:
    kind: str
    ref: str


@dataclass(frozen=True)
class Provenance:
    source: str
    note: str = ""
    source_db: Optional[str] = None


@dataclass(frozen=True)
class ObservationWindow:
    start: Optional[str] = None
    end: Optional[str] = None


@dataclass(frozen=True)
class CandidateDocument:
    candidate_id: str
    canonical_url: str
    title: str
    source: Optional[str] = None
    publisher: Optional[str] = None
    published_at: Optional[str] = None
    retrieved_at: Optional[str] = None
    content_hash: Optional[str] = None
    content_type: str = "metadata"
    excerpt: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class GoldEventGroup:
    event_id: str
    candidate_ids: tuple[str, ...]
    rationale: str = ""
    must_not_merge_with: tuple[str, ...] = ()


@dataclass(frozen=True)
class GoldClaim:
    claim_id: str
    event_id: str
    proposition: str
    importance: str = "relevant"
    expected_state: str = "supported"
    supersedes_claim_id: Optional[str] = None
    rationale: str = ""


@dataclass(frozen=True)
class GoldEvidenceSpan:
    evidence_id: str
    claim_id: str
    candidate_id: str
    excerpt: str
    locator: Optional[str] = None
    relationship: str = "supports"
    span_hash: Optional[str] = None


@dataclass(frozen=True)
class Contradiction:
    claim_id: str
    evidence_id: str
    note: str = ""


@dataclass(frozen=True)
class MaterialChange:
    event_id: str
    claim_id: Optional[str] = None
    description: str = ""
    from_state: Optional[str] = None
    to_state: Optional[str] = None


@dataclass(frozen=True)
class EvaluationCase:
    schema_version: int
    case_id: str
    title: str
    description: str
    case_type: str
    monitored_targets: tuple[MonitoredTarget, ...]
    observation_window: ObservationWindow
    provenance: Provenance
    reviewer_notes: str
    candidates: tuple[CandidateDocument, ...]
    gold_groups: tuple[GoldEventGroup, ...]
    gold_claims: tuple[GoldClaim, ...]
    gold_evidence: tuple[GoldEvidenceSpan, ...]
    expected_primary_sources: tuple[str, ...] = ()
    noise_candidates: tuple[str, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()
    material_changes: tuple[MaterialChange, ...] = ()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _req_str(obj: dict, key: str, *, allow_empty: bool = False) -> str:
    val = obj.get(key)
    if not isinstance(val, str):
        raise ValidationError(f"{key!r} must be a string, got {type(val).__name__}")
    if not allow_empty and not val.strip():
        raise ValidationError(f"{key!r} must be non-empty")
    return val


def _opt_str(obj: dict, key: str) -> Optional[str]:
    val = obj.get(key)
    if val is None:
        return None
    if not isinstance(val, str):
        raise ValidationError(f"{key!r} must be a string or null")
    if not val.strip():
        return None
    return val


def _req_list(obj: dict, key: str) -> list:
    val = obj.get(key, [])
    if not isinstance(val, list):
        raise ValidationError(f"{key!r} must be a list")
    return val


def _enum(value: Any, allowed: frozenset, name: str) -> str:
    if value not in allowed:
        raise ValidationError(
            f"invalid {name!r}: {value!r}; allowed: {sorted(allowed)}"
        )
    return value


def _parse_timestamp(value: Optional[str], name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) < 10:
        raise ValidationError(f"{name!r} must be an ISO-8601 string or null")
    return value


# ---------------------------------------------------------------------------
# Case validation
# ---------------------------------------------------------------------------


def _validate_candidate(raw: dict, index: int) -> CandidateDocument:
    if not isinstance(raw, dict):
        raise ValidationError(f"candidate[{index}] must be an object")
    candidate_id = _req_str(raw, "candidate_id")
    if not _CASE_ID_RE.match(candidate_id):
        raise ValidationError(f"candidate[{index}].candidate_id has invalid id {candidate_id!r}")
    return CandidateDocument(
        candidate_id=candidate_id,
        canonical_url=_req_str(raw, "canonical_url"),
        title=_req_str(raw, "title"),
        source=_opt_str(raw, "source"),
        publisher=_opt_str(raw, "publisher"),
        published_at=_parse_timestamp(_opt_str(raw, "published_at"), "published_at"),
        retrieved_at=_parse_timestamp(_opt_str(raw, "retrieved_at"), "retrieved_at"),
        content_hash=_opt_str(raw, "content_hash"),
        content_type=_req_str(raw, "content_type"),
        excerpt=_opt_str(raw, "excerpt"),
        notes=_opt_str(raw, "notes"),
    )


def _validate_group(raw: dict, index: int) -> GoldEventGroup:
    if not isinstance(raw, dict):
        raise ValidationError(f"gold_groups[{index}] must be an object")
    event_id = _req_str(raw, "event_id")
    ids = _req_list(raw, "candidate_ids")
    if not ids or not all(isinstance(i, str) for i in ids):
        raise ValidationError(f"gold_groups[{index}].candidate_ids must be a non-empty list of strings")
    must_not = _req_list(raw, "must_not_merge_with") if "must_not_merge_with" in raw else []
    return GoldEventGroup(
        event_id=event_id,
        candidate_ids=tuple(ids),
        rationale=_opt_str(raw, "rationale") or "",
        must_not_merge_with=tuple(must_not),
    )


def _validate_claim(raw: dict, index: int) -> GoldClaim:
    if not isinstance(raw, dict):
        raise ValidationError(f"gold_claims[{index}] must be an object")
    return GoldClaim(
        claim_id=_req_str(raw, "claim_id"),
        event_id=_req_str(raw, "event_id"),
        proposition=_req_str(raw, "proposition"),
        importance=_enum(_req_str(raw, "importance"), IMPORTANCES, "importance"),
        expected_state=_enum(_req_str(raw, "expected_state"), CLAIM_STATES, "expected_state"),
        supersedes_claim_id=_opt_str(raw, "supersedes_claim_id"),
        rationale=_opt_str(raw, "rationale") or "",
    )


def _validate_evidence(raw: dict, index: int) -> GoldEvidenceSpan:
    if not isinstance(raw, dict):
        raise ValidationError(f"gold_evidence[{index}] must be an object")
    return GoldEvidenceSpan(
        evidence_id=_req_str(raw, "evidence_id"),
        claim_id=_req_str(raw, "claim_id"),
        candidate_id=_req_str(raw, "candidate_id"),
        excerpt=_req_str(raw, "excerpt"),
        locator=_opt_str(raw, "locator"),
        relationship=_enum(
            _req_str(raw, "relationship"),
            EVIDENCE_RELATIONSHIPS,
            "relationship",
        ),
        span_hash=_opt_str(raw, "span_hash"),
    )


def validate_case(data: dict) -> EvaluationCase:
    """Validate a raw case dict and return a typed :class:`EvaluationCase`.

    Raises :class:`ValidationError` with a precise message on the first problem.
    """
    if not isinstance(data, dict):
        raise ValidationError("case must be a JSON object")

    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValidationError(
            f"unsupported schema_version {version!r}; expected {SCHEMA_VERSION}"
        )

    case_id = _req_str(data, "case_id")
    if not _CASE_ID_RE.match(case_id):
        raise ValidationError(f"invalid case_id {case_id!r}")

    case_type = _enum(_req_str(data, "case_type"), CASE_TYPES, "case_type")

    targets = tuple(
        MonitoredTarget(
            kind=_enum(_req_str(t, "kind"), MONITOR_TARGET_KINDS, "monitored_target.kind"),
            ref=_req_str(t, "ref"),
        )
        for t in _req_list(data, "monitored_targets")
    )
    if not targets:
        raise ValidationError("monitored_targets must not be empty")

    win = data.get("observation_window") or {}
    if not isinstance(win, dict):
        raise ValidationError("observation_window must be an object")

    prov = data.get("provenance") or {}
    if not isinstance(prov, dict):
        raise ValidationError("provenance must be an object")

    candidates = tuple(
        _validate_candidate(c, i) for i, c in enumerate(_req_list(data, "candidates"))
    )
    if not candidates:
        raise ValidationError("candidates must not be empty")

    candidate_ids = {c.candidate_id for c in candidates}
    if len(candidate_ids) != len(candidates):
        raise ValidationError("duplicate candidate_id values")

    groups = tuple(
        _validate_group(g, i) for i, g in enumerate(_req_list(data, "gold_groups"))
    )
    claims = tuple(
        _validate_claim(c, i) for i, c in enumerate(_req_list(data, "gold_claims"))
    )
    evidence = tuple(
        _validate_evidence(e, i) for i, e in enumerate(_req_list(data, "gold_evidence"))
    )
    contradictions = tuple(
        Contradiction(
            claim_id=_req_str(c, "claim_id"),
            evidence_id=_req_str(c, "evidence_id"),
            note=_opt_str(c, "note") or "",
        )
        for c in _req_list(data, "contradictions")
    )

    def _mk_material_change(raw: dict) -> MaterialChange:
        return MaterialChange(
            event_id=_req_str(raw, "event_id"),
            claim_id=_opt_str(raw, "claim_id"),
            description=_opt_str(raw, "description") or "",
            from_state=_opt_str(raw, "from_state"),
            to_state=_opt_str(raw, "to_state"),
        )

    material_changes = tuple(_mk_material_change(m) for m in _req_list(data, "material_changes"))

    expected_primary = tuple(_req_list(data, "expected_primary_sources"))
    noise = tuple(_req_list(data, "noise_candidates"))

    # --- Referential integrity -------------------------------------------
    group_by_id = {g.event_id: g for g in groups}
    claim_by_id = {c.claim_id: c for c in claims}
    evidence_by_id = {e.evidence_id: e for e in evidence}

    seen_group_ids: set[str] = set()
    for g in groups:
        if g.event_id in seen_group_ids:
            raise ValidationError(f"duplicate gold_group event_id {g.event_id!r}")
        seen_group_ids.add(g.event_id)
        for cid in g.candidate_ids:
            if cid not in candidate_ids:
                raise ValidationError(f"gold_group {g.event_id!r} references unknown candidate {cid!r}")
        for cid in g.must_not_merge_with:
            if cid not in candidate_ids:
                raise ValidationError(f"gold_group {g.event_id!r} must_not_merge_with unknown candidate {cid!r}")

    for c in claims:
        if c.event_id not in group_by_id:
            raise ValidationError(f"gold_claim {c.claim_id!r} references unknown event {c.event_id!r}")
        if c.supersedes_claim_id is not None and c.supersedes_claim_id not in claim_by_id:
            raise ValidationError(f"gold_claim {c.claim_id!r} supersedes unknown claim {c.supersedes_claim_id!r}")

    for e in evidence:
        if e.claim_id not in claim_by_id:
            raise ValidationError(f"gold_evidence {e.evidence_id!r} references unknown claim {e.claim_id!r}")
        if e.candidate_id not in candidate_ids:
            raise ValidationError(f"gold_evidence {e.evidence_id!r} references unknown candidate {e.candidate_id!r}")

    for c in contradictions:
        if c.claim_id not in claim_by_id:
            raise ValidationError(f"contradiction references unknown claim {c.claim_id!r}")
        if c.evidence_id not in evidence_by_id:
            raise ValidationError(f"contradiction references unknown evidence {c.evidence_id!r}")

    for cid in expected_primary:
        if cid not in candidate_ids:
            raise ValidationError(f"expected_primary_sources references unknown candidate {cid!r}")
    for cid in noise:
        if cid not in candidate_ids:
            raise ValidationError(f"noise_candidates references unknown candidate {cid!r}")

    for m in material_changes:
        if m.event_id not in group_by_id:
            raise ValidationError(f"material_change references unknown event {m.event_id!r}")
        if m.claim_id is not None and m.claim_id not in claim_by_id:
            raise ValidationError(f"material_change references unknown claim {m.claim_id!r}")

    return EvaluationCase(
        schema_version=version,
        case_id=case_id,
        title=_req_str(data, "title"),
        description=_req_str(data, "description"),
        case_type=case_type,
        monitored_targets=targets,
        observation_window=ObservationWindow(
            start=_parse_timestamp(_opt_str(win, "start"), "observation_window.start"),
            end=_parse_timestamp(_opt_str(win, "end"), "observation_window.end"),
        ),
        provenance=Provenance(
            source=_req_str(prov, "source"),
            note=_opt_str(prov, "note") or "",
            source_db=_opt_str(prov, "source_db"),
        ),
        reviewer_notes=_opt_str(data, "reviewer_notes") or "",
        candidates=candidates,
        gold_groups=groups,
        gold_claims=claims,
        gold_evidence=evidence,
        expected_primary_sources=expected_primary,
        noise_candidates=noise,
        contradictions=contradictions,
        material_changes=material_changes,
    )


# ---------------------------------------------------------------------------
# Canonical serialization (stable ordering, used for case/fixture hashing)
# ---------------------------------------------------------------------------


def _json_default(o: Any) -> Any:
    if hasattr(o, "__dataclass_fields__"):
        return asdict(o)  # type: ignore[arg-type]
    if isinstance(o, (tuple, set)):
        return list(o)
    raise TypeError(f"not JSON serializable: {type(o).__name__}")


def case_to_dict(case: EvaluationCase) -> dict:
    """Serialize a case back to its canonical dict form (stable ordering)."""
    return json.loads(json.dumps(asdict(case), default=_json_default))


def canonical_json(data: Any) -> str:
    """Deterministic JSON encoding: sorted keys, compact separators, UTF-8."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_json_default)


def content_hash(data: Any) -> str:
    """SHA-256 hex digest of the canonical JSON encoding of ``data``."""
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()
