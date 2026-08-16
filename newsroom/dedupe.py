"""Dedup / merge decision engine (BUILD_PLAN §8).

Conservative pipeline:

1. Canonical URL exact identity (canonical_url match across stories).
2. Candidate narrowing (bounded by topic overlap + time window).
3. Conservative deterministic headline similarity.
4. Semantic event-signature corroboration.
5. Anti-entity-only-merge safeguards.
6. Final create-vs-merge decision.

False merges are worse than occasional duplicate story cards. When
evidence is ambiguous, we create a new story.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from .event_sig import (
    event_keys_match,
    event_signature_token_overlap,
    normalize_event_signature,
)
from .similarity import (
    HeadlineSimilarity,
    headline_similarity,
    is_merge_candidate,
    is_moderate,
)
from .url_norm import normalize_url


# Stage-1: existing source canonical_url hit returns this flag.
DUPLICATE_SOURCE_URL = "duplicate_source_url"


@dataclass
class CandidateStory:
    """Lightweight candidate record scoped to the merge decision."""
    id: str
    headline: str
    normalized_headline: str
    event_key: str
    published_at: Optional[str]
    created_at: str
    topic_ids: list[str]
    source_canonical_urls: set[str]


def _iso(v: Optional[str]) -> Optional[datetime]:
    if not v:
        return None
    try:
        return datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _merge_tolerance_hours(story_meta: Optional[dict[str, Any]] = None) -> int:
    """Time-compatibility window for merges. Caller can override via settings."""
    if story_meta and "merge_tolerance_hours" in story_meta:
        return int(story_meta["merge_tolerance_hours"])
    return 72


def _sources_for_story(conn: Any, story_id: str) -> set[str]:
    """Return the set of canonical URLs attached to a story."""
    return {
        r["canonical_url"]
        for r in conn.execute(
            "SELECT canonical_url FROM sources WHERE story_id = ?", (story_id,)
        )
    }


def _topic_ids_for_story(conn: Any, story_id: str) -> list[str]:
    return [
        r["topic_id"]
        for r in conn.execute(
            "SELECT topic_id FROM story_topics WHERE story_id = ?", (story_id,)
        )
    ]


def _build_candidate(
    conn: Any,
    story_row: dict[str, Any],
) -> CandidateStory:
    return CandidateStory(
        id=story_row["id"],
        headline=story_row["headline"],
        normalized_headline=story_row["normalized_headline"],
        event_key=story_row["event_key"],
        published_at=story_row.get("published_at"),
        created_at=story_row["created_at"],
        topic_ids=_topic_ids_for_story(conn, story_row["id"]),
        source_canonical_urls=_sources_for_story(conn, story_row["id"]),
    )


def _time_compatible(
    new_published_at: Optional[str],
    candidate_published_at: Optional[str],
    candidate_created_at: str,
    tolerance_hours: int,
) -> bool:
    """True if the new story's timing is compatible with the candidate.

    If both have a published_at, use |diff| <= tolerance_hours.
    Otherwise, fall back to candidate_created_at vs now.
    """
    new_ts = _iso(new_published_at)
    cand_pub = _iso(candidate_published_at)
    cand_created = _iso(candidate_created_at)
    if new_ts is not None and cand_pub is not None:
        return abs((new_ts - cand_pub).total_seconds()) <= tolerance_hours * 3600
    if new_ts is not None and cand_created is not None:
        return abs((new_ts - cand_created).total_seconds()) <= tolerance_hours * 3600
    # If both sides lack timing metadata, do not block the merge on
    # missing data. The candidate-recency window already filters old
    # candidates (bounded by dedupe_history_days). Refuse only when
    # one side has a date that contradicts the other side's date.
    if cand_pub is None and cand_created is not None:
        # Compare candidate's created_at to now. The candidate window is
        # already bounded by dedupe_history_days (default 14). If a
        # candidate is here at all, it is recent enough.
        return True
    if new_ts is None and cand_pub is None:
        # No timing on either side -> allow.
        return True
    return False


def _stage1_url_identity(
    new_sources: list[dict[str, Any]],
    candidates: list[CandidateStory],
) -> Optional[str]:
    """Stage 1: exact canonical URL identity. Returns the matching story_id."""
    new_canon = {
        normalize_url(s["canonical_url"])
        for s in new_sources
        if isinstance(s, dict) and isinstance(s.get("canonical_url"), str)
    }
    hits = []
    for c in candidates:
        candidate_urls = {
            normalize_url(url) for url in c.source_canonical_urls
        }
        if candidate_urls & new_canon:
            hits.append(c.id)
    return min(hits) if hits else None


def _stage2_3_4_headline_merge(
    new_headline: str,
    new_normalized_headline: str,
    new_topic_ids: list[str],
    new_event_signature: Optional[str],
    new_published_at: Optional[str],
    candidates: list[CandidateStory],
    tolerance_hours: int,
) -> Optional[CandidateStory]:
    """Stages 2-4: candidate narrowing + headline sim + event corroboration.

    Returns the candidate to merge into, or None to create a new story.
    """
    new_topic_set = set(new_topic_ids)
    eligible: list[tuple[CandidateStory, tuple[float, ...]]] = []
    for c in candidates:
        # Stage 2: topic overlap.
        if not (new_topic_set & set(c.topic_ids)):
            continue
        # Stage 3: time compatibility.
        if not _time_compatible(
            new_published_at, c.published_at, c.created_at, tolerance_hours
        ):
            continue
        sim: HeadlineSimilarity = headline_similarity(new_headline, c.headline)
        # Stage 4: VERY_HIGH is sufficient on its own.
        if is_merge_candidate(sim):
            eligible.append(
                (
                    c,
                    (
                        2.0,
                        sim.headline_sim,
                        sim.jaccard,
                        sim.overlap,
                        sim.seqmatch,
                        0.0,
                    ),
                )
            )
            continue
        # MODERATE requires event-signature corroboration.
        if is_moderate(sim):
            sig_eq = event_keys_match(new_event_signature, c.event_key)
            sig_overlap = event_signature_token_overlap(
                new_event_signature, c.event_key
            )
            if sig_eq or sig_overlap >= 0.5:
                eligible.append(
                    (
                        c,
                        (
                            1.0,
                            sim.headline_sim,
                            sim.jaccard,
                            sim.overlap,
                            sim.seqmatch,
                            1.0 if sig_eq else sig_overlap,
                        ),
                    )
                )
        # Entity-only / topic-only overlap is NEVER sufficient.
    if not eligible:
        return None
    eligible.sort(
        key=lambda item: (
            -item[1][0],
            -item[1][1],
            -item[1][2],
            -item[1][3],
            -item[1][4],
            -item[1][5],
            item[0].id,
        )
    )
    return eligible[0][0]


def merge_decision(
    existing_stories: list[dict[str, Any]],
    new_headline: str,
    new_normalized_headline: str,
    new_sources: list[dict[str, Any]],
    new_topic_ids: list[str],
    new_event_signature: Optional[str],
    new_published_at: Optional[str],
    *,
    merge_tolerance_hours: int = 72,
) -> dict[str, Any]:
    """Pure decision function over already-built candidate records.

    Returns a dict with `action` in {new, merge, duplicate_source_url} and
    an optional `story_id`. Does not open a DB connection.
    """
    # Accept both raw dicts (DB rows) and pre-built CandidateStory objects.
    candidates: list[CandidateStory] = []
    for row in existing_stories:
        if isinstance(row, CandidateStory):
            candidates.append(row)
        else:
            candidates.append(
                CandidateStory(
                    id=row["id"],
                    headline=row["headline"],
                    normalized_headline=row.get("normalized_headline") or "",
                    event_key=row.get("event_key") or "",
                    published_at=row.get("published_at"),
                    created_at=row.get("created_at") or "",
                    topic_ids=list(row.get("topic_ids") or []),
                    source_canonical_urls=set(row.get("source_canonical_urls") or []),
                )
            )

    # Stage 1: canonical URL identity.
    hit = _stage1_url_identity(new_sources, candidates)
    if hit:
        return {"action": "merge", "story_id": hit, "via": "url_identity"}

    # Stage 4-equivalent: detect the case where the same canonical URL
    # already exists but on a different story (rare but possible via UI).
    # Reuse Stage 1; if no match, fall through to stages 2-4.

    # Stages 2-4.
    chosen = _stage2_3_4_headline_merge(
        new_headline=new_headline,
        new_normalized_headline=new_normalized_headline,
        new_topic_ids=new_topic_ids,
        new_event_signature=new_event_signature,
        new_published_at=new_published_at,
        candidates=candidates,
        tolerance_hours=merge_tolerance_hours,
    )
    if chosen is not None:
        return {"action": "merge", "story_id": chosen.id, "via": "headline_sim"}

    return {"action": "new"}
