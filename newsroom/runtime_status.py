"""Authenticated, bounded projection of managed runtime health and recovery actions."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from . import storage
from .config import RuntimeConfig
from .runtime_managed import (
    ComponentState,
    ManagedOwner,
    component_state,
    request_component_stop,
)

RuntimeControlAction = Literal[
    "restart_api",
    "restart_worker",
    "restart_scheduler",
    "stop_newsroom",
]
CONTROL_ACTIONS: tuple[RuntimeControlAction, ...] = (
    "restart_api",
    "restart_worker",
    "restart_scheduler",
    "stop_newsroom",
)
_COMPONENT_ROLES = ("api", "worker", "scheduler")


class RuntimeControlUnavailable(RuntimeError):
    """Raised when a requested recovery action cannot be targeted safely."""


def _active_work(db_path: str | Path) -> dict[str, int | str]:
    conn = storage.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) AS queued_jobs,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS running_jobs
            FROM jobs
            """
        ).fetchone()
    finally:
        conn.close()
    queued = int(row["queued_jobs"] or 0)
    running = int(row["running_jobs"] or 0)
    state = "processing" if running else "queued" if queued else "idle"
    return {"state": state, "queued_jobs": queued, "running_jobs": running}


def _public_component(state: ComponentState) -> dict[str, object]:
    owner = state.owner
    return {
        "status": state.status,
        "detail": state.detail,
        "managed": bool(owner and owner.supervisor_managed),
    }


class RuntimeStatusService:
    """Read existing AST-03 heartbeat state without performing readiness scans."""

    def __init__(
        self,
        config: RuntimeConfig,
        runtime_identity: dict[str, object] | None,
        *,
        heartbeat_timeout_seconds: float = 2.0,
    ) -> None:
        self.config = config
        self.runtime_identity = runtime_identity or {}
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self.installation_id = str(self.runtime_identity.get("installation_id") or "")
        self.release_id = str(self.runtime_identity.get("release_id") or "")

    @property
    def managed_identity_available(self) -> bool:
        return bool(self.installation_id and self.release_id)

    def _state(self, role: str) -> ComponentState:
        if not self.managed_identity_available:
            return ComponentState(
                role=role,
                status="unmanaged",
                detail="managed runtime identity is unavailable",
                owner=None,
            )
        return component_state(
            self.config,
            role,
            installation_id=self.installation_id,
            release_id=self.release_id,
            heartbeat_timeout_seconds=self.heartbeat_timeout_seconds,
        )

    def snapshot(self) -> dict[str, object]:
        work = _active_work(self.config.database_path)
        states = {role: self._state(role) for role in ("supervisor", *_COMPONENT_ROLES)}
        unhealthy = [role for role, state in states.items() if state.status != "healthy"]
        overall = "degraded" if unhealthy else str(work["state"])

        actions: list[RuntimeControlAction] = []
        supervisor = states["supervisor"]
        supervisor_controllable = bool(
            supervisor.status == "healthy"
            and supervisor.owner is not None
            and supervisor.owner.supervisor_managed
        )
        if supervisor_controllable:
            actions.append("stop_newsroom")
            for role in _COMPONENT_ROLES:
                state = states[role]
                if (
                    state.status in {"healthy", "stale"}
                    and state.owner is not None
                    and state.owner.supervisor_managed
                ):
                    actions.append(f"restart_{role}")  # type: ignore[arg-type]

        return {
            "managed": self.managed_identity_available,
            "overall": overall,
            "supervisor": _public_component(states["supervisor"]),
            "components": {role: _public_component(states[role]) for role in _COMPONENT_ROLES},
            "work": work,
            "controls": {
                "available": bool(actions),
                "actions": actions,
            },
        }

    def prepare_control(self, action: RuntimeControlAction) -> ManagedOwner:
        if action not in CONTROL_ACTIONS:
            raise RuntimeControlUnavailable("runtime action is not allowed")
        snapshot = self.snapshot()
        allowed = snapshot["controls"]
        assert isinstance(allowed, dict)
        actions = allowed.get("actions", [])
        if action not in actions:
            raise RuntimeControlUnavailable("requested runtime action is not safely available")
        role = "supervisor" if action == "stop_newsroom" else action.removeprefix("restart_")
        state = self._state(role)
        if state.owner is None or not state.owner.supervisor_managed:
            raise RuntimeControlUnavailable("requested runtime owner is not verified as supervisor-managed")
        return state.owner

    def dispatch_control(self, owner: ManagedOwner) -> None:
        """Send only the cooperative stop primitive already enforced by AST-03.

        Restart actions target a single owned child. The supervisor observes the
        child exit and applies its existing bounded restart policy. Stopping the
        whole application targets the supervisor, whose shutdown path drains the
        scheduler/worker before the API.
        """
        request_component_stop(self.config, owner)


__all__ = [
    "CONTROL_ACTIONS",
    "RuntimeControlAction",
    "RuntimeControlUnavailable",
    "RuntimeStatusService",
]
