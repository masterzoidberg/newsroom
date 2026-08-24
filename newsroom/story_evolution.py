"""Conservative Story evolution, provenance, and novelty services.

This module keeps event identity deterministic at the persistence boundary. Text
and embedding signals narrow candidates; they do not silently turn an ambiguous
match into a merge. The database service below records every accepted link and
classification as append-only provenance.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import storage
from .domain import DomainConflict, DomainNotFound, DomainValidation, new_id, normalized_text, utc_now
from .event_sig import normalize_event_signature
from .similarity import headline_similarity
from .story_context import current_story_documents, current_story_document_ids
from .url_norm import normalize_url


UPDATE_CLASSES = (
    "new_story",
    "duplicate",
    "corroboration",
    "contradiction",
    "qualification",
    "correction",
    "material_update",
)

LINEAGE_RELATIONSHIPS = (
    "cites",
    "syndicated_from",
    "wire_propagation",
    "rewritten_from",
    "common_primary_document",
)

_DUPLICATING_LINEAGE = frozenset({"syndicated_from", "wire_propagation", "rewritten_from"})
_CORRECTION_MARKERS = frozenset({"correct", "corrected", "correction", "erratum", "revised", "revision", "error"})
_CONTRADICTION_MARKERS = frozenset({"denied", "denies", "disputes", "disputed", "false", "incorrect", "contradicts"})
_MATERIAL_MARKERS = frozenset({
    "adds", "added", "approved", "blocked", "changed", "change", "definitive",
    "reached", "reaches", "revised", "revises", "rises", "rose", "settled",
})


def _as_set(value: Any) -> frozenset[str]:
    if value is None:
        return frozenset()
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(normalized_text(str(item)) for item in values if str(item).strip())


def _claim_keys(values: Any) -> frozenset[str]:
    if values is None:
        return frozenset()
    items = [values] if isinstance(values, str) else values
    if not isinstance(items, (list, tuple, set, frozenset)):
        return frozenset()
    result: set[str] = set()
    for item in items:
        proposition = item.get("proposition", item.get("text", "")) if isinstance(item, Mapping) else item
        if isinstance(proposition, str) and proposition.strip():
            result.add(normalized_text(proposition))
    return frozenset(result)


def _tokens(value: str) -> frozenset[str]:
    return frozenset(re.findall(r"[\w][\w'-]*", normalized_text(value)))


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 0.0
    return len(left & right) / len(left | right)


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _time_compatible(left: Any, right: Any, hours: int) -> bool:
    a, b = _parse_time(left), _parse_time(right)
    return a is None or b is None or abs((a - b).total_seconds()) <= hours * 3600


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    denominator = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return numerator / denominator if denominator else 0.0


@dataclass(frozen=True)
class StoryCandidate:
    """The bounded identity signals used by the resolver."""

    id: str
    headline: str
    canonical_url: str | None = None
    document_id: str | None = None
    published_at: str | None = None
    created_at: str | None = None
    event_key: str | None = None
    entities: frozenset[str] = field(default_factory=frozenset)
    locations: frozenset[str] = field(default_factory=frozenset)
    claim_keys: frozenset[str] = field(default_factory=frozenset)
    topic_ids: frozenset[str] = field(default_factory=frozenset)
    subject_ids: frozenset[str] = field(default_factory=frozenset)
    embedding: tuple[float, ...] = ()
    exclusion_keys: frozenset[str] = field(default_factory=frozenset)
    text: str = ""
    source_ids: frozenset[str] = field(default_factory=frozenset)
    data_truncated: bool = False

    def __post_init__(self) -> None:
        for name in ("entities", "locations", "claim_keys", "topic_ids", "subject_ids", "source_ids", "exclusion_keys"):
            object.__setattr__(self, name, _as_set(getattr(self, name)))
        object.__setattr__(self, "event_key", normalize_event_signature(self.event_key) if self.event_key else None)
        object.__setattr__(self, "embedding", tuple(float(value) for value in self.embedding))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "StoryCandidate":
        return cls(
            id=str(value["id"]),
            headline=str(value.get("headline", "")),
            text=str(value.get("text") or value.get("excerpt") or value.get("content_text") or ""),
            canonical_url=value.get("canonical_url"),
            document_id=value.get("document_id"),
            published_at=value.get("published_at"),
            created_at=value.get("created_at"),
            event_key=value.get("event_key") or value.get("event_key_hint"),
            entities=_as_set(value.get("entities")),
            locations=_as_set(value.get("locations")),
            claim_keys=_claim_keys(value.get("claim_keys") or value.get("claims")),
            topic_ids=_as_set(value.get("topic_ids")),
            subject_ids=_as_set(value.get("subject_ids")),
            source_ids=_as_set(value.get("source_ids")),
            embedding=tuple(value.get("embedding") or ()),
            exclusion_keys=_as_set(value.get("exclusion_keys")),
            data_truncated=bool(value.get("data_truncated", False)),
        )


@dataclass(frozen=True)
class Resolution:
    action: str
    story_id: str | None
    classification: str
    via: str
    score: float
    signals: dict[str, Any]
    ambiguous: bool = False
    adjudicated: bool = False


def _candidate_signals(incoming: StoryCandidate, existing: StoryCandidate, time_window_hours: int) -> dict[str, Any]:
    try:
        incoming_url = normalize_url(incoming.canonical_url) if incoming.canonical_url else None
        existing_url = normalize_url(existing.canonical_url) if existing.canonical_url else None
    except ValueError:
        incoming_url = existing_url = None
    headline = headline_similarity(incoming.headline, existing.headline)
    text_overlap = _jaccard(_tokens(incoming.text), _tokens(existing.text))
    incoming_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", f"{incoming.headline} {incoming.text}"))
    existing_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", f"{existing.headline} {existing.text}"))
    incoming_markers = _tokens(f"{incoming.headline} {incoming.text}")
    entity_overlap = _jaccard(incoming.entities, existing.entities)
    location_overlap = _jaccard(incoming.locations, existing.locations)
    claim_overlap = _jaccard(incoming.claim_keys, existing.claim_keys)
    incoming_text_tokens = _tokens(f"{incoming.headline} {incoming.text}")
    existing_text_tokens = _tokens(f"{existing.headline} {existing.text}")
    shared_claims = incoming.claim_keys & existing.claim_keys
    same_event_key = bool(incoming.event_key and existing.event_key and incoming.event_key == existing.event_key)
    event_key_conflict = bool(incoming.event_key and existing.event_key and incoming.event_key != existing.event_key)
    location_conflict = bool(incoming.locations and existing.locations and not incoming.locations & existing.locations)
    return {
        "url_identity": bool(incoming.document_id and incoming.document_id == existing.document_id) or bool(incoming_url and incoming_url == existing_url),
        "time_compatible": _time_compatible(incoming.published_at, existing.published_at or existing.created_at, time_window_hours),
        "headline_similarity": round(headline.headline_sim, 6),
        "headline_level": headline.level,
        "text_overlap": round(text_overlap, 6),
        "text_overlap_count": len(incoming_text_tokens & existing_text_tokens),
        "numeric_change": bool(incoming_numbers and existing_numbers and incoming_numbers != existing_numbers),
        "correction_marker": bool(incoming_markers & _CORRECTION_MARKERS),
        "contradiction_marker": bool(incoming_markers & _CONTRADICTION_MARKERS),
        "material_marker": bool(incoming_markers & _MATERIAL_MARKERS),
        "entity_overlap": round(entity_overlap, 6),
        "location_overlap": round(location_overlap, 6),
        "claim_exact_match": bool(shared_claims),
        "source_overlap": round(_jaccard(incoming.source_ids, existing.source_ids), 6),
        "topic_overlap": round(_jaccard(incoming.topic_ids, existing.topic_ids), 6),
        "subject_overlap": round(_jaccard(incoming.subject_ids, existing.subject_ids), 6),
        "story_data_truncated": existing.data_truncated,
        "location_conflict": location_conflict,
        "shared_claim_overlap": round(claim_overlap, 6),
        "semantic_similarity": round(_cosine(incoming.embedding, existing.embedding), 6),
        "same_event_key": same_event_key,
        "event_key_conflict": event_key_conflict,
        "explicit_exclusion": bool(
            incoming.exclusion_keys & existing.exclusion_keys
            or existing.event_key in incoming.exclusion_keys
            or incoming.event_key in existing.exclusion_keys
        ),
    }


def candidate_signals(
    incoming: StoryCandidate,
    existing: StoryCandidate,
    time_window_hours: int = 72,
) -> dict[str, Any]:
    """Expose the shared deterministic identity signals to side-effect-free resolvers."""

    return _candidate_signals(incoming, existing, time_window_hours)


def resolve_candidate(
    incoming: StoryCandidate | Mapping[str, Any],
    existing: Sequence[StoryCandidate | Mapping[str, Any]],
    *,
    time_window_hours: int = 72,
    ambiguity_margin: float = 0.10,
    adjudicator: Callable[[StoryCandidate, StoryCandidate, Mapping[str, Any]], Any] | None = None,
) -> Resolution:
    """Resolve one candidate conservatively against already-retrieved Stories."""
    incoming_candidate = incoming if isinstance(incoming, StoryCandidate) else StoryCandidate.from_mapping(incoming)
    candidates = sorted(
        (item if isinstance(item, StoryCandidate) else StoryCandidate.from_mapping(item) for item in existing),
        key=lambda item: item.id,
    )
    scored: list[tuple[float, StoryCandidate, dict[str, Any], str]] = []
    for candidate in candidates:
        signals = _candidate_signals(incoming_candidate, candidate, time_window_hours)
        if signals["url_identity"]:
            return Resolution("merge", candidate.id, "duplicate", "url_identity", 1.0, signals)
        time_gate = signals["time_compatible"] or (
            signals["same_event_key"]
            and (signals["text_overlap"] >= 0.20 or signals["shared_claim_overlap"] >= 0.50)
        )
        if not time_gate or signals["event_key_conflict"] or signals["explicit_exclusion"]:
            continue
        score = max(
            signals["shared_claim_overlap"],
            signals["semantic_similarity"],
            signals["headline_similarity"],
            signals["text_overlap"],
        )
        if signals["same_event_key"]:
            score += 0.25
        if signals["entity_overlap"] > 0:
            score += 0.10 * signals["entity_overlap"]
        if signals["location_overlap"] > 0:
            score += 0.10 * signals["location_overlap"]
        score = min(score, 1.0)
        if score >= 0.45:
            via = "shared_claims" if signals["shared_claim_overlap"] >= max(signals["headline_similarity"], 0.45) else "identity_signals"
            scored.append((score, candidate, signals, via))
    if not scored:
        return Resolution("new", None, "new_story", "no_candidate", 0.0, {}, ambiguous=False)

    scored.sort(key=lambda item: (-item[0], item[1].id))
    score, candidate, signals, via = scored[0]
    ambiguous = signals["location_conflict"] or len(scored) > 1 and score - scored[1][0] < ambiguity_margin
    deterministic_merge = (
        not ambiguous
        and (
            signals["headline_level"] == "VERY_HIGH"
            or signals["same_event_key"] and (
                signals["shared_claim_overlap"] > 0
                or signals["entity_overlap"] > 0
                or signals["semantic_similarity"] >= 0.70
                or signals["headline_similarity"] >= 0.50
                or signals["text_overlap"] >= 0.15
            )
            or signals["shared_claim_overlap"] >= 0.50
            or signals["semantic_similarity"] >= 0.82 and signals["entity_overlap"] > 0
        )
    )
    if deterministic_merge:
        if signals["contradiction_marker"]:
            classification = "contradiction"
        elif signals["correction_marker"]:
            classification = "correction"
        elif signals["numeric_change"] or signals["material_marker"] and signals["text_overlap"] < 0.50:
            classification = "material_update"
        else:
            classification = "corroboration"
        return Resolution("merge", candidate.id, classification, via, score, signals)
    if adjudicator is not None:
        raw = adjudicator(incoming_candidate, candidate, signals)
        if isinstance(raw, Mapping):
            approved = bool(raw.get("merge")) and float(raw.get("confidence", 0.0)) >= 0.75
        else:
            approved = raw is True
        if approved:
            return Resolution("merge", candidate.id, "corroboration", "adjudication", score, signals, ambiguous=True, adjudicated=True)
    return Resolution("new", None, "new_story", via, score, signals, ambiguous=True, adjudicated=False)


def _marker_set(values: Any) -> frozenset[str]:
    return frozenset(token for value in (values if isinstance(values, (list, tuple, set, frozenset)) else [values]) for token in _tokens(str(value)))


def classify_update(
    previous_claims: Any,
    incoming_claims: Any,
    *,
    same_document: bool = False,
    same_lineage: bool = False,
    same_source: bool = False,
    source_independent: bool = True,
    incoming_text: str = "",
    incoming_relationships: Sequence[str] = (),
    incoming_supersedes: bool = False,
) -> str:
    """Classify novelty without treating repeated publications as corroboration."""
    if same_document or same_lineage:
        return "duplicate"
    prior, incoming = _claim_keys(previous_claims), _claim_keys(incoming_claims)
    markers = _marker_set(incoming_text) | _marker_set(incoming)
    if "contradicts" in incoming_relationships or markers & _CONTRADICTION_MARKERS:
        return "correction" if incoming_supersedes or markers & _CORRECTION_MARKERS else "contradiction"
    if incoming_supersedes or markers & _CORRECTION_MARKERS:
        return "correction"
    if incoming and prior and incoming <= prior:
        return "duplicate" if same_source or not source_independent else "corroboration"
    if prior and incoming:
        prior_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", " ".join(prior)))
        incoming_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", " ".join(incoming)))
        if prior_numbers != incoming_numbers or markers & _MATERIAL_MARKERS:
            return "material_update"
    if incoming - prior:
        return "material_update" if markers & _MATERIAL_MARKERS else "qualification"
    return "corroboration" if source_independent else "duplicate"


def replay_evolution(
    candidates: Sequence[StoryCandidate | Mapping[str, Any]],
    *,
    adjudicator: Callable[[StoryCandidate, StoryCandidate, Mapping[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Run deterministic Story resolution over a frozen candidate sequence.

    The helper is intentionally provider-free so evaluation fixtures can prove
    grouping and novelty behavior without network access or a database.
    """
    stories: list[StoryCandidate] = []
    groups: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for raw in candidates:
        candidate = raw if isinstance(raw, StoryCandidate) else StoryCandidate.from_mapping(raw)
        resolution = resolve_candidate(candidate, stories, adjudicator=adjudicator)
        if resolution.action == "new":
            story_id = f"story-{len(stories) + 1}"
            stories.append(replace(candidate, id=story_id))
            groups.append({"story_id": story_id, "candidate_ids": [candidate.id]})
            update_class = "new_story"
        else:
            story_id = resolution.story_id
            group = next(group for group in groups if group["story_id"] == story_id)
            group["candidate_ids"].append(candidate.id)
            index = next(index for index, story in enumerate(stories) if story.id == story_id)
            prior = stories[index]
            stories[index] = replace(
                prior,
                entities=prior.entities | candidate.entities,
                locations=prior.locations | candidate.locations,
                claim_keys=prior.claim_keys | candidate.claim_keys,
            )
            update_class = resolution.classification
        events.append(
            {
                "candidate_id": candidate.id,
                "story_id": story_id,
                "update_class": update_class,
                "resolution": resolution.__dict__,
            }
        )
    return {"story_groups": groups, "events": events}


