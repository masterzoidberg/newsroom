"""Persist the user's Simple/Advanced product presentation preference."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .domain import CoreService, DomainValidation


MODES = frozenset({"simple", "advanced"})
DEFAULT_CAPABILITIES = {
    "attention": True,
    "coverage": True,
    "source_robustness": False,
    "hypotheses": False,
    "counterfactuals": False,
}


class ExperienceService:
    def __init__(self, db_path: str | Path):
        self.core = CoreService(db_path)

    def get(self) -> dict[str, Any]:
        settings = {item["key"]: item["value"] for item in self.core.list_settings(page_size=100)["items"]}
        mode = settings.get("experience.mode", "simple")
        if mode not in MODES:
            mode = "simple"
        capabilities = dict(DEFAULT_CAPABILITIES)
        if mode == "advanced":
            capabilities.update({"source_robustness": True, "hypotheses": True, "counterfactuals": True})
        override = settings.get("experience.capabilities")
        if override:
            try:
                values = json.loads(override)
                if isinstance(values, dict):
                    capabilities.update({key: bool(value) for key, value in values.items() if key in capabilities})
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        return {"mode": mode, "capabilities": capabilities}

    def set_mode(self, mode: str) -> dict[str, Any]:
        if mode not in MODES:
            raise DomainValidation("experience mode must be simple or advanced")
        self.core.set_setting("experience.mode", mode)
        return self.get()


__all__ = ["DEFAULT_CAPABILITIES", "ExperienceService", "MODES"]
