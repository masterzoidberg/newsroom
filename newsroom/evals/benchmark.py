"""Contract-bound Full/Lite benchmark runners and pairing checks."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..ask import AskService
from .benchmark_contract import compare_effective_conditions, verify_execution
from .lite import (
    LiteHarness,
    LiteBenchmarkError,
    _model_config,
    _require_frozen_binding,
    load_contract,
)


class PairedBenchmarkError(ValueError):
    """The Full and Lite runners are not evaluating the same contract."""

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.details = dict(details or {})


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


def _full_effective_config(answer: Mapping[str, Any]) -> dict[str, Any]:
    """Translate AskService's recorded route into honest benchmark metadata."""
    route = str(answer.get("provider_route") or "execution_unavailable")
    if route.startswith("local"):
        provider = "local"
        model = None
    else:
        provider = None
        model = None
    raw_retrieval = answer.get("retrieval")
    retrieval: Mapping[str, Any] = raw_retrieval if isinstance(raw_retrieval, Mapping) else {}
    return {
        "effective_provider": provider,
        "effective_model": model,
        "provider_route": route,
        "fallback_used": route.endswith("_fallback"),
        "effective_temperature": None,
        "deterministic": None,
        "effective_prompt_version": None,
        "effective_context_budget_tokens": retrieval.get("context_budget_tokens"),
        "effective_retrieval_limit": None,
        "effective_citation_limit": None,
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
        )
        return self._envelope(
            question_id,
            question,
            answer,
            effective_config=_full_effective_config(answer),
            test_double=False,
        )

    def run_with_test_double(
        self,
        question_id: str,
        synthesize: Callable[[str], Mapping[str, Any]],
        *,
        effective_config: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Run a callable only through the explicit deterministic test seam."""
        if question_id not in self.questions:
            raise LiteBenchmarkError(f"unknown Full question: {question_id}")
        if not isinstance(effective_config, Mapping):
            raise LiteBenchmarkError("Full test doubles must provide explicit effective execution metadata")
        question = self.questions[question_id]["question"]
        answer = dict(synthesize(question))
        return self._envelope(
            question_id,
            question,
            answer,
            effective_config=effective_config,
            test_double=True,
        )

    def _envelope(
        self,
        question_id: str,
        question: str,
        answer: Mapping[str, Any],
        *,
        effective_config: Mapping[str, Any],
        test_double: bool,
    ) -> dict[str, Any]:
        return {
            "runner": "full",
            "adapter": "explicit_test_double" if test_double else "newsroom.ask.AskService",
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
            "requested_config": dict(self.model_config),
            "effective_config": dict(effective_config),
            "contract_verification": verify_execution(self.model_config, effective_config),
            "blinding": dict(self.contract["blinding"]),
            "scoring": dict(self.contract["scoring"]),
            "test_double": test_double,
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

    def _validate_execution_pair(
        self,
        full_result: Mapping[str, Any],
        lite_result: Mapping[str, Any],
    ) -> None:
        full_verification = full_result.get("contract_verification")
        lite_verification = lite_result.get("contract_verification")
        if not isinstance(full_verification, Mapping) or not full_verification.get("valid"):
            raise PairedBenchmarkError(
                "paired benchmark contract is not satisfied by Full execution",
                details={"full": dict(full_result), "lite": dict(lite_result)},
            )
        if not isinstance(lite_verification, Mapping) or not lite_verification.get("valid"):
            raise PairedBenchmarkError(
                "paired benchmark contract is not satisfied by Lite execution",
                details={"full": dict(full_result), "lite": dict(lite_result)},
            )
        full_effective = full_result.get("effective_config")
        lite_effective = lite_result.get("effective_config")
        if not isinstance(full_effective, Mapping) or not isinstance(lite_effective, Mapping):
            raise PairedBenchmarkError("paired benchmark effective execution metadata is unavailable")
        mismatches = compare_effective_conditions(full_effective, lite_effective)
        if mismatches:
            raise PairedBenchmarkError(
                f"paired benchmark effective contract mismatch: {', '.join(mismatches)}",
                details={
                    "mismatch_fields": mismatches,
                    "full_effective_config": dict(full_effective),
                    "lite_effective_config": dict(lite_effective),
                },
            )

    def run(
        self,
        question_ids: Sequence[str] | None = None,
        *,
        lite_test_double: Callable[[str, Sequence[Any]], Mapping[str, Any]] | None = None,
        lite_effective_config: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self.validate_identity(self.full.identity, self.lite.identity)
        selected = tuple(question_ids or sorted(self.full.questions))
        results: list[dict[str, Any]] = []
        for question_id in selected:
            full_result = self.full.run(question_id)
            if lite_test_double is not None:
                if not isinstance(lite_effective_config, Mapping):
                    raise PairedBenchmarkError(
                        "Lite test doubles require explicit effective execution metadata"
                    )
                lite_result = self.lite.run_with_test_double(
                    question_id,
                    lite_test_double,
                    effective_config=lite_effective_config,
                )
            else:
                lite_result = self.lite.run(question_id)
            self._validate_execution_pair(full_result, lite_result)
            results.append({"question_id": question_id, "full": full_result, "lite": lite_result})
        return results

    def run_with_test_doubles(
        self,
        question_ids: Sequence[str] | None = None,
        *,
        full_synthesize: Callable[[str], Mapping[str, Any]],
        lite_synthesize: Callable[[str, Sequence[Any]], Mapping[str, Any]],
        full_effective_config: Mapping[str, Any],
        lite_effective_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        """Run both sides through explicit deterministic test seams."""
        self.validate_identity(self.full.identity, self.lite.identity)
        selected = tuple(question_ids or sorted(self.full.questions))
        results: list[dict[str, Any]] = []
        for question_id in selected:
            full_result = self.full.run_with_test_double(
                question_id,
                full_synthesize,
                effective_config=full_effective_config,
            )
            lite_result = self.lite.run_with_test_double(
                question_id,
                lite_synthesize,
                effective_config=lite_effective_config,
            )
            self._validate_execution_pair(full_result, lite_result)
            results.append({"question_id": question_id, "full": full_result, "lite": lite_result})
        return results


__all__ = [
    "FullBenchmarkRunner",
    "PairedBenchmarkError",
    "PairedBenchmarkOrchestrator",
]
