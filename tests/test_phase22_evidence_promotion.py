from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from newsroom import storage
from newsroom.article_analysis import (
    ANALYSIS_PROMPT_VERSION,
    ANALYSIS_SCHEMA_VERSION,
    ARTIFACT_INPUT_VIEW_VERSION,
    ArticleAnalysisService,
    analysis_identity_hash,
    analysis_input_text,
)
from newsroom.content_artifacts import ContentArtifactService
from newsroom.domain import CoreService
from newsroom.jobs import JobService
from newsroom.migrations import apply_migrations
from newsroom.monitoring import (
    DocumentVersionRelevanceService,
    MonitorService,
    MonitoringPolicyService,
    RelevanceResult,
)

T0 = "2026-08-20T12:00:00Z"


def _count(db, table: str) -> int:
    conn = storage.connect(db)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _analysis(
    db,
    *,
    text: str,
    excerpt: str,
    proposition: str = "The agency released a UAP report.",
    analyzed_count: int | None = None,
    content_kind: str = "visible_text",
):
    apply_migrations(db)
    core = CoreService(db)
    category = core.create_category({"slug": "science", "name": "Science"})
    topic = core.create_topic({"category_id": category["id"], "slug": "uap", "name": "UAP"})
    core.create_vocabulary(topic["id"], {"term": "UAP", "term_type": "include"})
    source = core.create_source({"name": "Example", "slug": "example", "homepage_url": "https://example.test"})
    policy = MonitoringPolicyService(db).create(
        {"name": "Policy", "allowed_channels": ["direct_http"], "base_cadence_seconds": 60,
         "min_cadence_seconds": 30, "max_cadence_seconds": 300}
    )
    monitor = MonitorService(db).create(
        {"target_type": "source", "target_id": source["id"], "policy_id": policy["id"],
         "need_type": "topic", "need_id": topic["id"], "next_check_at": T0}
    )
    document = core.create_document(
        {"source_id": source["id"], "canonical_url": "https://example.test/uap", "title": "UAP report"}
    )
    artifact = ContentArtifactService(db).create(normalized_text=text, content_kind=content_kind)
    version_id = "dv_phase22"
    conn = storage.connect(db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """INSERT INTO document_versions
                   (id, document_id, retrieved_at, content_hash, content_kind, artifact_id, normalized_json, created_at)
                   VALUES (?, ?, ?, 'raw-phase22', 'full_text', ?, '{}', ?)""",
                (version_id, document["id"], T0, artifact["id"], T0),
            )
    finally:
        conn.close()
    job = JobService(db).enqueue(
        "document_version_process",
        {"document_version_id": version_id, "document_id": document["id"], "source_id": source["id"],
         "monitor_id": monitor["id"], "scope_version": 1},
        document_version_id=version_id,
        idempotency_key="phase22",
    )
    relevance = DocumentVersionRelevanceService(db).persist_decision(
        job_id=job["id"], document_version_id=version_id, monitor_id=monitor["id"], scope_version=1,
        scope=MonitorService(db).scope_at_version(monitor["id"], 1),
        result=RelevanceResult(True, "exact", 1.0, ("UAP",), "match"), observed_at=T0,
    )
    loaded = ContentArtifactService(db).load_normalized_content(version_id)
    view = analysis_input_text(loaded)[1]
    count = len(view) if analyzed_count is None else analyzed_count
    analyzed = view[:count]
    input_hash = hashlib.sha256(view.encode()).hexdigest()
    analyzed_hash = hashlib.sha256(analyzed.encode()).hexdigest()
    identity = analysis_identity_hash(
        document_version_id=version_id, relevance_id=relevance["id"], scope_version=1,
        schema_version=ANALYSIS_SCHEMA_VERSION, prompt_version=ANALYSIS_PROMPT_VERSION,
        provider="local", model="deterministic-local-v1", artifact_id=artifact["id"],
        normalized_content_hash=artifact["normalized_content_hash"], input_view_version=(
            "feed_entry_projection_v1" if content_kind == "feed_metadata" else ARTIFACT_INPUT_VIEW_VERSION
        ),
        input_content_hash=input_hash, analyzed_content_hash=analyzed_hash,
    )
    result = {
        "summary": "A UAP report was discussed.", "key_developments": ["A report was discussed."],
        "entities": [], "dates": [], "locations": [], "significance": "Relevant.", "novelty": "New.",
        "candidate_claims": [{"index": 0, "proposition": proposition}],
        "candidate_evidence_excerpts": [{"candidate_claim_index": 0, "excerpt": excerpt}],
        "confidence": 0.9,
    }
    return ArticleAnalysisService(db).persist(
        document_version_id=version_id, relevance_id=relevance["id"], monitor_id=monitor["id"],
        scope_version=1, job_id=job["id"], artifact_id=artifact["id"],
        normalized_content_hash=artifact["normalized_content_hash"], schema_version=ANALYSIS_SCHEMA_VERSION,
        prompt_version=ANALYSIS_PROMPT_VERSION, identity_hash=identity, provider="local",
        model="deterministic-local-v1", paid=False, confidence=0.9, input_char_count=len(view),
        analyzed_char_count=count, truncated=count < len(view), input_view_version=(
            "feed_entry_projection_v1" if content_kind == "feed_metadata" else ARTIFACT_INPUT_VIEW_VERSION
        ),
        input_content_hash=input_hash, analyzed_content_hash=analyzed_hash, result=result,
    )


