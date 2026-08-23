from __future__ import annotations

import hashlib
import json

import pytest

from newsroom import storage
from newsroom.article_analysis import analysis_input_text
from newsroom.evidence import claim_proposition_hash
from newsroom.evidence_promotion import (
    ArticleAnalysisPromotionService,
    AutomaticPromotionIntegrityError,
    promotion_identity,
    verify_automatic_promotion,
)
from newsroom.integrity import check_database
from newsroom.repository import evidence_span_hash

from test_phase22_1_hardening import _variant_analysis
from test_phase22_evidence_promotion import _analysis


NOW = "2026-08-22T00:00:00Z"


def _analysis_rows(db, analysis_id):
    conn = storage.connect(db)
    try:
        analysis = conn.execute(
            "SELECT * FROM article_analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
        artifact = conn.execute(
            "SELECT * FROM content_artifacts WHERE id = ?", (analysis["artifact_id"],)
        ).fetchone()
        return analysis, artifact
    finally:
        conn.close()


def _direct_graph(
    db,
    analysis_id,
    *,
    excerpt="released a UAP report",
    start=11,
    end=32,
    claim_index=0,
    span_candidate_index=None,
    include_history=True,
    history_rows=(),
    drop_triggers=(),
):
    analysis, artifact = _analysis_rows(db, analysis_id)
    content = {
        "content_kind": artifact["content_kind"],
        "normalized_text": artifact["normalized_text"],
    }
    full_view = analysis_input_text(content)[1]
    view_hash = hashlib.sha256(full_view.encode("utf-8")).hexdigest()
    span_candidate_index = claim_index if span_candidate_index is None else span_candidate_index
    span_id = "span-direct"
    claim_id = "claim-direct"
    claim_evidence_id = "ce-direct"
    promotion_id = "promotion-direct"
    locator_value = f"{start};{end}"
    span_hash = evidence_span_hash(excerpt, "codepoint_offset", locator_value)
    provenance = json.dumps(
        {
            "analysis_id": analysis_id,
            "candidate_claim_index": span_candidate_index,
            "candidate_excerpt_index": 0,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    proposition = "The agency released a UAP report."
    conn = storage.connect(db)
    try:
        with storage.write_tx(conn):
            for trigger in drop_triggers:
                conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")
            conn.execute(
                """
                INSERT INTO evidence_spans
                    (id, document_version_id, excerpt, locator_type, locator_value,
                     span_hash, created_at, article_analysis_id, artifact_id,
                     artifact_content_hash, view_content_hash, view_kind, view_version,
                     field_path, start_offset, end_offset, verification_method,
                     provenance_json)
                VALUES (?, ?, ?, 'codepoint_offset', ?, ?, ?, ?, ?, ?, ?, 'artifact',
                        'artifact_norm_v1', NULL, ?, ?,
                        'exact_analyzed_slice_v1', ?)
                """,
                (
                    span_id,
                    analysis["document_version_id"],
                    excerpt,
                    locator_value,
                    span_hash,
                    NOW,
                    analysis_id,
                    artifact["id"],
                    artifact["normalized_content_hash"],
                    view_hash,
                    start,
                    end,
                    provenance,
                ),
            )
            conn.execute(
                """
                INSERT INTO claims
                    (id, story_id, proposition, proposition_hash, importance, state,
                     accepted_at, article_analysis_id, candidate_claim_index, created_at)
                VALUES (?, NULL, ?, ?, 'relevant', 'pending', NULL, ?, ?, ?)
                """,
                (
                    claim_id,
                    proposition,
                    claim_proposition_hash(proposition),
                    analysis_id,
                    claim_index,
                    NOW,
                ),
            )
            if include_history:
                conn.execute(
                    """
                    INSERT INTO claim_state_history
                        (id, claim_id, from_state, to_state, reason, created_at)
                    VALUES ('csh-direct', ?, NULL, 'pending', 'direct test', ?)
                    """,
                    (claim_id, NOW),
                )
            for index, row in enumerate(history_rows):
                conn.execute(
                    """
                    INSERT INTO claim_state_history
                        (id, claim_id, from_state, to_state, reason, created_at)
                    VALUES (?, ?, ?, ?, 'direct test', ?)
                    """,
                    (f"csh-direct-{index}", claim_id, row[0], row[1], NOW),
                )
            conn.execute(
                """
                INSERT INTO claim_evidence
                    (id, claim_id, evidence_span_id, relationship, created_at)
                VALUES (?, ?, ?, 'supports', ?)
                """,
                (claim_evidence_id, claim_id, span_id, NOW),
            )
            conn.execute(
                """
                INSERT INTO article_analysis_promotions
                    (id, promotion_identity, article_analysis_id, candidate_claim_index,
                     outcome_code, claim_id, evidence_span_ids_json, created_at)
                VALUES (?, ?, ?, ?, 'verified', ?, ?, ?)
                """,
                (
                    promotion_id,
                    promotion_identity(analysis["identity_hash"], claim_index),
                    analysis_id,
                    claim_index,
                    claim_id,
                    json.dumps([span_id]),
                    NOW,
                ),
            )
    finally:
        conn.close()
    return promotion_id, claim_id, span_id


def _assert_rejected(db, promotion_id):
    with pytest.raises(AutomaticPromotionIntegrityError):
        verify_automatic_promotion(db, promotion_id)
    report = check_database(db)
    assert not report.ok
    assert any(issue.code == "invalid_verified_promotion" for issue in report.issues)


def test_legitimate_phase22_promotion_passes_canonical_verification_and_integrity(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    promotion = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    promotion_id = promotion["outcomes"][0]["id"]

    graph = verify_automatic_promotion(tmp_db, promotion_id)

    assert graph["promotion"]["outcome_code"] == "verified"
    assert graph["claim"]["id"] == promotion["outcomes"][0]["claim_id"]
    assert graph["evidence_spans"][0]["excerpt"] == "released a UAP report"
    assert check_database(tmp_db).ok


def test_direct_sql_fake_graph_is_rejected_by_verifier_and_integrity_checker(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    promotion_id, _, _ = _direct_graph(
        tmp_db,
        analysis["id"],
        excerpt="fabricated evidence",
        start=0,
        end=len("fabricated evidence"),
    )

    _assert_rejected(tmp_db, promotion_id)


def test_verifier_rejects_offsets_that_do_not_select_the_stored_excerpt(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    promotion_id, _, _ = _direct_graph(
        tmp_db,
        analysis["id"],
        start=0,
        end=len("released a UAP report"),
    )

    _assert_rejected(tmp_db, promotion_id)


def test_verifier_rejects_duplicate_excerpt_occurrence(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="UAP repeated; UAP repeated",
        excerpt="UAP",
    )
    promotion_id, _, _ = _direct_graph(tmp_db, analysis["id"], excerpt="UAP", start=0, end=3)

    _assert_rejected(tmp_db, promotion_id)


def test_verifier_rejects_forged_canonical_view_hash(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    promotion = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    promotion_id = promotion["outcomes"][0]["id"]
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER evidence_spans_immutable_update")
            conn.execute(
                "UPDATE evidence_spans SET view_content_hash = 'forged-view-hash' WHERE id = ?",
                (promotion["outcomes"][0]["evidence_span_ids"][0],),
            )
    finally:
        conn.close()

    _assert_rejected(tmp_db, promotion_id)


def test_verifier_rejects_out_of_range_candidate_index(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    promotion_id, _, _ = _direct_graph(tmp_db, analysis["id"], claim_index=99)

    _assert_rejected(tmp_db, promotion_id)


def test_verifier_rejects_forged_promotion_identity(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    promotion_id, _, _ = _direct_graph(tmp_db, analysis["id"])
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER article_analysis_promotions_immutable_update")
            conn.execute(
                "UPDATE article_analysis_promotions SET promotion_identity = 'forged' WHERE id = ?",
                (promotion_id,),
            )
    finally:
        conn.close()

    _assert_rejected(tmp_db, promotion_id)


def test_verifier_rejects_cross_candidate_evidence_span_and_claim_evidence(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    promotion_id, _, _ = _direct_graph(
        tmp_db,
        analysis["id"],
        span_candidate_index=1,
        drop_triggers=(
            "claim_evidence_automatic_contract_insert",
            "article_analysis_promotions_verified_contract_insert",
        ),
    )

    _assert_rejected(tmp_db, promotion_id)


def test_verifier_rejects_missing_automatic_claim_state_history(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    promotion_id, _, _ = _direct_graph(tmp_db, analysis["id"], include_history=False)

    _assert_rejected(tmp_db, promotion_id)


def test_verifier_rejects_inconsistent_automatic_claim_state_history(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    promotion_id, _, _ = _direct_graph(
        tmp_db,
        analysis["id"],
        history_rows=(("supported", "pending"),),
    )

    _assert_rejected(tmp_db, promotion_id)


def test_verifier_rejects_duplicate_automatic_claim_state_transition(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    promotion = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    promotion_id = promotion["outcomes"][0]["id"]
    claim_id = promotion["outcomes"][0]["claim_id"]
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO claim_state_history
                    (id, claim_id, from_state, to_state, reason, created_at)
                VALUES ('csh-duplicate', ?, 'pending', 'pending', 'direct test', ?)
                """,
                (claim_id, NOW),
            )
    finally:
        conn.close()

    _assert_rejected(tmp_db, promotion_id)


def test_verifier_rejects_cross_analysis_claim_and_evidence_in_promotion(tmp_db):
    first_analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    first = ArticleAnalysisPromotionService(tmp_db).promote(first_analysis["id"])
    second_analysis = _variant_analysis(tmp_db, first_analysis)
    second = ArticleAnalysisPromotionService(tmp_db).promote(second_analysis["id"])
    first_outcome = first["outcomes"][0]
    second_outcome = second["outcomes"][0]
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER article_analysis_promotions_immutable_update")
            conn.execute(
                """
                UPDATE article_analysis_promotions
                SET claim_id = ?, evidence_span_ids_json = ?
                WHERE id = ?
                """,
                (
                    second_outcome["claim_id"],
                    json.dumps(second_outcome["evidence_span_ids"]),
                    first_outcome["id"],
                ),
            )
    finally:
        conn.close()

    _assert_rejected(tmp_db, first_outcome["id"])


def test_replaying_a_corrupted_verified_promotion_fails_closed(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    promotion_id, _, _ = _direct_graph(
        tmp_db,
        analysis["id"],
        excerpt="fabricated evidence",
        start=0,
        end=len("fabricated evidence"),
    )

    with pytest.raises(AutomaticPromotionIntegrityError):
        ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])

    assert not check_database(tmp_db).ok
