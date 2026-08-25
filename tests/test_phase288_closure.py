from __future__ import annotations

import sqlite3

import pytest

from newsroom import migrations
from newsroom.ai import CapabilityBundle, DeterministicSynthesisProvider, AIRouter, RoutePolicy
from newsroom.domain import CoreService
from newsroom.evals.benchmark import (
    FullBenchmarkRunner,
    PairedBenchmarkOrchestrator,
    PairedBenchmarkError,
)
from newsroom.evals.lite import LiteBenchmarkError, LiteHarness, bind_contract, load_contract
from newsroom.evals.semantic import SEMANTIC_CASE_IDS, SemanticCaseRunner, run_normal_evaluation
from newsroom.evidence import EvidenceService
from newsroom.migrations import apply_migrations
from newsroom.research_questions import ResearchQuestionExecutionService, ResearchQuestionService


SEMANTIC_CASES = (
    "ask-sufficiency-refusal",
    "conservative-absence",
    "late-dependency-discovery",
    "single-dependency-group-support",
    "late-story-correction",
    "late-story-split",
    "retracted-evidence",
    "silent-document-edit-version",
)


MATCHING_EFFECTIVE_CONFIG = {
    "effective_provider": "openai",
    "effective_model": "gpt-4o-mini",
    "provider_route": "test_double",
    "fallback_used": False,
    "effective_temperature": 0.0,
    "deterministic": True,
    "effective_prompt_version": "lite-document-synthesis-v1",
    "effective_context_budget_tokens": 6000,
    "effective_retrieval_limit": 8,
    "effective_citation_limit": 8,
}

LOCAL_FALLBACK_EFFECTIVE_CONFIG = {
    **MATCHING_EFFECTIVE_CONFIG,
    "effective_provider": "local",
    "effective_model": None,
    "provider_route": "local_deterministic",
    "fallback_used": True,
}


def _paired_test_doubles(tmp_db, *, full_effective_config, lite_effective_config):
    apply_migrations(tmp_db)
    contract = bind_contract(load_contract(), tmp_db)
    full = FullBenchmarkRunner(tmp_db, contract=contract)
    lite = LiteHarness(tmp_db, contract=contract)
    return PairedBenchmarkOrchestrator(full, lite).run_with_test_doubles(
        ["q01"],
        full_synthesize=lambda question: {"answer": "full test answer"},
        lite_synthesize=lambda question, documents: {"text": "lite test answer"},
        full_effective_config=full_effective_config,
        lite_effective_config=lite_effective_config,
    )


def test_semantic_cases_execute_real_newsroom_paths():
    results = [SemanticCaseRunner().run(case_id) for case_id in SEMANTIC_CASES]

    assert all(result.score.semantic.passed_count == result.score.semantic.assertion_count for result in results)
    assert all(assertion.actual_service for result in results for assertion in result.assertions)
    assert all(assertion.observed is not None for result in results for assertion in result.assertions)


def test_semantic_ask_negative_control_fails(monkeypatch):
    def answer_instead_of_refusing(self, *args, **kwargs):
        return {"status": "answered", "refusal_code": None, "statements": [{"classification": "fact"}]}

    monkeypatch.setattr("newsroom.ask.AskService.ask", answer_instead_of_refusing)
    result = SemanticCaseRunner().run("ask-sufficiency-refusal")

    assert result.score.semantic.failed_assertion_ids == ("ask_refusal",)


def test_semantic_dependency_negative_control_fails(monkeypatch):
    monkeypatch.setattr("newsroom.story_evolution.StoryEvolutionService.link_lineage", lambda *args, **kwargs: {})
    result = SemanticCaseRunner().run("late-dependency-discovery")

    assert result.score.semantic.failed_assertion_ids == ("dependency_groups",)


def test_semantic_correction_negative_control_fails(monkeypatch):
    monkeypatch.setattr(
        "newsroom.story_corrections.StoryCorrectionService.reassign_claim",
        lambda self, *args, **kwargs: {"already_applied": True},
    )
    result = SemanticCaseRunner().run("late-story-correction")

    assert result.score.semantic.failed_assertion_ids == ("correction_history",)


def test_normal_evaluation_includes_semantic_assertions():
    results = run_normal_evaluation()

    semantic_results = [result for result in results if result.system == "newsroom-semantic"]
    assert len(semantic_results) == len(SEMANTIC_CASE_IDS)
    assert sum(result.semantic.assertion_count for result in semantic_results) == len(SEMANTIC_CASE_IDS)