def test_unique_exact_excerpt_creates_verified_pending_claim(tmp_db):
    from newsroom.evidence_promotion import ArticleAnalysisPromotionService

    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    outcome = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])

    assert outcome["outcomes"][0]["code"] == "verified"
    assert _count(tmp_db, "evidence_spans") == 1
    assert _count(tmp_db, "claims") == 1
    assert _count(tmp_db, "claim_evidence") == 1
    conn = storage.connect(tmp_db)
    try:
        span = conn.execute("SELECT * FROM evidence_spans").fetchone()
        claim = conn.execute("SELECT * FROM claims").fetchone()
        assert span["excerpt"] == "released a UAP report"
        assert span["start_offset"] == 11
        assert span["end_offset"] == 32
        assert span["verification_method"] == "exact_analyzed_slice_v1"
        assert claim["state"] == "pending"
        assert claim["story_id"] is None
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("text", "excerpt", "code"),
    [
        ("The agency released a UAP report.", "fabricated evidence", "excerpt_not_found"),
        ("UAP repeated; UAP repeated", "UAP", "ambiguous_excerpt"),
    ],
)
def test_invalid_excerpt_fails_closed(tmp_db, text, excerpt, code):
    from newsroom.evidence_promotion import ArticleAnalysisPromotionService

    analysis = _analysis(tmp_db, text=text, excerpt=excerpt)
    outcome = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])

    assert outcome["outcomes"][0]["code"] == code
    assert _count(tmp_db, "evidence_spans") == 0
    assert _count(tmp_db, "claims") == 0
    assert _count(tmp_db, "claim_evidence") == 0


def test_excerpt_beyond_analyzed_prefix_is_rejected(tmp_db):
    from newsroom.evidence_promotion import ArticleAnalysisPromotionService

    analysis = _analysis(tmp_db, text="UAP visible. secret suffix", excerpt="secret suffix", analyzed_count=12)
    outcome = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    assert outcome["outcomes"][0]["code"] == "excerpt_not_found"
    assert _count(tmp_db, "claims") == 0


def test_promotion_is_sequentially_idempotent(tmp_db):
    from newsroom.evidence_promotion import ArticleAnalysisPromotionService

    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    service = ArticleAnalysisPromotionService(tmp_db)
    first = service.promote(analysis["id"])
    second = service.promote(analysis["id"])

    assert first["outcomes"][0]["claim_id"] == second["outcomes"][0]["claim_id"]
    assert _count(tmp_db, "evidence_spans") == 1
    assert _count(tmp_db, "claims") == 1
    assert _count(tmp_db, "claim_evidence") == 1


