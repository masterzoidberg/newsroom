"""Database integrity checks, including deliberate polymorphic references."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Optional

from . import storage
from .evidence_promotion import (
    AutomaticPromotionIntegrityError,
    verify_automatic_promotion,
)
from .provenance import ProvenanceValidationError, validate_analysis_provenance


@dataclass(frozen=True)
class IntegrityIssue:
    code: str
    detail: str


@dataclass(frozen=True)
class IntegrityReport:
    ok: bool
    issues: tuple[IntegrityIssue, ...]


_MONITOR_TARGET_TABLES = {
    "topic": "topics",
    "subject": "subjects",
    "story": "stories",
    "source": "sources",
    "research_question": "research_questions",
}

_QUESTION_ORIGIN_TABLES = {
    "story": "stories",
    "claim": "claims",
    "subject": "subjects",
    "monitor": "monitors",
}


def _table_exists(conn, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        is not None
    )


def check_database(db_path: Optional[str] = None) -> IntegrityReport:
    conn = storage.connect(db_path)
    issues: list[IntegrityIssue] = []
    try:
        if not _table_exists(conn, "schema_migrations"):
            return IntegrityReport(False, (IntegrityIssue("missing_schema", "schema_migrations is absent"),))

        pragma_result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if pragma_result != "ok":
            issues.append(IntegrityIssue("sqlite_integrity", str(pragma_result)))

        for row in conn.execute("PRAGMA foreign_key_check"):
            issues.append(
                IntegrityIssue(
                    "foreign_key_violation",
                    f"table={row[0]} rowid={row[1]} parent={row[2]}",
                )
            )

        if not _table_exists(conn, "monitors"):
            issues.append(IntegrityIssue("missing_schema", "monitors is absent"))
        for target_type, table in _MONITOR_TARGET_TABLES.items():
            if not _table_exists(conn, table):
                continue
            rows = conn.execute(
                f"""
                SELECT m.id, m.target_id
                FROM monitors AS m
                WHERE m.target_type = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM {table} AS target WHERE target.id = m.target_id
                  )
                ORDER BY m.id
                """,
                (target_type,),
            )
            issues.extend(
                IntegrityIssue(
                    "orphan_monitor_target",
                    f"monitor={row[0]} target_type={target_type} target_id={row[1]}",
                )
                for row in rows
            )

        if _table_exists(conn, "monitors"):
            for need_type, table in _MONITOR_TARGET_TABLES.items():
                if not _table_exists(conn, table):
                    continue
                rows = conn.execute(
                    f"""
                    SELECT m.id, m.need_id
                    FROM monitors AS m
                    WHERE m.need_type = ?
                      AND (m.need_id IS NULL OR NOT EXISTS (
                          SELECT 1 FROM {table} AS target WHERE target.id = m.need_id
                      ))
                    ORDER BY m.id
                    """,
                    (need_type,),
                )
                issues.extend(
                    IntegrityIssue(
                        "invalid_monitor_need_reference",
                        f"monitor={row[0]} need_type={need_type} need_id={row[1]}",
                    )
                    for row in rows
                )

        if not _table_exists(conn, "research_questions"):
            issues.append(IntegrityIssue("missing_schema", "research_questions is absent"))
        else:
            for origin_type, table in _QUESTION_ORIGIN_TABLES.items():
                if not _table_exists(conn, table):
                    continue
                rows = conn.execute(
                    f"""
                    SELECT q.id, q.origin_id
                    FROM research_questions AS q
                    WHERE q.origin_type = ?
                      AND (q.origin_id IS NULL OR NOT EXISTS (
                          SELECT 1 FROM {table} AS origin WHERE origin.id = q.origin_id
                      ))
                    ORDER BY q.id
                    """,
                    (origin_type,),
                )
                issues.extend(
                    IntegrityIssue(
                        "orphan_research_question_origin",
                        f"question={row[0]} origin_type={origin_type} origin_id={row[1]}",
                    )
                    for row in rows
                )

        if _table_exists(conn, "story_review") and _table_exists(conn, "story_revisions"):
            rows = conn.execute(
                """
                SELECT review.story_id, review.last_reviewed_revision_id
                FROM story_review AS review
                JOIN story_revisions AS revision
                  ON revision.id = review.last_reviewed_revision_id
                WHERE revision.story_id <> review.story_id
                """
            )
            issues.extend(
                IntegrityIssue(
                    "review_revision_story_mismatch",
                    f"story={row[0]} revision={row[1]}",
                )
                for row in rows
            )

        # Phase 18 — durable normalized content artifacts. Referenced artifacts
        # must exist (FK also guards this) and stored content must still hash to
        # its recorded normalized_content_hash, or the DB cannot be trusted.
        # Pre-Phase-18 versions legitimately have artifact_id = NULL and are not
        # flagged: no content is ever fabricated for historical versions.
        if _table_exists(conn, "content_artifacts") and _table_exists(conn, "document_versions"):
            rows = conn.execute(
                """
                SELECT dv.id, dv.artifact_id
                FROM document_versions AS dv
                WHERE dv.artifact_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM content_artifacts AS ca WHERE ca.id = dv.artifact_id
                  )
                ORDER BY dv.id
                """
            )
            issues.extend(
                IntegrityIssue(
                    "missing_content_artifact",
                    f"document_version={row[0]} artifact={row[1]}",
                )
                for row in rows
            )
            for row in conn.execute(
                """
                SELECT ca.id, ca.normalized_content_hash, ca.normalized_text, ca.text_length
                FROM content_artifacts AS ca
                ORDER BY ca.id
                """
            ):
                recomputed = hashlib.sha256(row[2].encode("utf-8")).hexdigest()
                if recomputed != row[1]:
                    issues.append(
                        IntegrityIssue(
                            "content_artifact_hash_mismatch",
                            f"artifact={row[0]} stored_hash={row[1][:16]}... recomputed={recomputed[:16]}...",
                        )
                    )
                if len(row[2]) != row[3]:
                    issues.append(
                        IntegrityIssue(
                            "content_artifact_length_mismatch",
                            f"artifact={row[0]} stored_length={len(row[2])} recorded={row[3]}",
                        )
                    )

        # Phase 21 — durable article analyses. Detection is read-only (no model
        # is ever re-run). Structural references are FK-guarded but are checked
        # explicitly like the other durable families; provenance states that
        # can never be produced by the writer (paid local analysis, empty
        # provider/model, malformed result_json) are flagged.
        if _table_exists(conn, "article_analyses"):
            if not _table_exists(conn, "document_versions"):
                issues.append(IntegrityIssue("missing_schema", "document_versions is absent"))
            else:
                rows = conn.execute(
                    """
                    SELECT aa.id, aa.document_version_id
                    FROM article_analyses AS aa
                    WHERE NOT EXISTS (
                        SELECT 1 FROM document_versions AS dv WHERE dv.id = aa.document_version_id
                    )
                    ORDER BY aa.id
                    """
                )
                issues.extend(
                    IntegrityIssue(
                        "orphan_analysis_version",
                        f"analysis={row[0]} document_version={row[1]}",
                    )
                    for row in rows
                )
            if not _table_exists(conn, "document_version_relevance"):
                issues.append(IntegrityIssue("missing_schema", "document_version_relevance is absent"))
            else:
                rows = conn.execute(
                    """
                    SELECT aa.id, aa.relevance_id
                    FROM article_analyses AS aa
                    WHERE NOT EXISTS (
                        SELECT 1 FROM document_version_relevance AS dvr
                        WHERE dvr.id = aa.relevance_id
                    )
                    ORDER BY aa.id
                    """
                )
                issues.extend(
                    IntegrityIssue(
                        "orphan_analysis_relevance",
                        f"analysis={row[0]} relevance={row[1]}",
                    )
                    for row in rows
                )
            for row in conn.execute(
                """
                SELECT aa.id, aa.provider, aa.model, aa.paid, aa.result_json
                FROM article_analyses AS aa
                ORDER BY aa.id
                """
            ):
                analysis_id, provider, model, paid, result_json = row
                if str(provider or "").strip() == "local" and paid == 1:
                    issues.append(
                        IntegrityIssue(
                            "invalid_analysis_provenance",
                            f"analysis={analysis_id} paid local analysis is impossible",
                        )
                    )
                if not str(model or "").strip():
                    issues.append(
                        IntegrityIssue(
                            "invalid_analysis_provenance",
                            f"analysis={analysis_id} has an empty model label",
                        )
                    )
                try:
                    parsed = json.loads(result_json)
                except (TypeError, ValueError):
                    issues.append(
                        IntegrityIssue(
                            "malformed_analysis_result",
                            f"analysis={analysis_id} result_json is not valid JSON",
                        )
                    )
                else:
                    if not isinstance(parsed, dict) or "summary" not in parsed:
                        issues.append(
                            IntegrityIssue(
                                "malformed_analysis_result",
                                f"analysis={analysis_id} result_json is not the analysis schema",
                            )
                        )
            for row in conn.execute("SELECT id FROM article_analyses ORDER BY id"):
                try:
                    validate_analysis_provenance(db_path, row[0])
                except ProvenanceValidationError as exc:
                    for detail in exc.issues:
                        code, _, message = detail.partition(":")
                        issues.append(IntegrityIssue(code or "invalid_analysis_provenance", f"analysis={row[0]} {message.strip()}"))
                except Exception as exc:
                    issues.append(IntegrityIssue("invalid_analysis_provenance", f"analysis={row[0]} {exc}"))

        # Phase 22.3 — verified promotions must be independently reconstructable
        # from the canonical artifact and the persisted ArticleAnalysis result.
        # Database triggers can enforce relationship shape, but cannot prove
        # that an excerpt is present at its claimed coordinates in the source
        # text. The shared read-only verifier closes that boundary.
        if _table_exists(conn, "article_analysis_promotions"):
            for row in conn.execute(
                "SELECT id FROM article_analysis_promotions WHERE outcome_code = 'verified' ORDER BY id"
            ):
                try:
                    verify_automatic_promotion(db_path, row[0])
                except AutomaticPromotionIntegrityError as exc:
                    for detail in exc.issues:
                        issues.append(
                            IntegrityIssue(
                                "invalid_verified_promotion",
                                f"promotion={row[0]} {detail}",
                            )
                        )
                except Exception as exc:
                    issues.append(
                        IntegrityIssue(
                            "invalid_verified_promotion",
                            f"promotion={row[0]} verification failed ({type(exc).__name__})",
                        )
                    )

        # Phase 23B — a completed Story checkpoint must resolve to the exact
        # Claim, Story revision, cited document, and evolution event created
        # for its verified promotion.
        if _table_exists(conn, "jobs") and _table_exists(conn, "story_evolution_events"):
            for job in conn.execute(
                """
                SELECT id, payload_json, result_json
                FROM jobs
                WHERE job_type = 'automatic_story_stage'
                  AND status IN ('succeeded', 'partial')
                ORDER BY id
                """
            ):
                try:
                    payload = json.loads(job["payload_json"])
                    result = json.loads(job["result_json"])
                except (TypeError, ValueError, json.JSONDecodeError):
                    payload = result = None
                valid = bool(
                    isinstance(payload, dict)
                    and isinstance(result, dict)
                    and result.get("stage_status")
                    in {"completed", "deferred", "terminal"}
                    and result.get("job_id") == job["id"]
                    and result.get("promotion_id") == payload.get("promotion_id")
                )
                if valid and result.get("stage_status") in {"deferred", "terminal"}:
                    valid = all(
                        result.get(field) is None
                        for field in ("story_id", "event_id", "revision_id")
                    )
                if valid and result.get("stage_status") == "completed":
                    chain = conn.execute(
                        """
                        SELECT c.story_id, p.id AS promotion_id,
                               src.revision_id, srd.document_id, e.id AS event_id
                        FROM article_analysis_promotions p
                        JOIN claims c ON c.id = p.claim_id
                        JOIN story_revision_claims src ON src.claim_id = c.id
                        JOIN story_revisions sr
                          ON sr.id = src.revision_id AND sr.story_id = c.story_id
                        JOIN story_revision_documents srd
                          ON srd.revision_id = sr.id
                        JOIN story_evolution_events e
                          ON e.story_id = c.story_id
                         AND e.document_id = srd.document_id
                         AND json_extract(e.decision_json, '$.automatic_story_stage.job_id') = ?
                         AND json_extract(e.decision_json, '$.automatic_story_stage.promotion_id') = p.id
                         AND json_extract(e.decision_json, '$.automatic_story_stage.claim_id') = c.id
                        WHERE p.id = ? AND c.id = ? AND sr.id = ? AND e.id = ?
                        """,
                        (
                            job["id"],
                            payload.get("promotion_id"),
                            result.get("claim_id"),
                            result.get("revision_id"),
                            result.get("event_id"),
                        ),
                    ).fetchone()
                    valid = bool(
                        chain
                        and chain["story_id"] == result.get("story_id")
                        and chain["promotion_id"] == result.get("promotion_id")
                        and chain["revision_id"] == result.get("revision_id")
                        and chain["event_id"] == result.get("event_id")
                    )
                if not valid:
                    issues.append(
                        IntegrityIssue(
                            "invalid_automatic_story_checkpoint",
                            f"job={job['id']}",
                        )
                    )

        # Phase 23C — report pointers, closed-world propositions, and exact
        # polymorphic causes must remain reconstructable from canonical rows.
        if _table_exists(conn, "living_reports") and _table_exists(conn, "report_revisions"):
            for row in conn.execute(
                """
                SELECT lr.id, lr.current_revision_id
                FROM living_reports lr
                LEFT JOIN report_revisions rr
                  ON rr.id = lr.current_revision_id AND rr.report_id = lr.id
                WHERE lr.current_revision_id IS NOT NULL AND rr.id IS NULL
                ORDER BY lr.id
                """
            ):
                issues.append(
                    IntegrityIssue(
                        "report_current_revision_mismatch",
                        f"report={row[0]} revision={row[1]}",
                    )
                )
            for revision in conn.execute(
                "SELECT id, propositions_json, what_changed FROM report_revisions ORDER BY id"
            ):
                claim_ids = {
                    item[0]
                    for item in conn.execute(
                        "SELECT claim_id FROM report_revision_claims WHERE revision_id = ?",
                        (revision["id"],),
                    )
                }
                cause_ids = {
                    item[0]
                    for item in conn.execute(
                        "SELECT id FROM report_revision_causes WHERE revision_id = ?",
                        (revision["id"],),
                    )
                }
                try:
                    propositions = json.loads(revision["propositions_json"])
                    changes = json.loads(revision["what_changed"] or "[]")
                except (TypeError, ValueError, json.JSONDecodeError):
                    issues.append(
                        IntegrityIssue(
                            "invalid_report_closed_world",
                            f"revision={revision['id']} malformed JSON",
                        )
                    )
                    continue
                if not isinstance(propositions, list) or any(
                    not isinstance(item, dict)
                    or not item.get("claim_ids")
                    or not set(item["claim_ids"]) <= claim_ids
                    for item in propositions
                ):
                    issues.append(
                        IntegrityIssue(
                            "invalid_report_closed_world",
                            f"revision={revision['id']} proposition cites outside Claim set",
                        )
                    )
                if not isinstance(changes, list) or any(
                    not isinstance(item, dict)
                    or not item.get("cause_ids")
                    or not set(item["cause_ids"]) <= cause_ids
                    for item in changes
                ):
                    issues.append(
                        IntegrityIssue(
                            "invalid_report_change_cause",
                            f"revision={revision['id']} what_changed lacks exact causes",
                        )
                    )
            for cause in conn.execute(
                "SELECT * FROM report_revision_causes ORDER BY revision_id, id"
            ):
                chain = conn.execute(
                    """
                    SELECT c.story_id, dv.document_id
                    FROM claims c
                    JOIN report_revision_claims rrc
                      ON rrc.claim_id = c.id AND rrc.revision_id = ?
                    JOIN claim_evidence ce
                      ON ce.claim_id = c.id AND ce.relationship = 'supports'
                    JOIN evidence_spans es
                      ON es.id = ce.evidence_span_id
                    JOIN document_versions dv
                      ON dv.id = es.document_version_id
                    JOIN documents d ON d.id = dv.document_id
                    JOIN sources s ON s.id = d.source_id
                    WHERE c.id = ? AND es.id = ?
                    """,
                    (cause["revision_id"], cause["claim_id"], cause["evidence_span_id"]),
                ).fetchone()
                valid = bool(
                    chain
                    and chain["story_id"] == cause["story_id"]
                    and chain["document_id"] == cause["document_id"]
                )
                if valid and cause["cause_id"] != cause["claim_id"]:
                    event = conn.execute(
                        "SELECT story_id, document_id FROM story_evolution_events WHERE id = ?",
                        (cause["cause_id"],),
                    ).fetchone()
                    valid = bool(
                        event
                        and event["story_id"] == cause["story_id"]
                        and event["document_id"] == cause["document_id"]
                    )
                if not valid:
                    issues.append(
                        IntegrityIssue(
                            "invalid_report_cause_chain",
                            f"revision={cause['revision_id']} cause={cause['id']}",
                        )
                    )
        if _table_exists(conn, "claims") and _table_exists(conn, "claim_state_history"):
            for claim in conn.execute(
                """
                SELECT c.id, c.state, c.accepted_at, h.id AS history_id,
                       h.from_state, h.to_state, h.reason
                FROM claim_state_history h
                JOIN claims c ON c.id = h.claim_id
                WHERE h.reason LIKE 'automatic_report_acceptance:%'
                ORDER BY c.id, h.rowid
                """
            ):
                duplicates = conn.execute(
                    """
                    SELECT COUNT(*) FROM claim_state_history
                    WHERE claim_id = ? AND reason = ?
                    """,
                    (claim["id"], claim["reason"]),
                ).fetchone()[0]
                if (
                    claim["from_state"] != "pending"
                    or claim["to_state"] != "supported"
                    or claim["state"] != "supported"
                    or claim["accepted_at"] is None
                    or duplicates != 1
                ):
                    issues.append(
                        IntegrityIssue(
                            "invalid_automatic_claim_acceptance",
                            f"claim={claim['id']} history={claim['history_id']}",
                        )
                    )
        if _table_exists(conn, "jobs"):
            for job in conn.execute(
                """
                SELECT id, payload_json, result_json
                FROM jobs
                WHERE job_type = 'automatic_report_stage'
                  AND status IN ('succeeded', 'partial')
                ORDER BY id
                """
            ):
                try:
                    payload = json.loads(job["payload_json"])
                    result = json.loads(job["result_json"])
                except (TypeError, ValueError, json.JSONDecodeError):
                    payload = result = None
                valid = bool(
                    isinstance(payload, dict)
                    and isinstance(result, dict)
                    and result.get("job_id") == job["id"]
                    and result.get("stage_status")
                    in {"completed", "no_change", "deferred", "terminal"}
                )
                if valid and result.get("stage_status") in {"deferred", "terminal"}:
                    valid = all(
                        result.get(field) is None
                        for field in (
                            "report_id",
                            "revision_id",
                            "input_identity",
                            "story_id",
                            "claim_id",
                            "promotion_id",
                        )
                    )
                if valid and result.get("stage_status") in {"completed", "no_change"}:
                    revision = conn.execute(
                        """
                        SELECT rr.report_id, lr.target_id
                        FROM report_revisions rr
                        JOIN living_reports lr
                          ON lr.id = rr.report_id AND lr.target_type = 'story'
                        JOIN report_revision_claims rrc
                          ON rrc.revision_id = rr.id AND rrc.claim_id = ?
                        WHERE rr.id = ? AND rr.report_id = ? AND lr.target_id = ?
                        """,
                        (
                            result.get("claim_id"),
                            result.get("revision_id"),
                            result.get("report_id"),
                            result.get("story_id"),
                        ),
                    ).fetchone()
                    valid = bool(
                        revision
                        and result.get("claim_id") == payload.get("claim_id")
                        and result.get("story_id") == payload.get("story_id")
                        and result.get("promotion_id") == payload.get("promotion_id")
                    )
                if not valid:
                    issues.append(
                        IntegrityIssue(
                            "invalid_automatic_report_checkpoint",
                            f"job={job['id']}",
                        )
                    )
        # Phase 23D — every persisted Alert cause must be an exact copy of a
        # cause owned by its pinned ReportRevision, and completed automatic
        # checkpoints must resolve to their durable in-app delivery rows.
        if _table_exists(conn, "alerts") and _table_exists(conn, "report_revision_causes"):
            cause_fields = (
                "id",
                "revision_id",
                "cause_type",
                "cause_id",
                "story_id",
                "claim_id",
                "evidence_span_id",
                "document_id",
                "rationale",
            )
            for alert in conn.execute(
                "SELECT id, report_revision_id, cause_json FROM alerts ORDER BY id"
            ):
                try:
                    causes = json.loads(alert["cause_json"])
                except (TypeError, ValueError, json.JSONDecodeError):
                    causes = None
                valid = bool(
                    alert["report_revision_id"]
                    and isinstance(causes, list)
                    and causes
                )
                if valid:
                    for cause in causes:
                        if not isinstance(cause, dict):
                            valid = False
                            break
                        persisted = conn.execute(
                            "SELECT * FROM report_revision_causes WHERE id = ? AND revision_id = ?",
                            (cause.get("id"), alert["report_revision_id"]),
                        ).fetchone()
                        if persisted is None or any(
                            cause.get(field) != persisted[field]
                            for field in cause_fields
                        ):
                            valid = False
                            break
                if not valid:
                    issues.append(
                        IntegrityIssue(
                            "invalid_alert_cause_reference",
                            f"alert={alert['id']} revision={alert['report_revision_id']}",
                        )
                    )
        if _table_exists(conn, "jobs") and _table_exists(conn, "alert_deliveries"):
            for job in conn.execute(
                """
                SELECT id, payload_json, result_json
                FROM jobs
                WHERE job_type = 'automatic_alert_stage'
                  AND status IN ('succeeded', 'partial')
                ORDER BY id
                """
            ):
                try:
                    payload = json.loads(job["payload_json"])
                    result = json.loads(job["result_json"])
                except (TypeError, ValueError, json.JSONDecodeError):
                    payload = result = None
                valid = bool(
                    isinstance(payload, dict)
                    and isinstance(result, dict)
                    and result.get("job_id") == job["id"]
                    and result.get("stage_status")
                    in {"completed", "no_alert", "deferred", "terminal"}
                    and result.get("report_id") == payload.get("report_id")
                    and result.get("report_revision_id")
                    == payload.get("report_revision_id")
                )
                if valid:
                    upstream = conn.execute(
                        "SELECT status, result_json FROM jobs WHERE id = ? AND job_type = 'automatic_report_stage'",
                        (payload.get("report_stage_job_id"),),
                    ).fetchone()
                    try:
                        upstream_result = (
                            json.loads(upstream["result_json"]) if upstream else None
                        )
                    except (TypeError, ValueError, json.JSONDecodeError):
                        upstream_result = None
                    valid = bool(
                        upstream
                        and upstream["status"] in {"succeeded", "partial"}
                        and isinstance(upstream_result, dict)
                        and upstream_result.get("stage_status") == "completed"
                        and upstream_result.get("report_id") == payload.get("report_id")
                        and upstream_result.get("revision_id")
                        == payload.get("report_revision_id")
                    )
                if valid and result.get("stage_status") in {"deferred", "terminal"}:
                    valid = not result.get("alert_ids") and not result.get("delivery_ids")
                if valid and result.get("stage_status") in {"completed", "no_alert"}:
                    revision = conn.execute(
                        "SELECT 1 FROM report_revisions WHERE id = ? AND report_id = ?",
                        (result.get("report_revision_id"), result.get("report_id")),
                    ).fetchone()
                    alert_ids = result.get("alert_ids")
                    delivery_ids = result.get("delivery_ids")
                    valid = bool(
                        revision
                        and isinstance(alert_ids, list)
                        and isinstance(delivery_ids, list)
                        and (
                            (
                                result.get("stage_status") == "completed"
                                and bool(alert_ids)
                            )
                            or (
                                result.get("stage_status") == "no_alert"
                                and not alert_ids
                                and not delivery_ids
                            )
                        )
                    )
                    if valid:
                        resolved_alerts = {
                            row[0]
                            for row in conn.execute(
                                "SELECT id FROM alerts WHERE report_revision_id = ?",
                                (result.get("report_revision_id"),),
                            )
                            if row[0] in alert_ids
                        }
                        resolved_deliveries = {
                            row["id"]
                            for row in conn.execute(
                                """
                                SELECT id, alert_id FROM alert_deliveries
                                WHERE channel = 'in_app'
                                  AND alert_id IN (
                                      SELECT id FROM alerts WHERE report_revision_id = ?
                                  )
                                """,
                                (result.get("report_revision_id"),),
                            )
                            if row["id"] in delivery_ids and row["alert_id"] in alert_ids
                        }
                        valid = (
                            resolved_alerts == set(alert_ids)
                            and resolved_deliveries == set(delivery_ids)
                            and len(alert_ids) == len(delivery_ids)
                        )
                if not valid:
                    issues.append(
                        IntegrityIssue(
                            "invalid_automatic_alert_checkpoint",
                            f"job={job['id']}",
                        )
                    )
        return IntegrityReport(not issues, tuple(issues))
    finally:
        conn.close()
