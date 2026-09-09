"""Validated API contracts for the Phase 03 core domain."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Literal, Optional

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ai import AIError, AIRouter, CapabilityBundle, SQLiteTelemetrySink
from .ai_pipeline import AIVerticalSliceService, VerticalSliceInput
from .acquisition import (
    AcquisitionError,
    AcquisitionService,
    SourceProfileService,
    SourceSuggestionService,
)
from .article_analysis import ArticleAnalysisService
from .domain import CoreService, DomainConflict, DomainNotFound, DomainValidation
from .evidence import EvidenceService
from .jobs import BudgetService, JobService, SchedulerService, compose_completion_hooks
from .intelligent_monitoring import WatchMaintenanceService, WatchService
from .monitoring import (
    MonitorService,
    MonitoringPolicyService,
    RelevanceCascade,
    RelevanceScope,
    ScopeSuggestionService,
    monitor_job_completion_hook,
)
from .research_questions import (
    research_job_completion_hook,
    research_job_rerun_factory,
    ResearchQuestionService,
    research_job_recovery_hook,
)
from .reports import AlertService, BriefingService, LivingReportService
from .story_evolution import StoryCandidate, StoryEvolutionService
from .workbench import ComparisonService, DiagnosticsService, SearchService, WorkbenchService
from .ask import AskService
from .knowledge import KnowledgeService
from .story_corrections import StoryCorrectionService
from .source_robustness import SourceRobustnessService
from .attention import AttentionService
from .hypotheses import HypothesisService
from .experience import ExperienceService
from .research_prioritization import ResearchPrioritizationService


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CategoryCreate(StrictModel):
    slug: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    display_order: int = Field(default=0, ge=0)
    enabled: bool = True
    priority: str = Field(default="normal", min_length=1, max_length=32)
    max_stories_per_run: Optional[int] = Field(default=None, ge=0)


class CategoryPatch(StrictModel):
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    display_order: Optional[int] = Field(default=None, ge=0)
    enabled: Optional[bool] = None
    priority: Optional[str] = Field(default=None, min_length=1, max_length=32)
    max_stories_per_run: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def reject_non_nullable_nulls(self):
        for field in ("name", "description", "display_order", "enabled", "priority"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class TopicCreate(StrictModel):
    category_id: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    enabled: bool = True
    priority: str = Field(default="normal", min_length=1, max_length=32)
    max_queries_per_run: Optional[int] = Field(default=None, ge=0)
    max_stories_per_run: Optional[int] = Field(default=None, ge=0)


class TopicPatch(StrictModel):
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    enabled: Optional[bool] = None
    priority: Optional[str] = Field(default=None, min_length=1, max_length=32)
    max_queries_per_run: Optional[int] = Field(default=None, ge=0)
    max_stories_per_run: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def reject_non_nullable_nulls(self):
        for field in ("name", "description", "enabled", "priority"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class VocabularyCreate(StrictModel):
    term: str = Field(min_length=1, max_length=300)
    term_type: str = Field(default="include", pattern="^(include|alias|entity|exclude)$")
    concept_kind: str = Field(default="term", pattern="^(term|acronym|related_concept)$")
    weight: float = Field(default=1.0, ge=0.0, le=100.0)


class VocabularyPatch(StrictModel):
    term: Optional[str] = Field(default=None, max_length=300)
    term_type: Optional[str] = Field(default=None, pattern="^(include|alias|entity|exclude)$")
    concept_kind: Optional[str] = Field(default=None, pattern="^(term|acronym|related_concept)$")
    weight: Optional[float] = Field(default=None, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def reject_term_null(self):
        if "term" in self.model_fields_set and self.term is None:
            raise ValueError("term cannot be null")
        return self


class ScopeSuggestionCreate(StrictModel):
    suggestion_type: str = Field(pattern="^(term|alias|acronym|related_concept|exclude)$")
    value: str = Field(min_length=1, max_length=300)
    rationale: str = Field(default="", max_length=2000)
    source: str = Field(default="ai", pattern="^(ai|user)$")


class ScopeSuggestionAssist(StrictModel):
    text: str = Field(min_length=1, max_length=20_000)
    limit: int = Field(default=10, ge=1, le=50)


class VocabularySuggestionCreate(StrictModel):
    suggestion_type: str = Field(pattern="^(term|synonym|acronym|alias|broader|narrower|related_concept|ambiguity|exclude)$")
    value: str = Field(min_length=1, max_length=300)
    rationale: str = Field(default="", max_length=2000)
    source: str = Field(default="ai", pattern="^(ai|user)$")


class MonitoringPolicyCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    allowed_channels: list[str] = Field(default_factory=list, max_length=20)
    base_cadence_seconds: int = Field(ge=1, le=31_536_000)
    min_cadence_seconds: int = Field(ge=1, le=31_536_000)
    max_cadence_seconds: int = Field(ge=1, le=31_536_000)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    query_budget: int = Field(default=0, ge=0)
    paid_budget_usd: float = Field(default=0.0, ge=0.0)
    local_model_budget: int = Field(default=0, ge=0)
    escalation_rules: dict[str, Any] = Field(default_factory=dict)
    backoff_rules: dict[str, Any] = Field(default_factory=dict)
    retirement_criteria: dict[str, Any] = Field(default_factory=dict)


class MonitoringPolicyPatch(StrictModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    allowed_channels: Optional[list[str]] = Field(default=None, max_length=20)
    base_cadence_seconds: Optional[int] = Field(default=None, ge=1, le=31_536_000)
    min_cadence_seconds: Optional[int] = Field(default=None, ge=1, le=31_536_000)
    max_cadence_seconds: Optional[int] = Field(default=None, ge=1, le=31_536_000)
    priority: Optional[str] = Field(default=None, pattern="^(low|normal|high|urgent)$")
    query_budget: Optional[int] = Field(default=None, ge=0)
    paid_budget_usd: Optional[float] = Field(default=None, ge=0.0)
    local_model_budget: Optional[int] = Field(default=None, ge=0)
    escalation_rules: Optional[dict[str, Any]] = None
    backoff_rules: Optional[dict[str, Any]] = None
    retirement_criteria: Optional[dict[str, Any]] = None


class MonitorCreate(StrictModel):
    target_type: str = Field(pattern="^(topic|subject|story|source|research_question)$")
    target_id: str = Field(min_length=1, max_length=200)
    policy_id: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    next_check_at: Optional[str] = Field(default=None, max_length=64)
    need_type: Optional[str] = Field(default=None, pattern="^(topic|subject|story|research_question)$")
    need_id: Optional[str] = Field(default=None, min_length=1, max_length=200)


class MonitorPatch(StrictModel):
    policy_id: Optional[str] = Field(default=None, min_length=1, max_length=200)
    enabled: Optional[bool] = None
    next_check_at: Optional[str] = Field(default=None, max_length=64)
    need_type: Optional[str] = Field(default=None, pattern="^(topic|subject|story|research_question)$")
    need_id: Optional[str] = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def reject_empty_patch(self):
        if not self.model_fields_set:
            raise ValueError("at least one monitor field must be supplied")
        return self


class WatchCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    target_type: str = Field(pattern="^(topic|subject|story|source|research_question)$")
    target_id: str = Field(min_length=1, max_length=200)
    policy_id: str = Field(min_length=1, max_length=200)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    discovery_enabled: bool = True


class WatchSetupCreate(StrictModel):
    request_id: str = Field(min_length=1, max_length=64)
    interest: str = Field(min_length=1, max_length=2_000)
    name: str = Field(min_length=1, max_length=200)
    primary_terms: list[str] = Field(min_length=1, max_length=100)


class PausedWatchDraft(StrictModel):
    draft_type: Literal["paused_watch"]
    version: Literal[1]
    resumed: bool
    request_id: str
    category_id: str
    topic_id: str
    policy_id: str
    watch_id: str
    name: str
    interest: str
    primary_terms: list[str]
    status: Literal["paused"]
    target_type: Literal["topic"]
    discovery_enabled: Literal[False]
    priority: Literal["normal"]
    next_action: Literal["add_sources"]
    paid_budget_usd: float
    paid_escalation_enabled: Literal[False]
    monitor_count: int
    job_count: int
    category: dict[str, Any]
    topic: dict[str, Any]
    topic_terms: list[dict[str, Any]]
    policy: dict[str, Any]
    watch: dict[str, Any]


class WatchPatch(StrictModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    policy_id: Optional[str] = Field(default=None, min_length=1, max_length=200)
    priority: Optional[str] = Field(default=None, pattern="^(low|normal|high|urgent)$")
    discovery_enabled: Optional[bool] = None


class WatchReview(StrictModel):
    """Shared approve/reject envelope for vocabulary and Source candidates."""

    status: str = Field(pattern="^(approved|rejected)$")


class WatchVocabularySuggest(StrictModel):
    limit: int = Field(default=20, ge=1, le=50)


class WatchDiscoveryRun(StrictModel):
    limit: int = Field(default=25, ge=1, le=25)


class WatchVocabularyCreate(StrictModel):
    term: str = Field(min_length=1, max_length=300)
    kind: str = Field(
        default="alias",
        pattern="^(primary|alias|synonym|acronym|acronym_expansion|related|include|exclude)$",
    )
    expansion_of: Optional[str] = Field(default=None, max_length=300)
    rationale: str = Field(default="Added by user", max_length=2000)


class SourceCandidateCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    source_id: Optional[str] = Field(default=None, max_length=200)
    homepage_url: Optional[str] = Field(default=None, max_length=2048)
    feed_url: Optional[str] = Field(default=None, max_length=2048)
    discovery_method: str = Field(default="manual", pattern="^(manual|existing_source|document_link|feed_discovery|web_search|ai_suggestion)$")
    rationale: str = Field(min_length=1, max_length=2000)
    authority_context: str = Field(default="", max_length=2000)
    limitations: str = Field(default="", max_length=2000)
    provenance: dict[str, Any] = Field(default_factory=dict)


class RelevanceEvaluate(StrictModel):
    text: str = Field(min_length=1, max_length=100_000)
    exact_terms: list[str] = Field(default_factory=list, max_length=100)
    vocabulary: list[str] = Field(default_factory=list, max_length=100)
    entities: list[str] = Field(default_factory=list, max_length=100)
    concepts: list[str] = Field(default_factory=list, max_length=100)
    semantic_terms: list[str] = Field(default_factory=list, max_length=100)
    exclusions: list[str] = Field(default_factory=list, max_length=100)
    semantic_threshold: float = Field(default=0.6, ge=0.0, le=1.0)


class SubjectCreate(StrictModel):
    canonical_name: str = Field(min_length=1, max_length=200)
    subject_type: str = Field(pattern="^(person|company|product|agency|law|case|project|technology|franchise|organization|other)$")
    description: str = Field(default="", max_length=2000)
    canonical_url: Optional[str] = Field(default=None, max_length=2048)
    canonical_id: Optional[str] = Field(default=None, max_length=300)
    enabled: bool = True
    priority: str = Field(default="normal", min_length=1, max_length=32)
    aliases: list[str] = Field(default_factory=list, max_length=100)
    topic_ids: list[str] = Field(default_factory=list, max_length=100)


class SubjectPatch(StrictModel):
    canonical_name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    canonical_url: Optional[str] = Field(default=None, max_length=2048)
    canonical_id: Optional[str] = Field(default=None, max_length=300)
    enabled: Optional[bool] = None
    priority: Optional[str] = Field(default=None, min_length=1, max_length=32)

    @model_validator(mode="after")
    def reject_non_nullable_nulls(self):
        for field in ("canonical_name", "description", "enabled", "priority"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class AliasCreate(StrictModel):
    alias: str = Field(min_length=1, max_length=300)


class SourceCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=120)
    domain: Optional[str] = Field(default=None, max_length=255)
    homepage_url: Optional[str] = Field(default=None, max_length=2048)
    feed_url: Optional[str] = Field(default=None, max_length=2048)
    source_kind: str = Field(default="web", pattern="^(web|feed|api|official|aggregator|unknown)$")
    default_quality: str = Field(default="unknown", pattern="^(primary|high|medium|low|unknown)$")


class SourcePatch(StrictModel):
    name: Optional[str] = Field(default=None, max_length=200)
    domain: Optional[str] = Field(default=None, max_length=255)
    homepage_url: Optional[str] = Field(default=None, max_length=2048)
    feed_url: Optional[str] = Field(default=None, max_length=2048)
    source_kind: Optional[str] = Field(default=None, pattern="^(web|feed|api|official|aggregator|unknown)$")
    default_quality: Optional[str] = Field(default=None, pattern="^(primary|high|medium|low|unknown)$")

    @model_validator(mode="after")
    def reject_name_null(self):
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        return self


class DocumentCreate(StrictModel):
    source_id: str = Field(min_length=1, max_length=200)
    canonical_url: str = Field(min_length=1, max_length=2048)
    title: str = Field(min_length=1, max_length=500)
    published_at: Optional[str] = Field(default=None, max_length=64)


class DocumentPatch(StrictModel):
    title: Optional[str] = Field(default=None, max_length=500)
    published_at: Optional[str] = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def reject_title_null(self):
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title cannot be null")
        return self


class DocumentVersionCreate(StrictModel):
    retrieved_at: Optional[str] = Field(default=None, max_length=64)
    content_hash: str = Field(min_length=1, max_length=256)
    content_kind: str = Field(default="metadata", pattern="^(metadata|excerpt|full_text)$")
    locator_type: Optional[str] = Field(default=None, max_length=100)
    locator_value: Optional[str] = Field(default=None, max_length=1000)
    normalized_json: Optional[dict[str, Any] | list[Any]] = None
    etag: Optional[str] = Field(default=None, max_length=500)
    last_modified: Optional[str] = Field(default=None, max_length=100)


class EvidenceSpanCreate(StrictModel):
    excerpt: str = Field(min_length=1, max_length=10000)
    locator_type: Optional[str] = Field(default=None, max_length=100)
    locator_value: Optional[str] = Field(default=None, max_length=1000)


class ClaimCreate(StrictModel):
    proposition: str = Field(min_length=1, max_length=4000)
    importance: str = Field(default="relevant", pattern="^(major|relevant|peripheral)$")
    supersedes_claim_id: Optional[str] = Field(default=None, max_length=200)


class ClaimStateWrite(StrictModel):
    state: str = Field(pattern="^(pending|supported|partially_supported|disputed|unsubstantiated|superseded)$")
    reason: str = Field(default="", max_length=2000)


class ClaimEvidenceCreate(StrictModel):
    evidence_span_id: str = Field(min_length=1, max_length=200)
    relationship: str = Field(pattern="^(supports|contradicts|contextualizes)$")


class ResearchQuestionCreate(StrictModel):
    question: str = Field(min_length=1, max_length=10_000)
    origin_type: str = Field(default="user", pattern="^(story|claim|subject|user|monitor)$")
    origin_id: Optional[str] = Field(default=None, max_length=200)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    search_attempt_budget: int = Field(default=0, ge=0, le=1000)
    query_budget: int = Field(default=0, ge=0, le=100_000)
    local_model_budget: int = Field(default=0, ge=0, le=100_000)
    paid_budget_usd: float = Field(default=0.0, ge=0.0, le=1_000_000)
    next_attempt_at: Optional[str] = Field(default=None, max_length=64)
    criteria: dict[str, Any] = Field(default_factory=dict)
    pursuit_policy: str = Field(default="manual", pattern="^(disabled|manual|automatic)$")
    pursuit_cooldown_seconds: int = Field(default=3600, ge=0, le=31_536_000)


class ResearchQuestionPatch(StrictModel):
    question: Optional[str] = Field(default=None, min_length=1, max_length=10_000)
    priority: Optional[str] = Field(default=None, pattern="^(low|normal|high|urgent)$")
    search_attempt_budget: Optional[int] = Field(default=None, ge=0, le=1000)
    query_budget: Optional[int] = Field(default=None, ge=0, le=100_000)
    local_model_budget: Optional[int] = Field(default=None, ge=0, le=100_000)
    paid_budget_usd: Optional[float] = Field(default=None, ge=0.0, le=1_000_000)
    next_attempt_at: Optional[str] = Field(default=None, max_length=64)
    criteria: Optional[dict[str, Any]] = None
    pursuit_policy: Optional[str] = Field(default=None, pattern="^(disabled|manual|automatic)$")
    pursuit_cooldown_seconds: Optional[int] = Field(default=None, ge=0, le=31_536_000)

    @model_validator(mode="after")
    def reject_empty_patch(self):
        if not self.model_fields_set:
            raise ValueError("at least one research question field must be supplied")
        return self


class ResearchQuestionTransition(StrictModel):
    reason: str = Field(min_length=1, max_length=4_000)
    claim_ids: list[str] = Field(default_factory=list, max_length=100)
    evidence_span_ids: list[str] = Field(default_factory=list, max_length=100)


class ResearchQuestionClaimLinkCreate(StrictModel):
    claim_id: str = Field(min_length=1, max_length=200)
    relationship: str = Field(default="resolves", pattern="^(supports|contradicts|contextualizes|resolves)$")


class ResearchQuestionEvidenceLinkCreate(StrictModel):
    evidence_span_id: str = Field(min_length=1, max_length=200)
    relationship: str = Field(default="resolves", pattern="^(supports|contradicts|contextualizes|resolves)$")


class ResearchQuestionNoteCreate(StrictModel):
    body: str = Field(min_length=1, max_length=10_000)
    note_type: str = Field(default="note", pattern="^(note|hypothesis)$")


class ResearchQuestionPursuitCreate(StrictModel):
    mode: str = Field(default="manual", pattern="^(manual|policy)$")
    query_units: int = Field(default=0, ge=0, le=100_000)
    local_model_units: int = Field(default=0, ge=0, le=100_000)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0, le=1_000_000)
    query: Optional[str] = Field(default=None, max_length=4_000)
    gap_id: Optional[str] = Field(default=None, max_length=200)
    limits: dict[str, int] = Field(default_factory=dict)


class ResearchQuestionClaimCorrection(StrictModel):
    relationship: str = Field(pattern="^(supports|contradicts|contextualizes|resolves)$")
    action: str = Field(default="exclude", pattern="^(exclude|restore)$")
    reason: str = Field(min_length=1, max_length=2_000)


class ResearchQuestionGapReview(StrictModel):
    status: str = Field(pattern="^(dismissed|open)$")
    reason: str = Field(min_length=1, max_length=4_000)


class ResearchQuestionAttemptWrite(StrictModel):
    status: str = Field(pattern="^(planned|running|succeeded|partial|failed|cancelled)$")
    outcome_note: str = Field(default="", max_length=4_000)
    started_at: Optional[str] = Field(default=None, max_length=64)
    completed_at: Optional[str] = Field(default=None, max_length=64)


class LivingReportCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    target_type: str = Field(pattern="^(monitor|story|topic|subject|source|research_question)$")
    target_id: str = Field(min_length=1, max_length=200)
    timezone_name: str = Field(default="UTC", min_length=1, max_length=100)


class BriefingGenerate(StrictModel):
    period: str = Field(pattern="^(daily|weekly)$")
    monitor_ids: list[str] = Field(default_factory=list, max_length=100)
    period_start: Optional[str] = Field(default=None, max_length=64)
    period_end: Optional[str] = Field(default=None, max_length=64)
    timezone_name: str = Field(default="UTC", min_length=1, max_length=100)


class AlertRuleCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    target_type: str = Field(default="all", pattern="^(all|report|monitor|story)$")
    target_id: Optional[str] = Field(default=None, max_length=200)
    event_types: list[str] = Field(default_factory=list, max_length=10)
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)
    browser_enabled: bool = False
    enabled: bool = True
    dedupe_window_seconds: int = Field(default=86400, ge=0, le=2_592_000)
    timezone_name: str = Field(default="UTC", min_length=1, max_length=100)


class AlertRulePatch(StrictModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    target_type: Optional[str] = Field(default=None, pattern="^(all|report|monitor|story)$")
    target_id: Optional[str] = Field(default=None, max_length=200)
    event_types: Optional[list[str]] = Field(default=None, max_length=10)
    min_importance: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    browser_enabled: Optional[bool] = None
    enabled: Optional[bool] = None
    dedupe_window_seconds: Optional[int] = Field(default=None, ge=0, le=2_592_000)
    timezone_name: Optional[str] = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def reject_empty_patch(self):
        if not self.model_fields_set:
            raise ValueError("at least one alert rule field must be supplied")
        return self


class NotificationPreferencesWrite(StrictModel):
    browser_enabled: bool
    permission_state: str = Field(pattern="^(default|granted|denied)$")
    online: bool = True


class AlertDeliveryWrite(StrictModel):
    status: str = Field(pattern="^(pending|sent|failed|denied|offline|skipped)$")
    error_detail: Optional[str] = Field(default=None, max_length=2000)


class ResearchGapSuggestionReview(StrictModel):
    status: str = Field(pattern="^(accepted|rejected)$")


class ResearchGapSuggestionConvert(StrictModel):
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    search_attempt_budget: int = Field(default=0, ge=0, le=1000)


class RevisionProposition(StrictModel):
    text: str = Field(min_length=1, max_length=4000)
    claim_ids: list[str] = Field(min_length=1, max_length=100)


class ManualClaimEvidence(StrictModel):
    excerpt: str = Field(min_length=1, max_length=10000)
    locator_type: Optional[str] = Field(default=None, max_length=100)
    locator_value: Optional[str] = Field(default=None, max_length=1000)
    relationship: str = Field(pattern="^(supports|contradicts|contextualizes)$")


class ManualClaim(StrictModel):
    proposition: str = Field(min_length=1, max_length=4000)
    importance: str = Field(default="relevant", pattern="^(major|relevant|peripheral)$")
    evidence: list[ManualClaimEvidence] = Field(default_factory=list, max_length=100)
    state: str = Field(default="pending", pattern="^(pending|supported|partially_supported|disputed|unsubstantiated|superseded)$")
    accept: bool = False
    supersedes_claim_id: Optional[str] = Field(default=None, max_length=200)


class ManualRevisionProposition(StrictModel):
    text: str = Field(min_length=1, max_length=4000)
    claim_indexes: list[int] = Field(min_length=1, max_length=100)


class ManualRevision(StrictModel):
    headline: str = Field(min_length=1, max_length=500)
    summary: str = Field(default="", max_length=10000)
    why_it_matters: str = Field(default="", max_length=10000)
    material_change: bool = False
    claim_indexes: list[int] = Field(min_length=1, max_length=100)
    propositions: list[ManualRevisionProposition] = Field(min_length=1, max_length=100)


class StoryCreate(StrictModel):
    headline: str = Field(min_length=1, max_length=500)
    summary: str = Field(default="", max_length=10000)
    why_it_matters: str = Field(default="", max_length=10000)
    lifecycle: str = Field(default="developing", pattern="^(developing|stable|resolved|archived)$")
    material_change: bool = False
    claim_set_hash: Optional[str] = Field(default=None, max_length=128)
    topic_ids: list[str] = Field(default_factory=list, max_length=100)
    subject_ids: list[str] = Field(default_factory=list, max_length=100)


class ManualDocument(StrictModel):
    canonical_url: str = Field(min_length=1, max_length=2048)
    title: str = Field(min_length=1, max_length=500)
    published_at: Optional[str] = Field(default=None, max_length=64)


class ManualRunCreate(StrictModel):
    source_id: Optional[str] = Field(default=None, max_length=200)
    source: Optional[SourceCreate] = None
    document_id: Optional[str] = Field(default=None, max_length=200)
    document: Optional[ManualDocument] = None
    document_version: DocumentVersionCreate
    story_id: Optional[str] = Field(default=None, max_length=200)
    story: Optional[StoryCreate] = None
    claims: list[ManualClaim] = Field(min_length=1, max_length=100)
    revision: Optional[ManualRevision] = None

    @model_validator(mode="after")
    def require_new_or_existing_parents(self):
        if (self.source_id is None) == (self.source is None):
            raise ValueError("provide exactly one of source_id or source")
        if (self.document_id is None) == (self.document is None):
            raise ValueError("provide exactly one of document_id or document")
        return self


class AIRunCreate(StrictModel):
    source_id: Optional[str] = Field(default=None, max_length=200)
    source: Optional[SourceCreate] = None
    document_id: Optional[str] = Field(default=None, max_length=200)
    document: Optional[ManualDocument] = None
    document_version: DocumentVersionCreate
    content_text: str = Field(min_length=1, max_length=50000)
    scope_terms: list[str] = Field(min_length=1, max_length=100)
    story_id: Optional[str] = Field(default=None, max_length=200)
    story: Optional[StoryCreate] = None
    work_id: Optional[str] = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def require_new_or_existing_parents(self):
        if (self.source_id is None) == (self.source is None):
            raise ValueError("provide exactly one of source_id or source")
        if (self.document_id is None) == (self.document is None):
            raise ValueError("provide exactly one of document_id or document")
        if self.story_id is not None and self.story is not None:
            raise ValueError("provide at most one of story_id or story")
        return self


class AcquisitionCreate(StrictModel):
    url: str = Field(min_length=1, max_length=2048)
    channel: str = Field(default="direct_http", pattern="^(direct_http|page)$")


class FeedPollCreate(StrictModel):
    feed_url: Optional[str] = Field(default=None, max_length=2048)


class SourceSuggestionCreate(StrictModel):
    source_id: Optional[str] = Field(default=None, max_length=200)
    name: str = Field(min_length=1, max_length=500)
    homepage_url: Optional[str] = Field(default=None, max_length=2048)
    feed_url: Optional[str] = Field(default=None, max_length=2048)
    rationale: str = Field(min_length=1, max_length=4000)
    likely_contribution: str = Field(min_length=1, max_length=4000)
    limitations: str = Field(default="", max_length=4000)
    supported_methods: list[str] = Field(min_length=1, max_length=10)


class SourceSuggestionReview(StrictModel):
    status: str = Field(pattern="^(approved|rejected)$")


class JobCreate(StrictModel):
    job_type: str = Field(min_length=1, max_length=120)
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, max_length=300)
    monitor_id: Optional[str] = Field(default=None, max_length=200)
    research_question_id: Optional[str] = Field(default=None, max_length=200)
    document_version_id: Optional[str] = Field(default=None, max_length=200)
    priority: int = Field(default=0, ge=-1000, le=1000)
    max_attempts: int = Field(default=3, ge=1, le=10)
    run_id: Optional[str] = Field(default=None, max_length=200)


class BudgetLimitWrite(StrictModel):
    scope_type: str = Field(pattern="^(global|policy|job|research_question)$")
    scope_id: Optional[str] = Field(default=None, max_length=200)
    period: str = Field(pattern="^(daily|monthly|lifetime)$")
    cap_type: str = Field(pattern="^(acquisition_units|local_model_units|paid_requests|usd)$")
    cap_value: float = Field(ge=0)
    enabled: bool = True


class PaidEnabledWrite(StrictModel):
    enabled: bool


class StoryRevisionCreate(StrictModel):
    headline: str = Field(min_length=1, max_length=500)
    summary: str = Field(default="", max_length=10000)
    why_it_matters: str = Field(default="", max_length=10000)
    material_change: bool = False
    claim_ids: list[str] = Field(default_factory=list, max_length=100)
    propositions: list[RevisionProposition] = Field(default_factory=list, max_length=100)


class StoryPatch(StrictModel):
    lifecycle: str = Field(pattern="^(developing|stable|resolved|archived)$")


class ClaimStoryCorrectionWrite(StrictModel):
    story_id: Optional[str] = Field(default=None, max_length=200)
    expected_from_story_id: Optional[str] = Field(default=None, max_length=200)
    reason: str = Field(default="", max_length=4000)


class StoryMergeWrite(StrictModel):
    destination_story_id: str = Field(min_length=1, max_length=200)
    expected_source_updated_at: Optional[str] = Field(default=None, max_length=64)
    expected_current_state_fingerprint: Optional[str] = Field(default=None, min_length=1, max_length=128)
    reason: str = Field(default="", max_length=4000)
    metadata_decisions: dict[str, Any] = Field(default_factory=dict)


class StorySplitWrite(StrictModel):
    groups: list[list[str]] = Field(min_length=2, max_length=20)
    expected_claim_ids: Optional[list[str]] = Field(default=None, max_length=500)
    expected_source_updated_at: Optional[str] = Field(default=None, max_length=64)
    reason: str = Field(default="", max_length=4000)
    child_metadata: list[StoryCreate] = Field(default_factory=list, max_length=20)


class StoryTargetResolutionWrite(StrictModel):
    selected_story_ids: list[str] = Field(min_length=1, max_length=1)
    disable: bool = False


class AttentionDecisionWrite(StrictModel):
    action: str = Field(pattern="^(seen|snoozed|not_useful)$")
    snooze_days: int = Field(default=7, ge=1, le=30)


class ExperienceModeWrite(StrictModel):
    mode: str = Field(pattern="^(simple|advanced)$")


class HypothesisCreate(StrictModel):
    statement: str = Field(min_length=1, max_length=10_000)
    origin: str = Field(default="human", pattern="^(human|deterministic|provider)$")
    provider_route: str = Field(default="local_deterministic", max_length=100)


class HypothesisClaimLinkCreate(StrictModel):
    relationship: str = Field(pattern="^(supports|contradicts|discriminates)$")


class HypothesisGapCreate(StrictModel):
    description: str = Field(min_length=1, max_length=4_000)


class HypothesisReviewWrite(StrictModel):
    status: str = Field(pattern="^(approved|rejected|archived)$")
    reason: str = Field(default="", max_length=4_000)


class CounterfactualWrite(StrictModel):
    exclude_document_ids: list[str] = Field(default_factory=list, max_length=100)
    exclude_source_ids: list[str] = Field(default_factory=list, max_length=100)


class StoryExtractWrite(StrictModel):
    claim_ids: list[str] = Field(min_length=1, max_length=500)
    story: StoryCreate
    reason: str = Field(default="", max_length=4000)


class DuplicateDecisionWrite(StrictModel):
    destination_story_id: str = Field(min_length=1, max_length=200)
    evidence_hash: str = Field(default="current", min_length=1, max_length=256)
    expected_source_updated_at: Optional[str] = Field(default=None, max_length=64)
    reason: str = Field(default="", max_length=4000)
    metadata_decisions: dict[str, Any] = Field(default_factory=dict)


class StoryEntityWrite(StrictModel):
    entity_id: str = Field(min_length=1, max_length=200)
    origin: str = Field(default="user", pattern="^(user|import)$")


class TagCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    namespace: str = Field(default="user", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    tag_type: str = Field(default="user", pattern="^(user|smart)$")


class TagPatch(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    namespace: Optional[str] = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    tag_type: Optional[str] = Field(default=None, pattern="^(user|smart)$")


class EntityAliasInput(StrictModel):
    alias: str = Field(min_length=1, max_length=500)
    alias_type: str = Field(default="alternate_name", pattern="^(alternate_name|acronym|expanded_name|abbreviation|former_name|deterministic)$")
    origin: Optional[str] = Field(default=None, pattern="^(user|subject|watch|article_analysis|deterministic|provider|import)$")


class EntityCreate(StrictModel):
    canonical_name: str = Field(min_length=1, max_length=500)
    entity_type: str = Field(default="unknown", pattern="^(person|organization|agency|company|program|location|event|legislation|technology|publication|other|unknown)$")
    description: str = Field(default="", max_length=5_000)
    aliases: list[EntityAliasInput] = Field(default_factory=list, max_length=20)


class EntityLinkCreate(StrictModel):
    entity_id: str = Field(min_length=1, max_length=200)
    role: str = Field(default="mentioned", pattern="^(subject|object|mentioned|context)$")


class TagAssignmentCreate(StrictModel):
    tag_id: Optional[str] = Field(default=None, max_length=200)
    object_type: str = Field(pattern="^(entity|claim|evidence|document|story|research_question|research_gap|research_task|source|watch|article_analysis)$")
    object_id: str = Field(min_length=1, max_length=200)
    origin: str = Field(default="user", pattern="^(user|deterministic|provider|import|backfill)$")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    reason: str = Field(default="", max_length=2_000)


class KnowledgeBackfillCreate(StrictModel):
    kind: str = Field(pattern="^(article_analysis_entities|smart_tags)$")
    row_limit: int = Field(default=500, ge=1, le=10_000)
    batch_size: int = Field(default=25, ge=1, le=100)


class StoryTagCreate(StrictModel):
    tag_id: str = Field(min_length=1, max_length=200)


class StoryReviewWrite(StrictModel):
    review_status: str = Field(pattern="^(new|saved|dismissed|not_useful)$")
    revision_id: Optional[str] = Field(default=None, max_length=200)


class EvolutionObservationCreate(StrictModel):
    document_id: str = Field(min_length=1, max_length=200)
    update_class: str = Field(
        pattern="^(new_story|duplicate|corroboration|contradiction|qualification|correction|material_update)$"
    )
    event_key: Optional[str] = Field(default=None, max_length=200)
    entities: list[str] = Field(default_factory=list, max_length=100)
    locations: list[str] = Field(default_factory=list, max_length=100)
    revision_id: Optional[str] = Field(default=None, max_length=200)
    decision: dict[str, Any] = Field(default_factory=dict)
    material_change: Optional[bool] = None


class LineageCreate(StrictModel):
    parent_document_id: str = Field(min_length=1, max_length=200)
    relationship: str = Field(
        pattern="^(cites|syndicated_from|wire_propagation|rewritten_from|common_primary_document)$"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    rationale: str = Field(default="", max_length=2000)


class StoryResolutionCandidate(StrictModel):
    id: str = Field(min_length=1, max_length=200)
    headline: str = Field(min_length=1, max_length=500)
    canonical_url: Optional[str] = Field(default=None, max_length=2048)
    document_id: Optional[str] = Field(default=None, max_length=200)
    published_at: Optional[str] = Field(default=None, max_length=64)
    event_key: Optional[str] = Field(default=None, max_length=200)
    entities: list[str] = Field(default_factory=list, max_length=100)
    locations: list[str] = Field(default_factory=list, max_length=100)
    claims: list[str] = Field(default_factory=list, max_length=100)
    embedding: list[float] = Field(default_factory=list, max_length=4096)
    text: str = Field(default="", max_length=20000)


class StoryEvolutionProcess(StoryResolutionCandidate):
    document_id: str = Field(min_length=1, max_length=200)
    story_id: Optional[str] = Field(default=None, max_length=200)
    update_class: Optional[str] = Field(
        default=None,
        pattern="^(new_story|duplicate|corroboration|contradiction|qualification|correction|material_update)$",
    )
    revision_id: Optional[str] = Field(default=None, max_length=200)


class SettingWrite(StrictModel):
    value: str = Field(max_length=4000)


class ComparisonCreate(StrictModel):
    document_ids: list[str] = Field(min_length=2, max_length=20)
    story_id: Optional[str] = Field(default=None, max_length=200)


class NoteCreate(StrictModel):
    object_type: str = Field(pattern="^(story|subject|document|claim|monitor|research_question)$")
    object_id: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)
    note_type: str = Field(default="note", pattern="^(note|hypothesis|context)$")


class AskConversationCreate(StrictModel):
    scope_type: str = Field(default="global", pattern="^(global|story|claim|evidence|document|report|question|research_question|subject|monitor|note|entity|research_task|source)$")
    scope_id: Optional[str] = Field(default=None, max_length=200)


class AskTurnCreate(StrictModel):
    prompt: str = Field(min_length=1, max_length=4_000)
    context_budget: int = Field(default=4_000, ge=100, le=12_000)
    provider_mode: str = Field(default="local", pattern="^(local|hosted)$")
    cost_cap_usd: float = Field(default=0.0, ge=0.0, le=1_000_000)
    as_of: Optional[str] = Field(default=None, max_length=80)


class AskDirectCreate(AskTurnCreate):
    scope_type: str = Field(default="global", pattern="^(global|story|claim|evidence|document|report|question|research_question|subject|monitor|note|entity|research_task|source)$")
    scope_id: Optional[str] = Field(default=None, max_length=200)


def _patch_data(model: BaseModel) -> dict:
    data = model.model_dump(exclude_unset=True)
    if not data:
        from .domain import DomainValidation
        raise DomainValidation("at least one field must be supplied")
    return data


_PHASE23_JOB_TYPES = {
    "automatic_story_stage",
    "automatic_report_stage",
    "automatic_alert_stage",
}
_PHASE23_STATUS_KEYS = (
    "promotion_id",
    "story_stage_job_id",
    "report_stage_job_id",
    "claim_id",
    "story_id",
    "report_id",
    "revision_id",
    "report_revision_id",
    "alert_ids",
    "delivery_ids",
    "reason_code",
)


def _job_api_result(job: dict[str, Any]) -> dict[str, Any]:
    """Project Phase 23 Jobs without exposing their internal JSON blobs."""
    if job.get("job_type") not in _PHASE23_JOB_TYPES:
        return job
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    outcome = result.get("stage_status")
    if not outcome:
        if job.get("status") == "running":
            outcome = "running"
        elif job.get("status") == "queued" and int(job.get("attempts") or 0) > 0:
            outcome = "retrying"
        else:
            outcome = job.get("status")
    orchestration = {"outcome": outcome}
    for key in _PHASE23_STATUS_KEYS:
        value = result.get(key, payload.get(key))
        if value is not None:
            orchestration[key] = value
    allowed = {
        "id",
        "job_type",
        "status",
        "priority",
        "attempts",
        "max_attempts",
        "next_attempt_at",
        "lease_owner",
        "lease_expires_at",
        "failure_cause",
        "created_at",
        "updated_at",
        "completed_at",
    }
    projected = {key: value for key, value in job.items() if key in allowed}
    projected["orchestration"] = orchestration
    return projected


def create_domain_router(
    service: CoreService,
    require_user: Callable,
    require_csrf: Callable,
    evidence_service: EvidenceService | None = None,
) -> APIRouter:
    router = APIRouter()
    ledger = evidence_service or EvidenceService(service.db_path)
    acquisition = AcquisitionService(service.db_path)
    profiles = SourceProfileService(service.db_path)
    suggestions = SourceSuggestionService(service.db_path)
    jobs = JobService(
        service.db_path,
        recovery_hook=research_job_recovery_hook,
        completion_hook=compose_completion_hooks(
            research_job_completion_hook,
            monitor_job_completion_hook,
        ),
        rerun_factory=research_job_rerun_factory,
    )
    budgets = BudgetService(service.db_path)
    scheduler = SchedulerService(service.db_path)
    policies = MonitoringPolicyService(service.db_path)
    monitors = MonitorService(service.db_path)
    watches = WatchService(
        service.db_path,
        router=AIRouter(
            local=CapabilityBundle.local_defaults(),
            telemetry=SQLiteTelemetrySink(service.db_path),
        ),
    )
    watch_maintenance = WatchMaintenanceService(service.db_path, watches=watches)
    vocabulary_service = ScopeSuggestionService(service.db_path)
    evolution = StoryEvolutionService(service.db_path)
    research = ResearchQuestionService(service.db_path)
    reports = LivingReportService(service.db_path)
    briefings = BriefingService(service.db_path)
    alerts = AlertService(service.db_path)
    search = SearchService(service.db_path)
    comparisons = ComparisonService(service.db_path)
    diagnostics = DiagnosticsService(service.db_path)
    workbench = WorkbenchService(service.db_path)
    ask = AskService(service.db_path)
    source_robustness = SourceRobustnessService(service.db_path)
    attention = AttentionService(service.db_path)
    hypotheses = HypothesisService(service.db_path)
    experience = ExperienceService(service.db_path)
    research_prioritization = ResearchPrioritizationService(service.db_path)
    analyses = ArticleAnalysisService(service.db_path)
    knowledge = KnowledgeService(service.db_path)
    corrections = StoryCorrectionService(service.db_path)

    def read_guard(request: Request):
        return require_user(request)

    def write_guard(request: Request):
        user = require_user(request)
        require_csrf(request, user)
        return user

    @router.get("/ask/conversations")
    async def ask_conversations(
        request: Request,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return ask.list_conversations(scope_type=scope_type, scope_id=scope_id, page=page, page_size=page_size)

    @router.post("/ask/conversations", status_code=201)
    async def create_ask_conversation(request: Request, payload: AskConversationCreate):
        write_guard(request)
        return ask.create_conversation(scope_type=payload.scope_type, scope_id=payload.scope_id)

    @router.get("/ask/conversations/{identifier}")
    async def get_ask_conversation(request: Request, identifier: str):
        read_guard(request)
        return ask.get_conversation(identifier)

    @router.post("/ask/conversations/{identifier}/turns", status_code=201)
    async def create_ask_turn(request: Request, identifier: str, payload: AskTurnCreate):
        write_guard(request)
        return ask.ask(
            identifier,
            payload.prompt,
            context_budget=payload.context_budget,
            provider_mode=payload.provider_mode,
            cost_cap_usd=payload.cost_cap_usd,
            as_of=payload.as_of,
        )

    @router.post("/ask", status_code=201)
    async def ask_direct(request: Request, payload: AskDirectCreate):
        write_guard(request)
        conversation = ask.create_conversation(scope_type=payload.scope_type, scope_id=payload.scope_id)
        result = ask.ask(
            conversation["id"],
            payload.prompt,
            context_budget=payload.context_budget,
            provider_mode=payload.provider_mode,
            cost_cap_usd=payload.cost_cap_usd,
            as_of=payload.as_of,
        )
        result["conversation_id"] = conversation["id"]
        return result

    @router.get("/ask/runs/{identifier}")
    async def get_ask_run(request: Request, identifier: str):
        read_guard(request)
        return ask.get_run(identifier)

    @router.post("/ask/runs/{identifier}/cancel")
    async def cancel_ask_run(request: Request, identifier: str):
        write_guard(request)
        return ask.cancel(identifier)

    @router.post("/ask/runs/{identifier}/research", status_code=201)
    async def research_from_ask(request: Request, identifier: str, payload: ResearchQuestionPursuitCreate):
        write_guard(request)
        run = ask.get_run(identifier)
        options = run.get("retrieval", {}).get("research_options", [])
        if not options and not payload.gap_id:
            raise DomainValidation("Ask run did not identify an open Research Question or Evidence Gap")
        question_id = next((item.get("question_id") for item in options if item.get("gap_id") == payload.gap_id), None) if payload.gap_id else next((item.get("question_id") for item in options), None)
        if question_id is None:
            raise DomainValidation("gap_id is not an open gap identified by this Ask run")
        values = payload.model_dump()
        values["gap_id"] = payload.gap_id or options[0].get("gap_id")
        return research.pursue(question_id, **values)

    @router.get("/search")
    async def search_workspace(
        request: Request,
        q: str = Query(..., min_length=1, max_length=500),
        entity_type: Optional[list[str]] = Query(default=None),
        source_id: Optional[str] = None,
        story_id: Optional[str] = None,
        subject_id: Optional[str] = None,
        monitor_id: Optional[str] = None,
        question_id: Optional[str] = None,
        tag_id: Optional[str] = None,
        document_id: Optional[str] = None,
        state: Optional[str] = None,
        assessment_state: Optional[str] = None,
        lifecycle: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return search.search(
            q,
            entity_types=entity_type,
            source_id=source_id,
            story_id=story_id,
            subject_id=subject_id,
            monitor_id=monitor_id,
            question_id=question_id,
            tag_id=tag_id,
            document_id=document_id,
            state=state,
            assessment_state=assessment_state,
            lifecycle=lifecycle,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )

    @router.get("/entities")
    async def entities(
        request: Request,
        q: Optional[str] = None,
        entity_type: Optional[str] = None,
        status: Optional[str] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return knowledge.list_entities(q=q, entity_type=entity_type, status=status, page=page, page_size=page_size)

    @router.post("/entities", status_code=201)
    async def create_entity(request: Request, payload: EntityCreate):
        write_guard(request)
        return knowledge.create_entity(payload.model_dump(exclude_none=True))

    @router.get("/entities/{identifier}")
    async def entity_detail(request: Request, identifier: str):
        read_guard(request)
        return knowledge.get_entity(identifier)

    @router.post("/entities/{identifier}/aliases", status_code=201)
    async def entity_alias(request: Request, identifier: str, payload: EntityAliasInput):
        write_guard(request)
        return knowledge.add_alias(identifier, payload.model_dump(exclude_none=True))

    @router.post("/entities/{identifier}/tags", status_code=201)
    async def entity_tag(request: Request, identifier: str, payload: TagAssignmentCreate):
        write_guard(request)
        if payload.tag_id is None or payload.object_type != "entity" or payload.object_id != identifier:
            raise DomainValidation("Entity tag assignment must target the path Entity")
        return knowledge.assign_tag(payload.tag_id, "entity", identifier, origin=payload.origin, confidence=payload.confidence, reason=payload.reason)

    @router.post("/tags/{identifier}/assignments", status_code=201)
    async def tag_assignment(request: Request, identifier: str, payload: TagAssignmentCreate):
        write_guard(request)
        return knowledge.assign_tag(identifier, payload.object_type, payload.object_id, origin=payload.origin, confidence=payload.confidence, reason=payload.reason)

    @router.post("/claims/{claim_id}/entities", status_code=201)
    async def claim_entity_link(request: Request, claim_id: str, payload: EntityLinkCreate):
        write_guard(request)
        return knowledge.link_claim_entity(claim_id, payload.entity_id, role=payload.role, origin="user")

    @router.post("/research-questions/{identifier}/entities", status_code=201)
    async def research_question_entity_link(request: Request, identifier: str, payload: EntityLinkCreate):
        write_guard(request)
        return knowledge.link_research_question_entity(identifier, payload.entity_id, origin="user")

    @router.post("/watches/{identifier}/entities", status_code=201)
    async def watch_entity_link(request: Request, identifier: str, payload: EntityLinkCreate):
        write_guard(request)
        return knowledge.link_watch_entity(identifier, payload.entity_id, origin="user")

    @router.post("/entities/backfill", status_code=202)
    async def start_knowledge_backfill(request: Request, payload: KnowledgeBackfillCreate):
        write_guard(request)
        return knowledge.start_backfill(payload.kind, row_limit=payload.row_limit, batch_size=payload.batch_size)

    @router.get("/entities/backfill/{identifier}")
    async def knowledge_backfill(request: Request, identifier: str):
        read_guard(request)
        return knowledge.get_backfill(identifier)

    @router.post("/entities/backfill/{identifier}/run")
    async def run_knowledge_backfill(request: Request, identifier: str):
        write_guard(request)
        return knowledge.run_backfill(identifier)

    @router.post("/comparisons")
    @router.post("/compare")
    @router.post("/documents/compare")
    async def compare_documents(request: Request, payload: ComparisonCreate):
        read_guard(request)
        return comparisons.compare(payload.document_ids, story_id=payload.story_id)

    @router.post("/workbench/notes", status_code=201)
    async def create_workbench_note(request: Request, payload: NoteCreate):
        write_guard(request)
        return workbench.add_note(payload.object_type, payload.object_id, payload.body, note_type=payload.note_type)

    @router.get("/subjects/{identifier}/workbench")
    async def subject_workbench(request: Request, identifier: str):
        read_guard(request)
        return workbench.subject_page(identifier)

    @router.get("/subjects/{identifier}/timeline")
    async def subject_timeline(request: Request, identifier: str):
        read_guard(request)
        return {"items": workbench.timeline("subject", identifier)}

    @router.get("/subjects/{identifier}/historical-context")
    async def subject_historical_context(request: Request, identifier: str):
        read_guard(request)
        return workbench.historical_context(identifier)

    @router.get("/diagnostics/health")
    async def diagnostics_health(request: Request):
        read_guard(request)
        return diagnostics.health()

    @router.get("/diagnostics/monitor-health")
    async def diagnostics_monitor_health(request: Request):
        read_guard(request)
        return diagnostics.monitor_health()

    @router.get("/diagnostics/metrics")
    async def diagnostics_metrics(request: Request):
        read_guard(request)
        return diagnostics.metrics()

    @router.get("/monitors/{identifier}/diagnostics")
    async def monitor_diagnostics(request: Request, identifier: str):
        read_guard(request)
        return diagnostics.monitor(identifier)

    @router.get("/categories")
    async def categories(
        request: Request,
        q: Optional[str] = None,
        slug: Optional[str] = None,
        include_deleted: bool = False,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return service.list_categories(q=q, slug=slug, include_deleted=include_deleted, page=page, page_size=page_size)

    @router.post("/categories", status_code=201)
    async def create_category(request: Request, payload: CategoryCreate):
        write_guard(request)
        return service.create_category(payload.model_dump())

    @router.get("/categories/{identifier}")
    async def category(request: Request, identifier: str, include_deleted: bool = False):
        read_guard(request)
        return service.get_category(identifier, include_deleted=include_deleted)

    @router.patch("/categories/{identifier}")
    async def patch_category(request: Request, identifier: str, payload: CategoryPatch):
        write_guard(request)
        return service.update_category(identifier, _patch_data(payload))

    @router.delete("/categories/{identifier}", status_code=204)
    async def delete_category(request: Request, identifier: str):
        write_guard(request)
        service.delete_category(identifier)
        return Response(status_code=204)

    @router.get("/topics")
    async def topics(
        request: Request,
        category_id: Optional[str] = None,
        q: Optional[str] = None,
        include_deleted: bool = False,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return service.list_topics(category_id=category_id, q=q, include_deleted=include_deleted, page=page, page_size=page_size)

    @router.post("/topics", status_code=201)
    async def create_topic(request: Request, payload: TopicCreate):
        write_guard(request)
        return service.create_topic(payload.model_dump())

    @router.get("/topics/{identifier}")
    async def topic(request: Request, identifier: str, include_deleted: bool = False):
        read_guard(request)
        return service.get_topic(identifier, include_deleted=include_deleted)

    @router.patch("/topics/{identifier}")
    async def patch_topic(request: Request, identifier: str, payload: TopicPatch):
        write_guard(request)
        return service.update_topic(identifier, _patch_data(payload))

    @router.delete("/topics/{identifier}", status_code=204)
    async def delete_topic(request: Request, identifier: str):
        write_guard(request)
        service.delete_topic(identifier)
        return Response(status_code=204)

    @router.get("/topics/{topic_id}/vocabulary")
    async def vocabulary(request: Request, topic_id: str, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100)):
        read_guard(request)
        return service.list_vocabulary(topic_id, page=page, page_size=page_size)

    @router.post("/topics/{topic_id}/vocabulary", status_code=201)
    async def create_vocabulary(request: Request, topic_id: str, payload: VocabularyCreate):
        write_guard(request)
        return service.create_vocabulary(topic_id, payload.model_dump())

    @router.patch("/topics/{topic_id}/vocabulary/{term_id}")
    async def patch_vocabulary(request: Request, topic_id: str, term_id: str, payload: VocabularyPatch):
        write_guard(request)
        term = service.get_vocabulary_item(term_id)
        if term["topic_id"] != topic_id:
            from .domain import DomainNotFound
            raise DomainNotFound("vocabulary term not found")
        return service.update_vocabulary(term_id, _patch_data(payload))

    @router.delete("/topics/{topic_id}/vocabulary/{term_id}", status_code=204)
    async def delete_vocabulary(request: Request, topic_id: str, term_id: str):
        write_guard(request)
        term = service.get_vocabulary_item(term_id)
        if term["topic_id"] != topic_id:
            from .domain import DomainNotFound
            raise DomainNotFound("vocabulary term not found")
        service.delete_vocabulary(term_id)
        return Response(status_code=204)

    @router.post("/topics/{topic_id}/scope-suggestions", status_code=201)
    async def create_scope_suggestion(request: Request, topic_id: str, payload: ScopeSuggestionCreate):
        write_guard(request)
        return service.create_scope_suggestion(topic_id, payload.model_dump())

    @router.post("/topics/{topic_id}/scope-suggestions/assist", status_code=201)
    async def assist_scope_suggestions(request: Request, topic_id: str, payload: ScopeSuggestionAssist):
        write_guard(request)
        return {"items": vocabulary_service.suggest_from_text(topic_id, payload.text, limit=payload.limit)}

    @router.get("/topics/{topic_id}/vocabulary-suggestions")
    async def vocabulary_suggestions(request: Request, topic_id: str, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
        read_guard(request)
        return vocabulary_service.list(topic_id, page=page, page_size=page_size)

    @router.post("/topics/{topic_id}/vocabulary-suggestions", status_code=201)
    async def create_vocabulary_suggestion(request: Request, topic_id: str, payload: VocabularySuggestionCreate):
        write_guard(request)
        return vocabulary_service.create(topic_id, payload.model_dump())

    @router.post("/topics/{topic_id}/vocabulary-suggestions/{suggestion_id}/approve")
    async def approve_vocabulary_suggestion(request: Request, topic_id: str, suggestion_id: str):
        user = write_guard(request)
        suggestion = vocabulary_service.get(suggestion_id)
        if suggestion["topic_id"] != topic_id:
            from .domain import DomainNotFound
            raise DomainNotFound("vocabulary suggestion not found")
        return vocabulary_service.review(suggestion_id, approved=True, reviewed_by=user.user_id)

    @router.post("/topics/{topic_id}/vocabulary-suggestions/{suggestion_id}/reject")
    async def reject_vocabulary_suggestion(request: Request, topic_id: str, suggestion_id: str):
        user = write_guard(request)
        suggestion = vocabulary_service.get(suggestion_id)
        if suggestion["topic_id"] != topic_id:
            from .domain import DomainNotFound
            raise DomainNotFound("vocabulary suggestion not found")
        return vocabulary_service.review(suggestion_id, approved=False, reviewed_by=user.user_id)

    @router.get("/topics/{topic_id}/scope-suggestions")
    async def scope_suggestions(request: Request, topic_id: str, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
        read_guard(request)
        return service.list_scope_suggestions(topic_id, page=page, page_size=page_size)

    @router.post("/topics/{topic_id}/scope-suggestions/{suggestion_id}/approve")
    async def approve_scope_suggestion(request: Request, topic_id: str, suggestion_id: str):
        user = write_guard(request)
        suggestion = service.get_scope_suggestion(suggestion_id)
        if suggestion["topic_id"] != topic_id:
            from .domain import DomainNotFound
            raise DomainNotFound("scope suggestion not found")
        return service.review_scope_suggestion(suggestion_id, approved=True, reviewed_by=user.user_id)

    @router.post("/topics/{topic_id}/scope-suggestions/{suggestion_id}/reject")
    async def reject_scope_suggestion(request: Request, topic_id: str, suggestion_id: str):
        user = write_guard(request)
        suggestion = service.get_scope_suggestion(suggestion_id)
        if suggestion["topic_id"] != topic_id:
            from .domain import DomainNotFound
            raise DomainNotFound("scope suggestion not found")
        return service.review_scope_suggestion(suggestion_id, approved=False, reviewed_by=user.user_id)

    @router.get("/subjects")
    async def subjects(
        request: Request,
        q: Optional[str] = None,
        subject_type: Optional[str] = None,
        include_deleted: bool = False,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return service.list_subjects(q=q, subject_type=subject_type, include_deleted=include_deleted, page=page, page_size=page_size)

    @router.post("/subjects", status_code=201)
    async def create_subject(request: Request, payload: SubjectCreate):
        write_guard(request)
        return service.create_subject(payload.model_dump())

    @router.get("/subjects/{identifier}")
    async def subject(request: Request, identifier: str, include_deleted: bool = False):
        read_guard(request)
        return service.get_subject(identifier, include_deleted=include_deleted)

    @router.patch("/subjects/{identifier}")
    async def patch_subject(request: Request, identifier: str, payload: SubjectPatch):
        write_guard(request)
        return service.update_subject(identifier, _patch_data(payload))

    @router.post("/subjects/{identifier}/aliases", status_code=201)
    async def add_alias(request: Request, identifier: str, payload: AliasCreate):
        write_guard(request)
        return service.add_subject_alias(identifier, payload.alias)

    @router.delete("/subjects/{identifier}", status_code=204)
    async def delete_subject(request: Request, identifier: str):
        write_guard(request)
        service.delete_subject(identifier)
        return Response(status_code=204)

    @router.get("/sources")
    async def sources(
        request: Request,
        q: Optional[str] = None,
        include_deleted: bool = False,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return service.list_sources(q=q, include_deleted=include_deleted, page=page, page_size=page_size)

    @router.post("/sources", status_code=201)
    async def create_source(request: Request, payload: SourceCreate):
        write_guard(request)
        return service.create_source(payload.model_dump())

    @router.get("/sources/{identifier}")
    async def source(request: Request, identifier: str, include_deleted: bool = False):
        read_guard(request)
        return service.get_source(identifier, include_deleted=include_deleted)

    @router.patch("/sources/{identifier}")
    async def patch_source(request: Request, identifier: str, payload: SourcePatch):
        write_guard(request)
        return service.update_source(identifier, _patch_data(payload))

    @router.get("/sources/{identifier}/profile")
    async def source_profile(request: Request, identifier: str):
        read_guard(request)
        return profiles.get(identifier)

    @router.get("/sources/{identifier}/source-robustness")
    async def source_robustness_summary(request: Request, identifier: str):
        read_guard(request)
        return source_robustness.source_summary(identifier)

    @router.post("/sources/{identifier}/acquire", status_code=201)
    async def acquire_source_document(request: Request, identifier: str, payload: AcquisitionCreate):
        write_guard(request)
        try:
            return asdict(acquisition.acquire_document(identifier, payload.url, channel=payload.channel))
        except AcquisitionError as exc:
            raise DomainValidation(f"acquisition failed safely: {type(exc).__name__}") from exc

    @router.post("/sources/{identifier}/feed/poll", status_code=201)
    async def poll_source_feed(request: Request, identifier: str, payload: FeedPollCreate):
        write_guard(request)
        try:
            return asdict(acquisition.poll_feed(identifier, payload.feed_url))
        except AcquisitionError as exc:
            raise DomainValidation(f"feed poll failed safely: {type(exc).__name__}") from exc

    @router.delete("/sources/{identifier}", status_code=204)
    async def delete_source(request: Request, identifier: str):
        write_guard(request)
        service.delete_source(identifier)
        return Response(status_code=204)

    @router.get("/documents")
    async def documents(
        request: Request,
        source_id: Optional[str] = None,
        q: Optional[str] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return service.list_documents(source_id=source_id, q=q, page=page, page_size=page_size)

    @router.post("/documents", status_code=201)
    async def create_document(request: Request, payload: DocumentCreate):
        write_guard(request)
        return service.create_document(payload.model_dump())

    @router.get("/documents/{identifier}")
    async def document(request: Request, identifier: str):
        read_guard(request)
        return service.get_document(identifier)

    @router.patch("/documents/{identifier}")
    async def patch_document(request: Request, identifier: str, payload: DocumentPatch):
        write_guard(request)
        return service.update_document(identifier, _patch_data(payload))

    @router.get("/documents/{document_id}/versions")
    async def document_versions(
        request: Request,
        document_id: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return ledger.list_document_versions(document_id, page=page, page_size=page_size)

    @router.get("/documents/{document_id}/lineage")
    async def document_lineage(request: Request, document_id: str):
        read_guard(request)
        return evolution.lineage(document_id)

    @router.get("/documents/{document_id}/dependencies")
    async def document_dependencies(request: Request, document_id: str):
        read_guard(request)
        return source_robustness.dependency_summary(document_id)

    @router.post("/documents/{document_id}/lineage", status_code=201)
    async def create_document_lineage(request: Request, document_id: str, payload: LineageCreate):
        write_guard(request)
        return evolution.link_lineage(
            document_id,
            payload.parent_document_id,
            payload.relationship,
            confidence=payload.confidence,
            rationale=payload.rationale,
        )

    @router.post("/documents/{document_id}/versions", status_code=201)
    async def create_document_version(request: Request, document_id: str, payload: DocumentVersionCreate):
        write_guard(request)
        return ledger.create_document_version(document_id, payload.model_dump())

    @router.get("/document-versions/{identifier}")
    async def document_version(request: Request, identifier: str):
        read_guard(request)
        return ledger.get_document_version(identifier)

    @router.get("/document-versions/{document_version_id}/evidence-spans")
    async def evidence_spans(
        request: Request,
        document_version_id: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(100, ge=1, le=100),
    ):
        read_guard(request)
        return ledger.list_evidence_spans(document_version_id, page=page, page_size=page_size)

    @router.post("/document-versions/{document_version_id}/evidence-spans", status_code=201)
    async def create_evidence_span(request: Request, document_version_id: str, payload: EvidenceSpanCreate):
        write_guard(request)
        return ledger.create_evidence_span(document_version_id, payload.model_dump())

    @router.get("/evidence-spans/{identifier}")
    async def evidence_span(request: Request, identifier: str):
        read_guard(request)
        return ledger.get_evidence_span(identifier)

    @router.get("/document-versions/{document_version_id}/analyses")
    async def document_version_analyses(
        request: Request,
        document_version_id: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return analyses.list_for_document_version(
            document_version_id, page=page, page_size=page_size
        )

    @router.get("/article-analyses/{identifier}")
    async def article_analysis_detail(request: Request, identifier: str):
        read_guard(request)
        return analyses.get(identifier)

    @router.get("/research-questions")
    async def research_questions(
        request: Request,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        origin_type: Optional[str] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return research.list(status=status, priority=priority, origin_type=origin_type, page=page, page_size=page_size)

    @router.post("/research-questions", status_code=201)
    async def create_research_question(request: Request, payload: ResearchQuestionCreate):
        user = write_guard(request)
        return research.create(payload.model_dump(), actor=user.user_id)

    @router.post("/research-questions/pursue-due")
    async def pursue_due_research_questions(request: Request):
        write_guard(request)
        return research.pursue_due()

    @router.get("/research-questions/{identifier}/history")
    async def research_question_history(request: Request, identifier: str):
        read_guard(request)
        return {"items": research.get(identifier)["history"]}

    @router.get("/research-questions/{identifier}/assessment")
    async def research_question_assessment(request: Request, identifier: str):
        read_guard(request)
        item = research.get(identifier)
        return {
            "question_id": identifier,
            "state": item.get("assessment_state"),
            "assessment_hash": item.get("assessment_hash"),
            "assessment_at": item.get("assessment_at"),
            "explanation": item.get("assessment_explanation", ""),
            "history": item.get("assessment_history", []),
        }

    @router.get("/research-questions/{identifier}/hypotheses")
    async def list_hypotheses(request: Request, identifier: str, status: Optional[str] = None, limit: int = Query(100, ge=1, le=500)):
        read_guard(request)
        return hypotheses.list(identifier, status=status, limit=limit)

    @router.get("/research-questions/{identifier}/priorities")
    async def research_question_priorities(request: Request, identifier: str, limit: int = Query(100, ge=1, le=500)):
        read_guard(request)
        return research_prioritization.prioritize(identifier, limit=limit)

    @router.post("/research-questions/{identifier}/hypotheses", status_code=201)
    async def create_hypothesis(request: Request, identifier: str, payload: HypothesisCreate):
        write_guard(request)
        return hypotheses.create(identifier, payload.statement, origin=payload.origin, provider_route=payload.provider_route)

    @router.post("/research-questions/{identifier}/evaluate")
    async def evaluate_research_question(request: Request, identifier: str):
        write_guard(request)
        return research.evaluate(identifier, origin="manual")

    @router.get("/research-questions/{identifier}/gaps")
    async def research_question_gaps(
        request: Request,
        identifier: str,
        status: Optional[str] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=200),
    ):
        read_guard(request)
        return research.list_gaps(identifier, status=status, page=page, page_size=page_size)

    @router.post("/research-questions/{identifier}/gaps/{gap_id}/review")
    async def review_research_question_gap(request: Request, identifier: str, gap_id: str, payload: ResearchQuestionGapReview):
        user = write_guard(request)
        return research.set_gap_status(
            gap_id,
            payload.status,
            question_id=identifier,
            actor=user.user_id,
            reason=payload.reason,
        )

    @router.post("/research-questions/{identifier}/gaps/{gap_id}/pursue", status_code=201)
    async def pursue_research_question_gap(request: Request, identifier: str, gap_id: str, payload: ResearchQuestionPursuitCreate):
        write_guard(request)
        values = payload.model_dump()
        values["gap_id"] = gap_id
        return research.pursue(identifier, **values)

    @router.get("/research-questions/{identifier}/attempts")
    async def research_question_attempts(request: Request, identifier: str):
        read_guard(request)
        return {"items": research.get(identifier)["attempts"]}

    @router.get("/research-questions/{identifier}/tasks")
    async def research_question_tasks(
        request: Request,
        identifier: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=200),
    ):
        read_guard(request)
        return research.list_tasks(identifier, page=page, page_size=page_size)

    @router.get("/research-questions/{identifier}/tasks/{task_id}")
    async def research_question_task(request: Request, identifier: str, task_id: str):
        read_guard(request)
        return research.get_task(identifier, task_id)

    @router.get("/research-questions/{identifier}/notes")
    async def research_question_notes(request: Request, identifier: str):
        read_guard(request)
        return {"items": research.get(identifier)["notes"]}

    @router.get("/research-questions/{identifier}")
    async def get_research_question(request: Request, identifier: str):
        read_guard(request)
        return research.get(identifier)

    @router.patch("/research-questions/{identifier}")
    async def patch_research_question(request: Request, identifier: str, payload: ResearchQuestionPatch):
        write_guard(request)
        return research.update(identifier, _patch_data(payload))

    @router.post("/research-questions/{identifier}/resolve")
    async def resolve_research_question(request: Request, identifier: str, payload: ResearchQuestionTransition):
        user = write_guard(request)
        for claim_id in payload.claim_ids:
            research.link_claim(identifier, claim_id, "resolves")
        for evidence_span_id in payload.evidence_span_ids:
            research.link_evidence(identifier, evidence_span_id, "resolves")
        return research.resolve(identifier, payload.reason, actor=user.user_id)

    @router.post("/research-questions/{identifier}/abandon")
    async def abandon_research_question(request: Request, identifier: str, payload: ResearchQuestionTransition):
        user = write_guard(request)
        return research.abandon(identifier, payload.reason, actor=user.user_id)

    @router.post("/research-questions/{identifier}/reopen")
    async def reopen_research_question(request: Request, identifier: str, payload: ResearchQuestionTransition):
        user = write_guard(request)
        return research.reopen(identifier, payload.reason, actor=user.user_id)

    @router.post("/research-questions/{identifier}/claims", status_code=201)
    async def link_research_question_claim(request: Request, identifier: str, payload: ResearchQuestionClaimLinkCreate):
        write_guard(request)
        return research.link_claim(identifier, payload.claim_id, payload.relationship)

    @router.post("/hypotheses/{identifier}/claims/{claim_id}", status_code=201)
    async def link_hypothesis_claim(request: Request, identifier: str, claim_id: str, payload: HypothesisClaimLinkCreate):
        write_guard(request)
        return hypotheses.link_claim(identifier, claim_id, payload.relationship)

    @router.post("/hypotheses/{identifier}/gaps", status_code=201)
    async def create_hypothesis_gap(request: Request, identifier: str, payload: HypothesisGapCreate):
        write_guard(request)
        return hypotheses.add_gap(identifier, payload.description)

    @router.get("/hypotheses/{identifier}/compare/{other_identifier}")
    async def compare_hypotheses(request: Request, identifier: str, other_identifier: str):
        read_guard(request)
        return hypotheses.compare(identifier, other_identifier)

    @router.get("/hypotheses/{identifier}")
    async def get_hypothesis(request: Request, identifier: str):
        read_guard(request)
        return hypotheses.get(identifier)

    @router.post("/hypotheses/{identifier}/review")
    async def review_hypothesis(request: Request, identifier: str, payload: HypothesisReviewWrite):
        user = write_guard(request)
        return hypotheses.review(identifier, payload.status, actor=user.user_id, reason=payload.reason)

    @router.post("/research-questions/{identifier}/claims/{claim_id}/correction")
    async def correct_research_question_claim(request: Request, identifier: str, claim_id: str, payload: ResearchQuestionClaimCorrection):
        user = write_guard(request)
        return research.correct_claim_link(
            identifier, claim_id, payload.relationship,
            action=payload.action, actor=user.user_id, reason=payload.reason,
        )

    @router.post("/research-questions/{identifier}/evidence", status_code=201)
    async def link_research_question_evidence(request: Request, identifier: str, payload: ResearchQuestionEvidenceLinkCreate):
        write_guard(request)
        return research.link_evidence(identifier, payload.evidence_span_id, payload.relationship)

    @router.post("/research-questions/{identifier}/notes", status_code=201)
    async def add_research_question_note(request: Request, identifier: str, payload: ResearchQuestionNoteCreate):
        write_guard(request)
        return research.add_note(identifier, payload.body, note_type=payload.note_type)

    @router.post("/research-questions/{identifier}/pursue", status_code=201)
    async def pursue_research_question(request: Request, identifier: str, payload: ResearchQuestionPursuitCreate):
        write_guard(request)
        return research.pursue(identifier, **payload.model_dump())

    @router.post("/research-question-attempts/{attempt_id}")
    async def record_research_question_attempt(request: Request, attempt_id: str, payload: ResearchQuestionAttemptWrite):
        write_guard(request)
        return research.record_attempt(attempt_id, **payload.model_dump())

    @router.get("/reports")
    async def living_reports(
        request: Request,
        status: Optional[str] = None,
        target_type: Optional[str] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return reports.list(status=status, target_type=target_type, page=page, page_size=page_size)

    @router.post("/reports", status_code=201)
    async def create_living_report(request: Request, payload: LivingReportCreate):
        write_guard(request)
        return reports.create(payload.model_dump())

    @router.get("/reports/{identifier}")
    async def get_living_report(request: Request, identifier: str):
        read_guard(request)
        return reports.get(identifier)

    @router.post("/reports/{identifier}/generate")
    async def generate_living_report(request: Request, identifier: str):
        write_guard(request)
        result = reports.generate(identifier)
        revision = result.get("current_revision")
        if revision is not None:
            alerts.emit_for_report_revision(identifier, revision["id"])
        return result

    @router.get("/reports/{identifier}/revisions")
    async def living_report_revisions(request: Request, identifier: str):
        read_guard(request)
        return {"items": reports.get(identifier)["revisions"]}

    @router.post("/reports/{identifier}/archive")
    async def archive_living_report(request: Request, identifier: str):
        write_guard(request)
        return reports.archive(identifier)

    @router.post("/briefings/generate", status_code=201)
    async def generate_briefing(request: Request, payload: BriefingGenerate):
        write_guard(request)
        return briefings.generate(**payload.model_dump())

    @router.get("/briefings/{identifier}")
    async def get_briefing(request: Request, identifier: str):
        read_guard(request)
        return briefings.get(identifier)

    @router.get("/alert-rules")
    async def alert_rules(request: Request, enabled: Optional[bool] = None):
        read_guard(request)
        return {"items": alerts.list_rules(enabled=enabled)}

    @router.post("/alert-rules", status_code=201)
    async def create_alert_rule(request: Request, payload: AlertRuleCreate):
        write_guard(request)
        return alerts.create_rule(payload.model_dump())

    @router.patch("/alert-rules/{identifier}")
    async def patch_alert_rule(request: Request, identifier: str, payload: AlertRulePatch):
        write_guard(request)
        return alerts.update_rule(identifier, _patch_data(payload))

    @router.get("/alerts")
    async def list_alerts(
        request: Request,
        status: Optional[str] = None,
        min_importance: Optional[float] = Query(None, ge=0, le=1),
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return alerts.list_alerts(status=status, min_importance=min_importance, page=page, page_size=page_size)

    @router.get("/alerts/{identifier}")
    async def get_alert(request: Request, identifier: str):
        read_guard(request)
        return alerts.get_alert(identifier)

    @router.post("/alerts/{identifier}/acknowledge")
    async def acknowledge_alert(request: Request, identifier: str):
        user = write_guard(request)
        return alerts.acknowledge(identifier, acknowledged_by=user.user_id)

    @router.post("/alert-deliveries/{identifier}")
    async def record_alert_delivery(request: Request, identifier: str, payload: AlertDeliveryWrite):
        write_guard(request)
        return alerts.record_delivery(identifier, **payload.model_dump())

    @router.get("/notification-preferences")
    async def notification_preferences(request: Request):
        read_guard(request)
        return alerts.get_notification_preferences()

    @router.put("/notification-preferences")
    async def put_notification_preferences(request: Request, payload: NotificationPreferencesWrite):
        write_guard(request)
        return alerts.set_notification_preferences(payload.model_dump())

    @router.get("/stories/{story_id}/research-gaps")
    async def story_research_gaps(request: Request, story_id: str):
        read_guard(request)
        return {"items": research.detect_gaps(story_id=story_id)}

    @router.get("/claims/{claim_id}/research-gaps")
    async def claim_research_gaps(request: Request, claim_id: str):
        read_guard(request)
        return {"items": research.detect_gaps(claim_id=claim_id)}

    @router.get("/research-gap-suggestions")
    async def research_gap_suggestions(
        request: Request,
        origin_type: Optional[str] = None,
        origin_id: Optional[str] = None,
        question_id: Optional[str] = None,
        status: Optional[str] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=200),
    ):
        read_guard(request)
        return research.list_suggestions(
            origin_type=origin_type,
            origin_id=origin_id,
            question_id=question_id,
            status=status,
            page=page,
            page_size=page_size,
        )

    @router.post("/research-gap-suggestions/{identifier}/review")
    async def review_research_gap_suggestion(request: Request, identifier: str, payload: ResearchGapSuggestionReview):
        user = write_guard(request)
        return research.review_suggestion(identifier, payload.status, reviewed_by=user.user_id)

    @router.post("/research-gap-suggestions/{identifier}/convert", status_code=201)
    async def convert_research_gap_suggestion(request: Request, identifier: str, payload: ResearchGapSuggestionConvert):
        user = write_guard(request)
        return research.convert_suggestion(
            identifier,
            priority=payload.priority,
            search_attempt_budget=payload.search_attempt_budget,
            actor=user.user_id,
        )

    @router.get("/stories")
    async def stories(
        request: Request,
        q: Optional[str] = None,
        lifecycle: Optional[str] = None,
        include_deleted: bool = False,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return service.list_stories(q=q, lifecycle=lifecycle, include_deleted=include_deleted, page=page, page_size=page_size)

    @router.post("/stories", status_code=201)
    async def create_story(request: Request, payload: StoryCreate):
        write_guard(request)
        return service.create_story(payload.model_dump())

    @router.get("/stories/{story_id}/claims")
    async def story_claims(
        request: Request,
        story_id: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(100, ge=1, le=100),
    ):
        read_guard(request)
        return ledger.list_claims(story_id, page=page, page_size=page_size)

    @router.get("/claims")
    async def claims(
        request: Request,
        state: Optional[str] = None,
        assignment: Optional[str] = None,
        provenance: Optional[str] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return ledger.list_all_claims(
            state=state,
            assignment=assignment,
            provenance=provenance,
            page=page,
            page_size=page_size,
        )

    @router.post("/stories/{story_id}/claims", status_code=201)
    async def create_claim(request: Request, story_id: str, payload: ClaimCreate):
        write_guard(request)
        return ledger.create_claim(story_id, payload.model_dump())

    @router.post("/claims/{identifier}/reassign")
    async def reassign_claim(request: Request, identifier: str, payload: ClaimStoryCorrectionWrite):
        user = write_guard(request)
        if payload.story_id is None:
            raise DomainValidation("story_id is required for reassignment")
        return corrections.reassign_claim(
            identifier,
            payload.story_id,
            actor=user.user_id,
            reason=payload.reason,
            expected_from_story_id=payload.expected_from_story_id,
        )

    @router.post("/claims/{identifier}/unassign")
    async def unassign_claim(request: Request, identifier: str, payload: ClaimStoryCorrectionWrite | None = None):
        user = write_guard(request)
        values = payload or ClaimStoryCorrectionWrite()
        return corrections.unassign_claim(
            identifier,
            actor=user.user_id,
            reason=values.reason,
            expected_from_story_id=values.expected_from_story_id,
        )

    @router.get("/stories/{story_id}/evidence")
    async def story_evidence(request: Request, story_id: str):
        read_guard(request)
        return ledger.get_story_evidence(story_id)

    @router.get("/stories/{story_id}/timeline")
    async def story_timeline(request: Request, story_id: str):
        read_guard(request)
        return evolution.timeline(story_id)

    @router.get("/stories/{story_id}/corroboration")
    async def story_corroboration(request: Request, story_id: str, claim_id: Optional[str] = None):
        read_guard(request)
        return evolution.corroboration(story_id, claim_id=claim_id)

    @router.get("/stories/{story_id}/corrections")
    async def story_corrections(request: Request, story_id: str, limit: int = Query(100, ge=1, le=500)):
        read_guard(request)
        return {"items": corrections.correction_history(story_id, limit=limit)}

    @router.get("/stories/{story_id}/lineage")
    async def story_lineage(request: Request, story_id: str):
        read_guard(request)
        return corrections.lineage(story_id)

    @router.get("/stories/{story_id}/duplicates")
    async def story_duplicates(request: Request, story_id: str, limit: int = Query(20, ge=1, le=100)):
        read_guard(request)
        return {"items": corrections.suggest_duplicates(story_id, limit=limit)}

    @router.get("/story-intelligence/metrics")
    async def story_intelligence_metrics(request: Request):
        read_guard(request)
        return corrections.metrics()

    @router.get("/stories/{story_id}/entities")
    async def story_entities(request: Request, story_id: str):
        read_guard(request)
        return corrections.story_entities(story_id)

    @router.post("/stories/{story_id}/entities", status_code=201)
    async def set_story_entity(request: Request, story_id: str, payload: StoryEntityWrite):
        user = write_guard(request)
        return corrections.set_manual_entity(story_id, payload.entity_id, origin=payload.origin)

    @router.delete("/stories/{story_id}/entities/{entity_id}", status_code=204)
    async def remove_story_entity(request: Request, story_id: str, entity_id: str):
        write_guard(request)
        corrections.remove_manual_entity(story_id, entity_id)
        return Response(status_code=204)

    @router.post("/stories/{story_id}/duplicates/approve")
    async def approve_duplicate(request: Request, story_id: str, payload: DuplicateDecisionWrite):
        user = write_guard(request)
        return corrections.approve_duplicate(
            story_id,
            payload.destination_story_id,
            evidence_hash=payload.evidence_hash,
            actor=user.user_id,
            reason=payload.reason,
            expected_source_updated_at=payload.expected_source_updated_at,
            metadata_decisions=payload.metadata_decisions,
        )

    @router.post("/stories/{story_id}/duplicates/dismiss")
    async def dismiss_duplicate(request: Request, story_id: str, payload: DuplicateDecisionWrite):
        user = write_guard(request)
        return corrections.dismiss_duplicate(
            story_id,
            payload.destination_story_id,
            evidence_hash=payload.evidence_hash,
            actor=user.user_id,
            reason=payload.reason,
        )

    @router.get("/stories/{story_id}/review")
    async def story_review(request: Request, story_id: str):
        read_guard(request)
        return evolution.review_state(story_id)

    @router.post("/stories/{story_id}/review")
    async def write_story_review(request: Request, story_id: str, payload: StoryReviewWrite):
        write_guard(request)
        return evolution.review(story_id, payload.review_status, payload.revision_id)

    @router.post("/stories/{story_id}/evolution", status_code=201)
    async def record_story_evolution(request: Request, story_id: str, payload: EvolutionObservationCreate):
        write_guard(request)
        return evolution.record_observation(
            story_id,
            payload.document_id,
            payload.update_class,
            candidate={
                "id": payload.document_id,
                "headline": "",
                "event_key": payload.event_key,
                "entities": payload.entities,
                "locations": payload.locations,
            },
            decision=payload.decision,
            revision_id=payload.revision_id,
            material_change=payload.material_change,
        )

    @router.post("/story-evolution/resolve")
    async def resolve_story_candidate(request: Request, payload: StoryResolutionCandidate):
        read_guard(request)
        candidate = StoryCandidate.from_mapping(payload.model_dump())
        return evolution.resolve(candidate).__dict__

    @router.post("/story-evolution/process", status_code=201)
    async def process_story_candidate(request: Request, payload: StoryEvolutionProcess):
        write_guard(request)
        values = payload.model_dump()
        document_id = values.pop("document_id")
        story_id = values.pop("story_id")
        update_class = values.pop("update_class")
        revision_id = values.pop("revision_id")
        return evolution.process(
            document_id,
            values,
            story_id=story_id,
            update_class=update_class,
            revision_id=revision_id,
        )

    @router.post("/stories/{identifier}/merge-preview")
    async def merge_story_preview(request: Request, identifier: str, payload: StoryMergeWrite):
        read_guard(request)
        return corrections.preview_merge(identifier, payload.destination_story_id, payload.metadata_decisions)

    @router.post("/stories/{identifier}/merge")
    async def merge_stories(request: Request, identifier: str, payload: StoryMergeWrite):
        user = write_guard(request)
        return corrections.merge_stories(
            identifier,
            payload.destination_story_id,
            actor=user.user_id,
            reason=payload.reason,
            expected_source_updated_at=payload.expected_source_updated_at,
            expected_current_state_fingerprint=payload.expected_current_state_fingerprint,
            metadata_decisions=payload.metadata_decisions,
        )

    @router.get("/stories/{identifier}/split-preview")
    async def split_story_preview(request: Request, identifier: str):
        read_guard(request)
        return corrections.preview_split(identifier)

    @router.post("/stories/{identifier}/split")
    async def split_story(request: Request, identifier: str, payload: StorySplitWrite):
        user = write_guard(request)
        preview = corrections.preview_split(identifier)
        if payload.expected_source_updated_at is not None and payload.expected_source_updated_at != preview["source"]["updated_at"]:
            raise DomainConflict("split preview is stale")
        expected = set(payload.expected_claim_ids or preview["expected_claim_ids"])
        actual = {item for group in payload.groups for item in group}
        if actual != expected:
            raise DomainConflict("split preview is stale")
        return corrections.split_story(
            identifier,
            payload.groups,
            actor=user.user_id,
            reason=payload.reason,
            child_metadata=[item.model_dump() for item in payload.child_metadata],
        )

    @router.post("/stories/{identifier}/extract")
    async def extract_story_claims(request: Request, identifier: str, payload: StoryExtractWrite):
        user = write_guard(request)
        return corrections.extract_claims(
            identifier,
            payload.claim_ids,
            payload.story.model_dump(),
            actor=user.user_id,
            reason=payload.reason,
        )

    @router.get("/stories/{identifier}")
    async def story(request: Request, identifier: str, include_deleted: bool = False):
        read_guard(request)
        return service.get_story(identifier, include_deleted=include_deleted)

    @router.get("/stories/{identifier}/source-robustness")
    async def story_source_robustness(request: Request, identifier: str):
        read_guard(request)
        return source_robustness.evidence_summary("story", identifier)

    @router.post("/stories/{identifier}/source-robustness/counterfactual")
    async def story_source_robustness_counterfactual(request: Request, identifier: str, payload: CounterfactualWrite):
        read_guard(request)
        return source_robustness.counterfactual(
            "story",
            identifier,
            exclude_document_ids=payload.exclude_document_ids,
            exclude_source_ids=payload.exclude_source_ids,
        )

    @router.patch("/stories/{identifier}")
    async def patch_story(request: Request, identifier: str, payload: StoryPatch):
        write_guard(request)
        return service.update_story(identifier, payload.model_dump())

    @router.delete("/stories/{identifier}", status_code=204)
    async def delete_story(request: Request, identifier: str):
        write_guard(request)
        service.delete_story(identifier)
        return Response(status_code=204)

    @router.get("/stories/{identifier}/revisions")
    async def story_revisions(request: Request, identifier: str):
        read_guard(request)
        return {"items": ledger.get_story_revisions(identifier)}

    @router.post("/stories/{identifier}/revisions", status_code=201)
    async def create_story_revision(request: Request, identifier: str, payload: StoryRevisionCreate):
        write_guard(request)
        return ledger.create_story_revision(identifier, payload.model_dump())

    @router.get("/claims/{identifier}")
    async def claim(request: Request, identifier: str):
        read_guard(request)
        return ledger.get_claim(identifier)

    @router.get("/claims/{identifier}/source-robustness")
    async def claim_source_robustness(request: Request, identifier: str):
        read_guard(request)
        return source_robustness.evidence_summary("claim", identifier)

    @router.post("/claims/{identifier}/source-robustness/counterfactual")
    async def claim_source_robustness_counterfactual(request: Request, identifier: str, payload: CounterfactualWrite):
        read_guard(request)
        return source_robustness.counterfactual(
            "claim",
            identifier,
            exclude_document_ids=payload.exclude_document_ids,
            exclude_source_ids=payload.exclude_source_ids,
        )

    @router.post("/claims/{identifier}/state")
    async def set_claim_state(request: Request, identifier: str, payload: ClaimStateWrite):
        write_guard(request)
        return ledger.set_claim_state(identifier, payload.state, payload.reason)

    @router.post("/claims/{identifier}/accept")
    async def accept_claim(request: Request, identifier: str):
        write_guard(request)
        return ledger.accept_claim(identifier)

    @router.get("/claims/{identifier}/evidence")
    async def claim_evidence(request: Request, identifier: str):
        read_guard(request)
        return {"items": ledger.get_claim(identifier)["evidence"]}

    @router.post("/claims/{identifier}/evidence", status_code=201)
    async def link_claim_evidence(request: Request, identifier: str, payload: ClaimEvidenceCreate):
        write_guard(request)
        return ledger.link_claim_evidence(identifier, payload.model_dump())

    @router.post("/runs/manual", status_code=201)
    async def manual_run(request: Request, payload: ManualRunCreate):
        write_guard(request)
        return ledger.run_manual(payload.model_dump())

    @router.get("/source-suggestions")
    async def source_suggestions(request: Request, status: Optional[str] = None):
        read_guard(request)
        return {"items": suggestions.list(status=status)}

    @router.post("/source-suggestions", status_code=201)
    async def create_source_suggestion(request: Request, payload: SourceSuggestionCreate):
        write_guard(request)
        return suggestions.create(payload.model_dump())

    @router.post("/source-suggestions/{identifier}/review")
    async def review_source_suggestion(request: Request, identifier: str, payload: SourceSuggestionReview):
        user = write_guard(request)
        return suggestions.review(identifier, payload.status, user.user_id)

    @router.get("/jobs")
    async def list_jobs(
        request: Request,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=200),
    ):
        read_guard(request)
        result = jobs.list(status=status, job_type=job_type, page=page, page_size=page_size)
        result["items"] = [_job_api_result(item) for item in result["items"]]
        return result

    @router.post("/jobs", status_code=201)
    async def create_job(request: Request, payload: JobCreate):
        write_guard(request)
        return jobs.enqueue(**payload.model_dump(exclude_none=True))

    @router.get("/jobs/{identifier}")
    async def get_job(request: Request, identifier: str):
        read_guard(request)
        return _job_api_result(jobs.get(identifier))

    @router.post("/jobs/{identifier}/cancel")
    async def cancel_job(request: Request, identifier: str):
        write_guard(request)
        return jobs.cancel(identifier)

    @router.post("/jobs/{identifier}/rerun", status_code=201)
    async def rerun_job(request: Request, identifier: str):
        write_guard(request)
        return jobs.rerun(identifier)

    @router.get("/monitoring-policies")
    async def list_monitoring_policies(request: Request, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
        read_guard(request)
        return policies.list(page=page, page_size=page_size)

    @router.post("/monitoring-policies", status_code=201)
    async def create_monitoring_policy(request: Request, payload: MonitoringPolicyCreate):
        write_guard(request)
        return policies.create(payload.model_dump())

    @router.get("/monitoring-policies/{identifier}")
    async def get_monitoring_policy(request: Request, identifier: str):
        read_guard(request)
        return policies.get(identifier)

    @router.patch("/monitoring-policies/{identifier}")
    async def patch_monitoring_policy(request: Request, identifier: str, payload: MonitoringPolicyPatch):
        write_guard(request)
        return policies.update(identifier, _patch_data(payload))

    @router.get("/monitors")
    async def list_monitors(request: Request, enabled: Optional[bool] = None, target_type: Optional[str] = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
        read_guard(request)
        return monitors.list(enabled=enabled, target_type=target_type, page=page, page_size=page_size)

    @router.get("/watches")
    async def list_watches(request: Request, status: Optional[str] = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
        read_guard(request)
        return watches.list(status=status, page=page, page_size=page_size)

    @router.post("/watches/setup", response_model=PausedWatchDraft, status_code=201)
    async def setup_watch(request: Request, payload: WatchSetupCreate, response: Response):
        write_guard(request)
        result = watches.create_paused_setup(payload.model_dump())
        if result["resumed"]:
            response.status_code = 200
        else:
            response.status_code = 201
        return result

    @router.post("/watches", status_code=201)
    async def create_watch(request: Request, payload: WatchCreate):
        write_guard(request)
        return watches.create(payload.model_dump())

    @router.get("/watches/{identifier}")
    async def get_watch(request: Request, identifier: str):
        read_guard(request)
        return watches.get(identifier)

    @router.post("/watches/{identifier}/story-resolution")
    async def resolve_watch_story_target(request: Request, identifier: str, payload: StoryTargetResolutionWrite):
        user = write_guard(request)
        return corrections.resolve_split_target(
            "watch",
            identifier,
            payload.selected_story_ids,
            disable=payload.disable,
            actor=user.user_id,
        )

    @router.patch("/watches/{identifier}")
    async def update_watch(request: Request, identifier: str, payload: WatchPatch):
        write_guard(request)
        return watches.update(identifier, payload.model_dump(exclude_unset=True))

    @router.get("/watches/{identifier}/health")
    async def get_watch_health(request: Request, identifier: str):
        read_guard(request)
        return watches.health(identifier)

    @router.get("/watches/{identifier}/query-plan")
    async def get_watch_query_plan(
        request: Request, identifier: str, limit: int = Query(12, ge=1, le=100)
    ):
        read_guard(request)
        return watches.query_plan(identifier, limit=limit)

    @router.get("/watches/{identifier}/vocabulary")
    async def list_watch_vocabulary(
        request: Request,
        identifier: str,
        status: Optional[str] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return watches.list_vocabulary(
            identifier, status=status, page=page, page_size=page_size
        )

    @router.get("/watches/{identifier}/sources")
    async def list_watch_sources(
        request: Request,
        identifier: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return watches.list_sources(identifier, page=page, page_size=page_size)

    @router.get("/watches/{identifier}/source-candidates")
    async def list_watch_source_candidates(
        request: Request,
        identifier: str,
        status: Optional[str] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=100),
    ):
        read_guard(request)
        return watches.list_source_candidates(
            identifier, status=status, page=page, page_size=page_size
        )

    @router.post("/watches/{identifier}/pause")
    async def pause_watch(request: Request, identifier: str):
        write_guard(request)
        return watches.pause(identifier)

    @router.post("/watches/{identifier}/resume")
    async def resume_watch(request: Request, identifier: str):
        write_guard(request)
        return watches.resume(identifier)

    @router.post("/watches/{identifier}/disable")
    async def disable_watch(request: Request, identifier: str):
        write_guard(request)
        return watches.disable(identifier)

    @router.post("/watches/{identifier}/vocabulary/suggest", status_code=201)
    async def suggest_watch_vocabulary(request: Request, identifier: str, payload: WatchVocabularySuggest):
        write_guard(request)
        return {"items": watches.suggest_vocabulary(identifier, limit=payload.limit)}

    @router.post("/watches/{identifier}/vocabulary", status_code=201)
    async def create_watch_vocabulary(request: Request, identifier: str, payload: WatchVocabularyCreate):
        user = write_guard(request)
        return watches.add_vocabulary(identifier, {**payload.model_dump(), "created_by": user.user_id})

    @router.post("/watches/{identifier}/vocabulary/{vocabulary_id}/review")
    async def review_watch_vocabulary(request: Request, identifier: str, vocabulary_id: str, payload: WatchReview):
        user = write_guard(request)
        return watches.review_vocabulary(identifier, vocabulary_id, payload.status, user.user_id)

    @router.post("/watches/{identifier}/discover-sources")
    async def discover_watch_sources(request: Request, identifier: str, payload: WatchDiscoveryRun):
        write_guard(request)
        return watches.discover_sources(identifier, limit=payload.limit)

    @router.post("/watches/{identifier}/discovery-runs", status_code=202)
    async def enqueue_watch_discovery(request: Request, identifier: str, payload: WatchDiscoveryRun):
        write_guard(request)
        return watch_maintenance.enqueue_discovery(identifier, limit=payload.limit)

    @router.post("/watches/{identifier}/vocabulary/suggestion-runs", status_code=202)
    async def enqueue_watch_suggestion(request: Request, identifier: str, payload: WatchVocabularySuggest):
        write_guard(request)
        return watch_maintenance.enqueue_suggestion(identifier, limit=payload.limit)

    @router.post("/watches/{identifier}/source-candidates", status_code=201)
    async def create_watch_source_candidate(request: Request, identifier: str, payload: SourceCandidateCreate):
        write_guard(request)
        return watches.add_source_candidate(identifier, payload.model_dump(exclude_none=True))

    @router.post("/watches/{identifier}/source-candidates/{candidate_id}/review")
    async def review_watch_source_candidate(request: Request, identifier: str, candidate_id: str, payload: WatchReview):
        user = write_guard(request)
        return watches.review_source_candidate(identifier, candidate_id, payload.status, user.user_id)

    @router.delete("/watches/{identifier}/sources/{source_id}", status_code=204)
    async def remove_watch_source(request: Request, identifier: str, source_id: str):
        write_guard(request)
        watches.remove_source(identifier, source_id)
        return Response(status_code=204)

    @router.post("/monitors", status_code=201)
    async def create_monitor(request: Request, payload: MonitorCreate):
        write_guard(request)
        return monitors.create(payload.model_dump(exclude_none=True))

    @router.get("/monitors/{identifier}")
    async def get_monitor(request: Request, identifier: str):
        read_guard(request)
        return monitors.get(identifier)

    @router.post("/monitors/{identifier}/story-resolution")
    async def resolve_monitor_story_target(request: Request, identifier: str, payload: StoryTargetResolutionWrite):
        user = write_guard(request)
        return corrections.resolve_split_target(
            "monitor",
            identifier,
            payload.selected_story_ids,
            disable=payload.disable,
            actor=user.user_id,
        )

    @router.patch("/monitors/{identifier}")
    async def patch_monitor(request: Request, identifier: str, payload: MonitorPatch):
        write_guard(request)
        return monitors.update(identifier, _patch_data(payload))

    @router.post("/monitors/{identifier}/disable")
    async def disable_monitor(request: Request, identifier: str):
        write_guard(request)
        return monitors.disable(identifier)

    @router.post("/monitors/{identifier}/enable")
    async def enable_monitor(request: Request, identifier: str):
        write_guard(request)
        return monitors.enable(identifier)

    @router.get("/monitors/{identifier}/activity")
    async def monitor_activity(request: Request, identifier: str, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
        read_guard(request)
        return monitors.activity(identifier, page=page, page_size=page_size)

    @router.get("/monitors/{identifier}/scope-history")
    async def monitor_scope_history(request: Request, identifier: str, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
        read_guard(request)
        return monitors.scope_history(identifier, page=page, page_size=page_size)

    @router.get("/attention")
    async def list_attention(request: Request, limit: int = Query(100, ge=1, le=500)):
        read_guard(request)
        return attention.list(limit=limit)

    @router.get("/attention/{identifier}")
    async def get_attention(request: Request, identifier: str):
        read_guard(request)
        return attention.get(identifier)

    @router.post("/attention/{identifier}/decision")
    async def decide_attention(request: Request, identifier: str, payload: AttentionDecisionWrite):
        user = write_guard(request)
        return attention.decide(identifier, payload.action, actor=user.user_id, snooze_days=payload.snooze_days)

    @router.post("/relevance/evaluate")
    async def evaluate_relevance(request: Request, payload: RelevanceEvaluate):
        read_guard(request)
        scope = RelevanceScope(**payload.model_dump(exclude={"text"}))
        return RelevanceCascade().evaluate(payload.text, scope).as_dict()

    @router.get("/runs")
    async def list_runs(request: Request, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200)):
        read_guard(request)
        return jobs.list_runs(page=page, page_size=page_size)

    @router.get("/runs/{identifier}")
    async def get_run(request: Request, identifier: str):
        read_guard(request)
        return jobs.get_run(identifier)

    @router.get("/provider-usage")
    async def provider_usage(
        request: Request,
        job_id: Optional[str] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=200),
    ):
        read_guard(request)
        return budgets.list_usage(job_id=job_id, page=page, page_size=page_size)

    @router.get("/budgets/limits")
    async def list_budget_limits(request: Request):
        read_guard(request)
        return {"items": budgets.list_limits(), "paid_enabled": budgets.paid_enabled()}

    @router.put("/budgets/limits")
    async def configure_budget_limit(request: Request, payload: BudgetLimitWrite):
        write_guard(request)
        return budgets.configure_limit(**payload.model_dump())

    @router.put("/budgets/paid-enabled")
    async def set_paid_enabled(request: Request, payload: PaidEnabledWrite):
        write_guard(request)
        return budgets.set_paid_enabled(payload.enabled)

    @router.post("/scheduler/tick")
    async def scheduler_tick(request: Request):
        write_guard(request)
        return scheduler.tick()

    @router.post("/runs/ai", status_code=201)
    async def ai_run(request: Request, payload: AIRunCreate):
        write_guard(request)
        ai_service = AIVerticalSliceService(
            service.db_path,
            AIRouter(
                local=CapabilityBundle.local_defaults(),
                telemetry=SQLiteTelemetrySink(service.db_path),
            ),
        )
        try:
            return ai_service.run(
                VerticalSliceInput(
                    source=payload.source.model_dump() if payload.source else None,
                    source_id=payload.source_id,
                    document=payload.document.model_dump() if payload.document else None,
                    document_id=payload.document_id,
                    document_version=payload.document_version.model_dump(exclude_none=True),
                    content_text=payload.content_text,
                    scope_terms=payload.scope_terms,
                    story=payload.story.model_dump() if payload.story else None,
                    story_id=payload.story_id,
                    work_id=payload.work_id,
                )
            )
        except AIError as exc:
            raise DomainValidation(f"AI run failed safely: {type(exc).__name__}") from exc

    @router.post("/stories/{story_id}/tags", status_code=201)
    async def tag_story(request: Request, story_id: str, payload: StoryTagCreate):
        write_guard(request)
        return service.tag_story(story_id, payload.tag_id)

    @router.get("/tags")
    async def tags(request: Request, q: Optional[str] = None, namespace: Optional[str] = None, tag_type: Optional[str] = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
        read_guard(request)
        return service.list_tags(q=q, namespace=namespace, tag_type=tag_type, page=page, page_size=page_size)

    @router.post("/tags", status_code=201)
    async def create_tag(request: Request, payload: TagCreate):
        write_guard(request)
        return service.create_tag(payload.model_dump())

    @router.get("/tags/{identifier}")
    async def tag(request: Request, identifier: str):
        read_guard(request)
        return service.get_tag(identifier)

    @router.patch("/tags/{identifier}")
    async def patch_tag(request: Request, identifier: str, payload: TagPatch):
        write_guard(request)
        return service.update_tag(identifier, payload.model_dump())

    @router.delete("/tags/{identifier}", status_code=204)
    async def delete_tag(request: Request, identifier: str):
        write_guard(request)
        service.delete_tag(identifier)
        return Response(status_code=204)

    @router.get("/settings")
    async def settings(request: Request, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=100)):
        read_guard(request)
        return service.list_settings(page=page, page_size=page_size)

    @router.get("/experience")
    async def get_experience(request: Request):
        read_guard(request)
        return experience.get()

    @router.put("/experience")
    async def set_experience(request: Request, payload: ExperienceModeWrite):
        write_guard(request)
        return experience.set_mode(payload.mode)

    @router.put("/settings/{key}")
    async def set_setting(request: Request, key: str, payload: SettingWrite):
        write_guard(request)
        return service.set_setting(key, payload.value)

    return router


__all__ = ["create_domain_router"]
