"""Provider-neutral local AI capabilities and bounded routing.

The module deliberately keeps provider-specific concerns behind small capability
interfaces. Model-shaped values are validated before they can reach domain
services or the evidence ledger.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from . import storage
from .domain import utc_now


ModelT = TypeVar("ModelT", bound="AIModel")


class AIError(RuntimeError):
    """Base class for safe, attributable AI execution failures."""


class AIValidationError(AIError):
    """A provider returned a value outside the capability contract."""


class AIProviderError(AIError):
    """A provider failed while processing a capability request."""


class AITimeout(AIProviderError):
    """A provider did not return within its configured time limit."""


class AIBudgetExceeded(AIError):
    """A paid escalation was refused by the hard budget."""


class AIDisabled(AIError):
    """No enabled route is available for a capability."""


class AIConfigurationError(AIError):
    """Provider configuration is invalid or incomplete (terminal)."""


class AIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmbeddingOutput(AIModel):
    vector: list[float] = Field(min_length=1, max_length=4096)

    @field_validator("vector")
    @classmethod
    def finite_vector(cls, value: list[float]) -> list[float]:
        if any(not math.isfinite(item) for item in value):
            raise ValueError("embedding vector must contain finite values")
        return value


class RankingOutput(AIModel):
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    signal: str = Field(min_length=1, max_length=200)


class EntailmentOutput(AIModel):
    relationship: str = Field(pattern="^(entails|contradicts|unknown)$")
    confidence: float = Field(ge=0.0, le=1.0)
    signal: str = Field(min_length=1, max_length=200)


class RelevanceOutput(AIModel):
    relevant: bool
    confidence: float = Field(ge=0.0, le=1.0)
    signal: str = Field(min_length=1, max_length=200)


class EvidenceOutput(AIModel):
    excerpt: str = Field(min_length=1, max_length=20000)
    locator_type: str | None = Field(default=None, max_length=100)
    locator_value: str | None = Field(default=None, max_length=500)
    relationship: str = Field(pattern="^(supports|contradicts|contextualizes)$")


class ClaimOutput(AIModel):
    proposition: str = Field(min_length=1, max_length=2000)
    importance: str = Field(pattern="^(major|relevant|peripheral)$")
    evidence: list[EvidenceOutput] = Field(default_factory=list, max_length=20)
    state: str = Field(pattern="^(supported|partially_supported|disputed|unsubstantiated)$")
    accept: bool


class ExtractionOutput(AIModel):
    claims: list[ClaimOutput] = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0.0, le=1.0)


class ClaimDraft(AIModel):
    proposition: str = Field(min_length=1, max_length=2000)


class SynthesisProposition(AIModel):
    text: str = Field(min_length=1, max_length=5000)
    claim_indexes: list[int] = Field(min_length=1, max_length=100)


class SynthesisOutput(AIModel):
    headline: str = Field(min_length=1, max_length=500)
    summary: str = Field(default="", max_length=10000)
    why_it_matters: str = Field(default="", max_length=10000)
    material_change: bool = False
    claim_indexes: list[int] = Field(min_length=1, max_length=100)
    propositions: list[SynthesisProposition] = Field(min_length=1, max_length=100)
    confidence: float = Field(ge=0.0, le=1.0)


class ArticleAnalysisEntity(AIModel):
    """Structured entity mention in analyzed article content."""

    name: str = Field(min_length=1, max_length=300)
    category: str | None = Field(default=None, max_length=100)


class CandidateClaimOutput(AIModel):
    """Atomic factual proposition proposed by article analysis.

    This is a candidate claim only: it never enters the canonical ``claims``
    table. Phase 22 verifies candidate evidence before any canonical Claim may
    be created.
    """

    index: int = Field(ge=0, le=10_000)
    proposition: str = Field(min_length=1, max_length=2000)


class CandidateExcerptOutput(AIModel):
    """Short source-derived excerpt proposed as support for a candidate Claim.

    This is a candidate excerpt only: it never enters the canonical
    ``evidence_spans`` table. Phase 22 verifies membership against the
    immutable Phase 18 artifact before any EvidenceSpan may be created.
    """

    candidate_claim_index: int = Field(ge=0, le=10_000)
    excerpt: str = Field(min_length=1, max_length=2000)
    locator_type: str | None = Field(default=None, max_length=100)
    locator_value: str | None = Field(default=None, max_length=500)


class ArticleAnalysisOutput(AIModel):
    """Validated structured article-analysis proposal (Phase 21).

    All fields are bounded and strictly validated before the result can be
    persisted as a durable ArticleAnalysis. ``candidate_claims`` and
    ``candidate_evidence_excerpts`` are proposals: AI analysis is not evidence.
    """

    summary: str = Field(min_length=1, max_length=3000)
    key_developments: list[str] = Field(min_length=1, max_length=25)
    entities: list[ArticleAnalysisEntity] = Field(default_factory=list, max_length=100)
    dates: list[str] = Field(default_factory=list, max_length=50)
    locations: list[str] = Field(default_factory=list, max_length=50)
    significance: str = Field(min_length=1, max_length=3000)
    novelty: str = Field(min_length=1, max_length=3000)
    candidate_claims: list[CandidateClaimOutput] = Field(default_factory=list, max_length=50)
    candidate_evidence_excerpts: list[CandidateExcerptOutput] = Field(default_factory=list, max_length=50)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("key_developments")
    @classmethod
    def _bounded_developments(cls, value: list[str]) -> list[str]:
        for item in value:
            if not str(item).strip() or len(str(item)) > 2000:
                raise ValueError("key developments must be non-empty strings bounded to 2000 characters")
        return value

    @field_validator("dates", "locations")
    @classmethod
    def _bounded_strings(cls, value: list[str]) -> list[str]:
        for item in value:
            if not str(item).strip() or len(str(item)) > 300:
                raise ValueError("dates and locations must be non-empty strings bounded to 300 characters")
        return value

    @model_validator(mode="after")
    def _excerpt_indexes_reference_candidate_claims(self) -> "ArticleAnalysisOutput":
        indexes = {claim.index for claim in self.candidate_claims}
        for excerpt in self.candidate_evidence_excerpts:
            if excerpt.candidate_claim_index not in indexes:
                raise ValueError(
                    f"candidate excerpt references unknown candidate claim index "
                    f"{excerpt.candidate_claim_index}"
                )
        return self


@dataclass(frozen=True)
class ArticleAnalysisRequest:
    """Bounded input contract for article analysis.

    ``text`` is the exact verified Phase 18 normalized content (never
    caller-supplied, never re-fetched). ``scope_terms`` are the approved scope
    terms of the pinned relevance decision.
    """

    title: str
    text: str
    scope_terms: Sequence[str]
    work_id: str | None = None

    def __post_init__(self) -> None:
        if not str(self.text).strip():
            raise ValueError("article analysis text must not be empty")
        if len(self.text) > 2_000_000:
            raise ValueError("article analysis text is unreasonably large")


class VocabularySuggestion(AIModel):
    """One bounded, reviewable vocabulary proposal."""

    term: str = Field(min_length=1, max_length=300)
    kind: str = Field(
        pattern="^(primary|alias|synonym|acronym|acronym_expansion|related|include|exclude)$"
    )
    expansion_of: str | None = Field(default=None, max_length=300)
    rationale: str = Field(default="Provider suggestion", max_length=2000)

    @field_validator("term", "rationale")
    @classmethod
    def _nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("vocabulary text must not be blank")
        return value


class VocabularyOutput(AIModel):
    """Structured provider output for optional vocabulary assistance."""

    suggestions: list[VocabularySuggestion] = Field(default_factory=list, max_length=50)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _unique_suggestions(self) -> "VocabularyOutput":
        identities = set()
        for suggestion in self.suggestions:
            identity = (" ".join(suggestion.term.casefold().split()), suggestion.kind)
            if identity in identities:
                raise ValueError("vocabulary suggestions must be unique")
            identities.add(identity)
        return self


class ResearchPlanOutput(AIModel):
    """Bounded, non-authoritative planning suggestions for one Research Task."""

    query_suggestions: list[str] = Field(default_factory=list, max_length=20)
    preferred_source_classes: list[str] = Field(default_factory=list, max_length=10)
    date_from: str | None = Field(default=None, max_length=32)
    date_to: str | None = Field(default=None, max_length=32)
    explanation: str = Field(default="", max_length=500)

    @field_validator("query_suggestions", "preferred_source_classes")
    @classmethod
    def _bounded_plan_strings(cls, value: list[str]) -> list[str]:
        result = []
        seen: set[str] = set()
        for item in value:
            text = str(item).strip()
            identity = " ".join(text.casefold().split())
            if not identity or len(text) > 300 or identity in seen:
                raise ValueError("research plan suggestions must be unique, nonblank, and bounded")
            seen.add(identity)
            result.append(text)
        return result


@dataclass(frozen=True)
class ResearchPlanRequest:
    """Minimal Question/Gap context allowed into a planning provider."""

    question: str
    gap_type: str
    gap_description: str
    approved_vocabulary: Sequence[str]
    max_queries: int

    def __post_init__(self) -> None:
        if not str(self.question).strip() or len(str(self.question)) > 10_000:
            raise ValueError("research plan question is invalid")
        if not str(self.gap_type).strip() or len(str(self.gap_type)) > 80:
            raise ValueError("research plan gap type is invalid")
        if not str(self.gap_description).strip() or len(str(self.gap_description)) > 1_000:
            raise ValueError("research plan gap description is invalid")
        if isinstance(self.approved_vocabulary, (str, bytes)) or len(self.approved_vocabulary) > 25:
            raise ValueError("research plan vocabulary is too large")
        if any(not str(term).strip() or len(str(term)) > 300 for term in self.approved_vocabulary):
            raise ValueError("research plan vocabulary contains invalid text")
        if isinstance(self.max_queries, bool) or not 1 <= self.max_queries <= 50:
            raise ValueError("research plan max_queries must be between 1 and 50")


@dataclass(frozen=True)
class VocabularyRequest:
    """Bounded Watch context supplied to a vocabulary provider."""

    watch_name: str
    target_type: str
    approved_terms: Sequence[str]
    max_suggestions: int

    def __post_init__(self) -> None:
        if not str(self.watch_name).strip() or len(str(self.watch_name)) > 200:
            raise ValueError("vocabulary watch_name must be bounded and nonblank")
        if not str(self.target_type).strip() or len(str(self.target_type)) > 50:
            raise ValueError("vocabulary target_type must be bounded and nonblank")
        if isinstance(self.approved_terms, (str, bytes)) or len(self.approved_terms) > 200:
            raise ValueError("vocabulary approved_terms must contain at most 200 items")
        if any(not str(term).strip() or len(str(term)) > 300 for term in self.approved_terms):
            raise ValueError("vocabulary approved_terms contain invalid text")
        if isinstance(self.max_suggestions, bool) or not 1 <= self.max_suggestions <= 50:
            raise ValueError("vocabulary max_suggestions must be between 1 and 50")


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> EmbeddingOutput | Mapping[str, Any]: ...


class RerankerProvider(Protocol):
    def rerank(self, query: str, candidate: str) -> RankingOutput | Mapping[str, Any]: ...


class EntailmentProvider(Protocol):
    def assess(self, proposition: str, evidence: str) -> EntailmentOutput | Mapping[str, Any]: ...


class RelevanceProvider(Protocol):
    def classify(self, text: str, scope_terms: Sequence[str]) -> RelevanceOutput | Mapping[str, Any]: ...


class ExtractionProvider(Protocol):
    def extract(self, title: str, text: str) -> ExtractionOutput | Mapping[str, Any]: ...


class SynthesisProvider(Protocol):
    def synthesize(self, story_headline: str, claims: Sequence[ClaimDraft]) -> SynthesisOutput | Mapping[str, Any]: ...


class ArticleAnalysisProvider(Protocol):
    def analyze(self, request: ArticleAnalysisRequest) -> ArticleAnalysisOutput | Mapping[str, Any]: ...


class VocabularyProvider(Protocol):
    def suggest(self, request: VocabularyRequest) -> VocabularyOutput | Mapping[str, Any]: ...


class ResearchPlannerProvider(Protocol):
    def plan(self, request: ResearchPlanRequest) -> ResearchPlanOutput | Mapping[str, Any]: ...


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[\w][\w'-]*", text.casefold()))


def _validated(model_type: type[ModelT], value: Any) -> ModelT:
    try:
        return model_type.model_validate(value)
    except ValidationError as exc:
        raise AIValidationError(str(exc)) from exc


def _split_sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+|\n+", text) if item.strip()]


class LocalEmbeddingProvider:
    """Small, dependency-free token-hash embedding for local candidate retrieval."""

    def __init__(self, dimension: int = 32, *, output: Mapping[str, Any] | None = None):
        if dimension < 4 or dimension > 4096:
            raise ValueError("embedding dimension must be between 4 and 4096")
        self.dimension = dimension
        if output is not None:
            _validated(EmbeddingOutput, output)

    def embed(self, text: str) -> EmbeddingOutput:
        vector = [0.0] * self.dimension
        for token in _tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            vector[index] += 1.0 if digest[4] & 1 else -1.0
        norm = math.sqrt(sum(item * item for item in vector))
        if norm:
            vector = [item / norm for item in vector]
        return EmbeddingOutput(vector=vector)


class LocalRerankerProvider:
    def rerank(self, query: str, candidate: str) -> RankingOutput:
        query_tokens = _tokens(query)
        candidate_tokens = _tokens(candidate)
        score = len(query_tokens & candidate_tokens) / len(query_tokens) if query_tokens else 0.0
        return RankingOutput(
            score=score,
            confidence=min(1.0, 0.5 + score / 2),
            signal="token-overlap",
        )


class LocalEntailmentProvider:
    def assess(self, proposition: str, evidence: str) -> EntailmentOutput:
        proposition_tokens = _tokens(proposition)
        evidence_tokens = _tokens(evidence)
        overlap = len(proposition_tokens & evidence_tokens) / len(proposition_tokens) if proposition_tokens else 0.0
        contradiction_marker = bool(_tokens(evidence) & {"not", "denied", "denies", "correction", "incorrect"})
        if overlap >= 0.8 and contradiction_marker:
            relationship, confidence = "contradicts", 0.9
        elif overlap >= 0.8:
            relationship, confidence = "entails", 0.95
        elif overlap >= 0.4:
            relationship, confidence = "unknown", 0.6
        else:
            relationship, confidence = "unknown", 0.35
        return EntailmentOutput(relationship=relationship, confidence=confidence, signal="token-overlap")


class LocalRelevanceProvider:
    def __init__(self, *, output: Mapping[str, Any] | None = None):
        if output is not None:
            _validated(RelevanceOutput, output)

    def classify(self, text: str, scope_terms: Sequence[str]) -> RelevanceOutput:
        terms: set[str] = set()
        for term in scope_terms:
            terms.update(_tokens(term))
        overlap = len(terms & _tokens(text))
        relevant = bool(terms) and overlap / len(terms) >= 0.5
        confidence = 0.9 if relevant else 0.75 if terms else 0.4
        return RelevanceOutput(relevant=relevant, confidence=confidence, signal="scope-term-overlap")


class LocalExtractionProvider:
    def extract(self, title: str, text: str) -> ExtractionOutput:
        sentences = _split_sentences(text)
        claims = [
            ClaimOutput(
                proposition=sentence,
                importance="major" if index == 0 else "relevant",
                evidence=[
                    EvidenceOutput(
                        excerpt=sentence,
                        locator_type="sentence",
                        locator_value=str(index + 1),
                        relationship="supports",
                    )
                ],
                state="supported",
                accept=True,
            )
            for index, sentence in enumerate(sentences[:100])
        ]
        if not claims:
            raise AIValidationError("local extraction found no sentence-sized evidence")
        return ExtractionOutput(claims=claims, confidence=0.85)


class LocalSynthesisProvider:
    def synthesize(self, story_headline: str, claims: Sequence[ClaimDraft]) -> SynthesisOutput:
        if not claims:
            raise AIValidationError("local synthesis requires at least one accepted Claim")
        claim_indexes = list(range(len(claims)))
        summary = " ".join(claim.proposition for claim in claims)
        return SynthesisOutput(
            headline=story_headline.strip() or claims[0].proposition[:500],
            summary=summary,
            why_it_matters="This revision is grounded in the accepted evidence ledger Claims.",
            material_change=True,
            claim_indexes=claim_indexes,
            propositions=[
                SynthesisProposition(text=claim.proposition, claim_indexes=[index])
                for index, claim in enumerate(claims)
            ],
            confidence=0.9,
        )


class DeterministicRelevanceProvider:
    def __init__(self, *, relevant: bool = True, confidence: float = 1.0, output: Mapping[str, Any] | None = None):
        self._output = output or {"relevant": relevant, "confidence": confidence, "signal": "deterministic"}

    def classify(self, text: str, scope_terms: Sequence[str]) -> RelevanceOutput | Mapping[str, Any]:
        return self._output


class DeterministicEmbeddingProvider:
    def __init__(self, output: Mapping[str, Any] | EmbeddingOutput | None = None):
        self._output = output or {"vector": [1.0]}

    def embed(self, text: str) -> EmbeddingOutput | Mapping[str, Any]:
        return self._output


class DeterministicRerankerProvider:
    def __init__(self, output: Mapping[str, Any] | RankingOutput | None = None):
        self._output = output or {"score": 1.0, "confidence": 1.0, "signal": "deterministic"}

    def rerank(self, query: str, candidate: str) -> RankingOutput | Mapping[str, Any]:
        return self._output


class DeterministicEntailmentProvider:
    def __init__(self, output: Mapping[str, Any] | EntailmentOutput | None = None):
        self._output = output or {"relationship": "entails", "confidence": 1.0, "signal": "deterministic"}

    def assess(self, proposition: str, evidence: str) -> EntailmentOutput | Mapping[str, Any]:
        return self._output


class DeterministicExtractionProvider:
    def __init__(self, output: Mapping[str, Any] | ExtractionOutput | None = None):
        self._output = output or {
            "claims": [
                {
                    "proposition": "Deterministic claim",
                    "importance": "major",
                    "evidence": [{"excerpt": "Deterministic evidence", "relationship": "supports"}],
                    "state": "supported",
                    "accept": True,
                }
            ],
            "confidence": 1.0,
        }

    def extract(self, title: str, text: str) -> ExtractionOutput | Mapping[str, Any]:
        return self._output


class DeterministicSynthesisProvider:
    def __init__(self, output: Mapping[str, Any] | SynthesisOutput | None = None):
        self._output = output

    def synthesize(self, story_headline: str, claims: Sequence[ClaimDraft]) -> SynthesisOutput | Mapping[str, Any]:
        if self._output is not None:
            return self._output
        return LocalSynthesisProvider().synthesize(story_headline, claims)


_CAPITALIZED_WORDS = re.compile(r"\b[A-Z][a-zA-Z][a-zA-Z'\-]{1,60}\b")
_ISO_DATE = re.compile(
    r"\b\d{4}-\d{1,2}-\d{1,2}\b|\b\d{1,2}\s+(?:January|February|March|April|May|June|July|"
    r"August|September|October|November|December)[a-z]*\s+\d{4}\b|\b(?:January|February|"
    r"March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b"
)
_NON_ENTITY_WORDS = frozenset(
    {
        "The", "A", "An", "New", "This", "That", "These", "Those", "For", "And", "But", "With",
        "From", "After", "Before", "During", "Against", "Although", "While", "Since", "Until",
        "Among", "When", "Where", "What", "Who", "More", "Most", "Last", "First", "Next", "Our",
        "Their", "Its", "His", "Her", "Its", "Over", "Under", "Inside", "Outside", "Some", "Many",
        "Every", "Each", "Both", "Few", "Late", "Early", "Recent", "Today", "Yesterday",
    }
)


class LocalArticleAnalysisProvider:
    """Deterministic, offline ArticleAnalysis provider derived from source text.

    Intentionally crude: its purpose is architecture, offline testing, and
    zero-cost fallback, not semantic LLM analysis. It always returns the exact
    validated ``ArticleAnalysisOutput`` schema so local and real provider paths
    are interchangeable. Candidate Claims/Excerpts are sentence-level proposals
    and never enter canonical Evidence/Claims tables.
    """

    def __init__(self, *, max_claims: int = 10):
        if isinstance(max_claims, bool) or not isinstance(max_claims, int) or not 1 <= max_claims <= 50:
            raise ValueError("max_claims must be an integer between 1 and 50")
        self.max_claims = max_claims

    def analyze(self, request: ArticleAnalysisRequest) -> ArticleAnalysisOutput:
        sentences = _split_sentences(request.text)
        if not sentences:
            raise AIValidationError("local article analysis found no sentence-sized content")
        summary = sentences[0][:2000] or "No summary sentence available."
        developments = [sentence[:2000] for sentence in sentences[: min(5, self.max_claims)]]
        if not developments:
            developments = [summary[:2000]]
        entities: list[ArticleAnalysisEntity] = []
        for token in _CAPITALIZED_WORDS.findall(request.text):
            if token in _NON_ENTITY_WORDS or len(token) < 3:
                continue
            candidate = ArticleAnalysisEntity(name=token)
            if all(extract.name != token for extract in entities):
                entities.append(candidate)
        dates = [match.strip(".,") for match in _ISO_DATE.findall(request.text)][:10]
        locations = [token for token in _CAPITALIZED_WORDS.findall(request.text) if token not in _NON_ENTITY_WORDS and len(token) >= 3][:6]
        scope_text = ", ".join(str(term).strip() for term in request.scope_terms if str(term).strip())
        significance = (
            f"Article text matches the approved monitoring scope for this information need"
            f" ({scope_text or 'approved scope terms'}) and was acquired because the source "
            f"changed. Its importance for the need is assessed by the local provider only; "
            f"semantic significance requires the real provider."
        )[:3000]
        novelty = (
            "Article-level observation: this is a new changed acquisition for the monitor. "
            "The local provider performs no cross-article or Story-level novelty comparison; "
            "no Story evolution is invoked."
        )[:3000]
        claims = [
            CandidateClaimOutput(index=index, proposition=sentence[:2000])
            for index, sentence in enumerate(sentences[: self.max_claims])
        ]
        excerpts = [
            CandidateExcerptOutput(
                candidate_claim_index=index,
                excerpt=sentence[:2000],
                locator_type="sentence",
                locator_value=str(index + 1),
            )
            for index, sentence in enumerate(sentences[: self.max_claims])
        ]
        return ArticleAnalysisOutput(
            summary=summary,
            key_developments=developments,
            entities=entities,
            dates=dates,
            locations=locations,
            significance=significance,
            novelty=novelty,
            candidate_claims=claims,
            candidate_evidence_excerpts=excerpts,
            confidence=0.85,
        )


class DeterministicArticleAnalysisProvider:
    def __init__(self, output: Mapping[str, Any] | ArticleAnalysisOutput | None = None):
        if output is not None:
            _validated(ArticleAnalysisOutput, output)
        self._output = output

    def analyze(self, request: ArticleAnalysisRequest) -> ArticleAnalysisOutput | Mapping[str, Any]:
        if self._output is not None:
            return self._output
        return LocalArticleAnalysisProvider().analyze(request)


class LocalVocabularyProvider:
    """Zero-cost local route; deterministic Watch derivation owns the terms."""

    model_name = "local-vocabulary"

    def suggest(self, request: VocabularyRequest) -> VocabularyOutput:
        return VocabularyOutput(suggestions=[], confidence=0.0)


class LocalResearchPlannerProvider:
    """Zero-cost route; deterministic query generation owns the baseline."""

    model_name = "local-research-planner"

    def plan(self, request: ResearchPlanRequest) -> ResearchPlanOutput:
        return ResearchPlanOutput()


@dataclass(frozen=True)
class CapabilityBundle:
    embedding: EmbeddingProvider | None = None
    reranker: RerankerProvider | None = None
    entailment: EntailmentProvider | None = None
    relevance: RelevanceProvider | None = None
    extraction: ExtractionProvider | None = None
    synthesis: SynthesisProvider | None = None
    article_analysis: ArticleAnalysisProvider | None = None
    vocabulary: VocabularyProvider | None = None
    research_plan: ResearchPlannerProvider | None = None

    @classmethod
    def local_defaults(cls) -> "CapabilityBundle":
        return cls(
            embedding=LocalEmbeddingProvider(),
            reranker=LocalRerankerProvider(),
            entailment=LocalEntailmentProvider(),
            relevance=LocalRelevanceProvider(),
            extraction=LocalExtractionProvider(),
            synthesis=LocalSynthesisProvider(),
            article_analysis=LocalArticleAnalysisProvider(),
            vocabulary=LocalVocabularyProvider(),
            research_plan=LocalResearchPlannerProvider(),
        )


@dataclass(frozen=True)
class RoutePolicy:
    local_enabled: bool = True
    paid_enabled: bool = False
    timeout_seconds: float = 5.0
    min_confidence: float = 0.7
    max_paid_calls: int = 0
    max_paid_cost_usd: float = 0.05
    max_paid_calls_per_work: int = 1
    max_paid_cost_usd_per_work: float = 0.05
    paid_request_cost_usd: float = 0.01

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 0 <= self.min_confidence <= 1:
            raise ValueError("min_confidence must be between 0 and 1")
        if min(
            self.max_paid_calls,
            self.max_paid_calls_per_work,
        ) < 0 or min(self.max_paid_cost_usd, self.max_paid_cost_usd_per_work, self.paid_request_cost_usd) < 0:
            raise ValueError("paid budgets and costs must be nonnegative")


@dataclass(frozen=True)
class TelemetryEvent:
    capability: str
    route: str
    provider: str
    outcome: str
    work_id: str | None
    model: str | None = None
    confidence: float | None = None
    decision_signal: str | None = None
    latency_ms: int = 0
    token_units: int | None = None
    compute_units: float | None = None
    estimated_cost_usd: float = 0.0
    escalation_reason: str | None = None
    error_code: str | None = None


class TelemetrySink(Protocol):
    def record(self, event: TelemetryEvent) -> None: ...


class SQLiteTelemetrySink:
    """Persist router events in the existing provider-usage ledger."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        job_id: str | None = None,
        monitor_id: str | None = None,
        research_question_id: str | None = None,
        invocation_id: str | None = None,
    ):
        self.db_path = Path(db_path)
        self.job_id = job_id
        self.monitor_id = monitor_id
        self.research_question_id = research_question_id
        self.invocation_id = invocation_id

    def record(self, event: TelemetryEvent) -> None:
        metadata = {
            "confidence": event.confidence,
            "compute_units": event.compute_units,
            "decision_signal": event.decision_signal,
            "escalation_reason": event.escalation_reason,
            "error_code": event.error_code,
            "model": event.model,
            "route": event.route,
            "work_id": event.work_id,
        }
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    """
                    INSERT INTO provider_usage
                        (id, job_id, monitor_id, research_question_id, capability,
                         provider, request_type, query_units, token_units,
                         estimated_cost_usd, latency_ms, outcome, created_at,
                         invocation_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"ai_{uuid.uuid4().hex[:24]}",
                        self.job_id,
                        self.monitor_id,
                        self.research_question_id,
                        event.capability,
                        event.provider,
                        f"ai:{event.route}",
                        1,
                        event.token_units,
                        event.estimated_cost_usd,
                        event.latency_ms,
                        json.dumps({"status": event.outcome, **metadata}, sort_keys=True),
                        utc_now(),
                        self.invocation_id,
                    ),
                )
        finally:
            conn.close()


def _record_telemetry(sink: list[TelemetryEvent] | TelemetrySink, event: TelemetryEvent) -> None:
    if isinstance(sink, list):
        sink.append(event)
    else:
        sink.record(event)


_OUTPUT_TYPES: dict[str, type[AIModel]] = {
    "embedding": EmbeddingOutput,
    "reranker": RankingOutput,
    "entailment": EntailmentOutput,
    "relevance": RelevanceOutput,
    "extraction": ExtractionOutput,
    "synthesis": SynthesisOutput,
    "article_analysis": ArticleAnalysisOutput,
    "vocabulary": VocabularyOutput,
    "research_plan": ResearchPlanOutput,
}


class AIRouter:
    """Route one capability at a time through local-first bounded providers."""

    def __init__(
        self,
        *,
        local: CapabilityBundle,
        paid: CapabilityBundle | None = None,
        policy: RoutePolicy | None = None,
        telemetry: list[TelemetryEvent] | TelemetrySink | None = None,
    ):
        self.local = local
        self.paid = paid or CapabilityBundle()
        self.policy = policy or RoutePolicy()
        self.telemetry = telemetry if telemetry is not None else []
        self._paid_calls = 0
        self._paid_cost = 0.0
        self._work_paid_calls: dict[str, int] = {}
        self._work_paid_cost: dict[str, float] = {}
        self._active_execution_events: list[TelemetryEvent] | None = None
        self.last_execution_events: tuple[TelemetryEvent, ...] = ()

    def embedding(self, text: str, *, work_id: str | None = None) -> EmbeddingOutput:
        return self._execute("embedding", lambda provider: provider.embed(text), work_id=work_id)

    def rerank(self, query: str, candidate: str, *, work_id: str | None = None) -> RankingOutput:
        return self._execute("reranker", lambda provider: provider.rerank(query, candidate), work_id=work_id)

    def entailment(self, proposition: str, evidence: str, *, work_id: str | None = None) -> EntailmentOutput:
        return self._execute("entailment", lambda provider: provider.assess(proposition, evidence), work_id=work_id)

    def relevance(self, text: str, scope_terms: Sequence[str], *, work_id: str | None = None) -> RelevanceOutput:
        return self._execute("relevance", lambda provider: provider.classify(text, scope_terms), work_id=work_id)

    def extraction(self, title: str, text: str, *, work_id: str | None = None) -> ExtractionOutput:
        return self._execute("extraction", lambda provider: provider.extract(title, text), work_id=work_id)

    def synthesis(self, story_headline: str, claims: Sequence[ClaimDraft], *, work_id: str | None = None) -> SynthesisOutput:
        return self._execute("synthesis", lambda provider: provider.synthesize(story_headline, claims), work_id=work_id)

    def article_analysis(self, request: ArticleAnalysisRequest, *, work_id: str | None = None) -> ArticleAnalysisOutput:
        return self._execute("article_analysis", lambda provider: provider.analyze(request), work_id=work_id)

    def vocabulary(self, request: VocabularyRequest, *, work_id: str | None = None) -> VocabularyOutput:
        return self._execute("vocabulary", lambda provider: provider.suggest(request), work_id=work_id)

    def research_plan(self, request: ResearchPlanRequest, *, work_id: str | None = None) -> ResearchPlanOutput:
        return self._execute("research_plan", lambda provider: provider.plan(request), work_id=work_id)

    def _execute(self, capability: str, call: Callable[[Any], Any], *, work_id: str | None) -> Any:
        events: list[TelemetryEvent] = []
        previous_events = self._active_execution_events
        self._active_execution_events = events
        try:
            local_provider = getattr(self.local, capability)
            local_failure: AIError | None = None
            if self.policy.local_enabled and local_provider is not None:
                try:
                    result = self._call_provider(capability, local_provider, call, "local", work_id, None)
                    if self._is_low_confidence(result):
                        paid_result = self._try_paid(capability, call, work_id, "low_confidence")
                        if paid_result is not None:
                            return paid_result
                    return result
                except AIError as exc:
                    local_failure = exc
            else:
                local_failure = AIDisabled("local route is disabled or unavailable")

            paid_result = self._try_paid(capability, call, work_id, "local_failure")
            if paid_result is not None:
                return paid_result
            if local_failure is not None:
                raise local_failure
            raise AIDisabled(f"no provider is configured for {capability}")
        finally:
            self.last_execution_events = tuple(events)
            self._active_execution_events = previous_events

    def _try_paid(self, capability: str, call: Callable[[Any], Any], work_id: str | None, reason: str) -> Any | None:
        provider = getattr(self.paid, capability)
        if not self.policy.paid_enabled or provider is None:
            self._record_blocked(capability, work_id, reason, "paid_disabled")
            return None
        if not self._reserve_paid(work_id):
            self._record_blocked(capability, work_id, reason, "paid_budget_exhausted")
            return None
        return self._call_provider(capability, provider, call, "paid", work_id, reason)

    def _reserve_paid(self, work_id: str | None) -> bool:
        if self._paid_calls >= self.policy.max_paid_calls:
            return False
        if self._paid_cost + self.policy.paid_request_cost_usd > self.policy.max_paid_cost_usd:
            return False
        key = work_id or "__unattributed__"
        if self._work_paid_calls.get(key, 0) >= self.policy.max_paid_calls_per_work:
            return False
        if self._work_paid_cost.get(key, 0.0) + self.policy.paid_request_cost_usd > self.policy.max_paid_cost_usd_per_work:
            return False
        self._paid_calls += 1
        self._paid_cost += self.policy.paid_request_cost_usd
        self._work_paid_calls[key] = self._work_paid_calls.get(key, 0) + 1
        self._work_paid_cost[key] = self._work_paid_cost.get(key, 0.0) + self.policy.paid_request_cost_usd
        return True

    def _call_provider(
        self,
        capability: str,
        provider: Any,
        call: Callable[[Any], Any],
        route: str,
        work_id: str | None,
        escalation_reason: str | None,
    ) -> Any:
        started = time.monotonic()
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="newsroom-ai")
        future = executor.submit(call, provider)
        try:
            raw = future.result(timeout=self.policy.timeout_seconds)
            result = _validated(_OUTPUT_TYPES[capability], raw)
        except FutureTimeout as exc:
            future.cancel()
            self._record_failure(capability, route, provider, work_id, escalation_reason, "timeout", started)
            raise AITimeout(f"{capability} provider timed out") from exc
        except AIValidationError as exc:
            self._record_failure(capability, route, provider, work_id, escalation_reason, "invalid_output", started)
            raise
        except Exception as exc:  # provider errors must not cross the domain boundary
            self._record_failure(capability, route, provider, work_id, escalation_reason, "provider_error", started)
            raise AIProviderError(f"{capability} provider failed") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        confidence = getattr(result, "confidence", None)
        signal = getattr(result, "signal", None)
        provider_name = getattr(provider, "provider_name", None) or type(provider).__name__
        provider_model = getattr(provider, "model_name", None) or type(provider).__name__
        usage = getattr(provider, "last_usage", None)
        token_units = None
        if isinstance(usage, Mapping):
            raw_units = usage.get("token_units")
            if isinstance(raw_units, (int, float)) and math.isfinite(float(raw_units)):
                token_units = int(raw_units)
        actual_cost = usage.get("cost_usd") if isinstance(usage, Mapping) else None
        if isinstance(actual_cost, (int, float)) and math.isfinite(float(actual_cost)):
            estimated_cost = float(actual_cost)
        else:
            estimated_cost = self.policy.paid_request_cost_usd if route == "paid" else 0.0
        self._emit_telemetry(
            TelemetryEvent(
                capability=capability,
                route=route,
                provider=provider_name,
                model=provider_model,
                outcome="low_confidence" if confidence is not None and confidence < self.policy.min_confidence else "succeeded",
                work_id=work_id,
                confidence=confidence,
                decision_signal=signal,
                latency_ms=max(0, int((time.monotonic() - started) * 1000)),
                token_units=token_units,
                estimated_cost_usd=estimated_cost,
                escalation_reason=escalation_reason,
            ),
        )
        return result

    def _record_failure(
        self,
        capability: str,
        route: str,
        provider: Any,
        work_id: str | None,
        escalation_reason: str | None,
        error_code: str,
        started: float,
    ) -> None:
        self._emit_telemetry(
            TelemetryEvent(
                capability=capability,
                route=route,
                provider=getattr(provider, "provider_name", None) or type(provider).__name__,
                model=getattr(provider, "model_name", None) or type(provider).__name__,
                outcome="failed",
                work_id=work_id,
                latency_ms=max(0, int((time.monotonic() - started) * 1000)),
                estimated_cost_usd=self.policy.paid_request_cost_usd if route == "paid" else 0.0,
                escalation_reason=escalation_reason,
                error_code=error_code,
            ),
        )

    def _record_blocked(self, capability: str, work_id: str | None, reason: str, error_code: str) -> None:
        self._emit_telemetry(
            TelemetryEvent(
                capability=capability,
                route="paid",
                provider="unavailable",
                model=None,
                outcome="blocked",
                work_id=work_id,
                escalation_reason=reason,
                error_code=error_code,
            ),
        )

    def _emit_telemetry(self, event: TelemetryEvent) -> None:
        _record_telemetry(self.telemetry, event)
        if self._active_execution_events is not None:
            self._active_execution_events.append(event)

    def _is_low_confidence(self, result: Any) -> bool:
        confidence = getattr(result, "confidence", None)
        return confidence is not None and confidence < self.policy.min_confidence


__all__ = [
    "AIError",
    "AIValidationError",
    "AIProviderError",
    "AITimeout",
    "AIBudgetExceeded",
    "AIDisabled",
    "AIConfigurationError",
    "AIModel",
    "EmbeddingOutput",
    "RankingOutput",
    "EntailmentOutput",
    "RelevanceOutput",
    "EvidenceOutput",
    "ClaimOutput",
    "ExtractionOutput",
    "ClaimDraft",
    "SynthesisProposition",
    "SynthesisOutput",
    "ArticleAnalysisEntity",
    "CandidateClaimOutput",
    "CandidateExcerptOutput",
    "ArticleAnalysisOutput",
    "ArticleAnalysisRequest",
    "EmbeddingProvider",
    "RerankerProvider",
    "EntailmentProvider",
    "RelevanceProvider",
    "ExtractionProvider",
    "SynthesisProvider",
    "ArticleAnalysisProvider",
    "VocabularySuggestion",
    "VocabularyOutput",
    "VocabularyRequest",
    "VocabularyProvider",
    "ResearchPlanOutput",
    "ResearchPlanRequest",
    "ResearchPlannerProvider",
    "LocalEmbeddingProvider",
    "LocalRerankerProvider",
    "LocalEntailmentProvider",
    "LocalRelevanceProvider",
    "LocalExtractionProvider",
    "LocalSynthesisProvider",
    "LocalArticleAnalysisProvider",
    "DeterministicRelevanceProvider",
    "DeterministicEmbeddingProvider",
    "DeterministicRerankerProvider",
    "DeterministicEntailmentProvider",
    "DeterministicExtractionProvider",
    "DeterministicSynthesisProvider",
    "DeterministicArticleAnalysisProvider",
    "LocalVocabularyProvider",
    "LocalResearchPlannerProvider",
    "CapabilityBundle",
    "RoutePolicy",
    "TelemetryEvent",
    "TelemetrySink",
    "SQLiteTelemetrySink",
    "AIRouter",
]
