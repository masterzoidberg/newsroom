"""Deterministic headline similarity (BUILD_PLAN §8.3-§8.4).

Three cheap signals combined conservatively:
- Jaccard similarity on token sets
- Overlap coefficient (`|A∩B| / min(|A|,|B|)`)
- `difflib.SequenceMatcher.ratio()` (order-sensitive near-match)

The combined `headline_sim` is classified into one of three buckets:
- VERY_HIGH  -> merge candidate (with topic & time compatibility)
- MODERATE   -> require corroborating event signature
- LOW        -> never merge

Thresholds are named constants. The plan calls `sim_very_high >= 0.80`
(e.g. `jaccard >= 0.80 AND overlap_coef >= 0.85`) and
`sim_moderate_lo = 0.50`. False merges are worse than occasional duplicates.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


# --- Thresholds ------------------------------------------------------------

SIM_VERY_HIGH: float = 0.80      # headline_sim >= this -> VERY_HIGH
SIM_MODERATE_LO: float = 0.50    # [0.50, 0.80) -> MODERATE; below -> LOW

# VERY_HIGH requires *both* jaccard and overlap to clear these:
JACCARD_VERY_HIGH: float = 0.80
OVERLAP_VERY_HIGH: float = 0.85

# MODERATE requires event-signature corroboration (see dedupe.py).
# Entity-only / topic-only overlap is NEVER sufficient.


# --- Conservative stop-word set -------------------------------------------
# Articles, common prepositions, generic connector words. Kept short.
# Numbers, versions, product names, and ticker-like tokens are preserved.
STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "in", "is", "it", "its", "of", "on", "or", "that",
    "the", "to", "was", "were", "will", "with", "this", "into",
})


# --- Normalization ----------------------------------------------------------


def normalize_headline(text: str) -> str:
    """Normalize a headline for storage and reuse.

    Steps:
    1. Unicode NFKD (decompose accents into base + combining marks).
    2. Drop combining marks (fold accents away).
    3. Lowercase.
    4. Strip punctuation EXCEPT intra-alnum `-` and `.` (so `steamos-3.9`
       and `3.9` survive intact).
    5. Collapse whitespace.
    """
    if not isinstance(text, str):
        return ""
    n = unicodedata.normalize("NFKD", text)
    # Remove combining marks (accents).
    n = "".join(ch for ch in n if not unicodedata.combining(ch))
    n = n.lower()
    # Keep letters, digits, whitespace, dot, hyphen.
    n = re.sub(r"[^a-z0-9\s\.\-]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _strip_token_edges(tok: str) -> str:
    """Strip leading/trailing dot and hyphen so `beta.` becomes `beta`.

    Internal dots and hyphens are preserved (e.g. `steamos-3.9`).
    """
    return tok.strip("-.")


def tokenize(text: str) -> list[str]:
    """Tokenize a normalized headline into a list of content tokens.

    Drop a small conservative stop-word set. Preserve numbers, versions,
    product names (e.g. `steamos-3.9`, `3.9`, `gpt-5`, `valve`).
    """
    if not text:
        return []
    raw = text.split(" ")
    cleaned = []
    for t in raw:
        t = _strip_token_edges(t)
        if t and t not in STOP_WORDS:
            cleaned.append(t)
    return cleaned


def _token_set(tokens: Iterable[str]) -> frozenset[str]:
    return frozenset(tokens)


# --- Individual signals ----------------------------------------------------


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    inter = sa & sb
    union = sa | sb
    return len(inter) / len(union)


def overlap_coefficient(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def seqmatch_ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# --- Combined classification ----------------------------------------------


@dataclass
class HeadlineSimilarity:
    """One class of similarity result for a headline pair."""
    jaccard: float
    overlap: float
    seqmatch: float
    headline_sim: float      # the combined scalar
    level: str               # "VERY_HIGH" | "MODERATE" | "LOW"


def headline_similarity(a: str, b: str) -> HeadlineSimilarity:
    """Compute the conservative similarity between two headlines.

    Returns the per-signal metrics and a level classification.
    """
    na = normalize_headline(a)
    nb = normalize_headline(b)
    ta = tokenize(na)
    tb = tokenize(nb)

    j = jaccard(ta, tb)
    o = overlap_coefficient(ta, tb)
    s = seqmatch_ratio(na, nb)

    # Combined scalar: weighted combination favoring the conservative
    # signals. Order-sensitivity (seqmatch) is included but with the
    # smallest weight. Jaccard is the primary token-set signal.
    headline_sim = 0.5 * j + 0.3 * o + 0.2 * s

    if headline_sim >= SIM_VERY_HIGH and j >= JACCARD_VERY_HIGH and o >= OVERLAP_VERY_HIGH:
        level = "VERY_HIGH"
    elif headline_sim >= SIM_MODERATE_LO:
        level = "MODERATE"
    else:
        level = "LOW"

    return HeadlineSimilarity(
        jaccard=j,
        overlap=o,
        seqmatch=s,
        headline_sim=headline_sim,
        level=level,
    )


def is_very_high(sim: HeadlineSimilarity) -> bool:
    return sim.level == "VERY_HIGH"


def is_moderate(sim: HeadlineSimilarity) -> bool:
    return sim.level == "MODERATE"


def is_merge_candidate(sim: HeadlineSimilarity) -> bool:
    """True if the headline similarity alone is sufficient to merge.

    Per BUILD_PLAN §8.5: VERY_HIGH alone is sufficient. MODERATE is not
    -- it requires event-signature corroboration (handled in dedupe.py).
    """
    return sim.level == "VERY_HIGH"
