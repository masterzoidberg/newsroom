"""Managed runtime identity, heartbeat, and stop-control protocol."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .config import RuntimeConfig
from .runtime_identity import ExclusiveFileLock, process_creation_token

RUNTIME_ROLES = ("api", "worker", "scheduler")
MANAGED_ROLES = ("supervisor", *RUNTIME_ROLES)
_MAX_STATE_BYTES = 16 * 1024


class SupervisorError(RuntimeError):
    """Raised when managed runtime ownership cannot be established safely."""


@dataclass(frozen=True)
class RuntimeManifest:
    installation_id: str
    environment: str
    root: str
    host: str
    port: int
    release_id: str


@dataclass(frozen=True)
class ManagedOwner:
    installation_id: str
    root: str
    role: str
    release_id: str
    pid: int
    process_creation_token: str
    supervisor_managed: bool


@dataclass(frozen=True)
class ComponentState:
    role: str
    status: str
    detail: str
    owner: ManagedOwner | None = None


@dataclass(frozen=True)
class ShutdownResult:
    drained: bool
    remaining_roles: tuple[str, ...]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _runtime_dir(config: RuntimeConfig) -> Path:
    path = config.root / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def manifest_path(config: RuntimeConfig) -> Path:
    return _runtime_dir(config) / "runtime-manifest.json"


def component_lock_path(config: RuntimeConfig, role: str) -> Path:
    _validate_role(role)
    return _runtime_dir(config) / f"{role}.managed.lock"


def component_owner_path(config: RuntimeConfig, role: str) -> Path:
    _validate_role(role)
    return _runtime_dir(config) / f"{role}-managed-owner.json"


def component_heartbeat_path(config: RuntimeConfig, role: str) -> Path:
    _validate_role(role)
    return _runtime_dir(config) / f"{role}-heartbeat.json"


def component_control_path(config: RuntimeConfig, role: str) -> Path:
    _validate_role(role)
    return _runtime_dir(config) / f"{role}-control.json"


def _validate_role(role: str) -> None:
    if role not in MANAGED_ROLES:
        raise ValueError(f"unsupported managed role: {role}")


def _normalized_root(path: str | Path) -> str:
    return os.path.normcase(str(Path(path).expanduser().resolve()))


def _read_json(path: Path) -> dict | None:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    if len(raw) > _MAX_STATE_BYTES:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_json_atomic(path: Path, payload: Mapping) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(dict(payload), handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def ensure_runtime_manifest(
    config: RuntimeConfig,
    *,
    installation_id: str,
    release_id: str,
    host: str,
    port: int,
    allow_release_update: bool = False,
) -> RuntimeManifest:
    expected = RuntimeManifest(
        installation_id=installation_id,
        environment=config.environment,
        root=str(config.root),
        host=host,
        port=port,
        release_id=release_id,
    )
    path = manifest_path(config)
    current = _read_json(path)
    if current is None:
        _write_json_atomic(path, {"format_version": 1, **asdict(expected)})
        return expected
    try:
        stored = RuntimeManifest(
            installation_id=str(current["installation_id"]),
            environment=str(current["environment"]),
            root=str(current["root"]),
            host=str(current["host"]),
            port=int(current["port"]),
            release_id=str(current["release_id"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SupervisorError("runtime manifest is invalid") from exc
    structural_mismatch = (
        stored.installation_id != expected.installation_id
        or stored.environment != expected.environment
        or _normalized_root(stored.root) != _normalized_root(expected.root)
        or stored.host != expected.host
        or stored.port != expected.port
    )
    if structural_mismatch:
        raise SupervisorError("runtime manifest does not match this installation/root/endpoint")
    if stored.release_id != expected.release_id:
        if not allow_release_update:
            raise SupervisorError("runtime manifest release differs while managed components may still be active")
        _write_json_atomic(path, {"format_version": 1, **asdict(expected)})
    return expected


def current_owner(
    config: RuntimeConfig,
    role: str,
) -> ManagedOwner | None:
    payload = _read_json(component_owner_path(config, role))
    if payload is None:
        return None
    try:
        owner = ManagedOwner(
            installation_id=str(payload["installation_id"]),
            root=str(payload["root"]),
            role=str(payload["role"]),
            release_id=str(payload["release_id"]),
            pid=int(payload["pid"]),
            process_creation_token=str(payload["process_creation_token"]),
            supervisor_managed=bool(payload.get("supervisor_managed", False)),
        )
    except (KeyError, TypeError, ValueError):
        return None
    return owner


def verify_owner(
    config: RuntimeConfig,
    role: str,
    owner: ManagedOwner | None,
    *,
    installation_id: str,
    release_id: str,
) -> tuple[bool, str]:
    if owner is None:
        return False, "owner metadata is missing or invalid"
    if owner.role != role:
        return False, "owner role mismatch"
    if owner.installation_id != installation_id:
        return False, "owner installation mismatch"
    if owner.release_id != release_id:
        return False, "owner release mismatch"
    if _normalized_root(owner.root) != _normalized_root(config.root):
        return False, "owner root mismatch"
    token = process_creation_token(owner.pid)
    if token is None:
        return False, "owner process is not running or cannot be inspected"
    if token != owner.process_creation_token:
        return False, "owner PID creation token mismatch"
    return True, "verified"


def component_state(
    config: RuntimeConfig,
    role: str,
    *,
    installation_id: str,
    release_id: str,
    heartbeat_timeout_seconds: float,
    now: float | None = None,
) -> ComponentState:
    owner = current_owner(config, role)
    verified, detail = verify_owner(
        config,
        role,
        owner,
        installation_id=installation_id,
        release_id=release_id,
    )
    if not verified:
        lock = ExclusiveFileLock(component_lock_path(config, role))
        if lock.acquire():
            lock.release()
            return ComponentState(role, "missing", detail, owner)
        return ComponentState(role, "ambiguous", detail, owner)
    if role in RUNTIME_ROLES and owner is not None and not owner.supervisor_managed:
        return ComponentState(role, "unmanaged", "verified direct child is not controlled by the supervisor", owner)
    heartbeat = _read_json(component_heartbeat_path(config, role))
    if heartbeat is None:
        return ComponentState(role, "stale", "heartbeat missing", owner)
    try:
        heartbeat_pid = int(heartbeat["pid"])
        heartbeat_token = str(heartbeat["process_creation_token"])
        heartbeat_at = float(heartbeat["monotonic_time"])
    except (KeyError, TypeError, ValueError):
        return ComponentState(role, "stale", "heartbeat invalid", owner)
    if owner is None or heartbeat_pid != owner.pid or heartbeat_token != owner.process_creation_token:
        return ComponentState(role, "stale", "heartbeat does not match verified owner", owner)
    clock = time.monotonic() if now is None else now
    if clock - heartbeat_at > heartbeat_timeout_seconds:
        return ComponentState(role, "stale", "heartbeat is stale", owner)
    return ComponentState(role, "healthy", "verified owner and fresh heartbeat", owner)


class ManagedRoleContext:
    """Hold one role lock, publish identity/heartbeat, and watch stop control."""

    def __init__(
        self,
        config: RuntimeConfig,
        *,
        installation_id: str,
        release_id: str,
        role: str,
        stop_event: threading.Event,
        heartbeat_interval_seconds: float = 0.5,
        supervisor_managed: bool = True,
    ) -> None:
        _validate_role(role)
        self.config = config
        self.installation_id = installation_id
        self.release_id = release_id
        self.role = role
        self.stop_event = stop_event
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.supervisor_managed = supervisor_managed
        self.lock = ExclusiveFileLock(component_lock_path(config, role))
        self.owner: ManagedOwner | None = None
        self._thread: threading.Thread | None = None
        self._thread_stop = threading.Event()

    def __enter__(self) -> "ManagedRoleContext":
        if not self.lock.acquire():
            raise SupervisorError(f"managed role {self.role} is already owned")
        pid = os.getpid()
        token = process_creation_token(pid)
        if token is None:
            self.lock.release()
            raise SupervisorError(f"cannot inspect managed role {self.role} process identity")
        self.owner = ManagedOwner(
            installation_id=self.installation_id,
            root=str(self.config.root),
            role=self.role,
            release_id=self.release_id,
            pid=pid,
            process_creation_token=token,
            supervisor_managed=self.supervisor_managed,
        )
        _write_json_atomic(component_owner_path(self.config, self.role), {"format_version": 1, **asdict(self.owner)})
        self._write_heartbeat()
        self._thread = threading.Thread(target=self._heartbeat_loop, name=f"newsroom-{self.role}-heartbeat", daemon=True)
        self._thread.start()
        return self

    def _write_heartbeat(self) -> None:
        if self.owner is None:
            return
        _write_json_atomic(
            component_heartbeat_path(self.config, self.role),
            {
                "format_version": 1,
                "role": self.role,
                "pid": self.owner.pid,
                "process_creation_token": self.owner.process_creation_token,
                "updated_at": _utc_now(),
                "monotonic_time": time.monotonic(),
            },
        )

    def _heartbeat_loop(self) -> None:
        while not self._thread_stop.wait(self.heartbeat_interval_seconds):
            self._write_heartbeat()
            control = _read_json(component_control_path(self.config, self.role))
            if control is None or self.owner is None:
                continue
            try:
                action = str(control["action"])
                pid = int(control["pid"])
                token = str(control["process_creation_token"])
            except (KeyError, TypeError, ValueError):
                continue
            if action == "stop" and pid == self.owner.pid and token == self.owner.process_creation_token:
                self.stop_event.set()
                try:
                    component_control_path(self.config, self.role).unlink()
                except FileNotFoundError:
                    pass

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self._thread_stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.heartbeat_interval_seconds * 3))
        if self.owner is not None:
            current = current_owner(self.config, self.role)
            if current == self.owner:
                for path in (
                    component_owner_path(self.config, self.role),
                    component_heartbeat_path(self.config, self.role),
                    component_control_path(self.config, self.role),
                ):
                    try:
                        path.unlink()
                    except FileNotFoundError:
                        pass
        self.lock.release()


def request_component_stop(config: RuntimeConfig, owner: ManagedOwner) -> None:
    _write_json_atomic(
        component_control_path(config, owner.role),
        {
            "format_version": 1,
            "action": "stop",
            "pid": owner.pid,
            "process_creation_token": owner.process_creation_token,
            "requested_at": _utc_now(),
        },
    )


__all__ = [
    "ComponentState",
    "ManagedOwner",
    "ManagedRoleContext",
    "RuntimeManifest",
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