CandidateStory = StoryCandidate
StoryResolution = Resolution


def _row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class StoryEvolutionService:
    """Persist Story evolution without rewriting historical evidence."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @staticmethod
    def _require(conn: sqlite3.Connection, table: str, identifier: str, label: str) -> sqlite3.Row:
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise DomainNotFound(f"{label} not found")
        return row

    @staticmethod
    def _validate_update_class(value: str) -> str:
        if value not in UPDATE_CLASSES:
            raise DomainValidation("invalid Story update class")
        return value

    def _event(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute(
                """
                SELECT e.*, d.canonical_url, d.title AS document_title, d.source_id,
                       s.name AS source_name, s.slug AS source_slug
                FROM story_evolution_events e
                JOIN documents d ON d.id = e.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE e.id = ?
                """,
                (identifier,),
            ).fetchone()
            if row is None:
                raise DomainNotFound("story evolution event not found")
            result = _row_dict(row)
            result["decision"] = json.loads(result.pop("decision_json"))
            result["document"] = {
                "id": result.pop("document_id"),
                "canonical_url": result.pop("canonical_url"),
                "title": result.pop("document_title"),
                "source_id": result.pop("source_id"),
                "source_name": result.pop("source_name"),
                "source_slug": result.pop("source_slug"),
            }
            result["document_id"] = result["document"]["id"]
            return result
        finally:
            conn.close()

    def record_observation(
        self,
        story_id: str,
        document_id: str,
        update_class: str,
        *,
        candidate: StoryCandidate | Mapping[str, Any] | None = None,
        decision: Mapping[str, Any] | None = None,
        revision_id: str | None = None,
        material_change: bool | None = None,
    ) -> dict[str, Any]:
        update_class = self._validate_update_class(update_class)
        candidate_values = {"id": document_id, "headline": ""}
        if candidate:
            candidate_values.update(candidate if isinstance(candidate, Mapping) else {})
        candidate_obj = candidate if isinstance(candidate, StoryCandidate) else StoryCandidate.from_mapping(candidate_values)
        material = bool(material_change) if material_change is not None else update_class in {"contradiction", "correction", "material_update"}
        event_id = new_id("evo")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "stories", story_id, "story")
                self._require(conn, "documents", document_id, "document")
                if revision_id is not None:
                    revision = self._require(conn, "story_revisions", revision_id, "story revision")
                    if revision["story_id"] != story_id:
                        raise DomainValidation("revision must belong to the Story")
                existing = conn.execute(
                    "SELECT 1 FROM story_documents WHERE story_id = ? AND document_id = ?",
                    (story_id, document_id),
                ).fetchone()
                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO story_documents
                            (story_id, document_id, event_key, entities_json, locations_json, linked_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            story_id,
                            document_id,
                            candidate_obj.event_key,
                            _json_value(sorted(candidate_obj.entities)),
                            _json_value(sorted(candidate_obj.locations)),
                            now,
                        ),
                    )
                conn.execute(
                    """
                    INSERT INTO story_evolution_events
                        (id, story_id, document_id, update_class, material_change, decision_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (event_id, story_id, document_id, update_class, int(material), _json_value(decision or {}), now),
                )
                if revision_id is not None:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO story_revision_documents
                            (revision_id, document_id, role, created_at)
                        VALUES (?, ?, 'trigger', ?)
                        """,
                        (revision_id, document_id, now),
                    )
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("Story evolution record violates a relationship") from exc
        finally:
            conn.close()
        return self._event(event_id)

    def record_automatic_observation_tx(
        self,
        conn: sqlite3.Connection,
        story_id: str,
        document_id: str,
        claim_id: str,
        promotion_id: str,
        job_id: str,
        update_class: str,
        *,
        candidate: StoryCandidate | Mapping[str, Any] | None = None,
        decision: Mapping[str, Any] | None = None,
        revision_id: str | None = None,
        material_change: bool = False,
    ) -> str:
        """Record one automatic event inside the Story mutation transaction.

        The existing public observation method remains the manual/API path.
        Automatic work supplies its durable Job identity in the decision
        context so retries can recognize the same logical event without a
        second Story-matching or mutation algorithm.
        """

        update_class = self._validate_update_class(update_class)
        self._require(conn, "stories", story_id, "story")
        self._require(conn, "documents", document_id, "document")
        claim = self._require(conn, "claims", claim_id, "claim")
        if claim["story_id"] != story_id:
            raise DomainValidation("automatic event Claim must belong to the Story")
        promotion = self._require(conn, "article_analysis_promotions", promotion_id, "promotion")
        if promotion["claim_id"] != claim_id or promotion["outcome_code"] != "verified":
            raise DomainValidation("automatic event promotion does not match the Claim")
        self._require(conn, "jobs", job_id, "Story-stage Job")
        if revision_id is not None:
            revision = self._require(conn, "story_revisions", revision_id, "story revision")
            if revision["story_id"] != story_id:
                raise DomainValidation("automatic event revision must belong to the Story")

        existing = conn.execute(
            """
            SELECT id FROM story_evolution_events
            WHERE json_extract(decision_json, '$.automatic_story_stage.job_id') = ?
            """,
            (job_id,),
        ).fetchone()
        if existing is not None:
            return existing[0]

        candidate_values = {"id": document_id, "headline": ""}
        if candidate:
            candidate_values.update(candidate if isinstance(candidate, Mapping) else {})
        candidate_obj = candidate if isinstance(candidate, StoryCandidate) else StoryCandidate.from_mapping(candidate_values)
        now = utc_now()
        if conn.execute(
            "SELECT 1 FROM story_documents WHERE story_id = ? AND document_id = ?",
            (story_id, document_id),
        ).fetchone() is None:
            conn.execute(
                """
                INSERT INTO story_documents
                    (story_id, document_id, event_key, entities_json, locations_json, linked_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    story_id,
                    document_id,
                    candidate_obj.event_key,
                    _json_value(sorted(candidate_obj.entities)),
                    _json_value(sorted(candidate_obj.locations)),
                    now,
                ),
            )
        event_decision = dict(decision or {})
        event_decision["automatic_story_stage"] = {
            "job_id": job_id,
            "promotion_id": promotion_id,
            "claim_id": claim_id,
        }
        event_id = new_id("evo")
        conn.execute(
            """
            INSERT INTO story_evolution_events
                (id, story_id, document_id, update_class, material_change, decision_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                story_id,
                document_id,
                update_class,
                int(material_change),
                _json_value(event_decision),
                now,
            ),
        )
        if revision_id is not None:
            conn.execute(
                """
                INSERT OR IGNORE INTO story_revision_documents
                    (revision_id, document_id, role, created_at)
                VALUES (?, ?, 'trigger', ?)
                """,
                (revision_id, document_id, now),
            )
        return event_id

    def link_lineage(
        self,
        document_id: str,
        parent_document_id: str,
        relationship: str,
        *,
        confidence: float = 1.0,
        rationale: str = "",
    ) -> dict[str, Any]:
        if relationship not in LINEAGE_RELATIONSHIPS:
            raise DomainValidation("invalid document lineage relationship")
        if document_id == parent_document_id:
            raise DomainValidation("a document cannot be its own lineage parent")
        if not 0.0 <= float(confidence) <= 1.0:
            raise DomainValidation("lineage confidence must be between 0 and 1")
        identifier = new_id("lin")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "documents", document_id, "document")
                self._require(conn, "documents", parent_document_id, "parent document")
                frontier = [parent_document_id]
                seen = {parent_document_id}
                while frontier:
                    current = frontier.pop()
                    if current == document_id:
                        raise DomainValidation("document lineage cannot contain a cycle")
                    for row in conn.execute(
                        "SELECT parent_document_id FROM document_lineage WHERE document_id = ?",
                        (current,),
                    ):
                        if row[0] not in seen:
                            seen.add(row[0])
                            frontier.append(row[0])
                try:
                    conn.execute(
                        """
                        INSERT INTO document_lineage
                            (id, document_id, parent_document_id, relationship, confidence, rationale, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (identifier, document_id, parent_document_id, relationship, float(confidence), rationale.strip(), utc_now()),
                    )
                except sqlite3.IntegrityError as exc:
                    raise DomainConflict("document lineage edge already exists") from exc
        finally:
            conn.close()
        return self.get_lineage_edge(identifier)

    def get_lineage_edge(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = self._require(conn, "document_lineage", identifier, "document lineage")
            return _row_dict(row) or {}
        finally:
            conn.close()

    def lineage(self, document_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            self._require(conn, "documents", document_id, "document")
            rows = conn.execute(
                """
                SELECT * FROM document_lineage
                WHERE document_id = ? OR parent_document_id = ?
                ORDER BY created_at, id
                """,
                (document_id, document_id),
            ).fetchall()
            return {"document_id": document_id, "edges": [_row_dict(row) for row in rows]}
        finally:
            conn.close()

    def _lineage_group(self, conn: sqlite3.Connection, document_id: str) -> str:
        seen = {document_id}
        frontier = [document_id]
        while frontier:
            current = frontier.pop()
            rows = conn.execute(
                """
                SELECT parent_document_id AS related FROM document_lineage
                WHERE document_id = ? AND relationship IN ('syndicated_from', 'wire_propagation', 'rewritten_from', 'common_primary_document')
                UNION
                SELECT document_id AS related FROM document_lineage
                WHERE parent_document_id = ? AND relationship IN ('syndicated_from', 'wire_propagation', 'rewritten_from', 'common_primary_document')
                """,
                (current, current),
            ).fetchall()
            for row in rows:
                related = row["related"]
                if related not in seen:
                    seen.add(related)
                    frontier.append(related)
        return min(seen)

    @staticmethod
    def _current_or_legacy_documents(conn: sqlite3.Connection, story_id: str) -> list[sqlite3.Row]:
        """Keep legacy document-only Story APIs without reviving stale rows."""
        rows = current_story_documents(conn, story_id)
        if rows:
            return rows
        has_membership_history = conn.execute(
            "SELECT 1 FROM claim_story_assignment_history WHERE from_story_id = ? OR to_story_id = ? LIMIT 1",
            (story_id, story_id),
        ).fetchone()
        if has_membership_history:
            return []
        return conn.execute(
            """
            SELECT sd.*, d.canonical_url, d.published_at, d.source_id
            FROM story_documents sd JOIN documents d ON d.id = sd.document_id
            WHERE sd.story_id = ? ORDER BY sd.linked_at DESC, sd.document_id DESC
            """,
            (story_id,),
        ).fetchall()

    def corroboration(self, story_id: str, claim_id: str | None = None) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            self._require(conn, "stories", story_id, "story")
            if claim_id is None:
                rows = self._current_or_legacy_documents(conn, story_id)
            else:
                self._require(conn, "claims", claim_id, "claim")
                rows = conn.execute(
                    """
                    SELECT DISTINCT d.id AS document_id, d.source_id
                    FROM documents d
                    JOIN document_versions dv ON dv.document_id = d.id
                    JOIN evidence_spans es ON es.document_version_id = dv.id
                    JOIN claim_evidence ce ON ce.evidence_span_id = es.id
                    JOIN claims c ON c.id = ce.claim_id AND c.story_id = ?
                    WHERE ce.claim_id = ?
                    ORDER BY d.id
                    """,
                    (story_id, claim_id),
                ).fetchall()
            document_ids = [row["document_id"] for row in rows]
            groups = {self._lineage_group(conn, identifier) for identifier in document_ids}
            group_sources: dict[str, set[str]] = {}
            for row in rows:
                group_sources.setdefault(self._lineage_group(conn, row["document_id"]), set()).add(row["source_id"])
            independent_keys = {
                group if len(source_ids) > 1 else next(iter(source_ids))
                for group, source_ids in group_sources.items()
            }
            result = {
                "publication_count": len(document_ids),
                "independent_source_count": len(independent_keys),
                "distinct_source_count": len({row["source_id"] for row in rows}),
                "lineage_group_count": len(groups),
                "document_ids": document_ids,
            }
        finally:
            conn.close()
        from .source_robustness import SourceRobustnessService

        robustness = SourceRobustnessService(self.db_path).evidence_summary(
            "claim" if claim_id is not None else "story",
            claim_id or story_id,
        )
        result["distinct_source_count"] = robustness["distinct_source_count"] or result["distinct_source_count"]
        result["lineage_group_count"] = robustness["lineage_group_count"] or result["lineage_group_count"]
        result["evidence_family_count"] = robustness["evidence_family_count"]
        result["fragility"] = SourceRobustnessService(self.db_path).analyze_fragility(
            "claim" if claim_id is not None else "story",
            claim_id or story_id,
        )
        return result

    def _new_update(self, conn: sqlite3.Connection, story_id: str) -> bool:
        review = conn.execute("SELECT last_reviewed_revision_id FROM story_review WHERE story_id = ?", (story_id,)).fetchone()
        if review is None:
            return False
        reviewed_number = 0
        if review["last_reviewed_revision_id"]:
            reviewed = conn.execute(
                "SELECT revision_number FROM story_revisions WHERE id = ? AND story_id = ?",
                (review["last_reviewed_revision_id"], story_id),
            ).fetchone()
            reviewed_number = reviewed["revision_number"] if reviewed else 0
        return conn.execute(
            "SELECT 1 FROM story_revisions WHERE story_id = ? AND material_change = 1 AND revision_number > ? LIMIT 1",
            (story_id, reviewed_number),
        ).fetchone() is not None

    def review(self, story_id: str, review_status: str, revision_id: str | None = None) -> dict[str, Any]:
        if review_status not in {"new", "saved", "dismissed", "not_useful"}:
            raise DomainValidation("invalid review status")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "stories", story_id, "story")
                if revision_id is None:
                    row = conn.execute(
                        "SELECT id FROM story_revisions WHERE story_id = ? ORDER BY revision_number DESC LIMIT 1",
                        (story_id,),
                    ).fetchone()
                    revision_id = row["id"] if row else None
                elif conn.execute(
                    "SELECT 1 FROM story_revisions WHERE id = ? AND story_id = ?", (revision_id, story_id)
                ).fetchone() is None:
                    raise DomainValidation("reviewed revision must belong to the Story")
                now = utc_now()
                columns = {
                    "review_status": review_status,
                    "last_reviewed_revision_id": revision_id,
                    "updated_at": now,
                }
                if review_status == "saved":
                    columns["saved_at"] = now
                elif review_status == "dismissed":
                    columns["dismissed_at"] = now
                elif review_status == "not_useful":
                    columns["not_useful_at"] = now
                assignments = ", ".join(f"{key} = ?" for key in columns)
                conn.execute(
                    f"UPDATE story_review SET {assignments} WHERE story_id = ?",
                    [*columns.values(), story_id],
                )
        finally:
            conn.close()
        return self.review_state(story_id)

    def review_state(self, story_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            self._require(conn, "stories", story_id, "story")
            row = conn.execute("SELECT * FROM story_review WHERE story_id = ?", (story_id,)).fetchone()
            if row is None:
                raise DomainNotFound("story review not found")
            result = _row_dict(row) or {}
            result["new_update"] = self._new_update(conn, story_id)
            return result
        finally:
            conn.close()

    def timeline(self, story_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            self._require(conn, "stories", story_id, "story")
            events = []
            for row in conn.execute(
                """
                SELECT e.*, d.canonical_url, d.title AS document_title, s.name AS source_name
                FROM story_evolution_events e
                JOIN documents d ON d.id = e.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE e.story_id = ? ORDER BY e.created_at, e.id
                """,
                (story_id,),
            ).fetchall():
                item = _row_dict(row) or {}
                item["decision"] = json.loads(item.pop("decision_json"))
                item["document"] = {
                    "id": item["document_id"],
                    "canonical_url": item.pop("canonical_url"),
                    "title": item.pop("document_title"),
                    "source_name": item.pop("source_name"),
                }
                item["lineage"] = self.lineage(item["document_id"])["edges"]
                events.append(item)
            revisions = []
            for row in conn.execute(
                "SELECT * FROM story_revisions WHERE story_id = ? ORDER BY revision_number, id", (story_id,)
            ).fetchall():
                item = _row_dict(row) or {}
                item["document_ids"] = [
                    value[0]
                    for value in conn.execute(
                        "SELECT document_id FROM story_revision_documents WHERE revision_id = ? ORDER BY document_id",
                        (item["id"],),
                    ).fetchall()
                ]
                revisions.append(item)
            return {"story_id": story_id, "events": events, "revisions": revisions}
        finally:
            conn.close()

    def _story_candidates(self, conn: sqlite3.Connection) -> list[StoryCandidate]:
        result: list[StoryCandidate] = []
        for story in conn.execute("SELECT * FROM stories WHERE deleted_at IS NULL ORDER BY id").fetchall():
            revision = conn.execute(
                "SELECT * FROM story_revisions WHERE story_id = ? ORDER BY revision_number DESC LIMIT 1", (story["id"],)
            ).fetchone()
            docs = self._current_or_legacy_documents(conn, story["id"])
            event_key = docs[0]["event_key"] if docs else None
            canonical_url = docs[0]["canonical_url"] if docs else None
            published_at = docs[0]["published_at"] if docs else None
            entities = {item for row in docs for item in json.loads(row["entities_json"])}
            locations = {item for row in docs for item in json.loads(row["locations_json"])}
            claims = [row[0] for row in conn.execute("SELECT proposition FROM claims WHERE story_id = ?", (story["id"],))]
            topics = [row[0] for row in conn.execute("SELECT topic_id FROM story_topics WHERE story_id = ?", (story["id"],))]
            subjects = [row[0] for row in conn.execute("SELECT subject_id FROM story_subjects WHERE story_id = ?", (story["id"],))]
            result.append(
                StoryCandidate(
                    id=story["id"],
                    headline=revision["headline"] if revision else "",
                    canonical_url=canonical_url,
                    document_id=docs[0]["document_id"] if docs else None,
                    published_at=published_at,
                    created_at=story["created_at"],
                    event_key=event_key,
                    entities=entities,
                    locations=locations,
                    claim_keys=_claim_keys(claims),
                    topic_ids=topics,
                    subject_ids=subjects,
                )
            )
        return result

    def resolve(self, candidate: StoryCandidate | Mapping[str, Any], *, adjudicator=None) -> Resolution:
        conn = storage.connect(self.db_path)
        try:
            return resolve_candidate(candidate, self._story_candidates(conn), adjudicator=adjudicator)
        finally:
            conn.close()

    def process(
        self,
        document_id: str,
        candidate: StoryCandidate | Mapping[str, Any],
        *,
        story_id: str | None = None,
        update_class: str | None = None,
        revision_id: str | None = None,
        adjudicator=None,
    ) -> dict[str, Any]:
        candidate_obj = candidate if isinstance(candidate, StoryCandidate) else StoryCandidate.from_mapping(candidate)
        resolution = self.resolve(candidate_obj, adjudicator=adjudicator) if story_id is None else Resolution("merge", story_id, "material_update", "explicit_story", 1.0, {})
        selected_story_id = story_id or resolution.story_id
        if selected_story_id is None:
            from .domain import CoreService

            story = CoreService(self.db_path).create_story(
                {
                    "headline": candidate_obj.headline,
                    "topic_ids": list(candidate_obj.topic_ids),
                    "subject_ids": list(candidate_obj.subject_ids),
                }
            )
            selected_story_id = story["id"]
            resolution = Resolution("new", None, "new_story", "new_story", 0.0, resolution.signals, resolution.ambiguous, resolution.adjudicated)
        if update_class is None:
            if resolution.action == "new":
                update_class = "new_story"
            else:
                candidate_values = candidate if isinstance(candidate, Mapping) else {}
                incoming_claims = candidate_values.get("claims") or candidate_obj.claim_keys
                incoming_text = str(candidate_values.get("text") or candidate_obj.headline)
                conn = storage.connect(self.db_path)
                try:
                    prior_claims = [
                        row[0]
                        for row in conn.execute(
                            "SELECT proposition FROM claims WHERE story_id = ? ORDER BY created_at, id",
                            (selected_story_id,),
                        )
                    ]
                    same_source = conn.execute(
                        """
                        SELECT 1
                        FROM claims current_claim
                        JOIN claim_evidence current_ce ON current_ce.claim_id = current_claim.id
                        JOIN evidence_spans current_es ON current_es.id = current_ce.evidence_span_id
                        JOIN document_versions existing_dv ON existing_dv.id = current_es.document_version_id
                        JOIN documents existing_doc ON existing_doc.id = existing_dv.document_id
                        JOIN documents incoming_doc ON incoming_doc.id = ?
                        WHERE current_claim.story_id = ? AND existing_doc.source_id = incoming_doc.source_id
                        LIMIT 1
                        """,
                        (document_id, selected_story_id),
                    ).fetchone() is not None
                    same_lineage = False
                    incoming_group = self._lineage_group(conn, document_id)
                    for row in conn.execute(
                        """
                        SELECT DISTINCT dv.document_id
                        FROM claims c
                        JOIN claim_evidence ce ON ce.claim_id = c.id
                        JOIN evidence_spans es ON es.id = ce.evidence_span_id
                        JOIN document_versions dv ON dv.id = es.document_version_id
                        WHERE c.story_id = ?
                        """,
                        (selected_story_id,),
                    ):
                        if self._lineage_group(conn, row[0]) == incoming_group and incoming_group != document_id:
                            same_lineage = True
                            break
                finally:
                    conn.close()
                update_class = classify_update(
                    prior_claims,
                    incoming_claims,
                    same_document=(candidate_obj.document_id == document_id or candidate_values.get("document_id") == document_id),
                    same_lineage=same_lineage,
                    same_source=same_source,
                    source_independent=not same_source,
                    incoming_text=incoming_text,
                    incoming_relationships=tuple(candidate_values.get("relationships") or ()),
                    incoming_supersedes=bool(candidate_values.get("supersedes_claim_id")),
                )
        event = self.record_observation(
            selected_story_id,
            document_id,
            update_class,
            candidate=candidate_obj,
            decision={"resolution": resolution.__dict__},
            revision_id=revision_id,
        )
        from .domain import CoreService

        return {"story": CoreService(self.db_path).get_story(selected_story_id, include_deleted=True), "resolution": resolution.__dict__, "event": event}


__all__ = [
    "LINEAGE_RELATIONSHIPS",
    "UPDATE_CLASSES",
    "CandidateStory",
    "Resolution",
    "StoryResolution",
    "StoryCandidate",
    "StoryEvolutionService",
    "candidate_signals",
    "classify_update",
    "replay_evolution",
    "resolve_candidate",
]
