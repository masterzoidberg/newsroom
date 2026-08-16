"""Event signature tests."""
from __future__ import annotations

import pytest

from newsroom.event_sig import (
    MAX_EVENT_KEY_LENGTH,
    event_keys_match,
    event_signature_token_overlap,
    fallback_event_key,
    normalize_event_signature,
)


# --- Normalization -------------------------------------------------------

def test_basic_normalization():
    out = normalize_event_signature("Valve SteamOS 3.9 Beta Release")
    assert out == "valve-steamos-3-9-beta-release"


def test_lowercases():
    assert normalize_event_signature("OPENAI GPT-5") == "openai-gpt-5"


def test_collapses_separators():
    assert normalize_event_signature("valve___steamos   3.9   release") == \
        "valve-steamos-3-9-release"


def test_strips_edge_hyphens():
    assert normalize_event_signature("--valve--") == "valve"


def test_strips_non_alnum_chars():
    assert normalize_event_signature("openai@gpt!5") == "openai-gpt-5"


def test_normalizes_dots():
    assert normalize_event_signature("steamos.3.9") == "steamos-3-9"


def test_cap_at_max_length():
    raw = " ".join(f"word{i}" for i in range(50))
    out = normalize_event_signature(raw)
    assert out is not None
    assert len(out) <= MAX_EVENT_KEY_LENGTH


def test_token_count_bounded():
    raw = " ".join(f"t{i}" for i in range(40))
    out = normalize_event_signature(raw)
    assert out is not None
    assert out.count("-") + 1 <= 16


def test_single_token_is_accepted():
    """A single token is a valid (if sparse) event signature."""
    assert normalize_event_signature("release") == "release"


def test_rejects_empty_string():
    assert normalize_event_signature("") is None
    assert normalize_event_signature("   ") is None


def test_rejects_none():
    assert normalize_event_signature(None) is None


def test_rejects_non_string():
    assert normalize_event_signature(123) is None  # type: ignore


def test_rejects_only_separators():
    """After stripping, no tokens remain."""
    assert normalize_event_signature("---") is None


def test_rejects_only_garbage():
    assert normalize_event_signature("@!#$%") is None


# --- Fallback -----------------------------------------------------------

def test_fallback_uses_normalized_headline():
    out = fallback_event_key(
        normalized_headline="valve releases steamos 3.9",
        leading_entity="",
    )
    assert out.startswith("valve-releases-steamos-3.9") or "valve" in out


def test_fallback_includes_leading_entity():
    out = fallback_event_key(
        normalized_headline="releases steamos 3.9",
        leading_entity="valve",
    )
    assert out.startswith("valve")


def test_fallback_handles_empty_inputs():
    out = fallback_event_key(normalized_headline="", leading_entity="")
    assert out == "event"


def test_fallback_caps_length():
    long_h = " ".join(f"word{i}" for i in range(50))
    out = fallback_event_key(normalized_headline=long_h, leading_entity="")
    assert len(out) <= MAX_EVENT_KEY_LENGTH


def test_fallback_is_deterministic():
    a = fallback_event_key("valve releases steamos 3.9", "valve")
    b = fallback_event_key("valve releases steamos 3.9", "valve")
    assert a == b


# --- Match / overlap ---------------------------------------------------

def test_match_identical():
    assert event_keys_match("valve-steamos-3-9", "valve-steamos-3-9") is True


def test_match_different():
    assert event_keys_match("valve-steamos-3-9", "openai-gpt-5") is False


def test_match_empty_returns_false():
    assert event_keys_match(None, "x") is False
    assert event_keys_match("x", None) is False
    assert event_keys_match("", "x") is False


def test_token_overlap_partial():
    o = event_signature_token_overlap(
        "valve-steamos-3-9-release",
        "valve-steamos-3-9-beta",
    )
    assert 0.0 < o < 1.0


def test_token_overlap_complete():
    assert event_signature_token_overlap(
        "valve-steamos-3-9", "valve-steamos-3-9"
    ) == 1.0


def test_token_overlap_disjoint():
    assert event_signature_token_overlap(
        "valve-steamos-3-9", "openai-gpt-5-launch"
    ) == 0.0


def test_token_overlap_empty_returns_zero():
    assert event_signature_token_overlap(None, "x") == 0.0
    assert event_signature_token_overlap("", "x") == 0.0


# --- Invariant: signature alone never merges ---------------------------

def test_signature_equality_alone_is_not_a_merge_signal():
    """Documented: signature equality is corroborating evidence ONLY.

    This test asserts the helper contract returns a boolean that callers
    must combine with other signals. The helper itself is correct; the
    dedupe module is responsible for NOT using the match alone.
    """
    assert event_keys_match("x", "x") is True
    # And corroborating semantics are enforced upstream.
    # See test_dedupe.py for the integration assertion.
