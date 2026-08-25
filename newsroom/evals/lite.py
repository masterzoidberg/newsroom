"""Frozen, document-only Lite comparator built on the existing FTS harness.

Lite is deliberately an execution contract, not a convenience wrapper around
an arbitrary database and callable. A run must bind to an immutable SQLite
snapshot and an adapter whose provider/model/prompt settings exactly match the
contract. Test doubles remain available, but only through an explicit test
flag so they cannot be mistaken for benchmark results.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .. import storage
from ..workbench import SearchService


class LiteBenchmarkError(ValueError):
    """The Lite benchmark contract or its runtime binding is invalid."""


def contract_path() -> Path:
    return Path(__file__).resolve().parents[2] / "evals" / "lite" / "20q_contract.json"


def _validate_contract(data: Mapping[str, Any]) -> dict[str, Any]:
    if data.get("frozen") is not True:
        raise LiteBenchmarkError("Lite benchmark requires a frozen contract")
    required = {
        "contract_id",
        "corpus_cutoff",
        "provider",
        "model",
        "temperature",
        "prompt_version",
        "context_budget_tokens",
        "retrieval_limit",
        "retrieval",
        "scoring",
        "blinding",
        "questions",
    }
    missing = sorted(required - set(data))
    if missing:
        raise LiteBenchmarkError(f"Lite contract missing required fields: {', '.join(missing)}")

    questions = data["questions"]
    if not isinstance(questions, list) or len(questions) != 20:
        raise LiteBenchmarkError("Lite benchmark requires exactly 20 questions")
    if not all(isinstance(item, Mapping) for item in questions):
        raise LiteBenchmarkError("Lite questions must be objects")
    question_ids = {item.get("id") for item in questions if isinstance(item, Mapping)}
    if len(question_ids) != 20 or question_ids != {f"q{index:02d}" for index in range(1, 21)}:
        raise LiteBenchmarkError("Lite questions must be the fixed q01-q20 set")
    expected_categories = {
        "factual": 6,
        "conservative_absence": 4,
        "dependency_corroboration": 4,
        "what_changed": 3,
        "unanswerable": 3,
    }
    counts = {
        key: sum(1 for item in questions if item.get("category") == key)
        for key in expected_categories
    }
    if counts != expected_categories:
        raise LiteBenchmarkError(f"Lite question mix is {counts}, expected {expected_categories}")
    for item in questions:
        if not isinstance(item.get("question"), str) or not item["question"].strip():
            raise LiteBenchmarkError(f"Lite question {item.get('id')!r} has no question text")
        if not isinstance(item.get("case_ids"), list) or not item["case_ids"]:
            raise LiteBenchmarkError(f"Lite question {item.get('id')!r} has no case binding")
    from .corpus import load_case

    for item in questions:
        for case_id in item["case_ids"]:
            try:
                load_case(str(case_id))
            except Exception as exc:
                raise LiteBenchmarkError(
                    f"Lite question {item['id']!r} references unknown case {case_id!r}"
                ) from exc

    retrieval = data["retrieval"]
    if not isinstance(retrieval, Mapping):
        raise LiteBenchmarkError("Lite retrieval settings must be an object")
    if retrieval.get("method") != "sqlite_fts5" or retrieval.get("entity_types") != ["document"]:
        raise LiteBenchmarkError("Lite retrieval must use document-only sqlite_fts5")
    if not isinstance(retrieval.get("citation_limit"), int) or retrieval["citation_limit"] < 1:
        raise LiteBenchmarkError("Lite citation_limit must be a positive integer")
    if not isinstance(data["blinding"], Mapping) or data["blinding"] != {
        "question_order": "shuffle_with_seed",
        "case_ids": "opaque_until_scored",
        "reveal": "after_rubric_scoring",
    }:
        raise LiteBenchmarkError("Lite blinding rules are not the fixed contract rules")
    if not isinstance(data["temperature"], (int, float)) or data["temperature"] != 0.0:
        raise LiteBenchmarkError("Lite temperature must be exactly 0.0")
    if data.get("deterministic") is not True:
        raise LiteBenchmarkError("Lite benchmark must be deterministic")
    return dict(data)


def load_contract(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else contract_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LiteBenchmarkError(f"cannot load Lite contract: {target}") from exc
    if not isinstance(data, Mapping):
        raise LiteBenchmarkError("Lite contract must be a JSON object")
    return _validate_contract(data)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone() is not None


def corpus_manifest(db_path: str | Path) -> str:
    """Hash the authoritative document corpus in a SQLite snapshot."""
    path = Path(db_path).resolve()
    if not path.is_file():
        raise LiteBenchmarkError(f"Lite corpus snapshot does not exist: {path}")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        tables = ("sources", "documents", "document_versions", "evidence_spans")
        if not all(_table_exists(conn, table) for table in tables[:3]):
            raise LiteBenchmarkError("Lite corpus snapshot is missing authoritative document tables")
        payload: dict[str, list[dict[str, Any]]] = {}
        for table in tables:
            if not _table_exists(conn, table):
                continue
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
            payload[table] = [dict(row) for row in rows]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
    finally:
        conn.close()


def frozen_corpus_binding(db_path: str | Path) -> dict[str, str]:
    """Return the identity that a Lite contract must bind to."""
    path = Path(db_path).resolve()
    return {"snapshot_path": str(path), "manifest_hash": corpus_manifest(path)}


def freeze_corpus_snapshot(source_db: str | Path, snapshot_path: str | Path) -> dict[str, str]:
    """Create a SQLite online-backup snapshot and return its binding."""
    destination = Path(snapshot_path).resolve()
    storage.online_backup(destination, source_path=source_db)
    return frozen_corpus_binding(destination)


def bind_contract(contract: Mapping[str, Any], snapshot_path: str | Path) -> dict[str, Any]:
    """Return a contract copy bound to one immutable corpus snapshot."""
    bound = dict(contract)
    bound["frozen_corpus"] = frozen_corpus_binding(snapshot_path)
    return bound


def _require_frozen_binding(db_path: Path, contract: Mapping[str, Any]) -> dict[str, str]:
    binding = contract.get("frozen_corpus")
    if not isinstance(binding, Mapping):
        raise LiteBenchmarkError("Lite run requires a frozen_corpus binding")
    expected_path = binding.get("snapshot_path")
    expected_hash = binding.get("manifest_hash")
    actual_path = str(db_path.resolve())
    if expected_path != actual_path or not isinstance(expected_hash, str) or not expected_hash:
        raise LiteBenchmarkError("Lite database does not match the contract's frozen corpus binding")
    actual_hash = corpus_manifest(db_path)
    if actual_hash != expected_hash:
        raise LiteBenchmarkError("Lite corpus manifest does not match the frozen contract")
    return {"snapshot_path": actual_path, "manifest_hash": actual_hash}


def _model_config(contract: Mapping[str, Any]) -> dict[str, Any]:
    retrieval = contract["retrieval"]
    return {
        "provider": contract["provider"],
        "model": contract["model"],
        "temperature": contract["temperature"],
        "prompt_version": contract["prompt_version"],
        "context_budget_tokens": contract["context_budget_tokens"],
        "retrieval_limit": contract["retrieval_limit"],
        "citation_limit": retrieval["citation_limit"],
    }


def _opaque_label(question_id: str) -> str:
    return f"q-{hashlib.sha256(question_id.encode('utf-8')).hexdigest()[:12]}"


@dataclass(frozen=True)
class LiteDocument:
    citation_id: str
    document_id: str
    title: str
    excerpt: str
    rank: int


class LiteHarness:
    """Retrieve documents and delegate synthesis through the frozen route."""

    def __init__(self, db_path: str | Path, *, contract: Mapping[str, Any] | None = None):
        self.db_path = Path(db_path).resolve()
        self.contract = _validate_contract(contract or load_contract())
        self.binding = _require_frozen_binding(self.db_path, self.contract)
        self.questions = {item["id"]: item for item in self.contract["questions"]}
        self.search = SearchService(self.db_path)

    def retrieve(self, question: str, *, limit: int | None = None) -> list[LiteDocument]:
        retrieval_limit = int(self.contract["retrieval_limit"] if limit is None else limit)
        if retrieval_limit < 1 or retrieval_limit > 20:
            raise LiteBenchmarkError("Lite retrieval limit must be between 1 and 20")
        result = self.search.search(question, entity_types=["document"], page_size=retrieval_limit)
        return [
            LiteDocument(
                citation_id=f"document:{item['entity_id']}",
                document_id=item["entity_id"],
                title=item["title"],
                excerpt=item["snippet"],
                rank=int(item.get("rank") or index + 1),
            )
            for index, item in enumerate(result["items"])
        ]

    def run(
        self,
        question_id: str,
        synthesize: Callable[[str, Sequence[LiteDocument]], Mapping[str, Any]],
        *,
        model_config: Mapping[str, Any] | None = None,
        test_double: bool = False,
    ) -> dict[str, Any]:
        if question_id not in self.questions:
            raise LiteBenchmarkError(f"unknown Lite question: {question_id}")
        expected_config = _model_config(self.contract)
        if test_double:
            effective_config = dict(expected_config)
        else:
            effective_config = dict(model_config or getattr(synthesize, "lite_config", {}))
            if effective_config != expected_config:
                raise LiteBenchmarkError("Lite synthesis route does not match the frozen provider/model contract")
        question = self.questions[question_id]["question"]
        documents = self.retrieve(question)
        answer = dict(synthesize(question, documents))
        answer_id = str(answer.get("answer_id") or "").strip()
        if not answer_id:
            encoded_answer = json.dumps(answer, sort_keys=True, separators=(",", ":"), default=str)
            answer_id = f"answer-{hashlib.sha256(encoded_answer.encode('utf-8')).hexdigest()[:16]}"
        cited_document_ids = answer.get("cited_document_ids", [])
        if not isinstance(cited_document_ids, list):
            cited_document_ids = []
        return {
            "contract_id": self.contract["contract_id"],
            "question_id": question_id,
            "opaque_question_id": _opaque_label(question_id),
            "question": question,
            "documents": [document.__dict__ for document in documents],
            "retrieved_document_ids": [document.document_id for document in documents],
            "cited_document_ids": [str(item) for item in cited_document_ids],
            "answer_id": answer_id,
            "answer": answer,
            "scope": "documents_only",
            "corpus_cutoff": self.contract["corpus_cutoff"],
            "frozen_corpus": self.binding,
            "model_config": effective_config,
            "blinding": dict(self.contract["blinding"]),
            "scoring": dict(self.contract["scoring"]),
            "scoring_version": "lite-scoring-v1",
            "scores": dict(answer.get("scores", {})) if isinstance(answer.get("scores", {}), Mapping) else {},
            "test_double": test_double,
        }


__all__ = [
    "LiteBenchmarkError",
    "LiteDocument",
    "LiteHarness",
    "bind_contract",
    "contract_path",
    "corpus_manifest",
    "freeze_corpus_snapshot",
    "frozen_corpus_binding",
    "load_contract",
]
