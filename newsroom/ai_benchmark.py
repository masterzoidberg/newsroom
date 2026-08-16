"""Reproducible, offline benchmark for the Phase 05 capability defaults."""
from __future__ import annotations

import argparse
import json
from typing import Any

from .ai import (
    ClaimDraft,
    LocalEmbeddingProvider,
    LocalEntailmentProvider,
    LocalExtractionProvider,
    LocalRelevanceProvider,
    LocalRerankerProvider,
    LocalSynthesisProvider,
)


def _candidate(name: str, passed: int, total: int, limitation: str) -> dict[str, Any]:
    return {
        "name": name,
        "cases_passed": passed,
        "case_count": total,
        "score": round(passed / total, 6) if total else 0.0,
        "limitation": limitation,
    }


def run_benchmark() -> dict[str, Any]:
    """Run fixed, network-free capability cases and return JSON-safe results."""
    embedding = LocalEmbeddingProvider()
    embedding_cases = [
        embedding.embed("Acme Atlas").vector == embedding.embed("Acme Atlas").vector,
        len(embedding.embed("Acme Atlas").vector) == 32,
    ]

    reranker = LocalRerankerProvider()
    reranker_cases = [
        reranker.rerank("Acme Atlas", "Acme launched Atlas").score > reranker.rerank("Acme Atlas", "Weather report").score,
        reranker.rerank("Acme Atlas", "Acme launched Atlas").confidence >= 0.5,
    ]

    entailment = LocalEntailmentProvider()
    entailment_cases = [
        entailment.assess("Acme launched Atlas", "Acme launched Atlas today.").relationship == "entails",
        entailment.assess("Acme launched Atlas", "Acme launched Atlas; correction: not correct.").relationship == "contradicts",
    ]

    relevance = LocalRelevanceProvider()
    relevance_cases = [
        relevance.classify("Acme launched Atlas", ["Acme", "Atlas"]).relevant is True,
        relevance.classify("Weather report", ["Acme", "Atlas"]).relevant is False,
    ]

    extraction = LocalExtractionProvider().extract(
        "Atlas update",
        "Acme launched Atlas. The product is available today.",
    )
    extraction_cases = [
        len(extraction.claims) == 2,
        extraction.claims[0].evidence[0].excerpt == "Acme launched Atlas.",
    ]

    synthesis = LocalSynthesisProvider().synthesize(
        "Atlas update",
        [ClaimDraft(proposition="Acme launched Atlas."), ClaimDraft(proposition="The product is available today.")],
    )
    synthesis_cases = [
        synthesis.claim_indexes == [0, 1],
        all(set(item.claim_indexes) <= {0, 1} for item in synthesis.propositions),
    ]

    task_cases: dict[str, tuple[str, list[bool], str]] = {
        "embedding": ("local-token-hash-v1", embedding_cases, "Hash vectors are lexical, not semantic."),
        "reranker": ("local-token-overlap-v1", reranker_cases, "Scores do not understand negation or entities."),
        "entailment": ("local-token-entailment-v1", entailment_cases, "Contradiction detection uses a small marker vocabulary."),
        "relevance": ("local-scope-overlap-v1", relevance_cases, "Multi-word scope terms are treated as independent tokens."),
        "extraction": ("local-sentence-extraction-v1", extraction_cases, "Sentence boundaries are heuristic and require later review."),
        "synthesis": ("local-claim-join-v1", synthesis_cases, "Synthesis is templated and intentionally not stylistically rich."),
    }
    tasks: dict[str, Any] = {}
    for capability, (selected, cases, limitation) in task_cases.items():
        passed = sum(1 for case in cases if case)
        total = len(cases)
        tasks[capability] = {
            "selected_default": selected,
            "candidates": [
                _candidate("deterministic-reference-v1", total, total, "Test-only reference; not a runtime provider."),
                _candidate(selected, passed, total, limitation),
            ],
        }
    return {
        "benchmark": "newsroom-phase05-ai",
        "schema_version": 1,
        "network": False,
        "tasks": tasks,
    }


def benchmark_json(result: dict[str, Any] | None = None) -> str:
    return json.dumps(result if result is not None else run_benchmark(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    argparse.ArgumentParser(description="Run the offline Newsroom AI benchmark").parse_args()
    print(benchmark_json(), end="")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["run_benchmark", "benchmark_json", "main"]
