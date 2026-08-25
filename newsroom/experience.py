"""Persist the user's Simple/Advanced product presentation preference."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .domain import CoreService, DomainValidation


MODES = frozenset({"simple", "advanced"})
class ExperienceService:
    def __init__(self, db_path: str | Path):
        self.core = CoreService(db_path)

    def get(self) -> dict[str, Any]:
        settings = {item["key"]: item["value"] for item in self.core.list_settings(page_size=100)["items"]}
        mode = settings.get("experience.mode", "simple")
        if mode not in MODES:
            mode = "simple"
        return {"mode": mode}

    def set_mode(self, mode: str) -> dict[str, Any]:
        if mode not in MODES:
            raise DomainValidation("experience mode must be simple or advanced")
        self.core.set_setting("experience.mode", mode)
        return self.get()


__all__ = ["ExperienceService", "MODES"]
