"""Reproducible Phase 26 structured-retrieval benchmark.

The fixture is intentionally small and uses the same domain services as the
application.  It records enough cases to decide whether aliases + typed SQL /
FTS retrieval are sufficient before adding derivative vector infrastructure.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from newsroom.domain import CoreService
from newsroom.evidence import EvidenceService
from newsroom.knowledge import KnowledgeService
from newsroom.migrations import apply_migrations
from newsroom.research_questions import ResearchQuestionService
from newsroom.workbench import SearchService


def _fixture(path: Path) -> dict[str, str]:
    apply_migrations(path)
    core = CoreService(path)
    source = core.create_source({"name": "Benchmark Gazette", "slug": "benchmark-gazette", "source_kind": "official", "default_quality": "primary"})
    document = core.create_document({"source_id": source["id"], "canonical_url": "https://benchmark.invalid/aaro", "title": "AARO hearing report"})
    ledger = EvidenceService(path)
    version = ledger.create_document_version(document["id"], {"content_hash": "phase26-benchmark", "content_kind": "excerpt"})
    story = core.create_story({"headline": "AARO hearing changes disclosure policy"})
    evidence = ledger.create_evidence_span(version["id"], {"excerpt": "AARO confirmed the 2026 disclosure policy during the hearing."})
    claim = ledger.create_claim(story["id"], {"proposition": "AARO confirmed the 2026 disclosure policy", "importance": "major"})
    ledger.link_claim_evidence(claim["id"], {"evidence_span_id": evidence["id"], "relationship": "supports"})
    entity = KnowledgeService(path).create_entity({"canonical_name": "All-domain Anomaly Resolution Office", "entity_type": "agency", "aliases": [{"alias": "AARO", "alias_type": "acronym"}]})
    knowledge = KnowledgeService(path)
    knowledge.link_claim_entity(claim["id"], entity["id"], role="subject")
    question = ResearchQuestionService(path).create({"question": "What did AARO confirm about disclosure?"})
    knowledge.link_research_question_entity(question["id"], entity["id"])
    tag = knowledge.create_tag({"name": "Government statement", "namespace": "benchmark", "tag_type": "smart"})
    knowledge.assign_tag(tag["id"], "entity", entity["id"], origin="deterministic")
    return {"source": source["id"], "document": document["id"], "version": version["id"], "story": story["id"], "evidence": evidence["id"], "claim": claim["id"], "entity": entity["id"], "question": question["id"]}


def run_benchmark() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="newsroom-phase26-benchmark-") as directory:
        path = Path(directory) / "benchmark.db"
        ids = _fixture(path)
        search = SearchService(path)
        cases = [
            ("exact Entity lookup", "All-domain Anomaly Resolution Office", "entity", ids["entity"]),
            ("alias lookup", "AARO", "entity", ids["entity"]),
            ("acronym lookup", "AARO hearing", "entity", ids["entity"]),
            ("Claim phrase lookup", "confirmed 2026 disclosure policy", "claim", ids["claim"]),
            ("Story lookup", "AARO hearing changes", "story", ids["story"]),
            ("Research Question lookup", "What did AARO confirm", "question", ids["question"]),
            ("evidence question", "confirmed policy hearing", "evidence", ids["evidence"]),
            ("contradiction question", "disclosure policy", "claim", ids["claim"]),
            ("what-changed question", "changes disclosure policy", "story", ids["story"]),
            ("date-bounded lookup", "2026 disclosure", "claim", ids["claim"]),
            ("cross-object lookup", "AARO disclosure", "entity", ids["entity"]),
        ]
        results = []
        started = time.perf_counter()
        for name, query, expected_type, expected_id in cases:
            case_started = time.perf_counter()
            response = search.retrieve_typed(query, max_results=5)
            top = response["items"][:5]
            hit = any(item["entity_type"] == expected_type and item["entity_id"] == expected_id for item in top)
            results.append({"name": name, "query": query, "expected": f"{expected_type}:{expected_id}", "hit_at_5": hit, "top": [f"{item['entity_type']}:{item['entity_id']}" for item in top], "match_reasons": [item.get("match_reason") for item in top], "latency_ms": round((time.perf_counter() - case_started) * 1000, 3)})
        passed = sum(1 for result in results if result["hit_at_5"])
        return {"cases": len(results), "passed": passed, "hit_at_5": round(passed / len(results), 4), "false_positive_cases": sum(1 for result in results if result["top"] and not result["hit_at_5"]), "latency_ms": round((time.perf_counter() - started) * 1000, 3), "max_results": 5, "vector_retrieval_introduced": False, "results": results}


if __name__ == "__main__":
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
