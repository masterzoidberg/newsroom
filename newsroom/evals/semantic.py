"""Executable semantic regression cases for the permanent evaluation corpus."""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..ask import AskService
from ..domain import CoreService
from ..evidence import EvidenceService
from ..migrations import apply_migrations
from ..source_robustness import SourceRobustnessService
from ..story_corrections import StoryCorrectionService
from ..story_evolution import StoryEvolutionService
from ..research_questions import ResearchQuestionService
from .corpus import fixtures_dir, load_all_cases, load_case
from .metrics import ScoreResult, score
from .prediction import validate_prediction
from .replay import ReplayResult, load_fixture
from .schema import EvaluationCase


SEMANTIC_CASE_IDS = (
    "ask-sufficiency-refusal",
    "conservative-absence",
    "late-dependency-discovery",
    "single-dependency-group-support",
    "late-story-correction",
    "late-story-split",
    "retracted-evidence",
    "silent-document-edit-version",
)


@dataclass(frozen=True)
class SemanticAssertionResult:
    case_id: str
    assertion_id: str
    subsystem: str
    actual_service: str
    observed: Any
    expected: Any
    passed: bool


@dataclass(frozen=True)
class SemanticCaseResult:
    case_id: str
    score: ScoreResult
    assertions: tuple[SemanticAssertionResult, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "score": self.score.as_dict(),
            "assertions": [
                {
                    "case_id": item.case_id,
                    "assertion_id": item.assertion_id,
                    "subsystem": item.subsystem,
                    "actual_service": item.actual_service,
                    "observed": item.observed,
                    "expected": item.expected,
                    "result": "pass" if item.passed else "fail",
                }
                for item in self.assertions
            ],
        }


@dataclass(frozen=True)
class _Observation:
    subsystem: str
    actual_service: str
    value: Any


class _SemanticWorld:
    def __init__(self, case: EvaluationCase, fixture: ReplayResult, root: Path):
        self.case = case
        self.fixture = fixture
        self.db_path = root / "semantic.sqlite"
        apply_migrations(self.db_path)
        self.core = CoreService(self.db_path)
        self.evidence = EvidenceService(self.db_path)
        self.documents: dict[str, str] = {}
        self.versions: dict[str, str] = {}
        self.spans: dict[str, str] = {}
        self._seed_documents()

    def _seed_documents(self) -> None:
        candidates = {candidate.candidate_id: candidate for candidate in self.case.candidates}
        by_url: dict[str, tuple[str, str]] = {}
        for index, document in enumerate(self.fixture.documents):
            candidate = candidates[document.candidate_id]
            identity = by_url.get(document.normalized_url)
            if identity is None:
                source = self.core.create_source(
                    {
                        "name": document.publisher or candidate.source or f"Semantic source {index + 1}",
                        "slug": f"semantic-{index + 1}",
                        "source_kind": "official" if candidate.source == "official" else "web",
                    }
                )
                created = self.core.create_document(
                    {
                        "source_id": source["id"],
                        "canonical_url": document.canonical_url,
                        "title": document.title,
                    }
                )
                identity = (source["id"], created["id"])
                by_url[document.normalized_url] = identity
            _source_id, document_id = identity
            self.documents[document.candidate_id] = document_id
            version = self.evidence.create_document_version(
                document_id,
                {
                    "content_hash": candidate.content_hash or document.content_hash,
                    "content_kind": "excerpt",
                    "retrieved_at": document.retrieved_at or f"2026-08-25T00:00:0{index}Z",
                    "normalized_json": {"text": document.excerpt or ""},
                },
            )
            self.versions[document.candidate_id] = version["id"]
            span = self.evidence.create_evidence_span(
                version["id"],
                {"excerpt": document.excerpt or document.title},
            )
            self.spans[document.candidate_id] = span["id"]

    def claim_for(self, story_id: str, proposition: str) -> dict[str, Any]:
        return self.evidence.create_claim(
            story_id,
            {"proposition": proposition, "importance": "major"},
        )

    def support_claim(self, claim_id: str, candidate_ids: list[str]) -> dict[str, Any]:
        for candidate_id in candidate_ids:
            self.evidence.link_claim_evidence(
                claim_id,
                {"evidence_span_id": self.spans[candidate_id], "relationship": "supports"},
            )
        self.evidence.set_claim_state(claim_id, "supported", "semantic fixture support")
        self.evidence.accept_claim(claim_id)
        return self.evidence.get_claim(claim_id)