def test_contrary_strategy_reports_availability_not_execution(tmp_db):
    apply_migrations(tmp_db)
    question = ResearchQuestionService(tmp_db).create({"question": "What happened?"})
    service = ResearchQuestionExecutionService(tmp_db)
    core = CoreService(tmp_db)
    claim = EvidenceService(tmp_db).create_claim(
        core.create_story({"headline": "Contrary source"})["id"],
        {"proposition": "The event did not happen"},
    )
    service.questions.link_claim(question["id"], claim["id"], "contradicts", origin="manual")

    strategy = service._safe_contrary_strategy(question["id"])

    assert strategy["status"] == "available"
    assert strategy["basis"] == {"type": "contradictory_claim", "claim_id": claim["id"]}


def test_duplicate_suppression_does_not_renew_cooldown(tmp_db):
    apply_migrations(tmp_db)
    question_service = ResearchQuestionService(tmp_db)
    question = question_service.create(
        {"question": "Did the event happen?", "pursuit_cooldown_seconds": 3600, "search_attempt_budget": 1}
    )
    task = question_service.pursue(question["id"], query="same query")
    current_time = ["2026-08-25T00:00:00Z"]
    execution = ResearchQuestionExecutionService(tmp_db, clock=lambda: current_time[0])
    execution._persist_query(task["task_id"], "same query", "explicit", 0)
    current_time[0] = "2026-08-25T00:00:01Z"
    execution._persist_query(
        task["task_id"],
        "same query",
        "duplicate_suppressed",
        1,
        execution_state="duplicate_suppressed",
    )
    current_time[0] = "2026-08-25T01:00:01Z"

    gap_id = question_service.get(question["id"])["gaps"][0]["id"]
    executable, suppressed = execution._suppress_recent_queries(
        {"question_id": question["id"], "gap_id": gap_id},
        question_service.get(question["id"]),
        [("same query", "explicit")],
        now=current_time[0],
    )

    assert executable == [("same query", "explicit")]
    assert suppressed == []


def test_production_lite_rejects_callable_but_test_seam_accepts(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Benchmark source", "slug": "benchmark-source"})
    core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": "https://benchmark.test/item",
            "title": "Benchmark document",
        }
    )
    harness = LiteHarness(tmp_db, contract=bind_contract(load_contract(), tmp_db))

    with pytest.raises(LiteBenchmarkError, match="arbitrary callable"):
        harness.run("q01", lambda question, documents: {"text": "fake"})

    result = harness.run_with_test_double(
        "q01",
        lambda question, documents: {
            "text": "deterministic fake",
            "cited_document_ids": [documents[0].document_id] if documents else [],
        },
        effective_config=MATCHING_EFFECTIVE_CONFIG,
    )
    assert result["test_double"] is True


def test_full_local_execution_is_rejected_for_openai_contract(tmp_db):
    apply_migrations(tmp_db)
    runner = FullBenchmarkRunner(tmp_db, contract=bind_contract(load_contract(), tmp_db))

    result = runner.run("q01")

    verification = result["contract_verification"]
    assert verification["valid"] is False
    assert verification["status"] == "benchmark_contract_not_satisfied"
    assert {"provider", "model"} <= set(verification["mismatch_fields"])
    assert result["effective_config"]["provider_route"] == "local_deterministic"
    assert result["effective_config"]["effective_provider"] == "local"
    assert result["effective_config"]["effective_model"] is None


def test_lite_records_router_effective_route_instead_of_echoing_contract(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Benchmark source", "slug": "benchmark-source"})
    core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": "https://benchmark.test/q01",
            "title": "What product launch is described, and what date and quantity are explicitly reported?",
        }
    )
    router = AIRouter(
        local=CapabilityBundle(synthesis=DeterministicSynthesisProvider()),
        policy=RoutePolicy(local_enabled=True, paid_enabled=False),
    )
    harness = LiteHarness(
        tmp_db,
        contract=bind_contract(load_contract(), tmp_db),
        router=router,
    )

    result = harness.run("q01")

    assert result["effective_config"]["provider_route"] == "local"
    assert result["effective_config"]["effective_provider"] == "local"
    assert result["effective_config"]["effective_model"] is None
    assert result["contract_verification"]["valid"] is False
    assert {"provider", "model"} <= set(result["contract_verification"]["mismatch_fields"])


