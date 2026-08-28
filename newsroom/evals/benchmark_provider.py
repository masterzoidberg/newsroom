"""Contract-bound synthesis adapters used by the Full/Lite benchmark runners."""
from __future__ import annotations

import json
import os
from typing import Any, Mapping, Sequence

from ..ai import (
    AIConfigurationError,
    AIRouter,
    CapabilityBundle,
    ClaimDraft,
    RoutePolicy,
    SynthesisOutput,
)


class OpenAICompatibleSynthesisProvider:
    """OpenAI-compatible synthesis with an explicit, inspectable identity."""

    provider_name = "openai"

    def __init__(
        self,
        *,
        model: str,
        temperature: float,
        deterministic: bool,
        prompt_version: str,
        context_budget_tokens: int,
        retrieval_limit: int,
        citation_limit: int,
        client_factory: Any | None = None,
    ):
        self.model_name = str(model)
        self.temperature = float(temperature)
        self.deterministic = bool(deterministic)
        self.prompt_version = str(prompt_version)
        self.context_budget_tokens = int(context_budget_tokens)
        self.retrieval_limit = int(retrieval_limit)
        self.citation_limit = int(citation_limit)
        self.api_key = os.environ.get("NEWSROOM_ANALYSIS_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.base_url = os.environ.get("NEWSROOM_ANALYSIS_BASE_URL") or None
        self._client_factory = client_factory
        self.last_usage: dict[str, Any] | None = None

    def _client(self) -> Any:
        if not self.api_key:
            raise AIConfigurationError("benchmark provider 'openai' requires NEWSROOM_ANALYSIS_API_KEY")
        if self._client_factory is not None:
            return self._client_factory(self)
        import httpx  # noqa: PLC0415
        from openai import OpenAI  # noqa: PLC0415

        return OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0, connect=10.0, read=30.0, write=30.0),
            max_retries=0,
        )

    @staticmethod
    def _system_prompt(prompt_version: str) -> str:
        return (
            f"Newsroom benchmark synthesis contract {prompt_version}. "
            "Return only JSON matching the supplied schema. Use only the provided Claims and Evidence."
        )

    def synthesize(self, story_headline: str, claims: Sequence[ClaimDraft]) -> SynthesisOutput | Mapping[str, Any]:
        claim_payload = [claim.model_dump() if hasattr(claim, "model_dump") else dict(claim) for claim in claims]
        schema = dict(SynthesisOutput.model_json_schema())
        schema.pop("title", None)
        completion = self._client().chat.completions.create(
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.context_budget_tokens,
            messages=[
                {"role": "system", "content": self._system_prompt(self.prompt_version)},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": story_headline, "claims": claim_payload},
                        sort_keys=True,
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "newsroom_synthesis", "schema": schema},
            },
        )
        usage = getattr(completion, "usage", None)
        if usage is not None:
            self.last_usage = {"token_units": getattr(usage, "total_tokens", None)}
        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            raise AIConfigurationError("benchmark provider returned no synthesis content")
        return json.loads(content)


def contract_router(contract: Mapping[str, Any]) -> AIRouter:
    """Build the production router from the frozen contract identity."""

    retrieval = contract["retrieval"]
    provider = OpenAICompatibleSynthesisProvider(
        model=str(contract["model"]),
        temperature=float(contract["temperature"]),
        deterministic=bool(contract["deterministic"]),
        prompt_version=str(contract["prompt_version"]),
        context_budget_tokens=int(contract["context_budget_tokens"]),
        retrieval_limit=int(contract["retrieval_limit"]),
        citation_limit=int(retrieval["citation_limit"]),
    )
    return AIRouter(
        local=CapabilityBundle(),
        paid=CapabilityBundle(synthesis=provider),
        policy=RoutePolicy(
            local_enabled=False,
            paid_enabled=True,
            max_paid_calls=max(1, len(contract["questions"])),
            max_paid_cost_usd=max(0.05, 0.05 * len(contract["questions"])),
            max_paid_calls_per_work=1,
            max_paid_cost_usd_per_work=0.05,
        ),
    )


__all__ = ["OpenAICompatibleSynthesisProvider", "contract_router"]