def _fixture_for(case_id: str) -> ReplayResult:
    path = fixtures_dir() / f"{case_id}.json"
    if not path.is_file():
        raise ValueError(f"semantic fixture not found: {path}")
    fixture = load_fixture(str(path))
    if fixture.case_id != case_id:
        raise ValueError(f"semantic fixture {path.name} is bound to {fixture.case_id!r}")
    return fixture


def _ask_observation(world: _SemanticWorld, *, conservative: bool) -> _Observation:
    prompt = (
        "Can the current Newsroom record establish that no additional announcement exists?"
        if conservative
        else "What answer is established by the current research question?"
    )
    question = ResearchQuestionService(world.db_path).create(
        {"question": prompt, "origin_type": "user", "search_attempt_budget": 1}
    )
    ask = AskService(world.db_path)
    conversation = ask.create_conversation(scope_type="question", scope_id=question["id"])
    result = ask.ask(conversation["id"], prompt)
    if conservative:
        classifications = {item.get("classification") for item in result.get("statements", [])}
        value = (
            "uncertainty_or_refusal"
            if result.get("status") == "refused" or ("uncertainty" in classifications and "fact" not in classifications)
            else "unsupported_answer"
        )
        return _Observation("Ask", "newsroom.ask.AskService.ask", value)
    return _Observation("Ask", "newsroom.ask.AskService.ask", result.get("refusal_code") or result.get("status"))


def _dependency_observation(world: _SemanticWorld, *, late_edge: bool, single_group: bool) -> _Observation:
    story = world.core.create_story({"headline": world.case.title})
    proposition = world.case.gold_claims[0].proposition
    claim = world.claim_for(story["id"], proposition)
    candidate_ids = [candidate.candidate_id for candidate in world.case.candidates]
    world.support_claim(claim["id"], candidate_ids)
    if single_group:
        StoryEvolutionService(world.db_path).link_lineage(
            world.documents["rewrite-a"], world.documents["primary"], "rewritten_from", rationale="same source text"
        )
        StoryEvolutionService(world.db_path).link_lineage(
            world.documents["rewrite-b"], world.documents["primary"], "rewritten_from", rationale="same source text"
        )
    elif late_edge:
        SourceRobustnessService(world.db_path).evidence_summary("claim", claim["id"])
        StoryEvolutionService(world.db_path).link_lineage(
            world.documents["derivative"], world.documents["primary"], "rewritten_from", rationale="late lineage discovery"
        )
    summary = SourceRobustnessService(world.db_path).evidence_summary("claim", claim["id"])
    if single_group:
        return _Observation(
            "Evidence Quality",
            "newsroom.source_robustness.SourceRobustnessService.evidence_summary",
            summary["dependency_group_count"] > 1,
        )
    return _Observation(
        "SourceRobustness",
        "newsroom.source_robustness.SourceRobustnessService.evidence_summary",
        summary["dependency_group_count"],
    )


def _correction_observation(world: _SemanticWorld) -> _Observation:
    wrong = world.core.create_story({"headline": "Initial story"})
    canonical = world.core.create_story({"headline": "Canonical story"})
    claim = world.claim_for(wrong["id"], world.case.gold_claims[0].proposition)
    StoryCorrectionService(world.db_path).reassign_claim(
        claim["id"], canonical["id"], actor="semantic-runner", reason="late correction"
    )
    current = world.evidence.get_claim(claim["id"])
    history = StoryCorrectionService(world.db_path).correction_history(canonical["id"])
    value = (
        "corrected_current_with_history"
        if current["story_id"] == canonical["id"] and history
        else "uncorrected_or_missing_history"
    )
    return _Observation("Story correction", "newsroom.story_corrections.StoryCorrectionService.reassign_claim", value)


def _split_observation(world: _SemanticWorld) -> _Observation:
    source = world.core.create_story({"headline": "Merged similar events"})
    claims = [
        world.claim_for(source["id"], claim.proposition)
        for claim in world.case.gold_claims
    ]
    result = StoryCorrectionService(world.db_path).split_story(
        source["id"], [[claims[0]["id"]], [claims[1]["id"]]], actor="semantic-runner", reason="late split"
    )
    current_source = world.core.get_story(source["id"], include_deleted=True)
    lineage = StoryCorrectionService(world.db_path).lineage(source["id"])
    history = StoryCorrectionService(world.db_path).correction_history(source["id"])
    value = (
        "split_current_with_history"
        if current_source["lifecycle"] == "archived"
        and len(result["children"]) == 2
        and len(lineage["outgoing"]) == 2
        and history
        else "unsplit_or_missing_history"
    )
    return _Observation("Story split", "newsroom.story_corrections.StoryCorrectionService.split_story", value)


