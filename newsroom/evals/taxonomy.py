"""Evaluation case taxonomy.

The corpus must not accidentally consist only of easy announcements. Each case is
assigned exactly one ``case_type`` so coverage can be audited against the full
range of difficult, real-world scenarios the product must handle.
"""
from __future__ import annotations

# --- Case taxonomy --------------------------------------------------------

CASE_TYPES: frozenset[str] = frozenset(
    {
        "official_announcement",       # 1 simple official announcement
        "multi_outlet",                # 2 one event reported by many outlets
        "similar_distinct_events",     # 3 similar-but-distinct events, same subject
        "developing_story",            # 4 developing/breaking story
        "rumor_confirmed",             # 5 rumor followed by confirmation
        "rumor_unsubstantiated",       # 6 rumor remaining unsubstantiated
        "conflicting_reports",         # 7 conflicting credible reports
        "official_correction",         # 8 official correction
        "changing_numeric_claim",      # 9 numerical/date claim changing over time
        "primary_vs_secondary",        # 10 primary source vs secondary reporting
        "cross_topic",                 # 11 cross-topic story
        "stale_recycled",              # 12 stale/recycled article
        "low_quality_noise",           # 13 low-quality aggregation/noise
        "duplicate_syndication",       # 14 duplicate publication/syndication
        "corroboration_no_update",     # 15 corroboration but no material update
        "material_update",             # 16 genuine material story update
        "mutating_document",           # 17 source page changes after retrieval
        "ambiguous_merge",             # 18 ambiguous merge where false merge harmful
    }
)

# Human-readable short label for each case type (used by CLI/summary output).
CASE_TYPE_LABELS: dict[str, str] = {
    "official_announcement": "simple official announcement",
    "multi_outlet": "one event reported by many outlets",
    "similar_distinct_events": "similar-but-distinct events (same subject)",
    "developing_story": "developing / breaking story",
    "rumor_confirmed": "rumor followed by confirmation",
    "rumor_unsubstantiated": "rumor remaining unsubstantiated",
    "conflicting_reports": "conflicting credible reports",
    "official_correction": "official correction",
    "changing_numeric_claim": "numerical/date claim changing over time",
    "primary_vs_secondary": "primary source vs secondary reporting",
    "cross_topic": "cross-topic story",
    "stale_recycled": "stale / recycled article",
    "low_quality_noise": "low-quality aggregation / noise",
    "duplicate_syndication": "duplicate publication / syndication",
    "corroboration_no_update": "corroboration with no material update",
    "material_update": "genuine material story update",
    "mutating_document": "source document changes after retrieval",
    "ambiguous_merge": "ambiguous merge where false merge is harmful",
}

# --- Domain enums shared by the evaluation contract ------------------------

CLAIM_STATES: frozenset[str] = frozenset(
    {
        "pending",
        "supported",
        "partially_supported",
        "disputed",
        "unsubstantiated",
        "superseded",
    }
)

EVIDENCE_RELATIONSHIPS: frozenset[str] = frozenset(
    {"supports", "contradicts", "contextualizes"}
)

IMPORTANCES: frozenset[str] = frozenset({"major", "relevant", "peripheral"})

CONTENT_TYPES: frozenset[str] = frozenset({"metadata", "excerpt", "full_text"})

MONITOR_TARGET_KINDS: frozenset[str] = frozenset(
    {"topic", "subject", "story", "source", "research_question"}
)