def test_paired_matching_effective_conditions_are_accepted(tmp_db):
    result = _paired_test_doubles(
        tmp_db,
        full_effective_config=MATCHING_EFFECTIVE_CONFIG,
        lite_effective_config=MATCHING_EFFECTIVE_CONFIG,
    )

    assert result[0]["full"]["contract_verification"]["valid"] is True
    assert result[0]["lite"]["contract_verification"]["valid"] is True


@pytest.mark.parametrize(
    ("full_effective_config", "lite_effective_config"),
    (
        (MATCHING_EFFECTIVE_CONFIG, LOCAL_FALLBACK_EFFECTIVE_CONFIG),
        (LOCAL_FALLBACK_EFFECTIVE_CONFIG, MATCHING_EFFECTIVE_CONFIG),
        (LOCAL_FALLBACK_EFFECTIVE_CONFIG, LOCAL_FALLBACK_EFFECTIVE_CONFIG),
        (
            {**MATCHING_EFFECTIVE_CONFIG, "effective_model": "model-B"},
            MATCHING_EFFECTIVE_CONFIG,
        ),
    ),
)
def test_paired_effective_condition_mismatch_is_rejected(
    tmp_db,
    full_effective_config,
    lite_effective_config,
):
    with pytest.raises(PairedBenchmarkError, match="contract"):
        _paired_test_doubles(
            tmp_db,
            full_effective_config=full_effective_config,
            lite_effective_config=lite_effective_config,
        )


def test_full_runner_uses_actual_ask_adapter(tmp_db):
    apply_migrations(tmp_db)
    runner = FullBenchmarkRunner(tmp_db, contract=bind_contract(load_contract(), tmp_db))

    with pytest.raises(TypeError):
        runner.run("q01", lambda question: {"answer": "bypass"})

    result = runner.run("q01")

    assert result["adapter"] == "newsroom.ask.AskService"
    assert result["question_id"] == "q01"
    assert "answer" in result
    assert result["model_config"] == runner.model_config


def test_paired_orchestrator_rejects_identity_mismatch(tmp_db):
    apply_migrations(tmp_db)
    contract = bind_contract(load_contract(), tmp_db)
    full = FullBenchmarkRunner(tmp_db, contract=contract)
    lite = LiteHarness(tmp_db, contract=contract)
    orchestrator = PairedBenchmarkOrchestrator(full, lite)

    with pytest.raises(PairedBenchmarkError, match="manifest"):
        orchestrator.validate_identity(
            {**full.identity, "corpus_manifest": "different"},
            lite.identity,
        )

    with pytest.raises(PairedBenchmarkError, match="model_config"):
        orchestrator.validate_identity(
            {**full.identity, "model_config": {**full.model_config, "model": "different"}},
            lite.identity,
        )


def test_schema36_history_field_and_query_execution_columns_are_truthful(tmp_path):
    db = tmp_path / "schema35.sqlite"
    conn = sqlite3.connect(db)
    conn.close()
    for version in range(1, 36):
        conn = sqlite3.connect(db)
        conn.execute("PRAGMA foreign_keys = OFF")
        migrations._ensure_ledger(conn)
        with conn:
            for statement in getattr(migrations, f"MIGRATION_{version:04d}_STATEMENTS"):
                conn.execute(statement)
            now = migrations.utc_now()
            conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)", (version, now))
            if version == 1:
                conn.execute("INSERT INTO app_meta(key, value) VALUES ('schema_version', '1')")
                conn.execute("INSERT INTO app_meta(key, value) VALUES ('schema_seeded_at', ?)", (now,))
            else:
                conn.execute("UPDATE app_meta SET value = ? WHERE key = 'schema_version'", (str(version),))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()

    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO blind_spot_review_history(source_id, target_type, target_id, source_class, priority, review_status, original_created_at, preserved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("suggestion-1", "story", "story-1", "official", 0.5, "dismissed", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()

    result = apply_migrations(db)

    assert result.current_version == 36
    conn = sqlite3.connect(db)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(blind_spot_review_history)")}
    query_columns = {row[1] for row in conn.execute("PRAGMA table_info(research_task_queries)")}
    row = conn.execute("SELECT original_suggestion_id, original_created_at, preserved_at FROM blind_spot_review_history").fetchone()
    conn.close()
    assert "original_suggestion_id" in columns
    assert "source_id" not in columns
    assert {"execution_state", "executed_at"} <= query_columns
    assert row[0] == "suggestion-1"
    assert row[2] != row[1]
