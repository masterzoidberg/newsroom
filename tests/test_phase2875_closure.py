from __future__ import annotations

import sqlite3

from newsroom import migrations, storage
from newsroom.attention import AttentionService
from newsroom.domain import CoreService, new_id, utc_now
from newsroom.evidence import EvidenceService
from newsroom.integrity import check_database
from newsroom.migrations import apply_migrations
from newsroom.hypotheses import HypothesisService
from newsroom.operations import export_logical, import_logical
from newsroom.research_questions import ResearchQuestionExecutionService, ResearchQuestionService
from newsroom.source_robustness import SourceRobustnessService
from newsroom.story_evolution import StoryEvolutionService


def _apply_historical_migrations(db_path, through: int) -> None:
    conn = storage.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        with storage.write_tx(conn):
            migrations._ensure_ledger(conn)
            for version in range(1, through + 1):
                for statement in getattr(migrations, f"MIGRATION_{version:04d}_STATEMENTS"):
                    conn.execute(statement)
                now = migrations.utc_now()
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, now),
                )
                if version == 1:
                    conn.execute(
                        "INSERT INTO app_meta(key, value) VALUES ('schema_version', '1')"
                    )
                    conn.execute(
                        "INSERT INTO app_meta(key, value) VALUES ('schema_seeded_at', ?)",
                        (now,),
                    )
                else:
                    conn.execute(
                        "UPDATE app_meta SET value = ? WHERE key = 'schema_version'",
                        (str(version),),
                    )
        conn.execute("PRAGMA foreign_keys = ON")
    finally:
        conn.close()


