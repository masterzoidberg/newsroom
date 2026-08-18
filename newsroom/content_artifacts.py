"""Durable immutable normalized content artifacts.

Phase 18 persists the exact bounded normalized content that each acquired
DocumentVersion represents so downstream workers can reload and hash-verify
the source material without any transient transport state.

An artifact is content-addressed by ``normalized_content_hash`` (sha256 of the
exact persisted normalized text), stored once, and referenced by one or more
``document_versions.artifact_id`` rows. Unchanged acquisition never creates a
duplicate DocumentVersion, and its already-stored artifact is reused. Referenced
artifacts are immutable (content columns are guarded by a database trigger) and
cannot be deleted through the FK.

Content is treated as untrusted plain text: nothing in this module renders,
interprets, or executes the stored text.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from . import storage
from .domain import DomainError, DomainNotFound, DomainValidation, new_id, utc_now


NORM_VERSION_VISIBLE_TEXT = "visible_text_v1"
NORM_VERSION_FEED_METADATA = "feed_metadata_v1"
NORM_VERSION_FALLBACK_TEXT = "fallback_text_v1"

CONTENT_KINDS = frozenset({"visible_text", "feed_metadata", "fallback_text"})

# The normalization contract encoded in each artifact version string.
NORM_VERSION_BY_KIND: Mapping[str, str] = {
    "visible_text": NORM_VERSION_VISIBLE_TEXT,
    "feed_metadata": NORM_VERSION_FEED_METADATA,
    "fallback_text": NORM_VERSION_FALLBACK_TEXT,
}

DEFAULT_MAX_TEXT_CHARS = 200_000


class ContentArtifactError(DomainError):
    """Base class for durable content artifact failures."""

    code = "content_artifact_error"


class ArtifactNotFound(ContentArtifactError, DomainNotFound):
    """A referenced artifact row is absent from the content_artifacts table."""

    code = "content_artifact_not_found"


class ArtifactHashMismatch(ContentArtifactError):
    """Stored artifact content no longer matches its recorded normalized hash."""

    code = "content_artifact_hash_mismatch"


class ArtifactLengthMismatch(ContentArtifactError):
    """Stored artifact content length no longer matches its recorded length."""

    code = "content_artifact_length_mismatch"


class LegacyVersionWithoutArtifact(ContentArtifactError):
    """A pre-Phase-18 DocumentVersion has no durable content artifact.

    This is a truthful, non-failure state: historical metadata remains fully
    readable, but the normalized text was never persisted.
    """

    code = "artifact_unavailable_legacy"


def normalized_text_hash(text: str) -> str:
    """Deterministic sha256 of the exact byte-for-byte normalized text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _as_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


