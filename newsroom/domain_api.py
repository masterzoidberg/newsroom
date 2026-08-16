"""Validated API contracts for the Phase 03 core domain."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Optional

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
from .domain import CoreService, DomainValidation
from .evidence import EvidenceService


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


class StoryRevisionCreate(StrictModel):
    headline: str = Field(min_length=1, max_length=500)
    summary: str = Field(default="", max_length=10000)
    why_it_matters: str = Field(default="", max_length=10000)
    material_change: bool = False
    claim_ids: list[str] = Field(default_factory=list, max_length=100)
    propositions: list[RevisionProposition] = Field(default_factory=list, max_length=100)


class StoryPatch(StrictModel):
    lifecycle: str = Field(pattern="^(developing|stable|resolved|archived)$")


class TagCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)


class TagPatch(StrictModel):
    name: str = Field(min_length=1, max_length=100)


class StoryTagCreate(StrictModel):
    tag_id: str = Field(min_length=1, max_length=200)


class SettingWrite(StrictModel):
    value: str = Field(max_length=4000)


def _patch_data(model: BaseModel) -> dict:
    data = model.model_dump(exclude_unset=True)
    if not data:
        from .domain import DomainValidation
        raise DomainValidation("at least one field must be supplied")
    return data


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

    def read_guard(request: Request):
        return require_user(request)

    def write_guard(request: Request):
        user = require_user(request)
        require_csrf(request, user)
        return user

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

    @router.post("/stories/{story_id}/claims", status_code=201)
    async def create_claim(request: Request, story_id: str, payload: ClaimCreate):
        write_guard(request)
        return ledger.create_claim(story_id, payload.model_dump())

    @router.get("/stories/{story_id}/evidence")
    async def story_evidence(request: Request, story_id: str):
        read_guard(request)
        return ledger.get_story_evidence(story_id)

    @router.get("/stories/{identifier}")
    async def story(request: Request, identifier: str, include_deleted: bool = False):
        read_guard(request)
        return service.get_story(identifier, include_deleted=include_deleted)

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
    async def tags(request: Request, q: Optional[str] = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
        read_guard(request)
        return service.list_tags(q=q, page=page, page_size=page_size)

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

    @router.put("/settings/{key}")
    async def set_setting(request: Request, key: str, payload: SettingWrite):
        write_guard(request)
        return service.set_setting(key, payload.value)

    return router


__all__ = ["create_domain_router"]
