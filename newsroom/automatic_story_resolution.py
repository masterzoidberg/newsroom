"""Phase 23A automatic Claim qualification and deterministic Story resolution.

This module is deliberately side-effect free.  It accepts only a promotion ID,
proves that promotion through ``verify_automatic_promotion`` and then returns a
typed decision.  It never accepts an arbitrary Claim ID, changes Claim state,
assigns a Story, or creates a Story.

The Story query is intentionally conservative: it returns at most a fixed
number of active candidates plus one saturation probe.  A saturated or
incomplete candidate set is deferred because uniqueness cannot be proven from
an incomplete set.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import storage
from .ai import ArticleAnalysisOutput
from .domain import DomainNotFound
from .evidence_promotion import (
    AutomaticPromotionIntegrityError,
    verify_automatic_promotion,
)
from .similarity import normalize_headline, tokenize
from .story_evolution import StoryCandidate, candidate_signals, effective_document_time


QUALIFIED = "qualified"
DEFERRED = "deferred"

MATCHED_EXISTING = "matched_existing"
NO_MATCH = "no_match"
AMBIGUOUS = "ambiguous"

MAX_CANDIDATE_STORIES = 20
MAX_STORY_CLAIMS = 50
MAX_STORY_DOCUMENTS = 50
MAX_STORY_TOPICS = 50
MAX_STORY_SUBJECTS = 50
MAX_STORY_TEXT_CHARS = 4_000
MAX_RETRIEVAL_TERMS = 32
STORY_TIME_WINDOW_HOURS = 72
AUTOMATIC_STORY_RESOLVER_VERSION = "automatic_story_resolver_v1"
STRONG_PROPOSITION_OVERLAP = 0.75
MIN_STRONG_PROPOSITION_TOKENS = 3
ENTITY_BACKED_PROPOSITION_OVERLAP = 0.40
MIN_ENTITY_BACKED_PROPOSITION_TOKENS = 2
_SEPARATOR = "\x1f"


@dataclass(frozen=True)
class StoryMatchSignal:
    """A bounded, deterministic explanation for one candidate Story."""

    story_id: str
    strength: int
    signals: dict[str, Any]


@dataclass(frozen=True)
class StoryMatchDecision:
    story_resolution: str
    story_resolution_reason_code: str
    selected_story_id: str | None
    signals: tuple[StoryMatchSignal, ...]


@dataclass(frozen=True)
class AutomaticStoryResolutionResult:
    """The reusable Phase 23A decision returned to later orchestration."""

    promotion_id: str
    claim_id: str | None
    qualification: str
    qualification_reason_code: str
    story_resolution: str
    story_resolution_reason_code: str
    candidate_story_ids: tuple[str, ...] = ()
    selected_story_id: str | None = None
    match_signals: tuple[StoryMatchSignal, ...] = ()
    candidate_saturated: bool = False


@dataclass(frozen=True)
class _CandidateRetrieval:
    candidates: tuple[StoryCandidate, ...]
    saturated: bool = False
    invalid_data: bool = False
    terms_truncated: bool = False


def _as_candidate(value: StoryCandidate | Mapping[str, Any]) -> StoryCandidate:
    return value if isinstance(value, StoryCandidate) else StoryCandidate.from_mapping(value)


def _automatic_match_strength(signals: Mapping[str, Any]) -> int:
    """Return a categorical strength; weak signals never merge by themselves."""

    if (
        not signals["time_compatible"]
        or signals["event_key_conflict"]
        or signals["explicit_exclusion"]
        or signals["location_conflict"]
    ):
        return 0
    if signals["claim_exact_match"]:
        return 3
    if (
        signals["text_overlap"] >= STRONG_PROPOSITION_OVERLAP
        and signals["text_overlap_count"] >= MIN_STRONG_PROPOSITION_TOKENS
    ):
        return 2
    if signals["entity_overlap"] > 0 and (
        signals["text_overlap"] >= ENTITY_BACKED_PROPOSITION_OVERLAP
        and signals["text_overlap_count"] >= MIN_ENTITY_BACKED_PROPOSITION_TOKENS
        or signals["headline_level"] == "VERY_HIGH"
    ):
        return 2
    return 0


def match_story_candidates(
    incoming: StoryCandidate | Mapping[str, Any],
    existing: Sequence[StoryCandidate | Mapping[str, Any]],
) -> StoryMatchDecision:
    """Classify already-bounded candidates without side effects or tie-breaking.

    A unique exact proposition is the strongest signal.  A strong lexical
    proposition match or entity-backed lexical/headline match is also usable.
    Source, topic, subject, and generic lexical overlap remain explanatory
    signals only.  If two candidates have any strong signal, the result is
    ambiguous regardless of their input order or tiny score differences.
    """

    incoming_candidate = _as_candidate(incoming)
    candidates = sorted((_as_candidate(item) for item in existing), key=lambda item: item.id)
    signals: list[StoryMatchSignal] = []
    for candidate in candidates:
        raw = candidate_signals(
            incoming_candidate,
            candidate,
            STORY_TIME_WINDOW_HOURS,
        )
        strength = _automatic_match_strength(raw)
        signals.append(StoryMatchSignal(candidate.id, strength, dict(raw)))

    strong = [item for item in signals if item.strength > 0]
    if not strong:
        return StoryMatchDecision(
            NO_MATCH,
            "no_plausible_active_story",
            None,
            tuple(signals),
        )
    if any(item.signals["story_data_truncated"] for item in strong):
        return StoryMatchDecision(
            DEFERRED,
            "candidate_story_data_saturated",
            None,
            tuple(signals),
        )
    if len(strong) > 1:
        return StoryMatchDecision(
            AMBIGUOUS,
            "multiple_strong_story_matches",
            None,
            tuple(signals),
        )
    selected = strong[0]
    return StoryMatchDecision(
        MATCHED_EXISTING,
        "unique_deterministic_story_match",
        selected.story_id,
        tuple(signals),
    )


def _issue_code(exc: AutomaticPromotionIntegrityError) -> str:
    issue = exc.issues[0] if exc.issues else "invalid_verified_promotion"
    return issue.split(":", 1)[0]


def _claim_qualification_reason(graph: Mapping[str, Any]) -> str:
    promotion = graph.get("promotion") or {}
    analysis = graph.get("analysis") or {}
    claim = graph.get("claim") or {}
    if promotion.get("outcome_code") != "verified":
        return "promotion_not_verified"
    if graph.get("provenance_class") != "automatic" or graph.get("input_contract_complete") is not True:
        return "promotion_not_automatic"
    if promotion.get("claim_id") != claim.get("id"):
        return "promotion_claim_mismatch"
    if claim.get("article_analysis_id") != analysis.get("id"):
        return "claim_analysis_mismatch"
    if claim.get("story_id") is not None:
        return "claim_already_assigned"
    if claim.get("state") != "pending" or claim.get("accepted_at") is not None:
        return "claim_not_pending"
    candidate_index = claim.get("candidate_claim_index")
    if type(candidate_index) is not int or candidate_index < 0:
        return "claim_candidate_index_invalid"
    output = graph.get("analysis_output")
    if not isinstance(output, ArticleAnalysisOutput):
        return "analysis_candidate_data_missing"
    candidates = [item for item in output.candidate_claims if item.index == candidate_index]
    if len(candidates) != 1 or candidates[0].proposition.strip() != claim.get("proposition"):
        return "analysis_candidate_proposition_invalid"
    spans = graph.get("evidence_spans") or ()
    links = graph.get("claim_evidence") or ()
    span_ids = [item.get("id") for item in spans]
    link_ids = [item.get("evidence_span_id") for item in links]
    if (
        not span_ids
        or len(span_ids) != len(set(span_ids))
        or len(link_ids) != len(span_ids)
        or len(link_ids) != len(set(link_ids))
        or set(link_ids) != set(span_ids)
    ):
        return "claim_evidence_not_exact"
    relationships = {item.get("relationship") for item in links}
    if "contradicts" in relationships:
        return "verified_contradictory_evidence"
    if "supports" not in relationships:
        return "no_supporting_verified_evidence"
    if graph.get("current_need_available") is not True:
        return "current_information_need_unavailable"
    if (graph.get("monitor") or {}).get("enabled") != 1:
        return "monitor_inactive"
    if (graph.get("source") or {}).get("deleted_at") is not None:
        return "source_deleted"
    return "verified_pending_automatic_claim"


def _split(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item for item in str(value).split(_SEPARATOR) if item)


def _decode_json_parts(value: Any) -> tuple[tuple[str, ...], bool]:
    items: list[str] = []
    invalid = False
    for part in _split(value):
        try:
            decoded = json.loads(part)
        except (TypeError, ValueError, json.JSONDecodeError):
            invalid = True
            continue
        if not isinstance(decoded, list):
            invalid = True
            continue
        for item in decoded:
            if isinstance(item, str) and item.strip():
                items.append(item.strip())
            else:
                invalid = True
    return tuple(dict.fromkeys(items)), invalid


def _row_candidate(row) -> tuple[StoryCandidate | None, bool]:
    claim_texts = _split(row["claim_text"])
    entities, entity_invalid = _decode_json_parts(row["entity_text"])
    locations, location_invalid = _decode_json_parts(row["location_text"])
    topics = _split(row["topic_text"])
    subjects = _split(row["subject_text"])
    sources = _split(row["source_text"])
    text = " ".join(
        item
        for item in (
            row["headline_text"],
            row["summary_text"],
            row["why_text"],
            *claim_texts,
        )
        if item
    )
    data_truncated = any(
        row[field] > limit
        for field, limit in (
            ("claim_total", MAX_STORY_CLAIMS),
            ("document_total", MAX_STORY_DOCUMENTS),
            ("topic_total", MAX_STORY_TOPICS),
            ("subject_total", MAX_STORY_SUBJECTS),
        )
    )
    if len(text) > MAX_STORY_TEXT_CHARS:
        text = text[:MAX_STORY_TEXT_CHARS]
        data_truncated = True
    invalid = entity_invalid or location_invalid
    try:
        candidate = StoryCandidate(
            id=row["id"],
            headline=row["headline_text"],
            text=text,
            created_at=row["story_created_at"],
            published_at=effective_document_time(
                row["latest_published_at"], row["latest_first_retrieved_at"]
            ),
            event_key=row["latest_event_key"],
            entities=entities,
            locations=locations,
            claim_keys=claim_texts,
            topic_ids=topics,
            subject_ids=subjects,
            source_ids=sources,
            data_truncated=data_truncated,
        )
    except (TypeError, ValueError):
        return None, True
    return candidate, invalid


class AutomaticStoryResolutionService:
    """Return the Phase 23A decision for one verified promotion identity."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        max_candidates: int = MAX_CANDIDATE_STORIES,
    ):
        if isinstance(max_candidates, bool) or not 1 <= max_candidates <= 100:
            raise ValueError("max_candidates must be between 1 and 100")
        self.db_path = Path(db_path)
        self.max_candidates = max_candidates

    def resolve(self, promotion_id: str) -> AutomaticStoryResolutionResult:
        try:
            graph = verify_automatic_promotion(self.db_path, promotion_id)
        except AutomaticPromotionIntegrityError as exc:
            return AutomaticStoryResolutionResult(
                promotion_id=promotion_id,
                claim_id=None,
                qualification=DEFERRED,
                qualification_reason_code="promotion_verification_failed",
                story_resolution=DEFERRED,
                story_resolution_reason_code=_issue_code(exc),
            )
        except DomainNotFound:
            return AutomaticStoryResolutionResult(
                promotion_id=promotion_id,
                claim_id=None,
                qualification=DEFERRED,
                qualification_reason_code="promotion_verification_failed",
                story_resolution=DEFERRED,
                story_resolution_reason_code="promotion_missing",
            )

        return self.resolve_verified_graph(promotion_id, graph)

    def resolve_verified_graph(
        self,
        promotion_id: str,
        graph: Mapping[str, Any],
        *,
        conn=None,
    ) -> AutomaticStoryResolutionResult:
        """Resolve a graph already returned by ``verify_automatic_promotion``.

        The worker uses this entry point after acquiring its write transaction
        so candidate retrieval observes the current Story state without
        opening a second database transaction. Callers must not provide an
        unchecked graph.
        """

        claim_id = graph["claim"]["id"]
        qualification_reason = _claim_qualification_reason(graph)
        if qualification_reason != "verified_pending_automatic_claim":
            return AutomaticStoryResolutionResult(
                promotion_id=promotion_id,
                claim_id=claim_id,
                qualification=DEFERRED,
                qualification_reason_code=qualification_reason,
                story_resolution=DEFERRED,
                story_resolution_reason_code="claim_unqualified",
            )

        if self._claim_has_human_unassignment(claim_id, conn=conn):
            return AutomaticStoryResolutionResult(
                promotion_id=promotion_id,
                claim_id=claim_id,
                qualification=DEFERRED,
                qualification_reason_code="human_unassignment_authoritative",
                story_resolution=DEFERRED,
                story_resolution_reason_code="human_unassignment_authoritative",
            )

        incoming = self._incoming_candidate(graph)
        retrieval = self._retrieve_candidates(incoming, conn=conn)
        if retrieval.terms_truncated:
            return self._deferred_result(
                promotion_id,
                claim_id,
                "retrieval_terms_saturated",
                candidate_saturated=True,
            )
        candidate_ids = tuple(item.id for item in retrieval.candidates)
        if retrieval.saturated:
            return AutomaticStoryResolutionResult(
                promotion_id=promotion_id,
                claim_id=claim_id,
                qualification=QUALIFIED,
                qualification_reason_code=qualification_reason,
                story_resolution=DEFERRED,
                story_resolution_reason_code="candidate_set_saturated",
                candidate_story_ids=candidate_ids,
                candidate_saturated=True,
            )
        if retrieval.invalid_data or any(item.data_truncated for item in retrieval.candidates):
            return AutomaticStoryResolutionResult(
                promotion_id=promotion_id,
                claim_id=claim_id,
                qualification=QUALIFIED,
                qualification_reason_code=qualification_reason,
                story_resolution=DEFERRED,
                story_resolution_reason_code="candidate_data_saturated",
                candidate_story_ids=candidate_ids,
            )

        decision = match_story_candidates(incoming, retrieval.candidates)
        return AutomaticStoryResolutionResult(
            promotion_id=promotion_id,
            claim_id=claim_id,
            qualification=QUALIFIED,
            qualification_reason_code=qualification_reason,
            story_resolution=decision.story_resolution,
            story_resolution_reason_code=decision.story_resolution_reason_code,
            candidate_story_ids=candidate_ids,
            selected_story_id=decision.selected_story_id,
            match_signals=decision.signals,
        )

    def _claim_has_human_unassignment(self, claim_id: str, *, conn=None) -> bool:
        owns_connection = conn is None
        conn = conn or storage.connect(self.db_path)
        try:
            row = conn.execute(
                """
                SELECT origin, to_story_id
                FROM claim_story_assignment_history
                WHERE claim_id = ?
                ORDER BY occurred_at DESC, id DESC
                LIMIT 1
                """,
                (claim_id,),
            ).fetchone()
            return bool(row and row["origin"] == "human" and row["to_story_id"] is None)
        finally:
            if owns_connection:
                conn.close()

    @staticmethod
    def _deferred_result(
        promotion_id: str,
        claim_id: str,
        reason_code: str,
        *,
        candidate_saturated: bool = False,
    ) -> AutomaticStoryResolutionResult:
        return AutomaticStoryResolutionResult(
            promotion_id=promotion_id,
            claim_id=claim_id,
            qualification=QUALIFIED,
            qualification_reason_code="verified_pending_automatic_claim",
            story_resolution=DEFERRED,
            story_resolution_reason_code=reason_code,
            candidate_saturated=candidate_saturated,
        )

    @staticmethod
    def _incoming_candidate(graph: Mapping[str, Any]) -> StoryCandidate:
        output: ArticleAnalysisOutput = graph["analysis_output"]
        claim = graph["claim"]
        analysis = graph["analysis"]
        document = graph["document"]
        version = graph["document_version"]
        monitor = graph["monitor"]
        need_type = monitor.get("need_type")
        need_id = monitor.get("need_id")
        topic_ids = [need_id] if need_type == "topic" and need_id else []
        subject_ids = [need_id] if need_type == "subject" and need_id else []
        return StoryCandidate(
            id=claim["id"],
            headline=claim["proposition"],
            text=claim["proposition"],
            created_at=analysis.get("created_at") or version.get("retrieved_at"),
            published_at=document.get("published_at") or version.get("retrieved_at"),
            entities=[item.name for item in output.entities],
            locations=list(output.locations),
            claim_keys=[claim["proposition"]],
            topic_ids=topic_ids,
            subject_ids=subject_ids,
            source_ids=[document["source_id"]],
        )

    def _retrieval_terms(self, incoming: StoryCandidate) -> tuple[tuple[str, ...], bool]:
        values = [incoming.text, *sorted(incoming.entities), *sorted(incoming.locations)]
        terms: list[str] = []

        def add(value: str) -> None:
            normalized = normalize_headline(value)
            if len(normalized) >= 3 and normalized not in terms:
                terms.append(normalized)
            for token in tokenize(normalized):
                if len(token) >= 3 and token not in terms:
                    terms.append(token)

        for value in values:
            add(value)
        return tuple(terms[:MAX_RETRIEVAL_TERMS]), len(terms) > MAX_RETRIEVAL_TERMS

    @staticmethod
    def _like_pattern(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped.casefold()}%"

    def _retrieve_candidates(self, incoming: StoryCandidate, *, conn=None) -> _CandidateRetrieval:
        terms, terms_truncated = self._retrieval_terms(incoming)
        if terms_truncated:
            return _CandidateRetrieval((), terms_truncated=True)
        if not terms and not (incoming.topic_ids or incoming.subject_ids or incoming.source_ids):
            return _CandidateRetrieval(())

        predicates = [
            "lower(COALESCE(search_text, '')) LIKE ? ESCAPE '\\'"
            for _ in terms
        ]
        params: list[Any] = [self._like_pattern(term) for term in terms]
        for field, values in (
            ("id_text", incoming.topic_ids),
            ("id_text", incoming.subject_ids),
            ("id_text", incoming.source_ids),
        ):
            for value in sorted(values):
                predicates.append(f"instr({field}, ?) > 0")
                params.append(f"{_SEPARATOR}{value}{_SEPARATOR}")
        if not predicates:
            return _CandidateRetrieval(())

        query = f"""
            WITH first_document_observations AS (
                SELECT document_id, MIN(retrieved_at) AS first_retrieved_at
                FROM document_versions
                GROUP BY document_id
            ),
            current_story_documents AS (
                SELECT DISTINCT c.story_id, d.id AS document_id,
                       d.published_at, d.source_id,
                       first_observation.first_retrieved_at,
                       COALESCE(sd.event_key, '') AS event_key,
                       COALESCE(sd.entities_json, '[]') AS entities_json,
                       COALESCE(sd.locations_json, '[]') AS locations_json
                FROM claims c
                JOIN claim_evidence ce ON ce.claim_id = c.id
                JOIN evidence_spans es ON es.id = ce.evidence_span_id
                JOIN document_versions dv ON dv.id = es.document_version_id
                JOIN documents d ON d.id = dv.document_id
                JOIN first_document_observations first_observation
                  ON first_observation.document_id = d.id
                LEFT JOIN story_documents sd
                  ON sd.story_id = c.story_id AND sd.document_id = d.id
                WHERE c.story_id IS NOT NULL
            ),
            active_stories AS (
                SELECT id
                FROM stories
                WHERE deleted_at IS NULL
                  AND lifecycle <> 'archived'
            ),
            ranked_revisions AS (
                SELECT sr.story_id, sr.headline, sr.summary, sr.why_it_matters,
                       ROW_NUMBER() OVER (
                           PARTITION BY sr.story_id
                           ORDER BY sr.revision_number DESC, sr.id DESC
                       ) AS revision_rank
                FROM story_revisions sr
            ),
            story_search AS (
                SELECT r.story_id AS id,
                       lower(COALESCE(r.headline, '') || ' ' ||
                             COALESCE(r.summary, '') || ' ' ||
                             COALESCE(r.why_it_matters, '')) AS search_text,
                       '' AS id_text
                FROM ranked_revisions r
                JOIN active_stories active ON active.id = r.story_id
                WHERE r.revision_rank = 1
                UNION ALL
                SELECT c.story_id AS id,
                       lower(c.proposition) AS search_text,
                       '' AS id_text
                FROM claims c
                JOIN active_stories active ON active.id = c.story_id
                WHERE c.story_id IS NOT NULL
                UNION ALL
                SELECT cd.story_id AS id,
                       lower(COALESCE(cd.entities_json, '') || ' ' ||
                             COALESCE(cd.locations_json, '')) AS search_text,
                       '' AS id_text
                FROM current_story_documents cd
                JOIN active_stories active ON active.id = cd.story_id
                JOIN documents doc ON doc.id = cd.document_id
                JOIN sources source_row
                  ON source_row.id = doc.source_id
                 AND source_row.deleted_at IS NULL
                UNION ALL
                SELECT st.story_id AS id,
                       '' AS search_text,
                       char(31) || st.topic_id || char(31) AS id_text
                FROM story_topics st
                JOIN active_stories active ON active.id = st.story_id
                JOIN topics topic_row
                  ON topic_row.id = st.topic_id
                 AND topic_row.deleted_at IS NULL
                UNION ALL
                SELECT ss.story_id AS id,
                       '' AS search_text,
                       char(31) || ss.subject_id || char(31) AS id_text
                FROM story_subjects ss
                JOIN active_stories active ON active.id = ss.story_id
                JOIN subjects subject_row
                  ON subject_row.id = ss.subject_id
                 AND subject_row.deleted_at IS NULL
                UNION ALL
                SELECT cd.story_id AS id,
                       '' AS search_text,
                       char(31) || doc.source_id || char(31) AS id_text
                FROM current_story_documents cd
                JOIN active_stories active ON active.id = cd.story_id
                JOIN documents doc ON doc.id = cd.document_id
                JOIN sources source_row
                  ON source_row.id = doc.source_id
                 AND source_row.deleted_at IS NULL
            ),
            candidate_story_ids AS (
                SELECT id
                FROM story_search
                WHERE {' OR '.join(predicates)}
                GROUP BY id
                ORDER BY id
                LIMIT ?
            ),
            ranked_claims AS (
                SELECT c.story_id, c.proposition,
                       ROW_NUMBER() OVER (
                           PARTITION BY c.story_id
                           ORDER BY c.created_at, c.id
                       ) AS claim_rank,
                       COUNT(*) OVER (PARTITION BY c.story_id) AS claim_total
                FROM claims c
                JOIN candidate_story_ids selected ON selected.id = c.story_id
                WHERE c.story_id IS NOT NULL
            ),
            claim_summary AS (
                SELECT story_id, MAX(claim_total) AS claim_total,
                       GROUP_CONCAT(
                           CASE WHEN claim_rank <= {MAX_STORY_CLAIMS}
                                THEN substr(proposition, 1, {MAX_STORY_TEXT_CHARS}) END,
                           char(31)
                       ) AS claim_text
                FROM ranked_claims
                GROUP BY story_id
            ),
            ranked_documents AS (
                SELECT cd.story_id, cd.event_key, cd.entities_json,
                       cd.locations_json, cd.published_at, cd.first_retrieved_at,
                       cd.source_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY cd.story_id
                           ORDER BY cd.published_at DESC, cd.document_id DESC
                       ) AS document_rank,
                       COUNT(*) OVER (PARTITION BY cd.story_id) AS document_total
                FROM current_story_documents cd
                JOIN candidate_story_ids selected ON selected.id = cd.story_id
                JOIN documents d ON d.id = cd.document_id
                JOIN sources source_row
                  ON source_row.id = d.source_id
                 AND source_row.deleted_at IS NULL
            ),
            document_summary AS (
                SELECT story_id,
                       MAX(document_total) AS document_total,
                       MAX(CASE WHEN document_rank = 1 THEN event_key END) AS latest_event_key,
                       MAX(CASE WHEN document_rank = 1 THEN published_at END) AS latest_published_at,
                       MAX(CASE WHEN document_rank = 1 THEN first_retrieved_at END) AS latest_first_retrieved_at,
                       GROUP_CONCAT(
                           CASE WHEN document_rank <= {MAX_STORY_DOCUMENTS}
                                THEN substr(entities_json, 1, {MAX_STORY_TEXT_CHARS}) END,
                           char(31)
                       ) AS entity_text,
                       GROUP_CONCAT(
                           CASE WHEN document_rank <= {MAX_STORY_DOCUMENTS}
                                THEN substr(locations_json, 1, {MAX_STORY_TEXT_CHARS}) END,
                           char(31)
                       ) AS location_text,
                       GROUP_CONCAT(
                           CASE WHEN document_rank <= {MAX_STORY_DOCUMENTS}
                                THEN source_id END,
                           char(31)
                       ) AS source_text
                FROM ranked_documents
                GROUP BY story_id
            ),
            ranked_topics AS (
                SELECT st.story_id, st.topic_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY st.story_id ORDER BY st.topic_id
                       ) AS topic_rank,
                       COUNT(*) OVER (PARTITION BY st.story_id) AS topic_total
                FROM story_topics st
                JOIN candidate_story_ids selected ON selected.id = st.story_id
                JOIN topics topic_row
                  ON topic_row.id = st.topic_id
                 AND topic_row.deleted_at IS NULL
            ),
            topic_summary AS (
                SELECT story_id, MAX(topic_total) AS topic_total,
                       GROUP_CONCAT(
                           CASE WHEN topic_rank <= {MAX_STORY_TOPICS} THEN topic_id END,
                           char(31)
                       ) AS topic_text
                FROM ranked_topics
                GROUP BY story_id
            ),
            ranked_subjects AS (
                SELECT ss.story_id, ss.subject_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY ss.story_id ORDER BY ss.subject_id
                       ) AS subject_rank,
                       COUNT(*) OVER (PARTITION BY ss.story_id) AS subject_total
                FROM story_subjects ss
                JOIN candidate_story_ids selected ON selected.id = ss.story_id
                JOIN subjects subject_row
                  ON subject_row.id = ss.subject_id
                 AND subject_row.deleted_at IS NULL
            ),
            subject_summary AS (
                SELECT story_id, MAX(subject_total) AS subject_total,
                       GROUP_CONCAT(
                           CASE WHEN subject_rank <= {MAX_STORY_SUBJECTS} THEN subject_id END,
                           char(31)
                       ) AS subject_text
                FROM ranked_subjects
                GROUP BY story_id
            ),
            story_rows AS (
                SELECT s.id,
                       s.created_at AS story_created_at,
                       COALESCE(r.headline, '') AS headline_text,
                       COALESCE(r.summary, '') AS summary_text,
                       COALESCE(r.why_it_matters, '') AS why_text,
                       COALESCE(c.claim_text, '') AS claim_text,
                       COALESCE(d.entity_text, '') AS entity_text,
                       COALESCE(d.location_text, '') AS location_text,
                       COALESCE(d.source_text, '') AS source_text,
                       COALESCE(t.topic_text, '') AS topic_text,
                       COALESCE(u.subject_text, '') AS subject_text,
                       COALESCE(c.claim_total, 0) AS claim_total,
                       COALESCE(d.document_total, 0) AS document_total,
                       COALESCE(t.topic_total, 0) AS topic_total,
                       COALESCE(u.subject_total, 0) AS subject_total,
                       d.latest_event_key,
                       d.latest_published_at,
                       d.latest_first_retrieved_at
                FROM candidate_story_ids selected
                JOIN active_stories active ON active.id = selected.id
                JOIN stories s ON s.id = selected.id
                LEFT JOIN ranked_revisions r
                  ON r.story_id = s.id AND r.revision_rank = 1
                LEFT JOIN claim_summary c ON c.story_id = s.id
                LEFT JOIN document_summary d ON d.story_id = s.id
                LEFT JOIN topic_summary t ON t.story_id = s.id
                LEFT JOIN subject_summary u ON u.story_id = s.id
            )
            SELECT *
            FROM story_rows
            ORDER BY id
        """
        params.append(self.max_candidates + 1)
        owns_connection = conn is None
        conn = conn or storage.connect(self.db_path)
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            if owns_connection:
                conn.close()

        saturated = len(rows) > self.max_candidates
        candidates: list[StoryCandidate] = []
        invalid_data = False
        for row in rows[: self.max_candidates]:
            candidate, invalid = _row_candidate(row)
            invalid_data = invalid_data or invalid
            if candidate is not None:
                candidates.append(candidate)
        candidates.sort(key=lambda item: item.id)
        return _CandidateRetrieval(
            tuple(candidates),
            saturated=saturated,
            invalid_data=invalid_data,
        )


__all__ = [
    "AMBIGUOUS",
    "AutomaticStoryResolutionResult",
    "AutomaticStoryResolutionService",
    "DEFERRED",
    "MATCHED_EXISTING",
    "MAX_CANDIDATE_STORIES",
    "NO_MATCH",
    "QUALIFIED",
    "StoryMatchDecision",
    "StoryMatchSignal",
    "match_story_candidates",
]
