"""Non-secret runtime identity, ownership, and endpoint diagnosis helpers."""
from __future__ import annotations

import ctypes
import hashlib
import http.client
import json
import os
import socket
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from . import __version__
from .config import RuntimeConfig


IDENTITY_FORMAT_VERSION = 1
OWNER_FORMAT_VERSION = 1
_MAX_IDENTITY_BYTES = 8192
_LOCK_RETRY_SECONDS = 0.01


class RuntimeIdentityError(RuntimeError):
    """Raised when persisted runtime identity is invalid or cannot be verified."""


class EndpointStatus(str, Enum):
    AVAILABLE = "available"
    MATCHING = "matching"
    MISMATCHED = "mismatched"
    UNMANAGED = "unmanaged"
    FOREIGN = "foreign"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class InstallationIdentity:
    installation_id: str
    root: str


@dataclass(frozen=True)
class RuntimeProcessIdentity:
    installation_id: str
    root: str
    role: str
    release_id: str
    pid: int
    process_creation_token: str
    host: str
    port: int

    def public_payload(self) -> dict[str, Any]:
        return {
            "installation_id": self.installation_id,
            "role": self.role,
            "release_id": self.release_id,
            "pid": self.pid,
            "process_creation_token": self.process_creation_token,
        }


@dataclass(frozen=True)
class EndpointDiagnosis:
    status: EndpointStatus
    detail: str
    identity: dict[str, Any] | None = None


