"""Semantic event signature handling (BUILD_PLAN §9).

The collector proposes a semantic event signature describing the actual
development (e.g. `valve-steamos-3-9-beta-release`). The backend:

- normalizes (lowercase ASCII alnum/hyphen, collapse separators)
- bounds length (default 120 chars)
- restricts to allowed form
- rejects malformed signatures
- generates a documented fallback when absent/invalid
- preserves existing event identity on merge (never rewrites on update)
- is corroborating evidence ONLY; never independently forces a merge
- explicitly excludes topic IDs from event identity
"""
from __future__ import annotations

import re
from typing import Optional


MAX_EVENT_KEY_LENGTH: int = 120
MIN_EVENT_KEY_TOKENS: int = 1     # a single token is a valid (if sparse) signature
MAX_EVENT_KEY_TOKENS: int = 16

# Allowed form: lowercase, ASCII alnum and hyphen, leading/trailing hyphens
# stripped. Tokens joined by single hyphens.
_TOKEN_RE = re.compile(r"[^a-z0-9]+")


def normalize_event_signature(raw: str | None) -> Optional[str]:
    """Normalize a model-proposed event signature.

    Returns the canonical signature string, or None if the input is
    absent / empty / cannot be normalized to a meaningful form.
    """
    if not isinstance(raw, str):
        return None
    s = raw.strip().lower()
    if not s:
        return None
    # Collapse separators to single hyphen, strip leading/trailing hyphens.
    s = _TOKEN_RE.sub("-", s).strip("-")
    if not s:
        return None
    tokens = [t for t in s.split("-") if t]
    if len(tokens) < MIN_EVENT_KEY_TOKENS:
        return None
    if len(tokens) > MAX_EVENT_KEY_TOKENS:
        tokens = tokens[:MAX_EVENT_KEY_TOKENS]
    out = "-".join(tokens)
    if len(out) > MAX_EVENT_KEY_LENGTH:
        out = out[:MAX_EVENT_KEY_LENGTH].rstrip("-")
    return out or None


def fallback_event_key(normalized_headline: str, leading_entity: str = "") -> str:
    """Generate a deterministic fallback event-key when the model supplies
    no usable signature.

    Uses the leading portion of the normalized headline plus any leading
    entity token. This is a *fallback*, not a semantic identity source.
    """
    base = (leading_entity or "").strip().lower()
    base = _TOKEN_RE.sub("-", base).strip("-")
    n = (normalized_headline or "").strip().lower()
    n = _TOKEN_RE.sub("-", n).strip("-")
    # Take the first 4 tokens of the normalized headline as a tail.
    tail_tokens = [t for t in n.split("-") if t][:4]
    combined = ([base] if base else []) + tail_tokens
    if not combined:
        combined = ["event"]
    s = "-".join(combined)
    if len(s) > MAX_EVENT_KEY_LENGTH:
        s = s[:MAX_EVENT_KEY_LENGTH].rstrip("-")
    return s or "event"


def event_keys_match(a: str | None, b: str | None) -> bool:
    """Return True if two non-empty event keys are equal.

    Used as *corroborating* evidence only. Never as the sole merge signal.
    """
    if not a or not b:
        return False
    return a == b


def event_signature_token_overlap(a: str | None, b: str | None) -> float:
    """Return a token-overlap score [0,1] between two event keys.

    Used by the dedupe module to support MODERATE merges: a high token
    overlap on the event signature, combined with overlapping headlines,
    increases confidence. ANY single signal alone is insufficient.
    """
    if not a or not b:
        return 0.0
    ta = set(a.split("-")) - {""}
    tb = set(b.split("-")) - {""}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
