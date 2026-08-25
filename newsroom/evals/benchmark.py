"""Contract-bound Full/Lite benchmark runners and pairing checks."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..ask import AskService
from .lite import (
    LiteHarness,
    LiteBenchmarkError,
    _model_config,
    _require_frozen_binding,
    load_contract,
)


class PairedBenchmarkError(ValueError):
    """The Full and Lite runners are not evaluating the same contract."""


def _identity(contract: Mapping[str, Any], binding: Mapping[str, str], model_config: Mapping[str, Any]) -> dict[str, Any]:
    questions = contract["questions"]
    return {
        "snapshot_id": binding["snapshot_path"],
        "corpus_manifest": binding["manifest_hash"],
        "question_contract": {
            "contract_id": contract["contract_id"],
            "question_ids": tuple(sorted(str(item["id"]) for item in questions)),
        },
        "model_config": dict(model_config),
        "blinding": dict(contract["blinding"]),
    }


class FullBenchmarkRunner:
    """Run the frozen question set through the real Ask Newsroom service."""

    def __init__(self, db_path: str | Path, *, contract: Mapping[str, Any] | None = None):
        self.db_path = Path(db_path).resolve()
        self.contract = contract or load_contract()
        self.binding = _require_frozen_binding(self.db_path, self.contract)
        self.questions = {item["id"]: item for item in self.contract["questions"]}
        self.model_config = _model_config(self.contract)
        self.identity = _identity(self.contract, self.binding, self.model_config)
        self.ask = AskService(self.db_path)

    def run(self, question_id: str) -> dict[str, Any]:
        if question_id not in self.questions:
            raise LiteBenchmarkError(f"unknown Full question: {question_id}")
        question = self.questions[question_id]["question"]
        conversation = self.ask.create_conversation()
        answer = self.ask.ask(
            conversation["id"],
            question,
            context_budget=int(self.model_config["context_budget_tokens"]),
            provider_mode="local",
            cost_cap_usd=0.0,
        )
        return {
            "runner": "full",
            "adapter": "newsroom.ask.AskService",
            "contract_id": self.contract["contract_id"],
            "question_id": question_id,
            "opaque_question_id": f"q-{question_id}",
            "question": question,
            "answer": answer,
            "retrieved_document_ids": [item["document_id"] for item in answer.get("citations", []) if item.get("document_id")],
            "cited_document_ids": [item["document_id"] for item in answer.get("citations", []) if item.get("document_id")],
            "scope": "full_newsroom",
            "corpus_cutoff": self.contract["corpus_cutoff"],
            "frozen_corpus": self.binding,
            "model_config": dict(self.model_config),
            "blinding": dict(self.contract["blinding"]),
            "scoring": dict(self.contract["scoring"]),
            "test_double": False,
        }


class PairedBenchmarkOrchestrator:
    """Run Full and Lite against one immutable identity and question order."""

    _IDENTITY_KEYS = ("snapshot_id", "corpus_manifest", "question_contract", "model_config", "blinding")

    def __init__(self, full: FullBenchmarkRunner, lite: LiteHarness):
        self.full = full
        self.lite = lite
        self.validate_identity(full.identity, lite.identity)

    def validate_identity(self, full_identity: Mapping[str, Any], lite_identity: Mapping[str, Any]) -> None:
        for key in self._IDENTITY_KEYS:
            if full_identity.get(key) != lite_identity.get(key):
                raise PairedBenchmarkError(f"paired benchmark {key} mismatch")

    def run(
        self,
        question_ids: Sequence[str] | None = None,
        *,
        lite_test_double: Callable[[str, Sequence[Any]], Mapping[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        self.validate_identity(self.full.identity, self.lite.identity)
        selected = tuple(question_ids or sorted(self.full.questions))
        results: list[dict[str, Any]] = []
        for question_id in selected:
            full_result = self.full.run(question_id)
            lite_result = (
                self.lite.run_with_test_double(question_id, lite_test_double)
                if lite_test_double is not None
                else self.lite.run(question_id)
            )
            results.append({"question_id": question_id, "full": full_result, "lite": lite_result})
        return results


__all__ = [
    "FullBenchmarkRunner",
    "PairedBenchmarkError",
    "PairedBenchmarkOrchestrator",
]
