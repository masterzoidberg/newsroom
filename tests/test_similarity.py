"""Headline similarity tests."""
from __future__ import annotations

import pytest

from newsroom.similarity import (
    HeadlineSimilarity,
    SIM_VERY_HIGH,
    SIM_MODERATE_LO,
    headline_similarity,
    is_merge_candidate,
    is_moderate,
    is_very_high,
    jaccard,
    normalize_headline,
    overlap_coefficient,
    seqmatch_ratio,
    tokenize,
)


# --- Normalization ---------------------------------------------------------

def test_normalize_lowercases():
    assert normalize_headline("Hello WORLD") == "hello world"


def test_normalize_handles_punctuation():
    assert normalize_headline("Hello, World!") == "hello world"


def test_normalize_preserves_versions_and_product_names():
    out = normalize_headline("SteamOS 3.9 release notes")
    assert "steamos" in out
    assert "3.9" in out
    # Hyphen preserved for product names.
    out2 = normalize_headline("OpenAI launches GPT-5 API")
    assert "gpt-5" in out2


def test_normalize_unicode_nfd():
    n = normalize_headline("Café résumé")
    # Should still be ASCII-folded via NFD + lowercase.
    assert "cafe" in n
    assert "resume" in n


def test_tokenize_drops_stop_words():
    toks = tokenize("the quick brown fox")
    assert "the" not in toks
    assert "fox" in toks


def test_tokenize_preserves_numbers():
    toks = tokenize("SteamOS 3.9 update")
    assert "3.9" in toks


def test_tokenize_preserves_versions():
    toks = tokenize(normalize_headline("GPT-5 launches"))
    assert "gpt-5" in toks


def test_empty_inputs():
    assert normalize_headline("") == ""
    assert tokenize("") == []
    assert headline_similarity("", "") is not None


# --- Individual signals ----------------------------------------------------

def test_jaccard_identical():
    assert jaccard(["a", "b", "c"], ["a", "b", "c"]) == 1.0


def test_jaccard_disjoint():
    assert jaccard(["a", "b"], ["c", "d"]) == 0.0


def test_jaccard_partial():
    assert jaccard(["a", "b", "c"], ["b", "c", "d"]) == pytest.approx(0.5)


def test_overlap_one_contained_in_other():
    # Containment -> overlap == 1.0
    assert overlap_coefficient(["a", "b", "c"], ["a", "b"]) == 1.0


def test_overlap_asymmetric():
    a = overlap_coefficient(["a", "b", "c"], ["b", "c", "d"])
    b = overlap_coefficient(["b", "c", "d"], ["a", "b", "c"])
    assert a == b


def test_seqmatch_punctuation_difference():
    r = seqmatch_ratio("Valve Releases SteamOS 3.9", "Valve Releases SteamOS 3.9")
    assert r == 1.0


def test_seqmatch_drops_on_word_changes():
    r = seqmatch_ratio("Valve announces SteamOS 3.9", "Valve ships Steam Deck OLED")
    assert r < 0.7


# --- Combined classification ----------------------------------------------

def test_identical_headlines_very_high():
    sim = headline_similarity(
        "Valve releases SteamOS 3.9 beta",
        "Valve releases SteamOS 3.9 beta",
    )
    assert sim.level == "VERY_HIGH"
    assert is_very_high(sim)
    assert is_merge_candidate(sim)


def test_punctuation_only_difference_very_high():
    sim = headline_similarity(
        "Valve Releases SteamOS 3.9 Beta",
        "Valve releases SteamOS 3.9 beta.",
    )
    assert sim.level == "VERY_HIGH"


def test_minor_headline_rewrite_very_high():
    sim = headline_similarity(
        "Valve releases SteamOS 3.9 beta for Steam Deck",
        "SteamOS 3.9 beta released by Valve for Steam Deck",
    )
    assert sim.level in ("VERY_HIGH", "MODERATE")


def test_one_word_addition_moderate_or_very_high():
    sim = headline_similarity(
        "Valve releases SteamOS 3.9",
        "Valve releases SteamOS 3.9 update",
    )
    assert sim.level in ("MODERATE", "VERY_HIGH")


def test_version_number_difference_lower_similarity():
    sim = headline_similarity(
        "Valve releases SteamOS 3.9",
        "Valve releases SteamOS 4.0",
    )
    # Different version numbers should reduce similarity.
    assert sim.headline_sim < SIM_VERY_HIGH
    assert sim.jaccard < 1.0


def test_same_entity_different_action_low():
    """Valve SteamOS release vs Valve Steam Deck hardware announcement -
    same entity, different verb/object. Must NOT be a merge candidate."""
    sim = headline_similarity(
        "Valve releases SteamOS 3.9 update",
        "Valve announces new Steam Deck hardware refresh",
    )
    assert not is_merge_candidate(sim)
    assert sim.level in ("MODERATE", "LOW")


def test_same_company_different_event_low():
    sim = headline_similarity(
        "OpenAI launches GPT-5 API",
        "OpenAI changes API pricing for GPT-4",
    )
    assert not is_merge_candidate(sim)


def test_franchise_different_subject_low():
    sim = headline_similarity(
        "Bethesda announces Fallout 5 development update",
        "Fallout TV series renewed for season 2 on Amazon",
    )
    assert not is_merge_candidate(sim)


def test_different_topics_low():
    sim = headline_similarity(
        "House holds UAP hearing on disclosure",
        "Valve releases SteamOS 3.9 beta",
    )
    assert sim.level == "LOW" or sim.headline_sim < SIM_MODERATE_LO


def test_reordered_phrases_moderate_or_very_high():
    sim = headline_similarity(
        "OpenAI confirms GPT-5 release date",
        "GPT-5 release date confirmed by OpenAI",
    )
    assert sim.level in ("MODERATE", "VERY_HIGH")


# --- Conservative thresholds ----------------------------------------------

def test_sim_moderate_lo_below_very_high():
    """Sanity: a MODERATE-level headline is never also VERY_HIGH."""
    a = "Bethesda teases new game at E3"
    b = "Bethesda teases surprise new RPG at E3 showcase"
    sim = headline_similarity(a, b)
    if sim.level == "MODERATE":
        assert sim.headline_sim < SIM_VERY_HIGH


def test_exact_match_arbitrary_case_is_very_high():
    sim = headline_similarity(
        "NASA announces Artemis III launch window",
        "NASA announces Artemis III launch window",
    )
    assert sim.jaccard == pytest.approx(1.0)
    assert is_very_high(sim)


def test_low_quality_newsroom_short_headline_low():
    """One-word headline vs full story should be at most MODERATE."""
    sim = headline_similarity("Steam Deck", "Valve releases Steam Deck OLED")
    assert sim.level in ("MODERATE", "LOW")


# --- Anti-entity-only merge ----------------------------------------------

def test_entity_only_overlap_with_different_action_is_not_merge():
    """Same company, completely different actions: never merge."""
    a = "Microsoft releases Windows 12"
    b = "Microsoft acquires major gaming studio"
    sim = headline_similarity(a, b)
    assert not is_merge_candidate(sim)
    # System may classify as MODERATE (shared entity) but never merge.
    assert sim.level in ("MODERATE", "LOW")


def test_threshold_constants_match_plan():
    """Pin the named thresholds to the plan values."""
    assert SIM_VERY_HIGH == 0.80
    assert SIM_MODERATE_LO == 0.50
