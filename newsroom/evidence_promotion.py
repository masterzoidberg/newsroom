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
from .evidence import ACCEPTED_STATES, CLAIM_STATES, claim_proposition_hash
from .provenance import ProvenanceValidationError, validate_analysis_provenance
from .repository import evidence_span_hash

VERIFICATION_METHOD = "exact_analyzed_slice_v1"
MAX_EXCERPT_CHARS = 2_000


class AutomaticPromotionIntegrityError(DomainValidation):
    """A persisted automatic promotion cannot be independently proven."""

    code = "invalid_verified_promotion"

    def __init__(self, message: str, *, issues: tuple[str, ...] = ()):
        super().__init__(message)
        self.issues = issues or (message,)


def promotion_identity(analysis_identity_hash: str, candidate_claim_index: int) -> str:
    """Return the stable identity used by the Phase 22 promotion writer."""

    return hashlib.sha256(
        f"{analysis_identity_hash}\x1f{candidate_claim_index}\x1f{VERIFICATION_METHOD}".encode()
    ).hexdigest()


def _promotion_integrity_failure(code: str, detail: str = "") -> None:
    message = f"{code}: {detail}" if detail else code
    raise AutomaticPromotionIntegrityError(message, issues=(message,))


def _strict_int(value: Any, code: str) -> int:
    if type(value) is not int:  # bool is intentionally not accepted
        _promotion_integrity_failure(code, "value is not an integer")
    return value