class ExclusiveFileLock:
    """Cross-platform OS-backed exclusive lock held for the life of this object."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._file = None
        self.acquired = False

    def acquire(self, *, timeout_seconds: float = 0.0) -> bool:
        if self.acquired:
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file_obj = self.path.open("a+b")
        file_obj.seek(0, os.SEEK_END)
        if file_obj.tell() == 0:
            file_obj.write(b"0")
            file_obj.flush()
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        while True:
            try:
                self._lock(file_obj)
            except OSError:
                if time.monotonic() >= deadline:
                    file_obj.close()
                    return False
                time.sleep(_LOCK_RETRY_SECONDS)
                continue
            self._file = file_obj
            self.acquired = True
            return True

    def release(self) -> None:
        if not self.acquired or self._file is None:
            return
        try:
            self._unlock(self._file)
        finally:
            self._file.close()
            self._file = None
            self.acquired = False

    def __enter__(self) -> "ExclusiveFileLock":
        if not self.acquire():
            raise RuntimeIdentityError(f"could not acquire runtime lock: {self.path.name}")
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.release()

    @staticmethod
    def _lock(file_obj) -> None:
        file_obj.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(file_obj.fileno(), msvcrt.LK_NBLCK, 1)
            return
        import fcntl

        fcntl.flock(file_obj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock(file_obj) -> None:
        file_obj.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)
            return
        import fcntl

        fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)


def _runtime_state_dir(config: RuntimeConfig) -> Path:
    return config.root / "runtime"


def installation_identity_path(config: RuntimeConfig) -> Path:
    return _runtime_state_dir(config) / "installation.json"


def api_lock_path(config: RuntimeConfig) -> Path:
    return _runtime_state_dir(config) / "api.lock"


def api_owner_path(config: RuntimeConfig) -> Path:
    return _runtime_state_dir(config) / "api-owner.json"


def _normalized_root(path: str | Path) -> str:
    return os.path.normcase(str(Path(path).expanduser().resolve()))


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    if len(raw) > _MAX_IDENTITY_BYTES:
        raise RuntimeIdentityError(f"runtime identity file is too large: {path.name}")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeIdentityError(f"runtime identity file is invalid: {path.name}") from exc
    if not isinstance(value, dict):
        raise RuntimeIdentityError(f"runtime identity file is invalid: {path.name}")
    return value


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as file_obj:
            json.dump(payload, file_obj, sort_keys=True, separators=(",", ":"))
            file_obj.write("\n")
            file_obj.flush()
            os.fsync(file_obj.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def ensure_installation_identity(config: RuntimeConfig) -> InstallationIdentity:
    """Return a stable non-secret UUID bound to this canonical runtime root."""
    state_dir = _runtime_state_dir(config)
    state_dir.mkdir(parents=True, exist_ok=True)
    lock = ExclusiveFileLock(state_dir / "installation.lock")
    if not lock.acquire(timeout_seconds=2.0):
        raise RuntimeIdentityError("could not lock installation identity")
    try:
        path = installation_identity_path(config)
        payload = _read_json(path)
        if payload is None:
            identity = InstallationIdentity(
                installation_id=str(uuid.uuid4()),
                root=str(config.root),
            )
            _write_json_atomic(
                path,
                {
                    "format_version": IDENTITY_FORMAT_VERSION,
                    **asdict(identity),
                },
            )
            return identity
        if payload.get("format_version") != IDENTITY_FORMAT_VERSION:
            raise RuntimeIdentityError("unsupported installation identity format")
        try:
            installation_id = str(uuid.UUID(str(payload.get("installation_id", ""))))
        except ValueError as exc:
            raise RuntimeIdentityError("installation identity UUID is invalid") from exc
        stored_root = str(payload.get("root", ""))
        if _normalized_root(stored_root) != _normalized_root(config.root):
            raise RuntimeIdentityError(
                "installation identity belongs to a different runtime root; refusing to rewrite it"
            )
        return InstallationIdentity(installation_id=installation_id, root=str(config.root))
    finally:
        lock.release()


def _git_head(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    head = result.stdout.strip()
    return head if head else None


def _source_digest(code_root: Path) -> str:
    digest = hashlib.sha256()
    package_root = code_root / "newsroom"
    for path in sorted(package_root.rglob("*.py"), key=lambda item: item.as_posix()):
        relative = path.relative_to(code_root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def resolve_release_id(code_root: str | Path | None = None) -> str:
    """Return a stable release identity for installed artifacts or source runs."""
    root = Path(code_root).resolve() if code_root is not None else Path(__file__).resolve().parents[1]
    manifest_path = root / "release-manifest.json"
    manifest = None
    try:
        raw_manifest = manifest_path.read_bytes()
    except FileNotFoundError:
        pass
    else:
        if len(raw_manifest) <= 2 * 1024 * 1024:
            try:
                decoded = json.loads(raw_manifest.decode("utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                decoded = None
            if isinstance(decoded, dict):
                manifest = decoded
    if manifest is not None:
        for key in ("installed_artifact_sha256", "artifact_sha256", "source_commit"):
            value = manifest.get(key)
            if isinstance(value, str) and value.strip():
                return f"manifest:{value.strip()}"
    head = _git_head(root)
    if head is not None:
        return f"git:{head}"
    return f"source:{__version__}:{_source_digest(root)}"


def process_creation_token(pid: int) -> str | None:
    """Return an OS process-creation token suitable for detecting PID reuse."""
    if pid <= 0:
        return None
    if os.name == "nt":
        return _windows_process_creation_token(pid)
    proc_stat = Path(f"/proc/{pid}/stat")
    try:
        raw = proc_stat.read_text(encoding="utf-8")
    except (FileNotFoundError, PermissionError, OSError):
        return None
    end = raw.rfind(")")
    if end < 0:
        return None
    fields = raw[end + 2 :].split()
    if len(fields) <= 19:
        return None
    return f"linux-startticks:{fields[19]}"


def _windows_process_creation_token(pid: int) -> str | None:
    from ctypes import wintypes

    class FileTime(ctypes.Structure):
        _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    process_query_limited_information = 0x1000
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return None
    try:
        creation = FileTime()
        exit_time = FileTime()
        kernel_time = FileTime()
        user_time = FileTime()
        success = kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        )
        if not success:
            return None
        value = (creation.high << 32) | creation.low
        return f"win-filetime:{value}"
    finally:
        kernel32.CloseHandle(handle)


def build_process_identity(
    config: RuntimeConfig,
    installation: InstallationIdentity,
    *,
    role: str,
    release_id: str,
    host: str,
    port: int,
) -> RuntimeProcessIdentity:
    pid = os.getpid()
    creation = process_creation_token(pid)
    if creation is None:
        raise RuntimeIdentityError("could not verify current process creation time")
    return RuntimeProcessIdentity(
        installation_id=installation.installation_id,
        root=str(config.root),
        role=role,
        release_id=release_id,
        pid=pid,
        process_creation_token=creation,
        host=host,
        port=port,
    )


def write_api_owner(config: RuntimeConfig, identity: RuntimeProcessIdentity) -> None:
    _write_json_atomic(
        api_owner_path(config),
        {
            "format_version": OWNER_FORMAT_VERSION,
            **asdict(identity),
        },
    )


def read_api_owner(config: RuntimeConfig) -> RuntimeProcessIdentity | None:
    try:
        payload = _read_json(api_owner_path(config))
    except RuntimeIdentityError:
        return None
    if payload is None:
        return None
    if payload.get("format_version") != OWNER_FORMAT_VERSION:
        return None
    try:
        return RuntimeProcessIdentity(
            installation_id=str(uuid.UUID(str(payload["installation_id"]))),
            root=str(payload["root"]),
            role=str(payload["role"]),
            release_id=str(payload["release_id"]),
            pid=int(payload["pid"]),
            process_creation_token=str(payload["process_creation_token"]),
            host=str(payload["host"]),
            port=int(payload["port"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def clear_api_owner(config: RuntimeConfig, identity: RuntimeProcessIdentity) -> None:
    current = read_api_owner(config)
    if current is None:
        return
    if (
        current.pid != identity.pid
        or current.process_creation_token != identity.process_creation_token
        or current.installation_id != identity.installation_id
    ):
        return
    try:
        api_owner_path(config).unlink()
    except FileNotFoundError:
        pass


def verify_api_owner(
    config: RuntimeConfig,
    owner: RuntimeProcessIdentity | None,
    *,
    installation: InstallationIdentity,
    release_id: str,
    host: str,
    port: int,
) -> tuple[bool, str]:
    if owner is None:
        return False, "owner metadata is missing or invalid"
    if _normalized_root(owner.root) != _normalized_root(config.root):
        return False, "owner metadata refers to a different runtime root"
    if owner.installation_id != installation.installation_id:
        return False, "owner installation identity does not match this runtime root"
    if owner.role != "api":
        return False, "owner role is not api"
    if owner.release_id != release_id:
        return False, "owner release identity differs from this launch"
    if owner.host != host or owner.port != port:
        return False, "owner endpoint differs from this launch"
    creation = process_creation_token(owner.pid)
    if creation is None:
        return False, "owner process is not running or cannot be inspected"
    if creation != owner.process_creation_token:
        return False, "owner PID creation time does not match; PID may have been reused"
    return True, "verified"


def _endpoint_bind_available(host: str, port: int) -> bool:
    """Prove a loopback endpoint is bindable without taking lasting ownership."""
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    probe = socket.socket(family, socket.SOCK_STREAM)
    try:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind((host, port))
    except OSError:
        return False
    finally:
        probe.close()
    return True


def _endpoint_connect_state(host: str, port: int, timeout_seconds: float) -> str:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return "open"
    except ConnectionRefusedError:
        return "closed"
    except (TimeoutError, socket.timeout, OSError):
        return "closed" if _endpoint_bind_available(host, port) else "unknown"


def _http_json(host: str, port: int, path: str, timeout_seconds: float) -> tuple[int, dict[str, Any] | None] | None:
    connection = http.client.HTTPConnection(host, port, timeout=timeout_seconds)
    try:
        connection.request("GET", path, headers={"Connection": "close"})
        response = connection.getresponse()
        body = response.read(_MAX_IDENTITY_BYTES + 1)
    except (OSError, TimeoutError, http.client.HTTPException):
        return None
    finally:
        connection.close()
    if len(body) > _MAX_IDENTITY_BYTES:
        return response.status, None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return response.status, None
    return response.status, payload if isinstance(payload, dict) else None


def diagnose_endpoint(
    host: str,
    port: int,
    *,
    expected_installation_id: str,
    expected_release_id: str,
    expected_owner: RuntimeProcessIdentity | None = None,
    timeout_seconds: float = 0.35,
) -> EndpointDiagnosis:
    """Classify the configured endpoint without killing or changing anything."""
    # Prove a free loopback endpoint by binding before any client connect.
    # This avoids TCP self-connect on Windows when a configured server port is
    # inside the dynamic client range and would otherwise be chosen as the
    # source port for the probe itself.
    if _endpoint_bind_available(host, port):
        return EndpointDiagnosis(EndpointStatus.AVAILABLE, "configured endpoint is available")

    connect_state = _endpoint_connect_state(host, port, timeout_seconds)
    if connect_state == "closed":
        return EndpointDiagnosis(EndpointStatus.AVAILABLE, "configured endpoint is available")
    if connect_state == "unknown":
        return EndpointDiagnosis(
            EndpointStatus.UNKNOWN,
            "configured endpoint could not be proven free or safely identified",
        )

    identity_response = _http_json(host, port, "/api/v1/runtime/identity", timeout_seconds)
    if identity_response is not None:
        status_code, payload = identity_response
        if status_code == 200 and payload is not None and payload.get("service") == "newsroom":
            if payload.get("managed") is not True:
                return EndpointDiagnosis(
                    EndpointStatus.UNMANAGED,
                    "configured endpoint is serving Newsroom without managed runtime identity",
                    payload,
                )
            if payload.get("installation_id") != expected_installation_id:
                return EndpointDiagnosis(
                    EndpointStatus.MISMATCHED,
                    "configured endpoint belongs to a different Newsroom installation",
                    payload,
                )
            if payload.get("release_id") != expected_release_id:
                return EndpointDiagnosis(
                    EndpointStatus.MISMATCHED,
                    "configured endpoint belongs to a different Newsroom release",
                    payload,
                )
            if payload.get("role") != "api":
                return EndpointDiagnosis(
                    EndpointStatus.UNKNOWN,
                    "configured endpoint returned an unexpected Newsroom runtime role",
                    payload,
                )
            if expected_owner is not None:
                if payload.get("pid") != expected_owner.pid or payload.get(
                    "process_creation_token"
                ) != expected_owner.process_creation_token:
                    return EndpointDiagnosis(
                        EndpointStatus.UNKNOWN,
                        "endpoint identity does not match verified local owner metadata",
                        payload,
                    )
            return EndpointDiagnosis(
                EndpointStatus.MATCHING,
                "configured endpoint is the verified matching Newsroom API",
                payload,
            )
        if status_code not in {404, 405}:
            return EndpointDiagnosis(
                EndpointStatus.FOREIGN,
                "configured endpoint returned a non-Newsroom HTTP response",
            )

    health_response = _http_json(host, port, "/api/v1/health", timeout_seconds)
    if health_response is not None:
        status_code, payload = health_response
        if status_code == 200 and payload is not None and payload.get("service") == "newsroom":
            return EndpointDiagnosis(
                EndpointStatus.UNMANAGED,
                "configured endpoint is an older or unmanaged Newsroom API",
                payload,
            )
        return EndpointDiagnosis(
            EndpointStatus.FOREIGN,
            "configured endpoint is occupied by another HTTP service",
        )
    return EndpointDiagnosis(
        EndpointStatus.UNKNOWN,
        "configured endpoint is occupied but its owner could not be verified",
    )


def diagnosis_message(host: str, port: int, diagnosis: EndpointDiagnosis) -> str:
    endpoint = f"{host}:{port}"
    if diagnosis.status is EndpointStatus.MATCHING:
        return f"Newsroom API is already running for this installation at {endpoint}; reusing it."
    if diagnosis.status is EndpointStatus.MISMATCHED:
        return (
            f"Port {endpoint} is already used by a different Newsroom installation or release. "
            "Close that Newsroom instance or use its configured endpoint, then retry. "
            "No process was stopped and no alternate port was selected."
        )
    if diagnosis.status is EndpointStatus.UNMANAGED:
        return (
            f"Port {endpoint} is occupied by an unmanaged Newsroom API. "
            "Close it or use diagnostics before retrying; this launch will not take ownership or stop it."
        )
    if diagnosis.status is EndpointStatus.FOREIGN:
        return (
            f"Port {endpoint} is occupied by another application. Close that application, then retry. "
            "Newsroom did not stop it or choose another port."
        )
    if diagnosis.status is EndpointStatus.UNKNOWN:
        return (
            f"Port {endpoint} is occupied but ownership could not be verified. Inspect or close the listener, then retry. "
            "Newsroom did not stop it or choose another port."
        )
    return f"Port {endpoint} is available."


__all__ = [
    "EndpointDiagnosis",
    "EndpointStatus",
    "ExclusiveFileLock",
    "InstallationIdentity",
    "RuntimeIdentityError",
    "RuntimeProcessIdentity",
    "api_lock_path",
    "api_owner_path",
    "build_process_identity",
    "clear_api_owner",
    "diagnose_endpoint",
    "diagnosis_message",
    "ensure_installation_identity",
    "process_creation_token",
    "read_api_owner",
    "resolve_release_id",
    "verify_api_owner",
    "write_api_owner",
]
