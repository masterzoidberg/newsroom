"""Deduplication engine tests."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from newsroom.dedupe import merge_decision, CandidateStory
from newsroom.event_sig import normalize_event_signature


def _candidate(
    id: str,
    headline: str,
    *,
    topic_ids: list[str] | None = None,
    event_key: str = "",
    source_urls: list[str] | None = None,
    published_at: str | None = None,
    created_at: str = "2026-01-01T00:00:00Z",
) -> CandidateStory:
    return CandidateStory(
        id=id,
        headline=headline,
        normalized_headline=headline.lower(),
        event_key=event_key,
        published_at=published_at,
        created_at=created_at,
        topic_ids=list(topic_ids or []),
        source_canonical_urls=set(source_urls or []),
    )


def _new_sources(*urls: str) -> list[dict]:
    from newsroom.url_norm import normalize_url
    return [
        {
            "title": "x", "url": normalize_url(u), "canonical_url": normalize_url(u),
            "domain": "example.com", "published_at": None,
            "source_type": "web", "source_quality": "medium",
            "is_primary": False, "fp_url": "",
        }
        for u in urls
    ]


# --- Stage 1: URL identity ----------------------------------------------

def test_identical_url_merges():
    cand = _candidate("s1", "Anything", source_urls=[
        "https://example.com/post/1",
    ])
    srcs = _new_sources("https://example.com/post/1")
    d = merge_decision(
        [cand], "Completely different headline",
        "completely different headline",
        srcs, ["t1"], None, None,
    )
    assert d["action"] == "merge"
    assert d["story_id"] == "s1"
    assert d["via"] == "url_identity"


def test_tracking_variant_merges():
    cand = _candidate("s1", "Headline", source_urls=[
        "https://example.com/post/1",
    ])
    srcs = _new_sources("https://example.com/post/1?utm_source=tw")
    d = merge_decision(
        [cand], "Headline", "headline",
        srcs, ["t1"], None, None,
    )
    assert d["action"] == "merge"


def test_www_variant_merges():
    cand = _candidate("s1", "Headline", source_urls=[
        "https://example.com/post/1",
    ])
    srcs = _new_sources("https://www.example.com/post/1")
    d = merge_decision(
        [cand], "Headline", "headline",
        srcs, ["t1"], None, None,
    )
    assert d["action"] == "merge"


# --- Stages 2-4: headline + event signature -----------------------------

def test_same_event_new_source_merges():
    """Same event from different publisher, similar headline -> merge."""
    cand = _candidate(
        "s1", "Valve releases SteamOS 3.9 beta",
        topic_ids=["t_steamdeck"], event_key="valve-steamos-3-9-beta",
        source_urls=["https://a.com/post/1"],
    )
    srcs = _new_sources("https://b.com/post/55")
    d = merge_decision(
        [cand], "Valve releases SteamOS 3.9 beta update",
        "valve releases steamos 3.9 beta update",
        srcs, ["t_steamdeck"], "valve-steamos-3-9-beta", None,
    )
    assert d["action"] == "merge"
    assert d["story_id"] == "s1"


def test_minor_headline_rewrite_merges():
    cand = _candidate(
        "s1", "Valve releases SteamOS 3.9 beta",
        topic_ids=["t_steamdeck"], event_key="valve-steamos-3-9-beta",
        source_urls=["https://a.com/post/1"],
    )
    srcs = _new_sources("https://b.com/post/55")
    d = merge_decision(
        [cand], "SteamOS 3.9 beta released by Valve for Steam Deck",
        "steamos 3.9 beta released by valve for steam deck",
        srcs, ["t_steamdeck"], "valve-steamos-3-9-beta", None,
    )
    assert d["action"] == "merge"


def test_same_entity_different_event_does_not_merge():
    """Valve SteamOS release vs Valve Steam Deck hardware announcement."""
    cand = _candidate(
        "s1", "Valve releases SteamOS 3.9 update",
        topic_ids=["t_steamdeck"], event_key="valve-steamos-3-9-release",
        source_urls=["https://a.com/1"],
    )
    srcs = _new_sources("https://b.com/2")
    d = merge_decision(
        [cand], "Valve announces new Steam Deck hardware refresh",
        "valve announces new steam deck hardware refresh",
        srcs, ["t_steamdeck"], "valve-steam-deck-hardware-refresh", None,
    )
    assert d["action"] == "new"


def test_openai_model_vs_pricing_does_not_merge():
    cand = _candidate(
        "s1", "OpenAI launches GPT-5 API",
        topic_ids=["t_openai"], event_key="openai-gpt-5-api-launch",
        source_urls=["https://a.com/1"],
    )
    srcs = _new_sources("https://b.com/2")
    d = merge_decision(
        [cand], "OpenAI changes API pricing for GPT-4",
        "openai changes api pricing for gpt-4",
        srcs, ["t_openai"], "openai-gpt-4-api-pricing-change", None,
    )
    assert d["action"] == "new"


def test_fallout_5_vs_tv_series_does_not_merge():
    cand = _candidate(
        "s1", "Bethesda announces Fallout 5 development update",
        topic_ids=["t_bethesda"], event_key="bethesda-fallout-5-development",
        source_urls=["https://a.com/1"],
    )
    srcs = _new_sources("https://b.com/2")
    d = merge_decision(
        [cand], "Fallout TV series renewed for season 2 on Amazon",
        "fallout tv series renewed for season 2 on amazon",
        srcs, ["t_bethesda"], "fallout-tv-series-season-2-renewal", None,
    )
    assert d["action"] == "new"


def test_no_topic_overlap_creates_new_story():
    """Same event vocabulary but completely different topic -> new."""
    cand = _candidate(
        "s1", "Steam Deck OLED review",
        topic_ids=["t_steamdeck"], event_key="steam-deck-oled-review",
        source_urls=["https://a.com/1"],
    )
    srcs = _new_sources("https://b.com/2")
    d = merge_decision(
        [cand], "Steam Deck OLED review",
        "steam deck oled review",
        srcs, ["t_openai"], None, None,
    )
    assert d["action"] == "new"


def test_event_signature_alone_does_not_merge():
    """Event signature match alone must NOT force a merge."""
    cand = _candidate(
        "s1", "Valve releases SteamOS 3.9",
        topic_ids=["t_steamdeck"], event_key="valve-steamos-3-9",
        source_urls=["https://a.com/1"],
    )
    srcs = _new_sources("https://b.com/2")
    # Headline is materially different; event sigs match.
    d = merge_decision(
        [cand], "Bethesda announces Fallout 5",
        "bethesda announces fallout 5",
        srcs, ["t_steamdeck"], "valve-steamos-3-9", None,
    )
    assert d["action"] == "new"


def test_incompatible_timing_creates_new_story():
    """VERY_HIGH headline but timing out of range -> new story."""
    cand = _candidate(
        "s1", "Valve releases SteamOS 3.9",
        topic_ids=["t_steamdeck"], event_key="valve-steamos-3-9",
        source_urls=["https://a.com/1"],
        published_at="2026-01-01T00:00:00Z",
    )
    srcs = _new_sources("https://b.com/2")
    far = "2026-06-01T00:00:00Z"
    d = merge_decision(
        [cand], "Valve releases SteamOS 3.9",
        "valve releases steamos 3.9",
        srcs, ["t_steamdeck"], "valve-steamos-3-9", far,
    )
    assert d["action"] == "new"


def test_moderate_headline_with_event_signature_overlap_merges():
    """MODERATE headline + event sig token overlap -> merge."""
    cand = _candidate(
        "s1", "Valve ships SteamOS 3.9 update",
        topic_ids=["t_steamdeck"], event_key="valve-steamos-3-9-release",
        source_urls=["https://a.com/1"],
    )
    srcs = _new_sources("https://b.com/2")
    d = merge_decision(
        [cand], "Valve pushes SteamOS 3.9 patch",
        "valve pushes steamos 3.9 patch",
        srcs, ["t_steamdeck"], "valve-steamos-3-9-release-notes", None,
    )
    assert d["action"] == "merge"


def test_event_signature_disjoint_with_moderate_does_not_merge():
    cand = _candidate(
        "s1", "Valve ships SteamOS 3.9 update",
        topic_ids=["t_steamdeck"], event_key="valve-steamos-3-9-release",
        source_urls=["https://a.com/1"],
    )
    srcs = _new_sources("https://b.com/2")
    d = merge_decision(
        [cand], "Valve pushes SteamOS 3.9 patch",
        "valve pushes steamos 3.9 patch",
        srcs, ["t_steamdeck"], "openai-gpt-5-launch", None,
    )
    # Without sig corroboration, MODERATE alone is not a merge.
    assert d["action"] == "new"


def test_no_candidates_returns_new():
    d = merge_decision(
        [], "Anything", "anything",
        _new_sources("https://example.com/1"),
        ["t1"], None, None,
    )
    assert d["action"] == "new"


def test_entity_only_overlap_does_not_merge():
    """Topic overlap alone must not trigger a merge."""
    cand = _candidate(
        "s1", "Microsoft releases Windows 12",
        topic_ids=["t_ms"], event_key="microsoft-windows-12-release",
        source_urls=["https://a.com/1"],
    )
    srcs = _new_sources("https://b.com/2")
    d = merge_decision(
        [cand], "Microsoft acquires major gaming studio",
        "microsoft acquires major gaming studio",
        srcs, ["t_ms"], "microsoft-gaming-acquisition", None,
    )
    assert d["action"] == "new"


def test_normalize_event_signature_used_in_dedupe():
    """The dedupe helper normalizes raw signatures before comparing."""
    from newsroom.event_sig import normalize_event_signature
    out = normalize_event_signature("Valve SteamOS 3.9 Beta Release")
    assert out == "valve-steamos-3-9-beta-release"
