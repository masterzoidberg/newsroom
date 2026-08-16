"""Deterministic retrieval replay.

A fixture is a frozen, normalized capture of what a retrieval step produced.
Replay loads the fixture, verifies its integrity hash, and re-normalizes each
document into the exact form downstream matching logic consumes -- without
contacting the live web.

Guarantees enforced here:

- integrity: the fixture ``content_hash`` must match the SHA-256 of the
  canonical JSON encoding of its ``documents`` list; per-document hashes must
  match each document's canonical fields;
- determinism: the same fixture always yields the same normalized inputs and
  the same ``replay_hash``;
- no network: replay only reads local fixture data and hashes strings.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional

from . import SCHEMA_VERSION
from .schema import ValidationError, canonical_json, content_hash
from ..url_norm import normalize_url, parse_url
from ..similarity import normalize_headline
from ..event_sig import normalize_event_signature, fallback_event_key

CONTENT_TYPES: frozenset[str] = frozenset({"metadata", "excerpt", "full_text"})


@dataclass(frozen=True)
class NormalizedCandidate:
    candidate_id: str
    canonical_url: str
    normalized_url: str
    fp_url: str
    domain: str
    title: str
    normalized_headline: str
    event_key: str
    publisher: Optional[str]
    published_at: Optional[str]
    retrieved_at: Optional[str]
    content_type: str
    excerpt: Optional[str]
    content_hash: str


@dataclass(frozen=True)
class ReplayResult:
    fixture_id: str
    case_id: str
    channel: str
    query: dict[str, str]
    captured_at: str
    documents: tuple[NormalizedCandidate, ...]
    replay_hash: str


def _document_hash(doc: dict) -> str:
    """Hash the replay-relevant fields of one fixture document."""
    fields = {
        "candidate_id": doc.get("candidate_id"),
        "canonical_url": doc.get("canonical_url"),
        "title": doc.get("title"),
        "source": doc.get("source"),
        "publisher": doc.get("publisher"),
        "published_at": doc.get("published_at"),
        "retrieved_at": doc.get("retrieved_at"),
        "content_type": doc.get("content_type"),
        "excerpt": doc.get("excerpt"),
        "proposed_event_key": doc.get("proposed_event_key"),
    }
    return content_hash(fields)


def _normalize_document(doc: dict, index: int) -> NormalizedCandidate:
    candidate_id = doc.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValidationError(f"documents[{index}].candidate_id must be non-empty")
    url = doc.get("canonical_url")
    if not isinstance(url, str) or not url:
        raise ValidationError(f"documents[{index}].canonical_url must be non-empty")
    title = doc.get("title")
    if not isinstance(title, str):
        raise ValidationError(f"documents[{index}].title must be a string")

    content_type = doc.get("content_type", "metadata")
    if content_type not in CONTENT_TYPES:
        raise ValidationError(f"documents[{index}].content_type invalid: {content_type!r}")

    try:
        parsed = parse_url(url)
        normalized_url = normalize_url(url)
    except ValueError as exc:
        raise ValidationError(f"documents[{index}].canonical_url invalid: {exc}") from exc

    nh = normalize_headline(title)
    event_key = normalize_event_signature(doc.get("proposed_event_key")) or fallback_event_key(nh)

    return NormalizedCandidate(
        candidate_id=candidate_id,
        canonical_url=url,
        normalized_url=normalized_url,
        fp_url=parsed["fp_url"],
        domain=parsed["domain"],
        title=title,
        normalized_headline=nh,
        event_key=event_key,
        publisher=doc.get("publisher") if isinstance(doc.get("publisher"), str) else None,
        published_at=doc.get("published_at") if isinstance(doc.get("published_at"), str) else None,
        retrieved_at=doc.get("retrieved_at") if isinstance(doc.get("retrieved_at"), str) else None,
        content_type=content_type,
        excerpt=doc.get("excerpt") if isinstance(doc.get("excerpt"), str) else None,
        content_hash=_document_hash(doc),
    )


def validate_fixture(data: dict) -> ReplayResult:
    """Validate and normalize a raw fixture dict into a :class:`ReplayResult`.

    Raises :class:`ValidationError` on any integrity or contract violation.
    """
    if not isinstance(data, dict):
        raise ValidationError("fixture must be a JSON object")

    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValidationError(
            f"unsupported fixture schema_version {data.get('schema_version')!r}"
        )

    case_id = data.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        raise ValidationError("fixture.case_id must be non-empty")

    documents_raw = data.get("documents")
    if not isinstance(documents_raw, list) or not documents_raw:
        raise ValidationError("fixture.documents must be a non-empty list")

    # Integrity: the whole-documents hash must match the stored content_hash.
    stored_hash = data.get("content_hash")
    if not isinstance(stored_hash, str) or not stored_hash:
        raise ValidationError("fixture.content_hash must be present")
    computed = content_hash(documents_raw)
    if computed != stored_hash:
        raise ValidationError(
            f"fixture content_hash mismatch: stored {stored_hash!r}, computed {computed!r}"
        )

    docs = tuple(_normalize_document(d, i) for i, d in enumerate(documents_raw))

    seen = {d.candidate_id for d in docs}
    if len(seen) != len(docs):
        raise ValidationError("fixture documents have duplicate candidate_id values")

    replay_hash = content_hash([asdict(d) for d in docs])

    query = data.get("query") or {}
    return ReplayResult(
        fixture_id=data.get("fixture_id", ""),
        case_id=case_id,
        channel=data.get("channel", "simulated"),
        query={k: v for k, v in query.items() if isinstance(v, str)},
        captured_at=data.get("captured_at", ""),
        documents=docs,
        replay_hash=replay_hash,
    )


def load_fixture(path: str) -> ReplayResult:
    """Load, validate, and replay a fixture file from disk (no network)."""
    import json

    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return validate_fixture(data)