def _seed_schema32_history(db_path) -> None:
    conn = storage.connect(db_path)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO attention_items
                    (id, object_type, object_id, reason_code, importance_score,
                     state, source_fingerprint, explanation_json, created_at, updated_at)
                VALUES ('attention-1', 'alert', 'alert-1', 'correction', 0.9,
                        'dismissed', 'basis-1', '{}', '2026-01-02T03:04:05Z',
                        '2026-01-02T03:04:05Z')
                """
            )
            conn.execute(
                """
                INSERT INTO attention_feedback(id, attention_id, feedback, actor, created_at)
                VALUES ('feedback-exact', 'attention-1', 'not_important', 'alice',
                        '2026-01-02T03:05:06Z')
                """
            )
            conn.execute(
                """
                INSERT INTO attention_feedback(id, attention_id, feedback, actor, created_at)
                VALUES ('feedback-legacy', 'attention-1', 'useful', 'bob',
                        '2026-01-02T03:06:07Z')
                """
            )
            conn.execute(
                """
                INSERT INTO blind_spot_suggestions
                    (id, target_type, target_id, source_class, coverage_run_id,
                     priority, reason, status, created_at, reviewed_at, reviewed_by)
                VALUES ('blind-1', 'story', 'story-1', 'official', NULL, 0.8,
                        'reviewed by operator', 'dismissed', '2026-01-03T00:00:00Z',
                        '2026-01-04T00:00:00Z', 'reviewer')
                """
            )
            conn.execute(
                """
                INSERT INTO research_questions
                    (id, question, origin_type, status, priority,
                     search_attempt_budget, created_at, updated_at)
                VALUES ('question-1', 'What happened?', 'user', 'open', 'normal',
                        3, '2026-01-05T00:00:00Z', '2026-01-05T00:00:00Z')
                """
            )
            conn.execute(
                """
                INSERT INTO hypotheses
                    (id, question_id, statement, status, origin, provider_route,
                     created_at, updated_at)
                VALUES ('hypothesis-1', 'question-1', 'Factor A caused it', 'approved',
                        'human', 'local_deterministic', '2026-01-05T00:01:00Z',
                        '2026-01-05T00:01:00Z')
                """
            )
            conn.execute(
                """
                INSERT INTO hypothesis_gaps
                    (id, hypothesis_id, description, status, created_at, updated_at)
                VALUES ('hyp-gap-1', 'hypothesis-1', 'Find the discriminating evidence',
                        'open', '2026-01-05T00:02:00Z', '2026-01-05T00:02:00Z')
                """
            )
    finally:
        conn.close()


def test_schema32_history_and_hypothesis_gap_survive_upgrade(tmp_path):
    db_path = tmp_path / "schema32.sqlite"
    _apply_historical_migrations(db_path, 32)
    _seed_schema32_history(db_path)

    result = apply_migrations(db_path)

    assert result.current_version == 36
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        attention = conn.execute(
            "SELECT * FROM attention_decisions ORDER BY id"
        ).fetchall()
        assert len(attention) == 2
        exact = next(row for row in attention if row["legacy_action"] is None)
        assert exact["object_type"] == "alert"
        assert exact["object_id"] == "alert-1"
        assert exact["reason_code"] == "correction"
        assert exact["basis_fingerprint"] == "basis-1"
        assert exact["action"] == "not_useful"
        assert exact["actor"] == "alice"
        assert exact["created_at"] == "2026-01-02T03:05:06Z"
        legacy = next(row for row in attention if row["legacy_action"] == "useful")
        assert legacy["action"] == "legacy"
        assert "useful" in (legacy["note"] or "")

        review = conn.execute(
            "SELECT * FROM blind_spot_review_history WHERE original_suggestion_id = 'blind-1'"
        ).fetchone()
        assert review is not None
        assert review["review_status"] == "dismissed"
        assert review["reviewer"] == "reviewer"
        assert review["reviewed_at"] == "2026-01-04T00:00:00Z"

        gap = conn.execute(
            "SELECT question_id, origin_hypothesis_id FROM research_question_gaps"
            " WHERE id = 'hypothesis-gap:hyp-gap-1'"
        ).fetchone()
        assert tuple(gap) == ("question-1", "hypothesis-1")
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()

    report = check_database(db_path)
    assert report.ok is True


def test_fresh_and_schema34_migrations_are_idempotent(tmp_path):
    fresh = tmp_path / "fresh.sqlite"
    assert apply_migrations(fresh).current_version == 36
    assert apply_migrations(fresh).applied_versions == ()

    schema34 = tmp_path / "schema34.sqlite"
    _apply_historical_migrations(schema34, 32)
    conn = storage.connect(schema34)
    try:
        with storage.write_tx(conn):
            for statement in migrations.MIGRATION_0033_STATEMENTS:
                conn.execute(statement)
            # Recreate the pre-closure schema-34 Attention table. This makes
            # migration 35 prove forward compatibility with the old shape,
            # rather than merely rerunning the current migration-33 DDL.
            conn.execute("DROP INDEX IF EXISTS attention_decisions_identity_idx")
            conn.execute("DROP TABLE attention_decisions")
            conn.execute(
                """
                CREATE TABLE attention_decisions (
                    id TEXT PRIMARY KEY,
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    basis_fingerprint TEXT NOT NULL,
                    action TEXT NOT NULL CHECK (action IN ('seen', 'snoozed', 'not_useful')),
                    actor TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX attention_decisions_identity_idx
                ON attention_decisions(object_type, object_id, reason_code, basis_fingerprint, created_at DESC, id DESC)
                """
            )
            for statement in migrations.MIGRATION_0034_STATEMENTS:
                conn.execute(statement)
            for version in (33, 34):
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, migrations.utc_now()),
                )
    finally:
        conn.close()

    result = apply_migrations(schema34)
    assert result.applied_versions == (35, 36)
    assert apply_migrations(schema34).applied_versions == ()


def _unread_alert(db_path, *, cause: str = "cause-1") -> str:
    story = CoreService(db_path).create_story({"headline": "Attention story"})
    now = utc_now()
    alert_id = new_id("alert")
    conn = storage.connect(db_path)
    try:
        with storage.write_tx(conn):
            rule_id = new_id("alert-rule")
            conn.execute(
                """
                INSERT INTO alert_rules
                    (id, name, target_type, target_id, event_types_json,
                     min_importance, browser_enabled, enabled, dedupe_window_seconds,
                     timezone_name, created_at, updated_at)
                VALUES (?, 'Attention rule', 'story', ?, '[]', 0, 0, 1, 0,
                        'UTC', ?, ?)
                """,
                (rule_id, story["id"], now, now),
            )
            conn.execute(
                """
                INSERT INTO alerts
                    (id, rule_id, story_id, event_type, title, body,
                     importance_score, dedupe_key, cause_json, status, created_at)
                VALUES (?, ?, ?, 'correction', 'Correction', 'A correction',
                        0.9, ?, ?, 'unread', ?)
                """,
                (alert_id, rule_id, story["id"], new_id("dedupe"),
                 '{"cause": "' + cause + '"}', now),
            )
    finally:
        conn.close()
    return alert_id


def test_attention_snooze_expires_and_new_material_basis_surfaces(tmp_db):
    apply_migrations(tmp_db)
    alert_id = _unread_alert(tmp_db)
    clock = ["2026-01-10T00:00:00Z"]
    attention = AttentionService(tmp_db, clock=lambda: clock[0])

    item = attention.list()["items"][0]
    attention.decide(item["id"], "snoozed", actor="tester")
    assert attention.list()["items"] == []

    clock[0] = "2026-01-16T23:59:59Z"
    assert attention.list()["items"] == []
    clock[0] = "2026-01-17T00:00:00Z"
    assert attention.list()["items"][0]["object_id"] == alert_id

    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE alerts SET cause_json = ? WHERE id = ?",
                ('{"cause": "cause-2"}', alert_id),
            )
    finally:
        conn.close()
    assert attention.list()["items"][0]["basis_fingerprint"] != item["basis_fingerprint"]


def test_alert_attention_seen_acknowledges_alert(tmp_db):
    apply_migrations(tmp_db)
    alert_id = _unread_alert(tmp_db)
    attention = AttentionService(tmp_db)
    item = attention.list()["items"][0]

    attention.decide(item["id"], "seen", actor="tester")

    conn = storage.connect(tmp_db)
    try:
        alert = conn.execute(
            "SELECT status, acknowledged_by FROM alerts WHERE id = ?", (alert_id,)
        ).fetchone()
        assert tuple(alert) == ("acknowledged", "tester")
    finally:
        conn.close()


def test_counterfactual_document_anchor_excludes_current_dependency_component(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    evidence = EvidenceService(tmp_db)
    story = core.create_story({"headline": "Dependency story"})
    claim = evidence.create_claim(story["id"], {"proposition": "The event occurred"})

    source_a = core.create_source({"name": "Source A", "slug": "source-a"})
    source_b = core.create_source({"name": "Source B", "slug": "source-b"})
    document_a = core.create_document(
        {"source_id": source_a["id"], "canonical_url": "https://a.test/story", "title": "A"}
    )
    document_b = core.create_document(
        {"source_id": source_b["id"], "canonical_url": "https://b.test/story", "title": "B"}
    )
    version_a = evidence.create_document_version(document_a["id"], {"content_hash": "hash-a", "content_kind": "excerpt"})
    version_b = evidence.create_document_version(document_b["id"], {"content_hash": "hash-b", "content_kind": "excerpt"})
    span_a = evidence.create_evidence_span(version_a["id"], {"excerpt": "The event occurred"})
    span_b = evidence.create_evidence_span(version_b["id"], {"excerpt": "The event occurred"})
    evidence.link_claim_evidence(claim["id"], {"evidence_span_id": span_a["id"], "relationship": "supports"})
    evidence.link_claim_evidence(claim["id"], {"evidence_span_id": span_b["id"], "relationship": "supports"})
    evidence.set_claim_state(claim["id"], "supported", "test")
    evidence.accept_claim(claim["id"])
    StoryEvolutionService(tmp_db).link_lineage(
        document_b["id"], document_a["id"], "syndicated_from", confidence=1.0, rationale="wire copy"
    )

    result = SourceRobustnessService(tmp_db).counterfactual(
        "claim", claim["id"], exclude_document_ids=[document_b["id"]]
    )

    assert result["resolved_excluded_document_ids"] == sorted([document_a["id"], document_b["id"]])
    assert result["dropped_claim_ids"] == [claim["id"]]
    assert result["resolved_dependency_groups"] == [sorted([document_a["id"], document_b["id"]])]
    assert evidence.get_claim(claim["id"])["state"] == "supported"


def test_logical_roundtrip_preserves_hypothesis_gap_provenance(tmp_db, tmp_path):
    apply_migrations(tmp_db)
    question = ResearchQuestionService(tmp_db).create({"question": "What explains it?"})
    hypothesis = HypothesisService(tmp_db).create(question["id"], "Factor A explains it")
    gap = HypothesisService(tmp_db).add_gap(hypothesis["id"], "Find the discriminating evidence")

    exported = export_logical(tmp_db, tmp_path / "logical.jsonl")
    destination = tmp_path / "roundtrip.sqlite"
    assert import_logical(exported, destination)["verified"] is True

    conn = storage.connect(destination)
    try:
        row = conn.execute(
            "SELECT id, question_id, origin_hypothesis_id FROM research_question_gaps WHERE id = ?",
            (gap["id"],),
        ).fetchone()
        assert tuple(row) == (gap["id"], question["id"], hypothesis["id"])
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_research_query_duplicate_is_suppressed_across_tasks(tmp_db):
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = service.create(
        {
            "question": "Did the event happen?",
            "search_attempt_budget": 3,
            "query_budget": 6,
            "pursuit_cooldown_seconds": 3600,
        }
    )
    first = service.pursue(question["id"], query="same investigative query")
    first_task = first["task_id"]
    ResearchQuestionExecutionService(tmp_db)._persist_query(
        first_task, "same investigative query", "explicit", 0
    )
    current = service.get(question["id"])
    gap_id = current["gaps"][0]["id"]
    executable, suppressed = ResearchQuestionExecutionService(tmp_db)._suppress_recent_queries(
        {"question_id": question["id"], "gap_id": gap_id},
        current,
        [("same investigative query", "explicit"), ("new scope query", "explicit")],
    )

    assert suppressed == ["same investigative query"]
    assert executable == [("new scope query", "explicit")]


def test_research_contrary_strategy_requires_canonical_basis(tmp_db):
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = service.create({"question": "What happened?"})
    execution = ResearchQuestionExecutionService(tmp_db)
    assert execution._safe_contrary_strategy(question["id"]) == {
        "status": "unavailable",
        "reason": "no_safe_contrary_strategy_available",
    }

    core = CoreService(tmp_db)
    claim = EvidenceService(tmp_db).create_claim(
        core.create_story({"headline": "Contrary story"})["id"],
        {"proposition": "The event did not happen"},
    )
    execution.questions.link_claim(question["id"], claim["id"], "contradicts", origin="manual")
    strategy = execution._safe_contrary_strategy(question["id"])
    assert strategy["status"] == "available"
    assert strategy["query"] == "The event did not happen"
    assert strategy["basis"] == {"type": "contradictory_claim", "claim_id": claim["id"]}


def test_research_source_class_diversity_changes_selected_candidates(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    official = core.create_source({"name": "Official", "slug": "official", "source_kind": "official"})
    feed = core.create_source({"name": "Feed", "slug": "feed", "source_kind": "feed"})

    class Search:
        def search(self, _query, **_kwargs):
            return {
                "items": [
                    {"entity_type": "claim", "entity_id": "claim-official-1", "source_id": official["id"]},
                    {"entity_type": "claim", "entity_id": "claim-official-2", "source_id": official["id"]},
                    {"entity_type": "evidence", "entity_id": "evidence-feed-1", "source_id": feed["id"]},
                ]
            }

    selected = ResearchQuestionExecutionService(tmp_db, search=Search())._research(
        [("event", "explicit")], cap=2
    )

    assert [(item["entity_type"], item["source_id"]) for item in selected] == [
        ("evidence", feed["id"]),
        ("claim", official["id"]),
    ]
