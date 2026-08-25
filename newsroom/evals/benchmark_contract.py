"""Shared requested/effective configuration checks for the Full/Lite benchmark."""
from __future__ import annotations

from typing import Any, Mapping


_CONFIG_FIELDS = (
    ("provider", "effective_provider"),
    ("model", "effective_model"),
    ("temperature", "effective_temperature"),
    ("deterministic", "deterministic"),
    ("prompt_version", "effective_prompt_version"),
    ("context_budget_tokens", "effective_context_budget_tokens"),
    ("retrieval_limit", "effective_retrieval_limit"),
    ("citation_limit", "effective_citation_limit"),
)


def verify_execution(
    requested: Mapping[str, Any],
    effective: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify that one execution honored the frozen requested configuration."""
    mismatches: list[str] = []
    for requested_key, effective_key in _CONFIG_FIELDS:
        expected = requested.get(requested_key)
        observed = effective.get(effective_key)
        if observed != expected:
            mismatches.append(requested_key)
    if effective.get("fallback_used") is True:
        mismatches.append("fallback_used")

    unique_mismatches = tuple(dict.fromkeys(mismatches))
    return {
        "valid": not unique_mismatches,
        "status": "verified" if not unique_mismatches else "benchmark_contract_not_satisfied",
        "mismatch_fields": unique_mismatches,
        "requested_config": dict(requested),
        "effective_config": dict(effective),
    }


def compare_effective_conditions(
    full: Mapping[str, Any],
    lite: Mapping[str, Any],
) -> tuple[str, ...]:
    """Return effective fields that differ between Full and Lite."""
    fields = (
        "effective_provider",
        "effective_model",
        "provider_route",
        "fallback_used",
        "effective_temperature",
        "deterministic",
        "effective_prompt_version",
        "effective_context_budget_tokens",
        "effective_retrieval_limit",
        "effective_citation_limit",
    )
    return tuple(field for field in fields if full.get(field) != lite.get(field))


def router_effective_config(router: Any) -> dict[str, Any]:
    """Extract the last successful route from AIRouter's execution trace."""
    events = getattr(router, "last_execution_events", ())
    successful = [
        event
        for event in events
        if getattr(event, "outcome", None) in {"succeeded", "low_confidence"}
    ]
    if not successful:
        return {
            "effective_provider": None,
            "effective_model": None,
            "provider_route": "execution_unavailable",
            "fallback_used": False,
        }

    first = successful[0]
    last = successful[-1]
    effective_provider = "local" if last.route == "local" else last.provider
    effective_model = None if last.route == "local" else last.model
    return {
        "effective_provider": effective_provider,
        "effective_model": effective_model,
        "provider_route": last.route,
        "fallback_used": len({event.route for event in successful}) > 1,
    }


def add_effective_settings(
    effective: Mapping[str, Any],
    requested: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach settings actually supplied by the benchmark adapter."""
    result = dict(effective)
    result.setdefault("effective_temperature", requested.get("temperature"))
    result.setdefault("deterministic", requested.get("deterministic"))
    result.setdefault("effective_prompt_version", requested.get("prompt_version"))
    result.setdefault("effective_context_budget_tokens", requested.get("context_budget_tokens"))
    result.setdefault("effective_retrieval_limit", requested.get("retrieval_limit"))
    result.setdefault("effective_citation_limit", requested.get("citation_limit"))
    return result


__all__ = [
    "add_effective_settings",
    "compare_effective_conditions",
    "router_effective_config",
    "verify_execution",
]
