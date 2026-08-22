"""Phase 22 trust boundary from ArticleAnalysis proposals to verified Claims."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from . import storage
from .ai import ArticleAnalysisOutput, LocalEntailmentProvider
from .article_analysis import (
    ARTIFACT_INPUT_VIEW_VERSION,
    FEED_INPUT_VIEW_VERSION,
    analysis_input_text,
)
from .content_artifacts import ContentArtifactService
from .domain import DomainValidation, new_id, utc_now
from .evidence import claim_proposition_hash
from .provenance import validate_analysis_provenance
from .repository import evidence_span_hash

VERIFICATION_METHOD = "exact_analyzed_slice_v1"
MAX_EXCERPT_CHARS = 2_000


class ArticleAnalysisPromotionService:
    """Promote durable analysis candidates after local exact verification."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def promote(self, analysis_id: str) -> dict[str, Any]:
        bundle = validate_analysis_provenance(self.db_path, analysis_id)
        if not bundle["eligible_for_automatic_promotion"]:
            raise DomainValidation("article analysis is not eligible for automatic promotion")
        content = ContentArtifactService(self.db_path).load_normalized_content(
            bundle["analysis"]["document_version_id"]
        )
        _title, full_view = analysis_input_text(content)
        if content["content_kind"] == "feed_metadata":
            metadata = json.loads(content["normalized_text"])
            if not str(metadata.get("title") or "").strip() and not str(metadata.get("summary") or "").strip():
                raise DomainValidation("empty feed projection is not eligible for evidence promotion")
        analysis = bundle["analysis"]
        analyzed_slice = full_view[: int(analysis["analyzed_char_count"])]
        parsed = ArticleAnalysisOutput.model_validate(json.loads(analysis["result_json"]))
        claim_indexes = [claim.index for claim in parsed.candidate_claims]
        if len(claim_indexes) != len(set(claim_indexes)):
            raise DomainValidation("candidate claim indexes must be unique")
        excerpts_by_claim: dict[int, list[tuple[int, Any]]] = {}
        for excerpt_index, candidate in enumerate(parsed.candidate_evidence_excerpts):
            excerpts_by_claim.setdefault(candidate.candidate_claim_index, []).append((excerpt_index, candidate))
        outcomes = []
        for claim in parsed.candidate_claims:
            outcomes.append(
                self._promote_candidate(
                    bundle=bundle,
                    content=content,
                    analyzed_slice=analyzed_slice,
                    claim=claim,
                    excerpts=excerpts_by_claim.get(claim.index, []),
                )
            )
        return {"article_analysis_id": analysis_id, "outcomes": outcomes}

    def _promote_candidate(self, *, bundle, content, analyzed_slice, claim, excerpts):
        identity = hashlib.sha256(
            f"{bundle['analysis']['identity_hash']}\x1f{claim.index}\x1f{VERIFICATION_METHOD}".encode()
        ).hexdigest()
        existing = self._existing(identity)
        if existing is not None:
            return existing
        verified: list[dict[str, Any]] = []
        failures: list[str] = []
        for excerpt_index, candidate in excerpts:
            excerpt = candidate.excerpt
            if not excerpt or len(excerpt) > MAX_EXCERPT_CHARS:
                failures.append("invalid_excerpt")
                continue
            starts: list[int] = []
            cursor = 0
            while len(starts) < 2:
                found = analyzed_slice.find(excerpt, cursor)
                if found < 0:
                    break
                starts.append(found)
                cursor = found + 1
            if not starts:
                failures.append("excerpt_not_found")
                continue
            if len(starts) > 1:
                failures.append("ambiguous_excerpt")
                continue
            start = starts[0]
            end = start + len(excerpt)
            if analyzed_slice[start:end] != excerpt:
                failures.append("excerpt_not_found")
                continue
            relationship = LocalEntailmentProvider().assess(claim.proposition, excerpt).relationship
            verified.append(
                {
                    "excerpt_index": excerpt_index,
                    "excerpt": excerpt,
                    "start": start,
                    "end": end,
                    "relationship": {
                        "entails": "supports", "contradicts": "contradicts", "unknown": "contextualizes"
                    }[relationship],
                }
            )
        if not verified:
            code = failures[0] if len(excerpts) == 1 and failures else "no_verified_evidence"
            return self._record_failure(identity, bundle["analysis"]["id"], claim.index, code)

        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute(
                    "SELECT * FROM article_analysis_promotions WHERE promotion_identity = ?", (identity,)
                ).fetchone()
                if row is not None:
                    return self._read_outcome(row)
                claim_id = self._insert_claim_tx(conn, bundle["analysis"]["id"], claim.index, claim.proposition)
                span_ids: list[str] = []
                for item in verified:
                    span_id = self._insert_span_tx(conn, bundle, content, claim.index, item)
                    self._insert_link_tx(conn, claim_id, span_id, item["relationship"])
                    span_ids.append(span_id)
                outcome_id = new_id("promo")
                conn.execute(
                    """INSERT INTO article_analysis_promotions
                       (id, promotion_identity, article_analysis_id, candidate_claim_index,
                        outcome_code, claim_id, evidence_span_ids_json, created_at)
                       VALUES (?, ?, ?, ?, 'verified', ?, ?, ?)""",
                    (outcome_id, identity, bundle["analysis"]["id"], claim.index, claim_id,
                     json.dumps(span_ids, separators=(",", ":")), utc_now()),
                )
                row = conn.execute("SELECT * FROM article_analysis_promotions WHERE id = ?", (outcome_id,)).fetchone()
                return self._read_outcome(row)
        except sqlite3.IntegrityError:
            existing = self._existing(identity)
            if existing is not None:
                return existing
            raise
        finally:
            conn.close()

    def _insert_claim_tx(self, conn, analysis_id: str, candidate_index: int, proposition: str) -> str:
        existing = conn.execute(
            "SELECT id FROM claims WHERE article_analysis_id = ? AND candidate_claim_index = ?",
            (analysis_id, candidate_index),
        ).fetchone()
        if existing is not None:
            return existing[0]
        value = str(proposition).strip()
        if not value:
            raise DomainValidation("candidate proposition must not be empty")
        identifier = new_id("claim")
        now = utc_now()
        conn.execute(
            """INSERT INTO claims
               (id, story_id, proposition, proposition_hash, importance, state,
                article_analysis_id, candidate_claim_index, created_at)
               VALUES (?, NULL, ?, ?, 'relevant', 'pending', ?, ?, ?)""",
            (identifier, value, claim_proposition_hash(value), analysis_id, candidate_index, now),
        )
        conn.execute(
            """INSERT INTO claim_state_history
               (id, claim_id, from_state, to_state, reason, created_at)
               VALUES (?, ?, NULL, 'pending', 'verified analysis candidate promoted', ?)""",
            (new_id("csh"), identifier, now),
        )
        return identifier

    def _insert_span_tx(self, conn, bundle, content, claim_index: int, item: dict[str, Any]) -> str:
        locator_value = f"{item['start']};{item['end']}"
        span_hash = evidence_span_hash(item["excerpt"], "codepoint_offset", locator_value)
        is_feed = content["content_kind"] == "feed_metadata"
        full_view = analysis_input_text(content)[1]
        view_content_hash = hashlib.sha256(full_view.encode()).hexdigest()
        view_kind = "feed" if is_feed else "artifact"
        view_version = FEED_INPUT_VIEW_VERSION if is_feed else ARTIFACT_INPUT_VIEW_VERSION
        field_path = "title;summary" if is_feed else None
        provenance_json = json.dumps(
            {
                "analysis_id": bundle["analysis"]["id"],
                "candidate_claim_index": claim_index,
                "candidate_excerpt_index": item["excerpt_index"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        existing = conn.execute(
            """SELECT id FROM evidence_spans
               WHERE document_version_id = ? AND span_hash = ?
                 AND verification_method = ? AND article_analysis_id = ?
                 AND artifact_id = ? AND artifact_content_hash = ?
                 AND view_content_hash = ? AND view_kind = ? AND view_version = ?
                 AND field_path IS ? AND start_offset = ? AND end_offset = ?
                 AND provenance_json = ?""",
            (
                bundle["analysis"]["document_version_id"], span_hash, VERIFICATION_METHOD,
                bundle["analysis"]["id"], content["artifact_id"],
                content["normalized_content_hash"], view_content_hash, view_kind,
                view_version, field_path, item["start"], item["end"], provenance_json,
            ),
        ).fetchone()
        if existing is not None:
            return existing[0]
        identifier = new_id("span")
        conn.execute(
            """INSERT INTO evidence_spans
               (id, document_version_id, excerpt, locator_type, locator_value, span_hash, created_at,
                article_analysis_id, artifact_id, artifact_content_hash, view_content_hash,
                view_kind, view_version, field_path, start_offset, end_offset,
                verification_method, provenance_json)
               VALUES (?, ?, ?, 'codepoint_offset', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                identifier, bundle["analysis"]["document_version_id"], item["excerpt"], locator_value,
                span_hash, utc_now(), bundle["analysis"]["id"], content["artifact_id"],
                content["normalized_content_hash"], view_content_hash, view_kind,
                view_version, field_path, item["start"], item["end"], VERIFICATION_METHOD,
                provenance_json,
            ),
        )
        return identifier

    def _insert_link_tx(self, conn, claim_id: str, span_id: str, relationship: str) -> None:
        existing = conn.execute(
            "SELECT 1 FROM claim_evidence WHERE claim_id = ? AND evidence_span_id = ? AND relationship = ?",
            (claim_id, span_id, relationship),
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO claim_evidence (id, claim_id, evidence_span_id, relationship, created_at) VALUES (?, ?, ?, ?, ?)",
                (new_id("ce"), claim_id, span_id, relationship, utc_now()),
            )

    def _record_failure(self, identity: str, analysis_id: str, candidate_index: int, code: str):
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute(
                    "SELECT * FROM article_analysis_promotions WHERE promotion_identity = ?", (identity,)
                ).fetchone()
                if row is None:
                    conn.execute(
                        """INSERT INTO article_analysis_promotions
                           (id, promotion_identity, article_analysis_id, candidate_claim_index,
                            outcome_code, evidence_span_ids_json, created_at)
                           VALUES (?, ?, ?, ?, ?, '[]', ?)""",
                        (new_id("promo"), identity, analysis_id, candidate_index, code, utc_now()),
                    )
                    row = conn.execute(
                        "SELECT * FROM article_analysis_promotions WHERE promotion_identity = ?", (identity,)
                    ).fetchone()
                return self._read_outcome(row)
        finally:
            conn.close()

    def _existing(self, identity: str):
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM article_analysis_promotions WHERE promotion_identity = ?", (identity,)
            ).fetchone()
            return self._read_outcome(row) if row is not None else None
        finally:
            conn.close()

    @staticmethod
    def _read_outcome(row) -> dict[str, Any]:
        return {
            "id": row["id"], "code": row["outcome_code"], "claim_id": row["claim_id"],
            "evidence_span_ids": json.loads(row["evidence_span_ids_json"]),
        }


__all__ = ["ArticleAnalysisPromotionService", "VERIFICATION_METHOD"]