def verify_automatic_promotion(
    db_path: str | Path,
    promotion_id: str,
) -> dict[str, Any]:
    """Independently prove one persisted verified Phase 22 promotion.

    The supported writer validates candidate excerpts before insertion. This
    read-only verifier repeats the proof from persisted canonical inputs so a
    direct SQL writer cannot counterfeit a trusted graph with plausible hashes
    or relational links.
    """

    conn = storage.connect(db_path)
    try:
        promotion_row = conn.execute(
            "SELECT * FROM article_analysis_promotions WHERE id = ?", (promotion_id,)
        ).fetchone()
        if promotion_row is None:
            _promotion_integrity_failure("promotion_missing", f"promotion={promotion_id}")
        promotion = dict(promotion_row)
    finally:
        conn.close()

    if promotion["outcome_code"] != "verified":
        _promotion_integrity_failure(
            "promotion_not_verified", f"promotion={promotion_id}"
        )

    try:
        bundle = validate_analysis_provenance(
            db_path, promotion["article_analysis_id"]
        )
    except ProvenanceValidationError as exc:
        codes = tuple(item.split(":", 1)[0] for item in exc.issues)
        raise AutomaticPromotionIntegrityError(
            f"analysis_provenance_invalid: analysis={promotion['article_analysis_id']}",
            issues=codes or ("analysis_provenance_invalid",),
        ) from exc
    except Exception as exc:
        raise AutomaticPromotionIntegrityError(
            f"analysis_provenance_unreadable: analysis={promotion['article_analysis_id']}",
            issues=("analysis_provenance_unreadable",),
        ) from exc

    analysis = dict(bundle["analysis"])
    if bundle["provenance_class"] != "automatic" or not bundle["input_contract_complete"]:
        _promotion_integrity_failure(
            "promotion_analysis_not_automatic", f"analysis={analysis['id']}"
        )

    try:
        content = ContentArtifactService(db_path).load_normalized_content(
            analysis["document_version_id"]
        )
        if not content.get("available"):
            _promotion_integrity_failure(
                "canonical_content_unavailable",
                f"document_version={analysis['document_version_id']}",
            )
        full_view = analysis_input_text(content)[1]
    except AutomaticPromotionIntegrityError:
        raise
    except Exception as exc:
        raise AutomaticPromotionIntegrityError(
            f"canonical_view_unreadable: analysis={analysis['id']}",
            issues=("canonical_view_unreadable",),
        ) from exc

    if content["artifact_id"] != analysis["artifact_id"]:
        _promotion_integrity_failure("analysis_artifact_mismatch", f"analysis={analysis['id']}")
    expected_view_version = (
        FEED_INPUT_VIEW_VERSION
        if content["content_kind"] == "feed_metadata"
        else ARTIFACT_INPUT_VIEW_VERSION
    )
    if analysis["input_view_version"] != expected_view_version:
        _promotion_integrity_failure(
            "analysis_view_version_mismatch", f"analysis={analysis['id']}"
        )
    input_count = _strict_int(analysis["input_char_count"], "analysis_input_count_invalid")
    analyzed_count = _strict_int(
        analysis["analyzed_char_count"], "analysis_analyzed_count_invalid"
    )
    if not 1 <= analyzed_count <= input_count or len(full_view) != input_count:
        _promotion_integrity_failure(
            "analysis_input_bounds_invalid", f"analysis={analysis['id']}"
        )
    if hashlib.sha256(full_view.encode("utf-8")).hexdigest() != analysis["input_content_hash"]:
        _promotion_integrity_failure("canonical_view_hash_mismatch", f"analysis={analysis['id']}")
    analyzed_view = full_view[:analyzed_count]
    if hashlib.sha256(analyzed_view.encode("utf-8")).hexdigest() != analysis["analyzed_content_hash"]:
        _promotion_integrity_failure("analyzed_view_hash_mismatch", f"analysis={analysis['id']}")
    if bool(analysis["truncated"]) != (analyzed_count < input_count):
        _promotion_integrity_failure("analysis_truncation_mismatch", f"analysis={analysis['id']}")

    try:
        parsed = ArticleAnalysisOutput.model_validate(json.loads(analysis["result_json"]))
    except Exception as exc:
        raise AutomaticPromotionIntegrityError(
            f"analysis_result_invalid: analysis={analysis['id']}",
            issues=("analysis_result_invalid",),
        ) from exc

    candidate_claims = {}
    for candidate in parsed.candidate_claims:
        if candidate.index in candidate_claims:
            _promotion_integrity_failure(
                "candidate_claim_index_duplicate",
                f"analysis={analysis['id']} index={candidate.index}",
            )
        candidate_claims[candidate.index] = candidate

    candidate_index = _strict_int(
        promotion["candidate_claim_index"], "promotion_candidate_index_invalid"
    )
    if candidate_index not in candidate_claims:
        _promotion_integrity_failure(
            "promotion_candidate_index_unknown",
            f"promotion={promotion_id} index={candidate_index}",
        )
    expected_candidate = candidate_claims[candidate_index]
    expected_promotion_identity = promotion_identity(
        analysis["identity_hash"], candidate_index
    )
    if promotion["promotion_identity"] != expected_promotion_identity:
        _promotion_integrity_failure(
            "promotion_identity_mismatch", f"promotion={promotion_id}"
        )

    try:
        evidence_ids = json.loads(promotion["evidence_span_ids_json"])
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AutomaticPromotionIntegrityError(
            f"promotion_evidence_ids_invalid: promotion={promotion_id}",
            issues=("promotion_evidence_ids_invalid",),
        ) from exc
    if (
        not isinstance(evidence_ids, list)
        or not evidence_ids
        or any(type(value) is not str or not value for value in evidence_ids)
        or len(evidence_ids) != len(set(evidence_ids))
    ):
        _promotion_integrity_failure(
            "promotion_evidence_ids_invalid", f"promotion={promotion_id}"
        )

    conn = storage.connect(db_path)
    try:
        claim_row = conn.execute(
            "SELECT * FROM claims WHERE id = ?", (promotion["claim_id"],)
        ).fetchone()
        if claim_row is None:
            _promotion_integrity_failure(
                "promotion_claim_missing", f"promotion={promotion_id}"
            )
        claim = dict(claim_row)
        if claim["article_analysis_id"] != analysis["id"]:
            _promotion_integrity_failure(
                "claim_analysis_mismatch", f"claim={claim['id']}"
            )
        if _strict_int(claim["candidate_claim_index"], "claim_candidate_index_invalid") != candidate_index:
            _promotion_integrity_failure("claim_candidate_index_mismatch", f"claim={claim['id']}")
        if claim["proposition"] != expected_candidate.proposition.strip():
            _promotion_integrity_failure("claim_proposition_mismatch", f"claim={claim['id']}")
        if claim["proposition_hash"] != claim_proposition_hash(claim["proposition"]):
            _promotion_integrity_failure("claim_proposition_hash_mismatch", f"claim={claim['id']}")

        history = conn.execute(
            "SELECT * FROM claim_state_history WHERE claim_id = ? ORDER BY rowid",
            (claim["id"],),
        ).fetchall()
        if not history:
            _promotion_integrity_failure("claim_initial_state_history_missing", f"claim={claim['id']}")
        previous_state = None
        for position, state_row in enumerate(history):
            if state_row["to_state"] not in CLAIM_STATES:
                _promotion_integrity_failure("claim_state_history_invalid", f"claim={claim['id']}")
            if position == 0:
                if state_row["from_state"] is not None or state_row["to_state"] != "pending":
                    _promotion_integrity_failure("claim_initial_state_invalid", f"claim={claim['id']}")
            elif state_row["from_state"] == state_row["to_state"]:
                _promotion_integrity_failure("claim_state_history_noop", f"claim={claim['id']}")
            elif state_row["from_state"] != previous_state:
                _promotion_integrity_failure("claim_state_history_inconsistent", f"claim={claim['id']}")
            previous_state = state_row["to_state"]
        if previous_state != claim["state"]:
            _promotion_integrity_failure("claim_state_history_current_mismatch", f"claim={claim['id']}")
        if claim["accepted_at"] is not None and claim["state"] not in ACCEPTED_STATES:
            _promotion_integrity_failure("claim_acceptance_state_mismatch", f"claim={claim['id']}")

        claim_evidence_rows = conn.execute(
            "SELECT * FROM claim_evidence WHERE claim_id = ? ORDER BY created_at, id",
            (claim["id"],),
        ).fetchall()
        if not claim_evidence_rows:
            _promotion_integrity_failure("claim_evidence_missing", f"claim={claim['id']}")
        evidence_by_id = {
            row["id"]: row
            for row in conn.execute(
                f"SELECT * FROM evidence_spans WHERE id IN ({','.join('?' for _ in evidence_ids)})",
                evidence_ids,
            ).fetchall()
        }
        missing = [identifier for identifier in evidence_ids if identifier not in evidence_by_id]
        if missing:
            _promotion_integrity_failure(
                "promotion_evidence_missing", f"promotion={promotion_id}"
            )

        expected_relationships = {
            "entails": "supports",
            "contradicts": "contradicts",
            "unknown": "contextualizes",
        }
        validated_spans: dict[str, dict[str, Any]] = {}
        validated_links: list[dict[str, Any]] = []
        for evidence_id in evidence_ids:
            span = evidence_by_id[evidence_id]
            validated_spans[evidence_id] = _verify_promotion_span(
                span,
                analysis=analysis,
                content=content,
                full_view=full_view,
                analyzed_view=analyzed_view,
                candidate_index=candidate_index,
                parsed=parsed,
            )

        for link in claim_evidence_rows:
            if link["evidence_span_id"] not in validated_spans:
                extra_span = conn.execute(
                    "SELECT * FROM evidence_spans WHERE id = ?",
                    (link["evidence_span_id"],),
                ).fetchone()
                if extra_span is None:
                    _promotion_integrity_failure("claim_evidence_span_missing", f"claim={claim['id']}")
                validated_spans[link["evidence_span_id"]] = _verify_promotion_span(
                    extra_span,
                    analysis=analysis,
                    content=content,
                    full_view=full_view,
                    analyzed_view=analyzed_view,
                    candidate_index=candidate_index,
                    parsed=parsed,
                )
            expected_relationship = expected_relationships[
                LocalEntailmentProvider().assess(
                    expected_candidate.proposition,
                    validated_spans[link["evidence_span_id"]]["excerpt"],
                ).relationship
            ]
            if link["relationship"] != expected_relationship:
                _promotion_integrity_failure(
                    "claim_evidence_relationship_mismatch", f"claim={claim['id']}"
                )
            validated_links.append(dict(link))

        for evidence_id in evidence_ids:
            matching_links = [
                link for link in validated_links if link["evidence_span_id"] == evidence_id
            ]
            if len(matching_links) != 1:
                _promotion_integrity_failure(
                    "promotion_claim_evidence_mismatch", f"promotion={promotion_id}"
                )

        return {
            "promotion": promotion,
            "analysis": analysis,
            "claim": claim,
            "evidence_spans": tuple(validated_spans[identifier] for identifier in evidence_ids),
            "claim_evidence": tuple(validated_links),
        }
    finally:
        conn.close()


