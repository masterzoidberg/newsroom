"""Local AI orchestration for the Phase 04 evidence-ledger vertical slice."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .ai import AIValidationError, AIRouter, ClaimDraft, SynthesisOutput
from .evidence import EvidenceService


@dataclass(frozen=True)
class VerticalSliceInput:
    source: Mapping[str, Any] | None
    document: Mapping[str, Any] | None
    document_version: Mapping[str, Any]
    content_text: str
    scope_terms: Sequence[str]
    story: Mapping[str, Any] | None = None
    work_id: str | None = None
    source_id: str | None = None
    document_id: str | None = None
    story_id: str | None = None

    def __post_init__(self) -> None:
        if (self.source is None) == (self.source_id is None):
            raise ValueError("provide exactly one of source or source_id")
        if (self.document is None) == (self.document_id is None):
            raise ValueError("provide exactly one of document or document_id")
        if not self.content_text.strip():
            raise ValueError("content_text must not be empty")
        if not self.document_version.get("content_hash"):
            raise ValueError("document_version.content_hash must be supplied")


class AIVerticalSliceService:
    """Use the router for interpretation, then delegate authority to the ledger."""

    def __init__(self, db_path, router: AIRouter):
        self.ledger = EvidenceService(db_path)
        self.router = router

    def run(self, request: VerticalSliceInput) -> dict[str, Any]:
        relevance = self.router.relevance(
            request.content_text,
            request.scope_terms,
            work_id=request.work_id,
        )
        if not relevance.relevant:
            return {
                "resolution": "not_relevant",
                "relevance": relevance.model_dump(),
                "claims": [],
                "revision": None,
            }

        embedding = self.router.embedding(request.content_text, work_id=request.work_id)
        rerank = self.router.rerank(
            str((request.document or {}).get("title", "")),
            request.content_text,
            work_id=request.work_id,
        )
        extracted = self.router.extraction(
            str((request.document or {}).get("title", "")),
            request.content_text,
            work_id=request.work_id,
        )
        manual_claims: list[dict[str, Any]] = []
        accepted_indexes: list[int] = []
        accepted_drafts: list[ClaimDraft] = []
        for claim in extracted.claims:
            evidence: list[dict[str, Any]] = []
            has_support = False
            has_contradiction = False
            for candidate in claim.evidence:
                entailment = self.router.entailment(
                    claim.proposition,
                    candidate.excerpt,
                    work_id=request.work_id,
                )
                relationship = candidate.relationship
                if entailment.relationship == "contradicts":
                    relationship = "contradicts"
                elif entailment.relationship == "entails":
                    relationship = "supports"
                has_support = has_support or relationship == "supports"
                has_contradiction = has_contradiction or relationship == "contradicts"
                evidence.append(
                    {
                        "excerpt": candidate.excerpt,
                        "locator_type": candidate.locator_type,
                        "locator_value": candidate.locator_value,
                        "relationship": relationship,
                    }
                )
            state = self._claim_state(has_support, has_contradiction)
            accepted = claim.accept and state in {"supported", "partially_supported"}
            manual_claims.append(
                {
                    "proposition": claim.proposition,
                    "importance": claim.importance,
                    "evidence": evidence,
                    "state": state,
                    "accept": accepted,
                }
            )
            if accepted:
                accepted_indexes.append(len(manual_claims) - 1)
                accepted_drafts.append(ClaimDraft(proposition=claim.proposition))

        revision: dict[str, Any] | None = None
        synthesis: SynthesisOutput | None = None
        if accepted_drafts:
            story_headline = str(
                (request.story or {}).get("headline")
                or (request.document or {}).get("title")
                or request.content_text.split(".", 1)[0][:500]
            )
            synthesis = self.router.synthesis(
                story_headline,
                accepted_drafts,
                work_id=request.work_id,
            )
            revision = self._revision_payload(synthesis, accepted_indexes)

        payload: dict[str, Any] = {
            "document_version": self._version_payload(request),
            "claims": manual_claims,
        }
        if request.source_id is not None:
            payload["source_id"] = request.source_id
        else:
            payload["source"] = dict(request.source or {})
        if request.document_id is not None:
            payload["document_id"] = request.document_id
        else:
            payload["document"] = dict(request.document or {})
        if request.story_id is not None:
            payload["story_id"] = request.story_id
        else:
            payload["story"] = dict(
                request.story
                or {
                    "headline": (request.document or {}).get("title")
                    or request.content_text.split(".", 1)[0][:500]
                }
            )
        if revision is not None:
            payload["revision"] = revision

        result = self.ledger.run_manual(payload)
        result["ai"] = {
            "mode": "local-first",
            "relevance": relevance.model_dump(),
            "embedding_dimensions": len(embedding.vector),
            "rerank": rerank.model_dump(),
            "extraction_confidence": extracted.confidence,
            "synthesis_confidence": synthesis.confidence if synthesis else None,
        }
        return result

    @staticmethod
    def _claim_state(has_support: bool, has_contradiction: bool) -> str:
        if has_support and has_contradiction:
            return "disputed"
        if has_support:
            return "supported"
        if has_contradiction:
            return "disputed"
        return "unsubstantiated"

    @staticmethod
    def _revision_payload(synthesis: SynthesisOutput, accepted_indexes: list[int]) -> dict[str, Any]:
        def map_index(index: int) -> int:
            if index < 0 or index >= len(accepted_indexes):
                raise AIValidationError("synthesis cited a Claim outside the accepted Claim set")
            return accepted_indexes[index]

        return {
            "headline": synthesis.headline,
            "summary": synthesis.summary,
            "why_it_matters": synthesis.why_it_matters,
            "material_change": synthesis.material_change,
            "claim_indexes": [map_index(index) for index in synthesis.claim_indexes],
            "propositions": [
                {
                    "text": proposition.text,
                    "claim_indexes": [map_index(index) for index in proposition.claim_indexes],
                }
                for proposition in synthesis.propositions
            ],
        }

    @staticmethod
    def _version_payload(request: VerticalSliceInput) -> dict[str, Any]:
        version = dict(request.document_version)
        version.setdefault("content_kind", "excerpt")
        version.setdefault("normalized_json", {"content_length": len(request.content_text)})
        version.setdefault(
            "content_hash",
            hashlib.sha256(request.content_text.encode("utf-8")).hexdigest(),
        )
        return version


__all__ = ["VerticalSliceInput", "AIVerticalSliceService"]