class ContentArtifactService:
    """Create, read, and verify immutable normalized content artifacts.

    ``create`` content-addresses by exact normalized text: identical text
    returns the same immutable artifact. The service enforces its own bounded
    character limit so direct callers cannot bypass acquisition limits.
    """

    def __init__(self, db_path: str | Path, *, max_text_chars: int = DEFAULT_MAX_TEXT_CHARS):
        self.db_path = Path(db_path)
        if isinstance(max_text_chars, bool) or not isinstance(max_text_chars, int) or max_text_chars < 1:
            raise ValueError("max_text_chars must be a positive integer")
        self.max_text_chars = max_text_chars

    def create(self, *, normalized_text: str, content_kind: str) -> dict[str, Any]:
        if content_kind not in CONTENT_KINDS:
            raise DomainValidation(f"unsupported content kind {content_kind!r}")
        if not isinstance(normalized_text, str):
            raise DomainValidation("normalized_text must be a string")
        if len(normalized_text) > self.max_text_chars:
            raise DomainValidation(
                f"normalized content exceeds the {self.max_text_chars} character artifact limit"
            )
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                artifact = self.create_tx(conn, normalized_text=normalized_text, content_kind=content_kind, max_text_chars=self.max_text_chars)
        finally:
            conn.close()
        return artifact

    def get(self, artifact_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM content_artifacts WHERE id = ?", (artifact_id,)
            ).fetchone()
            if row is None:
                raise ArtifactNotFound(f"content artifact {artifact_id} not found")
            return _as_dict(row)
        finally:
            conn.close()

    def artifact_for_document_version(self, document_version_id: str) -> dict[str, Any] | None:
        """Return the artifact referenced by the version, or None for legacy rows."""
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT artifact_id FROM document_versions WHERE id = ?",
                (document_version_id,),
            ).fetchone()
            if row is None:
                raise DomainNotFound("document version not found")
            artifact_id = row[0]
            if artifact_id is None:
                return None
        finally:
            conn.close()
        return self.get(artifact_id)

    def verify(self, artifact_id: str) -> dict[str, Any]:
        """Return a verified artifact or raise on missing/corrupt content.

        Verification recomputes sha256 and length of the exact stored text and
        compares against the recorded hash/length. It never silently returns
        corrupted content.
        """
        artifact = self.get(artifact_id)
        stored = artifact["normalized_text"]
        recomputed = normalized_text_hash(stored)
        if recomputed != artifact["normalized_content_hash"]:
            raise ArtifactHashMismatch(
                f"content artifact {artifact_id} hash mismatch "
                f"(stored={artifact['normalized_content_hash'][:16]}... recomputed={recomputed[:16]}...)"
            )
        if len(stored) != artifact["text_length"]:
            raise ArtifactLengthMismatch(
                f"content artifact {artifact_id} length mismatch "
                f"(stored={len(stored)} recorded={artifact['text_length']})"
            )
        return artifact

    def load_normalized_content(self, document_version_id: str) -> dict[str, Any]:
        """Load verified normalized content for a DocumentVersion.

        Returns a structured, truthful result. A pre-Phase-18 historical
        version without an artifact reports ``available=False`` instead of any
        fabricated or re-fetched content; it never mutates historical
        provenance. Missing or corrupt referenced artifacts raise instead of
        returning unsafe content.
        """
        artifact = self.artifact_for_document_version(document_version_id)
        if artifact is None:
            return {
                "available": False,
                "reason": "legacy_version_without_artifact",
                "document_version_id": document_version_id,
                "artifact_id": None,
            }
        verified = self.verify(artifact["id"])
        return {
            "available": True,
            "normalized_text": verified["normalized_text"],
            "text_length": verified["text_length"],
            "normalized_content_hash": verified["normalized_content_hash"],
            "content_kind": verified["content_kind"],
            "norm_version": verified["norm_version"],
            "artifact_id": verified["id"],
            "document_version_id": document_version_id,
        }

    def load_verified_text(self, document_version_id: str) -> str:
        """Strict convenience loader: returns exact verified normalized text.

        Raises ``LegacyVersionWithoutArtifact`` for historical versions instead
        of pretending content exists.
        """
        result = self.load_normalized_content(document_version_id)
        if not result["available"]:
            raise LegacyVersionWithoutArtifact(
                f"document version {document_version_id} has no content artifact "
                f"({result['reason']})"
            )
        return result["normalized_text"]

    @staticmethod
    def create_tx(
        conn: sqlite3.Connection,
        *,
        normalized_text: str,
        content_kind: str,
        max_text_chars: int,
    ) -> dict[str, Any]:
        """Transaction-scoped create used inside the acquisition write context.

        Artifact creation and DocumentVersion association commit together, so
        a failed artifact write can never leave a falsely successful
        acquisition. Content-addressing is race-safe: a concurrent writer that
        inserts the same hash first simply returns the existing artifact.
        """
        if content_kind not in CONTENT_KINDS or len(normalized_text) > max_text_chars:
            raise DomainValidation("artifact content violates size/kind limits")
        content_hash = normalized_text_hash(normalized_text)
        existing = conn.execute(
            "SELECT * FROM content_artifacts WHERE normalized_content_hash = ?",
            (content_hash,),
        ).fetchone()
        if existing is not None:
            return _as_dict(existing)
        artifact_id = new_id("art")
        now = utc_now()
        try:
            conn.execute(
                """
                INSERT INTO content_artifacts
                    (id, normalized_content_hash, content_kind, norm_version,
                     normalized_text, text_length, retention_eligible, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    artifact_id,
                    content_hash,
                    content_kind,
                    NORM_VERSION_BY_KIND[content_kind],
                    normalized_text,
                    len(normalized_text),
                    now,
                ),
            )
        except sqlite3.IntegrityError:
            # A concurrent writer already created the artifact for this hash.
            existing = conn.execute(
                "SELECT * FROM content_artifacts WHERE normalized_content_hash = ?",
                (content_hash,),
            ).fetchone()
            if existing is None:
                raise
            return _as_dict(existing)
        return {
            "id": artifact_id,
            "normalized_content_hash": content_hash,
            "content_kind": content_kind,
            "norm_version": NORM_VERSION_BY_KIND[content_kind],
            "normalized_text": normalized_text,
            "text_length": len(normalized_text),
            "retention_eligible": 1,
        }


@dataclass(frozen=True)
class ContentArtifactSummary:
    artifact_id: str
    normalized_content_hash: str
    content_kind: str
    norm_version: str
    text_length: int


__all__ = [
    "ArtifactHashMismatch",
    "ArtifactLengthMismatch",
    "ArtifactNotFound",
    "CONTENT_KINDS",
    "ContentArtifactError",
    "ContentArtifactService",
    "ContentArtifactSummary",
    "DEFAULT_MAX_TEXT_CHARS",
    "LegacyVersionWithoutArtifact",
    "NORM_VERSION_BY_KIND",
    "NORM_VERSION_FALLBACK_TEXT",
    "NORM_VERSION_FEED_METADATA",
    "NORM_VERSION_VISIBLE_TEXT",
    "normalized_text_hash",
]