def _verify_promotion_span(
    span,
    *,
    analysis: dict[str, Any],
    content: dict[str, Any],
    full_view: str,
    analyzed_view: str,
    candidate_index: int,
    parsed: ArticleAnalysisOutput,
) -> dict[str, Any]:
    if span["verification_method"] != VERIFICATION_METHOD:
        _promotion_integrity_failure("evidence_verification_method_invalid", f"span={span['id']}")
    if span["document_version_id"] != analysis["document_version_id"]:
        _promotion_integrity_failure("evidence_document_version_mismatch", f"span={span['id']}")
    if span["article_analysis_id"] != analysis["id"]:
        _promotion_integrity_failure("evidence_analysis_mismatch", f"span={span['id']}")
    if span["artifact_id"] != content["artifact_id"] or span["artifact_content_hash"] != content["normalized_content_hash"]:
        _promotion_integrity_failure("evidence_artifact_mismatch", f"span={span['id']}")
    expected_kind = "feed" if content["content_kind"] == "feed_metadata" else "artifact"
    expected_version = FEED_INPUT_VIEW_VERSION if expected_kind == "feed" else ARTIFACT_INPUT_VIEW_VERSION
    expected_field_path = "title;summary" if expected_kind == "feed" else None
    if (
        span["view_kind"] != expected_kind
        or span["view_version"] != expected_version
        or span["field_path"] != expected_field_path
        or span["view_content_hash"] != analysis["input_content_hash"]
    ):
        _promotion_integrity_failure("evidence_view_provenance_mismatch", f"span={span['id']}")

    try:
        provenance = json.loads(span["provenance_json"])
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AutomaticPromotionIntegrityError(
            f"evidence_provenance_invalid: span={span['id']}",
            issues=("evidence_provenance_invalid",),
        ) from exc
    if not isinstance(provenance, dict) or provenance.get("analysis_id") != analysis["id"]:
        _promotion_integrity_failure("evidence_provenance_mismatch", f"span={span['id']}")
    span_candidate_index = provenance.get("candidate_claim_index")
    if type(span_candidate_index) is not int or span_candidate_index != candidate_index:
        _promotion_integrity_failure("evidence_candidate_index_mismatch", f"span={span['id']}")
    excerpt_index = provenance.get("candidate_excerpt_index")
    if type(excerpt_index) is not int or not 0 <= excerpt_index < len(parsed.candidate_evidence_excerpts):
        _promotion_integrity_failure("evidence_excerpt_index_invalid", f"span={span['id']}")
    candidate_excerpt = parsed.candidate_evidence_excerpts[excerpt_index]
    if candidate_excerpt.candidate_claim_index != candidate_index or span["excerpt"] != candidate_excerpt.excerpt:
        _promotion_integrity_failure("evidence_candidate_excerpt_mismatch", f"span={span['id']}")

    start = _strict_int(span["start_offset"], "evidence_start_offset_invalid")
    end = _strict_int(span["end_offset"], "evidence_end_offset_invalid")
    if not 0 <= start < end <= len(full_view) or end > _strict_int(analysis["analyzed_char_count"], "analysis_analyzed_count_invalid"):
        _promotion_integrity_failure("evidence_offset_bounds_invalid", f"span={span['id']}")
    if span["excerpt"] != full_view[start:end] or span["locator_type"] != "codepoint_offset" or span["locator_value"] != f"{start};{end}":
        _promotion_integrity_failure("evidence_offset_membership_invalid", f"span={span['id']}")
    if len(span["excerpt"]) > MAX_EXCERPT_CHARS:
        _promotion_integrity_failure("evidence_excerpt_too_long", f"span={span['id']}")

    starts: list[int] = []
    cursor = 0
    while len(starts) < 2:
        found = analyzed_view.find(span["excerpt"], cursor)
        if found < 0:
            break
        starts.append(found)
        cursor = found + 1
    if len(starts) != 1 or starts[0] != start:
        _promotion_integrity_failure("evidence_excerpt_not_unique", f"span={span['id']}")
    expected_span_hash = evidence_span_hash(
        span["excerpt"], span["locator_type"], span["locator_value"]
    )
    if span["span_hash"] != expected_span_hash:
        _promotion_integrity_failure("evidence_span_hash_mismatch", f"span={span['id']}")
    return dict(span)


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
        identity = promotion_identity(bundle["analysis"]["identity_hash"], claim.index)
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
        result = None
        try:
            with storage.write_tx(conn):
                row = conn.execute(
                    "SELECT * FROM article_analysis_promotions WHERE promotion_identity = ?", (identity,)
                ).fetchone()
                if row is not None:
                    result = self._read_outcome(row)
                else:
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
                    result = self._read_outcome(row)
        except sqlite3.IntegrityError:
            existing = self._existing(identity)
            if existing is not None:
                return existing
            raise
        finally:
            conn.close()
        if result is None:
            raise AutomaticPromotionIntegrityError(
                f"promotion_result_missing: analysis={bundle['analysis']['id']} candidate={claim.index}",
                issues=("promotion_result_missing",),
            )
        if result["code"] == "verified":
            verify_automatic_promotion(self.db_path, result["id"])
        return result

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
            if row is None:
                return None
            if row["outcome_code"] == "verified":
                verify_automatic_promotion(self.db_path, row["id"])
            return self._read_outcome(row)
        finally:
            conn.close()

    @staticmethod
    def _read_outcome(row) -> dict[str, Any]:
        return {
            "id": row["id"], "code": row["outcome_code"], "claim_id": row["claim_id"],
            "evidence_span_ids": json.loads(row["evidence_span_ids_json"]),
        }


__all__ = [
    "ArticleAnalysisPromotionService",
    "AutomaticPromotionIntegrityError",
    "VERIFICATION_METHOD",
    "promotion_identity",
    "verify_automatic_promotion",
]