def test_candidate_transaction_rolls_back_on_link_failure(tmp_db, monkeypatch):
    from newsroom.evidence_promotion import ArticleAnalysisPromotionService

    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    service = ArticleAnalysisPromotionService(tmp_db)
    monkeypatch.setattr(service, "_insert_link_tx", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        service.promote(analysis["id"])
    assert _count(tmp_db, "evidence_spans") == 0
    assert _count(tmp_db, "claims") == 0
    assert _count(tmp_db, "claim_evidence") == 0
    assert _count(tmp_db, "article_analysis_promotions") == 0


@pytest.mark.parametrize(
    ("title", "summary", "excerpt", "start"),
    [
        ("Title", "Summary", "Title", 0),
        ("Title", "", "Title", 0),
        ("", "Summary", "Summary", 1),
        ("  Title  ", "  Summary  ", "  Summary  ", 10),
        ("Café", "naïve report", "naïve", 5),
        ("Line one\nLine two", "Summary", "Line two\nSummary", 9),
    ],
)
def test_feed_projection_offsets_are_exact(tmp_db, title, summary, excerpt, start):
    from newsroom.evidence_promotion import ArticleAnalysisPromotionService

    raw = json.dumps({"title": title, "summary": summary, "link": "https://ignored.test"}, ensure_ascii=False)
    analysis = _analysis(tmp_db, text=raw, excerpt=excerpt, proposition=excerpt, content_kind="feed_metadata")
    outcome = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])

    assert outcome["outcomes"][0]["code"] == "verified"
    conn = storage.connect(tmp_db)
    try:
        span = conn.execute("SELECT * FROM evidence_spans").fetchone()
        assert span["start_offset"] == start
        assert span["end_offset"] == start + len(excerpt)
        assert span["view_kind"] == "feed"
        assert span["view_version"] == "feed_entry_projection_v1"
        assert span["field_path"] == "title;summary"
        assert span["artifact_content_hash"] != span["view_content_hash"]
    finally:
        conn.close()


def test_feed_excerpt_beyond_analyzed_prefix_is_rejected(tmp_db):
    from newsroom.evidence_promotion import ArticleAnalysisPromotionService

    raw = json.dumps({"title": "UAP title", "summary": "hidden summary"})
    analysis = _analysis(
        tmp_db, text=raw, excerpt="hidden summary", analyzed_count=len("UAP title\n"), content_kind="feed_metadata"
    )
    outcome = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    assert outcome["outcomes"][0]["code"] == "excerpt_not_found"
    assert _count(tmp_db, "claims") == 0


def test_verified_span_provenance_is_database_immutable(tmp_db):
    from newsroom.evidence_promotion import ArticleAnalysisPromotionService

    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    conn = storage.connect(tmp_db)
    try:
        with pytest.raises(storage.sqlite3.IntegrityError, match="evidence spans are immutable"):
            conn.execute("UPDATE evidence_spans SET start_offset = 0")
        with pytest.raises(storage.sqlite3.IntegrityError, match="automatic claim provenance is immutable"):
            conn.execute("UPDATE claims SET proposition = 'tampered'")
    finally:
        conn.close()


def test_concurrent_replay_reuses_one_canonical_promotion(tmp_db):
    from newsroom.evidence_promotion import ArticleAnalysisPromotionService

    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"]), range(2)))

    assert outcomes[0]["outcomes"][0]["claim_id"] == outcomes[1]["outcomes"][0]["claim_id"]
    assert _count(tmp_db, "evidence_spans") == 1
    assert _count(tmp_db, "claims") == 1
    assert _count(tmp_db, "claim_evidence") == 1
    assert _count(tmp_db, "article_analysis_promotions") == 1