def _retracted_observation(world: _SemanticWorld) -> _Observation:
    story = world.core.create_story({"headline": "Correction story"})
    claim = world.claim_for(story["id"], world.case.gold_claims[0].proposition)
    candidate_id = world.case.candidates[0].candidate_id
    world.evidence.link_claim_evidence(
        claim["id"],
        {"evidence_span_id": world.spans[candidate_id], "relationship": "contradicts"},
    )
    current = world.evidence.set_claim_state(claim["id"], "disputed", "source correction")
    return _Observation("Claim/Evidence", "newsroom.evidence.EvidenceService.set_claim_state", current["state"])


def _silent_edit_observation(world: _SemanticWorld) -> _Observation:
    candidate_ids = [candidate.candidate_id for candidate in world.case.candidates]
    document_id = world.documents[candidate_ids[0]]
    versions = world.evidence.list_document_versions(document_id)["items"]
    span_versions = {world.evidence.get_evidence_span(world.spans[candidate_id])["document_version"]["id"] for candidate_id in candidate_ids}
    distinct_hashes = {item["content_hash"] for item in versions}
    value = (
        "distinct_versions_distinct_hashes"
        if len({item["id"] for item in versions}) == 2
        and len(distinct_hashes) == 2
        and len(span_versions) == 2
        else "versions_or_provenance_collapsed"
    )
    return _Observation(
        "DocumentVersion provenance",
        "newsroom.evidence.EvidenceService.create_document_version/create_evidence_span",
        value,
    )


_EXECUTORS: dict[str, Callable[[_SemanticWorld], _Observation]] = {
    "ask-sufficiency-refusal": lambda world: _ask_observation(world, conservative=False),
    "conservative-absence": lambda world: _ask_observation(world, conservative=True),
    "late-dependency-discovery": lambda world: _dependency_observation(world, late_edge=True, single_group=False),
    "single-dependency-group-support": lambda world: _dependency_observation(world, late_edge=False, single_group=True),
    "late-story-correction": _correction_observation,
    "late-story-split": _split_observation,
    "retracted-evidence": _retracted_observation,
    "silent-document-edit-version": _silent_edit_observation,
}


class SemanticCaseRunner:
    """Run a semantic case against a fresh deterministic Newsroom database."""

    def run(self, case_id: str) -> SemanticCaseResult:
        case = load_case(case_id)
        executor = _EXECUTORS.get(case_id)
        if executor is None:
            raise ValueError(f"no semantic executor registered for {case_id}")
        fixture = _fixture_for(case_id)
        with tempfile.TemporaryDirectory(prefix="newsroom-semantic-") as directory:
            world = _SemanticWorld(case, fixture, Path(directory))
            observation = executor(world)
        observations = {assertion.assertion_id: observation.value for assertion in case.semantic_assertions}
        prediction = validate_prediction(
            {
                "prediction_id": f"newsroom-semantic-{case_id}",
                "case_id": case_id,
                "system": "newsroom-semantic",
                "story_groups": [
                    {"story_id": f"semantic-story-{candidate.candidate_id}", "candidate_ids": [candidate.candidate_id]}
                    for candidate in case.candidates
                ],
                "semantic_results": observations,
            },
            case=case,
        )
        result = score(case, prediction)
        details = tuple(
            SemanticAssertionResult(
                case_id=case_id,
                assertion_id=assertion.assertion_id,
                subsystem=observation.subsystem,
                actual_service=observation.actual_service,
                observed=observations[assertion.assertion_id],
                expected=assertion.expected,
                passed=observations[assertion.assertion_id] == assertion.expected,
            )
            for assertion in case.semantic_assertions
        )
        return SemanticCaseResult(case_id=case_id, score=result, assertions=details)


def run_semantic_cases(case_ids: tuple[str, ...] = SEMANTIC_CASE_IDS) -> list[ScoreResult]:
    return [SemanticCaseRunner().run(case_id).score for case_id in case_ids]


def run_normal_evaluation() -> list[ScoreResult]:
    """Run the ordinary v1 baseline plus the executable semantic cases."""
    from .baseline import load_v1_export, run_baseline

    cases = load_all_cases()
    return [*run_baseline(cases, load_v1_export()), *run_semantic_cases()]


__all__ = [
    "SEMANTIC_CASE_IDS",
    "SemanticAssertionResult",
    "SemanticCaseResult",
    "SemanticCaseRunner",
    "run_normal_evaluation",
    "run_semantic_cases",
]
