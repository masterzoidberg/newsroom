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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

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


@dataclass(frozen=True)
class CapabilityBundle:
    embedding: EmbeddingProvider | None = None
    reranker: RerankerProvider | None = None
    entailment: EntailmentProvider | None = None
    relevance: RelevanceProvider | None = None
    extraction: ExtractionProvider | None = None
    synthesis: SynthesisProvider | None = None

    @classmethod
    def local_defaults(cls) -> "CapabilityBundle":
        return cls(
            embedding=LocalEmbeddingProvider(),
            reranker=LocalRerankerProvider(),
            entailment=LocalEntailmentProvider(),
            relevance=LocalRelevanceProvider(),
            extraction=LocalExtractionProvider(),
            synthesis=LocalSynthesisProvider(),
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
    ):
        self.db_path = Path(db_path)
        self.job_id = job_id
        self.monitor_id = monitor_id
        self.research_question_id = research_question_id

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
                         estimated_cost_usd, latency_ms, outcome, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"ai_{hashlib.sha256(f'{event.capability}:{event.route}:{event.work_id}:{time.monotonic_ns()}'.encode()).hexdigest()[:24]}",
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

    def _execute(self, capability: str, call: Callable[[Any], Any], *, work_id: str | None) -> Any:
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
        _record_telemetry(
            self.telemetry,
            TelemetryEvent(
                capability=capability,
                route=route,
                provider=type(provider).__name__,
                model=type(provider).__name__,
                outcome="low_confidence" if confidence is not None and confidence < self.policy.min_confidence else "succeeded",
                work_id=work_id,
                confidence=confidence,
                decision_signal=signal,
                latency_ms=max(0, int((time.monotonic() - started) * 1000)),
                estimated_cost_usd=self.policy.paid_request_cost_usd if route == "paid" else 0.0,
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
        _record_telemetry(
            self.telemetry,
            TelemetryEvent(
                capability=capability,
                route=route,
                provider=type(provider).__name__,
                model=type(provider).__name__,
                outcome="failed",
                work_id=work_id,
                latency_ms=max(0, int((time.monotonic() - started) * 1000)),
                estimated_cost_usd=self.policy.paid_request_cost_usd if route == "paid" else 0.0,
                escalation_reason=escalation_reason,
                error_code=error_code,
            ),
        )

    def _record_blocked(self, capability: str, work_id: str | None, reason: str, error_code: str) -> None:
        _record_telemetry(
            self.telemetry,
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
    "EmbeddingProvider",
    "RerankerProvider",
    "EntailmentProvider",
    "RelevanceProvider",
    "ExtractionProvider",
    "SynthesisProvider",
    "LocalEmbeddingProvider",
    "LocalRerankerProvider",
    "LocalEntailmentProvider",
    "LocalRelevanceProvider",
    "LocalExtractionProvider",
    "LocalSynthesisProvider",
    "DeterministicRelevanceProvider",
    "DeterministicEmbeddingProvider",
    "DeterministicRerankerProvider",
    "DeterministicEntailmentProvider",
    "DeterministicExtractionProvider",
    "DeterministicSynthesisProvider",
    "CapabilityBundle",
    "RoutePolicy",
    "TelemetryEvent",
    "TelemetrySink",
    "SQLiteTelemetrySink",
    "AIRouter",
]
