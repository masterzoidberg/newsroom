from __future__ import annotations

import json
import sqlite3

import pytest

from newsroom.evals.phase29_protocol import (
    Phase29ProtocolError,
    ResumablePairRecorder,
    create_blind_plan,
    snapshot_manifest,
)


REQUESTED_CONFIG = {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.0,
    "deterministic": True,
    "prompt_version": "lite-document-synthesis-v1",
    "context_budget_tokens": 6000,
    "retrieval_limit": 8,
    "citation_limit": 8,
}


def _envelope(side: str, question_id: str, *, valid: bool = True) -> dict:
    effective = {
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
    return {
        "question_id": question_id,
        "opaque_question_id": f"opaque-{question_id}",
        "question": "What does the evidence support?",
        "answer": {"status": "answered", "text": f"answer-{side}"},
        "cited_document_ids": ["doc-1"],
        "requested_config": REQUESTED_CONFIG,
        "effective_config": effective,
        "contract_verification": {
            "valid": valid,
            "status": "verified" if valid else "benchmark_contract_not_satisfied",
            "mismatch_fields": [] if valid else ["model"],
        },
        "frozen_corpus": {"snapshot_path": "C:/snapshot.db", "manifest_hash": "a" * 64},
        "corpus_cutoff": "2026-08-25T00:00:00Z",
        "contract_id": "newsroom-lite-20q-v1",
        "test_double": True,
    }


def _pair(question_id: str, *, valid: bool = True) -> dict:
    return {
        "question_id": question_id,
        "full": _envelope("full", question_id, valid=valid),
        "lite": _envelope("lite", question_id, valid=valid),
    }


def test_blind_plan_is_reproducible_and_hides_system_identity():
    first = create_blind_plan(("q01", "q02", "q03"), seed=17)
    second = create_blind_plan(("q01", "q02", "q03"), seed=17)

    assert first == second
    assert set(first["question_order"]) == {"q01", "q02", "q03"}
    assert all(
        value["full_label"] != value["lite_label"]
        and {value["full_label"], value["lite_label"]} == {"system-a", "system-b"}
        for value in first["mapping"].values()
    )


def test_pair_recorder_writes_raw_blind_and_resumable_artifacts(tmp_path):
    recorder = ResumablePairRecorder(
        tmp_path,
        identity={"snapshot_id": "C:/snapshot.db", "corpus_manifest": "a" * 64},
        contract_id="newsroom-lite-20q-v1",
        corpus_cutoff="2026-08-25T00:00:00Z",
        question_ids=("q01", "q02"),
        blind_seed=17,
    )

    state = recorder.record_pair(
        _pair("q01"),
        latency_ms=12,
        actual_cost_usd={"full": 0.0, "lite": 0.0},
    )
    assert state["status"] == "partial"
    assert state["scoring_started"] is False
    assert state["identities_revealed"] is False

    resumed = ResumablePairRecorder(
        tmp_path,
        identity={"snapshot_id": "C:/snapshot.db", "corpus_manifest": "a" * 64},
        contract_id="newsroom-lite-20q-v1",
        corpus_cutoff="2026-08-25T00:00:00Z",
        question_ids=("q01", "q02"),
        blind_seed=17,
    )
    assert resumed.completed_question_ids == ("q01",)
    resumed.record_pair(_pair("q01"), latency_ms=99, actual_cost_usd={"full": 0.0, "lite": 0.0})
    resumed.record_pair(_pair("q02"), latency_ms=13, actual_cost_usd={"full": 0.0, "lite": 0.0})
    assert resumed.status == "complete"

    blind_text = (tmp_path / "blind-answers.jsonl").read_text(encoding="utf-8")
    assert "effective_provider" not in blind_text
    assert '"blind_label"' in blind_text
    raw = [json.loads(line) for line in (tmp_path / "raw-envelopes.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(raw) == 2
    assert raw[0]["full_execution"]["requested_provider"] == "openai"
    assert raw[0]["full_execution"]["effective_model"] == "gpt-4o-mini"
    assert raw[0]["full_execution"]["latency_ms"] == 12
    assert raw[0]["full_execution"]["actual_cost_usd"] == 0.0
    assert raw[0]["full_execution"]["execution_validity"]["valid"] is True


def test_pair_recorder_fails_closed_and_preserves_invalid_attempt(tmp_path):
    recorder = ResumablePairRecorder(
        tmp_path,
        identity={"snapshot_id": "C:/snapshot.db", "corpus_manifest": "a" * 64},
        contract_id="newsroom-lite-20q-v1",
        corpus_cutoff="2026-08-25T00:00:00Z",
        question_ids=("q01",),
    )

    with pytest.raises(Phase29ProtocolError, match="not scoreable"):
        recorder.record_pair(_pair("q01", valid=False), latency_ms=12)
    assert recorder.status == "invalid"
    assert len(recorder._state["attempts"]) == 1
    assert (tmp_path / "blind-answers.jsonl").read_text(encoding="utf-8") == ""


def test_snapshot_manifest_records_cutoff_eligibility(tmp_path):
    db = tmp_path / "snapshot.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE documents (id TEXT PRIMARY KEY, source_id TEXT, published_at TEXT);
        CREATE TABLE document_versions (
            id TEXT PRIMARY KEY,
            document_id TEXT,
            retrieved_at TEXT,
            content_hash TEXT
        );
        INSERT INTO documents VALUES ('doc-1', 'src-1', NULL);
        INSERT INTO documents VALUES ('doc-2', 'src-1', NULL);
        INSERT INTO document_versions VALUES ('dv-1', 'doc-1', '2026-08-20T00:00:00Z', 'a');
        INSERT INTO document_versions VALUES ('dv-2', 'doc-2', '2026-08-26T00:00:00Z', 'b');
        """
    )
    conn.commit()
    conn.close()

    result = snapshot_manifest(
        db,
        manifest_hash="b" * 64,
        cutoff="2026-08-25T00:00:00Z",
    )
    assert result["eligible_document_version_ids"] == ["dv-1"]
    assert result["excluded_post_cutoff_document_version_ids"] == ["dv-2"]