@pytest.mark.parametrize(
    ("text", "excerpt", "proposition", "relationship"),
    [
        ("The agency released a UAP report.", "The agency released a UAP report.",
         "The agency released a UAP report.", "supports"),
        ("The agency did not release the UAP report.", "The agency did not release the UAP report.",
         "The agency release the UAP report.", "contradicts"),
        ("A UAP report mentioned weather.", "mentioned weather", "The agency released a UAP report.",
         "contextualizes"),
    ],
)
def test_relationships_are_classified_locally(tmp_db, text, excerpt, proposition, relationship):
    from newsroom.evidence_promotion import ArticleAnalysisPromotionService

    analysis = _analysis(tmp_db, text=text, excerpt=excerpt, proposition=proposition)
    ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT relationship FROM claim_evidence").fetchone()[0] == relationship
    finally:
        conn.close()


def test_artifact_integrity_failure_prevents_all_phase22_writes(tmp_db):
    from newsroom.evidence_promotion import ArticleAnalysisPromotionService
    from newsroom.provenance import ProvenanceValidationError

    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER content_artifacts_immutable_content")
            conn.execute("UPDATE content_artifacts SET normalized_text = 'tampered'")
    finally:
        conn.close()

    with pytest.raises(ProvenanceValidationError):
        ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    assert _count(tmp_db, "evidence_spans") == 0
    assert _count(tmp_db, "claims") == 0
    assert _count(tmp_db, "claim_evidence") == 0
    assert _count(tmp_db, "article_analysis_promotions") == 0


def test_duplicate_candidate_indexes_are_rejected_before_writes(tmp_db):
    from newsroom.evidence_promotion import ArticleAnalysisPromotionService
    from newsroom.domain import DomainValidation

    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER article_analyses_immutable_update")
            result = json.loads(conn.execute("SELECT result_json FROM article_analyses").fetchone()[0])
            result["candidate_claims"].append({"index": 0, "proposition": "Duplicate index"})
            conn.execute(
                "UPDATE article_analyses SET result_json = ?",
                (json.dumps(result, sort_keys=True, separators=(",", ":")),),
            )
    finally:
        conn.close()

    with pytest.raises(DomainValidation, match="indexes must be unique"):
        ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    assert _count(tmp_db, "evidence_spans") == 0
    assert _count(tmp_db, "claims") == 0
    assert _count(tmp_db, "article_analysis_promotions") == 0


def test_legacy_analysis_is_not_automatically_promoted(tmp_db):
    from newsroom.evidence_promotion import ArticleAnalysisPromotionService
    from newsroom.domain import DomainValidation

    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    conn = storage.connect(tmp_db)
    try:
        row = conn.execute("SELECT * FROM article_analyses WHERE id = ?", (analysis["id"],)).fetchone()
        legacy_identity = analysis_identity_hash(
            document_version_id=row["document_version_id"], relevance_id=row["relevance_id"],
            scope_version=row["scope_version"], schema_version=row["schema_version"],
            prompt_version=row["prompt_version"], provider=row["provider"], model=row["model"],
        )
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER article_analyses_immutable_update")
            conn.execute(
                """UPDATE article_analyses
                   SET input_view_version = NULL, input_content_hash = NULL,
                       analyzed_content_hash = NULL, identity_hash = ? WHERE id = ?""",
                (legacy_identity, analysis["id"]),
            )
    finally:
        conn.close()

    with pytest.raises(DomainValidation, match="not eligible"):
        ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    assert _count(tmp_db, "evidence_spans") == 0
    assert _count(tmp_db, "claims") == 0


def test_invalid_paid_invocation_provenance_prevents_phase22_writes(tmp_db):
    from newsroom.evidence_promotion import ArticleAnalysisPromotionService
    from newsroom.provenance import ProvenanceValidationError

    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER article_analyses_immutable_update")
            conn.execute("UPDATE article_analyses SET paid = 1, invocation_id = NULL WHERE id = ?", (analysis["id"],))
    finally:
        conn.close()

    with pytest.raises(ProvenanceValidationError, match="invocation"):
        ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    assert _count(tmp_db, "evidence_spans") == 0
    assert _count(tmp_db, "claims") == 0
    assert _count(tmp_db, "article_analysis_promotions") == 0
