"""Small per-runtime supervisor for Newsroom child processes."""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Sequence

from .config import RuntimeConfig
from .migrations import apply_migrations
from .runtime_identity import ExclusiveFileLock
from .runtime_managed import (
    ComponentState,
    ManagedOwner,
    ManagedRoleContext,
    RuntimeManifest,
    ShutdownResult,
    SupervisorError,
    component_control_path,
    component_heartbeat_path,
    component_lock_path,
    component_owner_path,
    component_state,
    ensure_runtime_manifest,
    request_component_stop,
)

RUNTIME_ROLES = ("api", "worker", "scheduler")

CommandFactory = Callable[[str], Sequence[str]]
PopenFactory = Callable[..., subprocess.Popen]
ApiReadiness = Callable[[], tuple[bool, str]]


class RuntimeSupervisor:
    """Own and reconcile one API, worker, and scheduler for a runtime root."""

    def __init__(
        self,
        config: RuntimeConfig,
        *,
        installation_id: str,
        release_id: str,
        host: str,
        port: int,
        command_factory: CommandFactory | None = None,
        heartbeat_timeout_seconds: float = 2.0,
        startup_timeout_seconds: float = 8.0,
        shutdown_timeout_seconds: float = 8.0,
        restart_limit: int = 3,
        restart_backoff_seconds: float = 0.25,
        poll_interval_seconds: float = 0.1,
        popen_factory: PopenFactory = subprocess.Popen,
        api_readiness: ApiReadiness | None = None,
    ) -> None:
        self.config = config
        self.installation_id = installation_id
        self.release_id = release_id
        self.host = host
        self.port = port
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self.startup_timeout_seconds = startup_timeout_seconds
        self.shutdown_timeout_seconds = shutdown_timeout_seconds
        self.restart_limit = restart_limit
        self.restart_backoff_seconds = restart_backoff_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.popen_factory = popen_factory
        self._api_readiness = api_readiness or self._default_api_readiness
        self._command_factory = command_factory or self._default_command
        self._children: dict[str, subprocess.Popen] = {}
        self._restart_counts = {role: 0 for role in RUNTIME_ROLES}
        self._restart_after = {role: 0.0 for role in RUNTIME_ROLES}

    def _default_command(self, role: str) -> Sequence[str]:
        common = [
            sys.executable,
            "-m",
            "newsroom.runtime",
            role,
            "--environment",
            self.config.environment,
            "--root",
            str(self.config.root),
            "--managed-child",
        ]
        if role == "api":
            common.extend(["--host", self.host, "--port", str(self.port)])
        elif role == "worker":
            common.extend(["--worker-id", f"newsroom-worker-{self.installation_id[:8]}"])
        return common

    def _default_api_readiness(self) -> tuple[bool, str]:
        from .runtime_identity import EndpointStatus, diagnose_endpoint

        diagnosis = diagnose_endpoint(
            self.host,
            self.port,
            expected_installation_id=self.installation_id,
            expected_release_id=self.release_id,
        )
        if diagnosis.status is EndpointStatus.MATCHING:
            return True, "verified matching API endpoint"
        return False, f"API endpoint is {diagnosis.status.value}: {diagnosis.detail}"

    def state(self, role: str) -> ComponentState:
        process = self._children.get(role)
        if process is not None and process.poll() is not None:
            self._children.pop(role, None)
        state = component_state(
            self.config,
            role,
            installation_id=self.installation_id,
            release_id=self.release_id,
            heartbeat_timeout_seconds=self.heartbeat_timeout_seconds,
        )
        if role == "api" and state.status == "healthy":
            ready, detail = self._api_readiness()
            if not ready:
                return ComponentState(role, "starting", detail, state.owner)
        return state

    def _any_component_lock_held(self) -> bool:
        for role in RUNTIME_ROLES:
            lock = ExclusiveFileLock(component_lock_path(self.config, role))
            if not lock.acquire():
                return True
            lock.release()
        return False

    def prepare(self) -> None:
        active_components = self._any_component_lock_held()
        ensure_runtime_manifest(
            self.config,
            installation_id=self.installation_id,
            release_id=self.release_id,
            host=self.host,
            port=self.port,
            allow_release_update=not active_components,
        )
        # Only the supervisor performs normal managed migrations, and only when
        # every managed writer role is stopped. Reconciliation of an existing
        # same-release child set deliberately skips migration writes.
        if not active_components:
            apply_migrations(self.config.database_path)

    def _spawn(self, role: str) -> None:
        process = self.popen_factory(
            list(self._command_factory(role)),
            cwd=Path(__file__).resolve().parents[1],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._children[role] = process

    def ensure_role(self, role: str) -> ComponentState:
        state = self.state(role)
        if state.status == "healthy":
            return state
        if state.status in {"stale", "ambiguous", "unmanaged"}:
            return state
        spawned = False
        if state.status == "missing":
            self._spawn(role)
            spawned = True
        deadline = time.monotonic() + self.startup_timeout_seconds
        while time.monotonic() < deadline:
            state = self.state(role)
            if state.status in {"healthy", "stale", "ambiguous", "unmanaged"}:
                return state
            if state.status == "missing" and not spawned:
                self._spawn(role)
                spawned = True
            time.sleep(self.poll_interval_seconds)
        return self.state(role)

    def ensure_all(self) -> dict[str, ComponentState]:
        initial = {role: self.state(role) for role in RUNTIME_ROLES}
        if any(state.status in {"stale", "ambiguous", "unmanaged"} for state in initial.values()):
            return initial
        return {role: self.ensure_role(role) for role in RUNTIME_ROLES}

    def monitor_once(self) -> dict[str, ComponentState]:
        states: dict[str, ComponentState] = {}
        now = time.monotonic()
        for role in RUNTIME_ROLES:
            state = self.state(role)
            if state.status == "missing":
                if self._restart_counts[role] >= self.restart_limit:
                    states[role] = ComponentState(role, "restart_exhausted", "bounded restart limit exhausted")
                    continue
                if now >= self._restart_after[role]:
                    self._restart_counts[role] += 1
                    self._restart_after[role] = now + self.restart_backoff_seconds * (2 ** (self._restart_counts[role] - 1))
                    state = self.ensure_role(role)
            states[role] = state
        return states

    def shutdown(self, *, timeout_seconds: float | None = None) -> ShutdownResult:
        deadline = time.monotonic() + (self.shutdown_timeout_seconds if timeout_seconds is None else timeout_seconds)
        blocked: list[str] = []
        targets: list[str] = []
        for role in ("scheduler", "worker"):
            state = self.state(role)
            if state.status == "missing":
                continue
            if (
                state.owner is not None
                and state.owner.supervisor_managed
                and state.status in {"healthy", "stale", "starting"}
            ):
                request_component_stop(self.config, state.owner)
                targets.append(role)
            else:
                blocked.append(role)
        while targets and time.monotonic() < deadline:
            targets = [role for role in targets if self.state(role).status != "missing"]
            if targets:
                time.sleep(self.poll_interval_seconds)
        remaining_writers = tuple(dict.fromkeys([*blocked, *targets]))
        if remaining_writers:
            return ShutdownResult(False, remaining_writers)

        api_state = self.state("api")
        if api_state.status == "missing":
            return ShutdownResult(True, ())
        if (
            api_state.owner is None
            or not api_state.owner.supervisor_managed
            or api_state.status not in {"healthy", "stale", "starting"}
        ):
            return ShutdownResult(False, ("api",))
        request_component_stop(self.config, api_state.owner)
        while time.monotonic() < deadline:
            if self.state("api").status == "missing":
                return ShutdownResult(True, ())
            time.sleep(self.poll_interval_seconds)
        return ShutdownResult(False, ("api",))

    def restart(self) -> ShutdownResult:
        result = self.shutdown()
        if not result.drained:
            return result
        self.prepare()
        states = self.ensure_all()
        remaining = tuple(role for role, state in states.items() if state.status != "healthy")
        return ShutdownResult(not remaining, remaining)

    def run_forever(self, stop_event: threading.Event) -> int:
        self.config.ensure_runtime_dirs()
        ownership = ManagedRoleContext(
            self.config,
            installation_id=self.installation_id,
            release_id=self.release_id,
            role="supervisor",
            stop_event=stop_event,
        )
        try:
            ownership.__enter__()
        except SupervisorError:
            deadline = time.monotonic() + self.startup_timeout_seconds
            while time.monotonic() < deadline:
                state = self.state("supervisor")
                if state.status == "healthy":
                    return 0
                if state.status == "missing":
                    try:
                        ownership.__enter__()
                        break
                    except SupervisorError:
                        pass
                time.sleep(self.poll_interval_seconds)
            else:
                return 3
        try:
            self.prepare()
            states = self.ensure_all()
            if any(state.status != "healthy" for state in states.values()):
                self.shutdown()
                return 3
            while not stop_event.wait(self.poll_interval_seconds):
                self.monitor_once()
            result = self.shutdown()
            return 0 if result.drained else 4
        finally:
            ownership.__exit__(None, None, None)


__all__ = [
    "ComponentState",
    "ManagedOwner",
    "ManagedRoleContext",
    "RuntimeManifest",
    "RuntimeSupervisor",
    "ShutdownResult",
    "SupervisorError",
    "component_control_path",
    "component_heartbeat_path",
    "component_lock_path",
    "component_owner_path",
    "component_state",
    "ensure_runtime_manifest",
    "request_component_stop",
]
