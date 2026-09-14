"""Transactional services for the user-managed Phase 03 domain."""
from __future__ import annotations

import re
import secrets
import sqlite3
import importlib
import json
import os
import sys
import uuid
from ipaddress import ip_address
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Protocol
from urllib.parse import urlsplit, urlunsplit

from . import storage
from .url_norm import normalize_url, parse_url, url_fingerprint


class DomainError(Exception):
    status_code = 400
    code = "domain_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class DomainNotFound(DomainError):
    status_code = 404
    code = "not_found"


class DomainConflict(DomainError):
    status_code = 409
    code = "conflict"


class DomainValidation(DomainError):
    status_code = 422
    code = "validation_error"


class CredentialStoreError(DomainError):
    status_code = 503
    code = "credential_store_unavailable"


class CredentialStoreUnavailable(CredentialStoreError):
    pass


class CredentialNotFound(CredentialStoreError):
    status_code = 404
    code = "credential_not_found"


SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SENSITIVE_SETTING_RE = re.compile(
    r"(?:password|secret|token|api[_-]?key|private|credential)", re.IGNORECASE
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def precise_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(16)}"


def normalized_text(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def normalized_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug or len(slug) > 120 or not SLUG_RE.fullmatch(slug):
        raise DomainValidation("slug must contain lowercase letters, numbers, and hyphens")
    return slug


def _as_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


AI_SUPPORTED_CAPABILITIES = ("article_analysis", "vocabulary", "source_discovery")
AI_ADAPTER_OPENAI_COMPATIBLE = "openai_compatible"
AI_LOCAL_ROUTE = "local"
AI_CONNECTION_ROUTE = "connection"
AI_FALLBACK_POLICIES = frozenset({"local", "fail"})
_AI_OPAQUE_REFERENCE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,199}$")
_CREDENTIAL_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")


def _ai_text(value: object, label: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise DomainValidation(f"{label} must be a string")
    result = value.strip()
    if not result:
        raise DomainValidation(f"{label} must not be empty")
    if len(result) > maximum:
        raise DomainValidation(f"{label} is too long")
    if any(ord(character) < 32 for character in result):
        raise DomainValidation(f"{label} contains control characters")
    return result


def normalize_ai_base_url(value: object) -> str:
    """Validate and normalize a provider base URL without accepting secrets."""
    raw = _ai_text(value, "base_url", maximum=2048)
    if any(character.isspace() for character in raw):
        raise DomainValidation("base_url must not contain whitespace")
    try:
        parsed = urlsplit(raw)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise DomainValidation("base_url has an invalid authority") from exc
    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"} or not hostname:
        raise DomainValidation("base_url must use http or https and include a host")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise DomainValidation("base_url must not contain user information")
    if parsed.query or parsed.fragment or "\\" in parsed.netloc or "%" in parsed.netloc:
        raise DomainValidation("base_url must not contain query, fragment, or ambiguous authority data")
    host = hostname.casefold().rstrip(".")
    if not host:
        raise DomainValidation("base_url host is invalid")
    if scheme == "http":
        try:
            loopback = ip_address(host).is_loopback
        except ValueError:
            loopback = host == "localhost"
        if not loopback:
            raise DomainValidation("http base_url is allowed only for loopback endpoints")
    if port is not None and not 1 <= port <= 65535:
        raise DomainValidation("base_url port is invalid")
    authority_host = f"[{host}]" if ":" in host else host
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    authority = authority_host if port is None or default_port else f"{authority_host}:{port}"
    path = parsed.path.rstrip("/")
    return urlunsplit((scheme, authority, path, "", ""))


def is_loopback_ai_base_url(value: str) -> bool:
    """Return whether an already-normalized AI URL targets loopback only."""
    try:
        host = urlsplit(str(value)).hostname
    except ValueError:
        return False
    if not host:
        return False
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return host.casefold().rstrip(".") == "localhost"


def _ai_opaque_reference(value: object | None) -> str | None:
    if value is None:
        return None
    reference = _ai_text(value, "credential_ref", maximum=200)
    if not _AI_OPAQUE_REFERENCE_RE.fullmatch(reference) or re.search(
        r"(?:api[_-]?key|secret|token|password|sk-[A-Za-z0-9])", reference, re.IGNORECASE
    ):
        raise DomainValidation("credential_ref must be an opaque vault reference")
    return reference


def _ai_positive_int(value: object, label: str, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise DomainValidation(f"{label} must be an integer between 1 and {maximum}")
    return value


def _ai_bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise DomainValidation(f"{label} must be a boolean")
    return value


class CredentialStore(Protocol):
    def put(self, namespace: str, connection_id: str, version: int, secret: str) -> None: ...

    def get(self, namespace: str, connection_id: str, version: int) -> str | None: ...

    def delete(self, namespace: str, connection_id: str, version: int) -> None: ...


class InMemoryCredentialStore:
    """Deterministic vault double for tests; never selected by production code."""

    def __init__(self) -> None:
        self.values: dict[tuple[str, str, int], str] = {}
        self.fail_on: set[str] = set()

    def _check(self, operation: str) -> None:
        if operation in self.fail_on:
            raise CredentialStoreError("credential store operation failed")

    def put(self, namespace: str, connection_id: str, version: int, secret: str) -> None:
        self._check("put")
        self.values[(namespace, connection_id, version)] = secret

    def get(self, namespace: str, connection_id: str, version: int) -> str | None:
        self._check("get")
        return self.values.get((namespace, connection_id, version))

    def delete(self, namespace: str, connection_id: str, version: int) -> None:
        self._check("delete")
        self.values.pop((namespace, connection_id, version), None)

    def contains(self, connection_id: str, version: int, *, namespace: str = "installation-test") -> bool:
        return (namespace, connection_id, version) in self.values


class OSCredentialStore:
    """Use only an explicitly selected OS-backed keyring backend."""

    def __init__(self, *, platform: str | None = None) -> None:
        selected = platform or sys.platform
        backend_path = {
            "win32": ("keyring.backends.Windows", "WinVaultKeyring"),
            "darwin": ("keyring.backends.macOS", "Keyring"),
        }.get(selected)
        if backend_path is None and selected.startswith("linux"):
            backend_path = ("keyring.backends.SecretService", "Keyring")
        if backend_path is None:
            raise CredentialStoreUnavailable("approved credential backend is unavailable")
        try:
            keyring = importlib.import_module("keyring")
            module = importlib.import_module(backend_path[0])
            backend_type = getattr(module, backend_path[1])
            backend = backend_type()
            keyring.set_keyring(backend)
        except Exception as exc:
            raise CredentialStoreUnavailable("approved credential backend is unavailable") from exc
        self._backend = backend

    @staticmethod
    def _service(namespace: str, connection_id: str, version: int) -> str:
        return f"Newsroom/{namespace}/{connection_id}/{version}"

    @staticmethod
    def _username(_connection_id: str, _version: int) -> str:
        return "credential"

    def put(self, namespace: str, connection_id: str, version: int, secret: str) -> None:
        try:
            self._backend.set_password(
                self._service(namespace, connection_id, version),
                self._username(connection_id, version),
                secret,
            )
        except Exception as exc:
            raise CredentialStoreError("credential store write failed") from exc

    def get(self, namespace: str, connection_id: str, version: int) -> str | None:
        try:
            return self._backend.get_password(
                self._service(namespace, connection_id, version),
                self._username(connection_id, version),
            )
        except Exception as exc:
            raise CredentialStoreError("credential store read failed") from exc

    def delete(self, namespace: str, connection_id: str, version: int) -> None:
        try:
            self._backend.delete_password(
                self._service(namespace, connection_id, version),
                self._username(connection_id, version),
            )
        except Exception as exc:
            raise CredentialStoreError("credential store delete failed") from exc


def _credential_namespace(value: object) -> str:
    if not isinstance(value, str) or not _CREDENTIAL_NAMESPACE_RE.fullmatch(value):
        raise CredentialStoreError("credential store namespace is invalid")
    return value


def _runtime_credential_namespace(db_path: Path) -> str | None:
    runtime_root = db_path.parent.parent
    identity_path = runtime_root / "runtime" / "installation.json"
    try:
        raw = identity_path.read_bytes()
        if len(raw) > 8192:
            return None
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        if Path(str(payload.get("root", ""))).expanduser().resolve() != runtime_root.resolve():
            return None
        if payload.get("format_version") != 1:
            return None
        return _credential_namespace(str(uuid.UUID(str(payload.get("installation_id", "")))))
    except (OSError, UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _credential_secret(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise DomainValidation("credential secret must not be empty")
    if len(value) > 16_384 or "\x00" in value:
        raise DomainValidation("credential secret is invalid or too long")
    return value


class AIConfigurationService:
    """Transactional public AI metadata and credential-store authority.

    Credential values are held only in the injected or explicitly selected OS
    store. SQLite retains an opaque reference and non-secret cleanup metadata;
    API projections never return either the reference or a credential value.
    """

    def __init__(
        self,
        db_path: str | Path,
        *,
        credential_store: CredentialStore | None = None,
        credential_namespace: str | None = None,
    ):
        self.db_path = Path(db_path)
        self.credential_store = credential_store
        self._resolved_credential_store: CredentialStore | None = None
        self.credential_namespace = (
            _credential_namespace(credential_namespace)
            if credential_namespace is not None
            else _runtime_credential_namespace(self.db_path)
        )

    @staticmethod
    def _generation(conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT generation FROM ai_config_state WHERE id = 1").fetchone()
        if row is None:
            raise DomainValidation("AI configuration schema is unavailable")
        return int(row[0])

    @staticmethod
    def _advance_generation(conn: sqlite3.Connection, now: str) -> int:
        current = AIConfigurationService._generation(conn)
        next_generation = current + 1
        conn.execute(
            "UPDATE ai_config_state SET generation = ?, updated_at = ? WHERE id = 1",
            (next_generation, now),
        )
        return next_generation

    @staticmethod
    def _connection_projection(row: sqlite3.Row, generation: int) -> dict[str, Any]:
        result = dict(row)
        result["enabled"] = bool(result["enabled"])
        result["credential_required"] = bool(result["credential_required"])
        result["credential_configured"] = bool(result.pop("credential_ref", None))
        cleanup_version = result.pop("credential_cleanup_version", None)
        result["credential_cleanup_required"] = cleanup_version is not None
        result["credential_removal_required"] = (
            cleanup_version is not None
            and cleanup_version == result.get("credential_ref_version")
            and not result["enabled"]
        )
        result["supported_capabilities"] = list(AI_SUPPORTED_CAPABILITIES)
        result["generation"] = generation
        return result

    @staticmethod
    def _route_projection(
        row: sqlite3.Row | Mapping[str, Any],
        connection: sqlite3.Row | Mapping[str, Any] | None,
        generation: int,
    ) -> dict[str, Any]:
        route = dict(row)
        route["effective"] = {
            "provider_route": AI_LOCAL_ROUTE,
            "provider": "local",
            "model": "local",
            "reason": "default_local",
        }
        if route["provider_route"] == AI_CONNECTION_ROUTE and connection is not None:
            configured = bool(connection["credential_ref"])
            if bool(connection["enabled"]) and (not bool(connection["credential_required"]) or configured):
                route["effective"] = {
                    "provider_route": AI_CONNECTION_ROUTE,
                    "provider": connection["adapter_kind"],
                    "model": connection["model"],
                    "connection_id": connection["id"],
                    "reason": "configured_connection",
                }
            elif route["fallback_policy"] == "fail":
                route["effective"] = {
                    "provider_route": AI_CONNECTION_ROUTE,
                    "provider": connection["adapter_kind"],
                    "model": connection["model"],
                    "connection_id": connection["id"],
                    "reason": "connection_unavailable",
                }
            else:
                route["effective"]["reason"] = "connection_unavailable"
        elif route["provider_route"] == AI_CONNECTION_ROUTE:
            if route["fallback_policy"] == "fail":
                route["effective"] = {
                    "provider_route": AI_CONNECTION_ROUTE,
                    "provider": "unavailable",
                    "model": None,
                    "connection_id": route["connection_id"],
                    "reason": "connection_missing",
                }
            else:
                route["effective"]["reason"] = "connection_missing"
        route["generation"] = generation
        return route

    def _snapshot(self, conn: sqlite3.Connection) -> dict[str, Any]:
        generation = self._generation(conn)
        rows = conn.execute("SELECT * FROM ai_connections ORDER BY display_name, id").fetchall()
        items = [self._connection_projection(row, generation) for row in rows]
        by_id = {row["id"]: row for row in rows}
        stored_routes = {
            row["capability"]: row
            for row in conn.execute("SELECT * FROM ai_capability_routes ORDER BY capability")
        }
        routes: list[dict[str, Any]] = []
        for capability in AI_SUPPORTED_CAPABILITIES:
            route = stored_routes.get(capability)
            if route is None:
                route = {
                    "capability": capability,
                    "provider_route": AI_LOCAL_ROUTE,
                    "connection_id": None,
                    "fallback_policy": "local",
                    "revision": 0,
                    "config_generation": generation,
                    "updated_at": None,
                }
            routes.append(self._route_projection(route, by_id.get(route["connection_id"]), generation))
        return {
            "generation": generation,
            "supported_capabilities": list(AI_SUPPORTED_CAPABILITIES),
            "items": items,
            "providers": items,
            "routes": routes,
            "effective_routes": {route["capability"]: route["effective"] for route in routes},
        }

    def list_connections(self) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return self._snapshot(conn)
        finally:
            conn.close()

    def get_connection(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            generation = self._generation(conn)
            row = conn.execute("SELECT * FROM ai_connections WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("AI connection not found")
            return self._connection_projection(row, generation)
        finally:
            conn.close()

    def create_connection(self, data: Mapping[str, Any]) -> dict[str, Any]:
        display_name = _ai_text(data.get("display_name"), "display_name", maximum=200)
        adapter_kind = data.get("adapter_kind", AI_ADAPTER_OPENAI_COMPATIBLE)
        if adapter_kind != AI_ADAPTER_OPENAI_COMPATIBLE:
            raise DomainValidation("unsupported AI adapter kind")
        base_url = normalize_ai_base_url(data.get("base_url"))
        model = _ai_text(data.get("model"), "model", maximum=200)
        enabled = _ai_bool(data.get("enabled", False), "enabled")
        if enabled:
            raise DomainValidation("new AI connections must be created disabled")
        credential_ref = _ai_opaque_reference(data.get("credential_ref"))
        credential_version = data.get("credential_ref_version")
        if credential_version is not None:
            credential_version = _ai_positive_int(credential_version, "credential_ref_version", maximum=1_000_000)
        if credential_version is not None and credential_ref is None:
            raise DomainValidation("credential_ref_version requires credential_ref")
        credential_required = _ai_bool(
            data.get("credential_required", True), "credential_required"
        )
        if not credential_required and not is_loopback_ai_base_url(base_url):
            raise DomainValidation(
                "keyless AI connections require a loopback base_url"
            )
        max_input_chars = _ai_positive_int(
            data.get("max_input_chars", 24_000), "max_input_chars", maximum=1_000_000
        )
        max_output_tokens = _ai_positive_int(
            data.get("max_output_tokens", 1_200), "max_output_tokens", maximum=100_000
        )
        now = utc_now()
        identifier = new_id("aic")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                generation = self._advance_generation(conn, now)
                conn.execute(
                    """
                    INSERT INTO ai_connections
                        (id, display_name, adapter_kind, base_url, model, enabled,
                         credential_ref, credential_ref_version, credential_required,
                         max_input_chars, max_output_tokens, revision, config_generation,
                         validation_status, validation_code, validation_revision,
                         validated_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 1, ?, 'unvalidated', NULL, NULL, NULL, ?, ?)
                    """,
                    (
                        identifier,
                        display_name,
                        adapter_kind,
                        base_url,
                        model,
                        credential_ref,
                        credential_version,
                        int(credential_required),
                        max_input_chars,
                        max_output_tokens,
                        generation,
                        now,
                        now,
                    ),
                )
        finally:
            conn.close()
        return self.get_connection(identifier)

    def _credential_store(self) -> CredentialStore:
        if self.credential_store is not None:
            return self.credential_store
        if self._resolved_credential_store is not None:
            return self._resolved_credential_store
        if self.credential_namespace is None:
            raise CredentialStoreUnavailable("approved credential backend is unavailable")
        self._resolved_credential_store = OSCredentialStore()
        return self._resolved_credential_store

    def _credential_slot(self, identifier: str, version: int) -> tuple[str, str, int]:
        if self.credential_namespace is None:
            raise CredentialStoreError("approved credential backend is unavailable")
        return self.credential_namespace, identifier, version

    @staticmethod
    def _credential_reference(namespace: str, identifier: str, version: int) -> str:
        return f"vault:{namespace}/{identifier}/{version}"

    def _connection_row(self, identifier: str) -> sqlite3.Row:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM ai_connections WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("AI connection not found")
            return row
        finally:
            conn.close()

    def _record_cleanup(self, identifier: str, version: int) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                current = conn.execute("SELECT * FROM ai_connections WHERE id = ?", (identifier,)).fetchone()
                if current is None:
                    raise DomainNotFound("AI connection not found")
                if current["credential_cleanup_version"] == version:
                    return self._connection_projection(current, self._generation(conn))
                now = utc_now()
                generation = self._advance_generation(conn, now)
                revision = int(current["revision"]) + 1
                conn.execute(
                    "UPDATE ai_connections SET credential_cleanup_version = ?, revision = ?, config_generation = ?, updated_at = ? WHERE id = ?",
                    (version, revision, generation, now, identifier),
                )
        finally:
            conn.close()
        return self.get_connection(identifier)

    def _clear_credential_metadata(
        self,
        identifier: str,
        *,
        expected_version: int,
    ) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                current = conn.execute("SELECT * FROM ai_connections WHERE id = ?", (identifier,)).fetchone()
                if current is None:
                    raise DomainNotFound("AI connection not found")
                if current["credential_ref_version"] != expected_version:
                    return self._connection_projection(current, self._generation(conn))
                now = utc_now()
                generation = self._advance_generation(conn, now)
                revision = int(current["revision"]) + 1
                conn.execute(
                    """
                    UPDATE ai_connections
                    SET credential_ref = NULL, credential_ref_version = NULL,
                        credential_cleanup_version = NULL, revision = ?,
                        config_generation = ?, validation_status = 'unvalidated',
                        validation_code = NULL, validation_revision = NULL,
                        validated_at = NULL, updated_at = ?
                    WHERE id = ?
                    """,
                    (revision, generation, now, identifier),
                )
        finally:
            conn.close()
        return self.get_connection(identifier)

    def set_credential(
        self,
        identifier: str,
        secret: object,
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        value = _credential_secret(secret)
        if expected_revision is not None:
            expected_revision = _ai_positive_int(expected_revision, "expected_revision", maximum=1_000_000)
        current = self._connection_row(identifier)
        base_revision = int(current["revision"])
        if expected_revision is not None and base_revision != expected_revision:
            raise DomainConflict("AI connection changed; refresh and retry")
        pending_version = current["credential_cleanup_version"]
        if pending_version is not None:
            raise DomainConflict("AI credential cleanup is pending; retry the removal")
        store = self._credential_store()
        old_version: int | None = None
        new_slot: tuple[str, str, int] | None = None
        put_attempted = False
        try:
            conn = storage.connect(self.db_path)
            try:
                with storage.write_tx(conn):
                    latest = conn.execute("SELECT * FROM ai_connections WHERE id = ?", (identifier,)).fetchone()
                    if latest is None:
                        raise DomainNotFound("AI connection not found")
                    if int(latest["revision"]) != base_revision:
                        raise DomainConflict("AI connection changed; refresh and retry")
                    if latest["credential_cleanup_version"] is not None:
                        raise DomainConflict("AI credential cleanup is pending; retry the removal")
                    old_version = latest["credential_ref_version"]
                    next_version = int(old_version or 0) + 1
                    namespace, connection_id, version = self._credential_slot(identifier, next_version)
                    new_slot = (namespace, connection_id, version)
                    put_attempted = True
                    # Hold the SQLite write lock while reserving the version and
                    # writing the vault entry. This prevents concurrent callers
                    # with the same expected revision from sharing a slot.
                    store.put(namespace, connection_id, version, value)
                    new_ref = self._credential_reference(namespace, identifier, next_version)
                    now = utc_now()
                    generation = self._advance_generation(conn, now)
                    revision = int(latest["revision"]) + 1
                    conn.execute(
                        """
                        UPDATE ai_connections
                        SET credential_ref = ?, credential_ref_version = ?,
                            credential_cleanup_version = NULL, revision = ?,
                            config_generation = ?, validation_status = 'unvalidated',
                            validation_code = NULL, validation_revision = NULL,
                            validated_at = NULL, updated_at = ?
                        WHERE id = ?
                        """,
                        (new_ref, next_version, revision, generation, now, identifier),
                    )
            finally:
                conn.close()
        except Exception:
            if not put_attempted or new_slot is None:
                raise
            try:
                store.delete(*new_slot)
            except Exception as cleanup_error:
                try:
                    self._record_cleanup(identifier, new_slot[2])
                except Exception as record_error:
                    raise CredentialStoreError(
                        "credential update was not committed; new credential cleanup needs retry"
                    ) from record_error
                raise CredentialStoreError(
                    "credential update was not committed; new credential cleanup needs retry"
                ) from cleanup_error
            raise

        if old_version is not None and current["credential_ref"]:
            try:
                old_namespace, old_connection_id, old_slot = self._credential_slot(identifier, int(old_version))
                store.delete(old_namespace, old_connection_id, old_slot)
            except Exception:
                return self._record_cleanup(identifier, int(old_version))
        return self.get_connection(identifier)

    def read_credential(self, identifier: str) -> str:
        current = self._connection_row(identifier)
        version = current["credential_ref_version"]
        if not current["credential_ref"] or version is None:
            raise CredentialNotFound("AI connection credential is not configured")
        namespace, connection_id, slot = self._credential_slot(identifier, int(version))
        value = self._credential_store().get(namespace, connection_id, slot)
        if value is None:
            raise CredentialNotFound("AI connection credential is not configured")
        return value

    def _disable_and_reroute(self, identifier: str, expected_revision: int | None) -> dict[str, Any]:
        if expected_revision is not None:
            expected_revision = _ai_positive_int(expected_revision, "expected_revision", maximum=1_000_000)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                current = conn.execute("SELECT * FROM ai_connections WHERE id = ?", (identifier,)).fetchone()
                if current is None:
                    raise DomainNotFound("AI connection not found")
                if expected_revision is not None and int(current["revision"]) != expected_revision:
                    raise DomainConflict("AI connection changed; refresh and retry")
                now = utc_now()
                generation = self._advance_generation(conn, now)
                revision = int(current["revision"]) + 1
                cleanup_version = current["credential_cleanup_version"] or current["credential_ref_version"]
                conn.execute(
                    "UPDATE ai_connections SET enabled = 0, credential_cleanup_version = ?, revision = ?, config_generation = ?, updated_at = ? WHERE id = ?",
                    (cleanup_version, revision, generation, now, identifier),
                )
                route = conn.execute(
                    "SELECT * FROM ai_capability_routes WHERE connection_id = ?", (identifier,)
                ).fetchall()
                for route_row in route:
                    route_revision = int(route_row["revision"]) + 1
                    conn.execute(
                        """
                        UPDATE ai_capability_routes
                        SET provider_route = 'local', connection_id = NULL,
                            fallback_policy = 'local', revision = ?,
                            config_generation = ?, updated_at = ?
                        WHERE capability = ?
                        """,
                        (route_revision, generation, now, route_row["capability"]),
                    )
        finally:
            conn.close()
        return self.get_connection(identifier)

    def remove_credential(
        self,
        identifier: str,
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        disabled = self._disable_and_reroute(identifier, expected_revision)
        current = self._connection_row(identifier)
        try:
            store = self._credential_store()
        except CredentialStoreError:
            return self.get_connection(identifier)
        pending_version = current["credential_cleanup_version"]
        if pending_version is None:
            return disabled
        namespace, connection_id, slot = self._credential_slot(identifier, int(pending_version))
        try:
            store.delete(namespace, connection_id, slot)
        except Exception:
            return self.get_connection(identifier)

        current_version = current["credential_ref_version"]
        if current_version is not None and current_version != pending_version:
            try:
                store.delete(namespace, connection_id, int(current_version))
            except Exception as delete_error:
                try:
                    return self._record_cleanup(identifier, int(current_version))
                except Exception as record_error:
                    raise CredentialStoreError(
                        "credential removal needs retry"
                    ) from record_error
        try:
            return self._clear_credential_metadata(
                identifier,
                expected_version=int(current_version or pending_version),
            )
        except Exception:
            try:
                return self._record_cleanup(identifier, int(current_version or pending_version))
            except Exception as cleanup_error:
                raise CredentialStoreError(
                    "credential was removed from the vault; metadata cleanup needs retry"
                ) from cleanup_error

    def update_connection(
        self,
        identifier: str,
        data: Mapping[str, Any],
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        if expected_revision is not None:
            expected_revision = _ai_positive_int(expected_revision, "expected_revision", maximum=1_000_000)
        allowed = {
            "display_name",
            "adapter_kind",
            "base_url",
            "model",
            "enabled",
            "credential_required",
            "max_input_chars",
            "max_output_tokens",
        }
        changes = {key: value for key, value in data.items() if key in allowed}
        if not changes:
            raise DomainValidation("at least one AI connection field must be supplied")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                current = conn.execute("SELECT * FROM ai_connections WHERE id = ?", (identifier,)).fetchone()
                if current is None:
                    raise DomainNotFound("AI connection not found")
                if expected_revision is not None and int(current["revision"]) != expected_revision:
                    raise DomainConflict("AI connection changed; refresh and retry")
                values: dict[str, Any] = {}
                for key, value in changes.items():
                    if key == "display_name":
                        values[key] = _ai_text(value, key, maximum=200)
                    elif key == "adapter_kind":
                        if value != AI_ADAPTER_OPENAI_COMPATIBLE:
                            raise DomainValidation("unsupported AI adapter kind")
                        values[key] = value
                    elif key == "base_url":
                        values[key] = normalize_ai_base_url(value)
                    elif key == "model":
                        values[key] = _ai_text(value, key, maximum=200)
                    elif key == "enabled":
                        values[key] = int(_ai_bool(value, key))
                    elif key == "credential_required":
                        values[key] = int(_ai_bool(value, key))
                    elif key == "max_input_chars":
                        values[key] = _ai_positive_int(value, key, maximum=1_000_000)
                    elif key == "max_output_tokens":
                        values[key] = _ai_positive_int(value, key, maximum=100_000)
                next_enabled = bool(values.get("enabled", current["enabled"]))
                next_credential_required = bool(
                    values.get("credential_required", current["credential_required"])
                )
                next_base_url = str(values.get("base_url", current["base_url"]))
                if not next_credential_required and not is_loopback_ai_base_url(next_base_url):
                    raise DomainValidation(
                        "keyless AI connections require a loopback base_url"
                    )
                if (
                    "base_url" in values
                    and values["base_url"] != current["base_url"]
                    and current["credential_ref"]
                ):
                    raise DomainConflict(
                        "AI connection base_url change requires removing credential first"
                    )
                if next_enabled and next_credential_required and not current["credential_ref"]:
                    raise DomainConflict("AI connection credentials are not configured")
                now = utc_now()
                generation = self._advance_generation(conn, now)
                revision = int(current["revision"]) + 1
                values.update({"revision": revision, "config_generation": generation, "updated_at": now})
                if any(key in values for key in ("base_url", "model", "adapter_kind", "max_input_chars", "max_output_tokens")):
                    values.update({"validation_status": "unvalidated", "validation_code": None, "validation_revision": None, "validated_at": None})
                assignments = ", ".join(f"{key} = ?" for key in values)
                conn.execute(
                    f"UPDATE ai_connections SET {assignments} WHERE id = ?",
                    [*values.values(), identifier],
                )
        finally:
            conn.close()
        return self.get_connection(identifier)

    def record_validation(
        self,
        identifier: str,
        *,
        expected_revision: int,
        status: str,
        code: str,
    ) -> dict[str, Any]:
        """Persist a bounded result tied to the exact connection revision."""
        expected_revision = _ai_positive_int(
            expected_revision, "expected_revision", maximum=1_000_000
        )
        status = _ai_text(status, "validation_status", maximum=16)
        if status not in {"passed", "failed"}:
            raise DomainValidation("validation_status must be passed or failed")
        code = _ai_text(code, "validation_code", maximum=80)
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                current = conn.execute(
                    "SELECT revision FROM ai_connections WHERE id = ?", (identifier,)
                ).fetchone()
                if current is None:
                    raise DomainNotFound("AI connection not found")
                if int(current["revision"]) != expected_revision:
                    raise DomainConflict("AI connection changed; discard this validation result")
                conn.execute(
                    """
                    UPDATE ai_connections
                    SET validation_status = ?, validation_code = ?,
                        validation_revision = ?, validated_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, code, expected_revision, now, now, identifier),
                )
        finally:
            conn.close()
        return self.get_connection(identifier)

    def remove_connection(
        self,
        identifier: str,
        *,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Disable/reroute and remove a connection only after vault cleanup."""
        disabled = self.remove_credential(identifier, expected_revision=expected_revision)
        current = self._connection_row(identifier)
        if current["credential_ref"] is not None or current["credential_cleanup_version"] is not None:
            disabled["deleted"] = False
            disabled["removal_required"] = True
            return disabled
        deletion_revision = int(disabled["revision"])
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                current = conn.execute(
                    "SELECT revision FROM ai_connections WHERE id = ?", (identifier,)
                ).fetchone()
                if current is None:
                    raise DomainNotFound("AI connection not found")
                if int(current["revision"]) != deletion_revision:
                    raise DomainConflict("AI connection changed; refresh and retry")
                now = utc_now()
                generation = self._advance_generation(conn, now)
                deleted = conn.execute(
                    """
                    DELETE FROM ai_connections
                    WHERE id = ? AND revision = ?
                      AND credential_ref IS NULL
                      AND credential_cleanup_version IS NULL
                      AND enabled = 0
                    """,
                    (identifier, deletion_revision),
                )
                if deleted.rowcount != 1:
                    raise DomainConflict("AI connection changed; refresh and retry")
        finally:
            conn.close()
        return {"id": identifier, "deleted": True, "generation": generation}

    def set_route(
        self,
        capability: str,
        *,
        provider_route: str | None = None,
        connection_id: str | None = None,
        fallback_policy: str = "local",
        expected_generation: int | None = None,
    ) -> dict[str, Any]:
        capability = _ai_text(capability, "capability", maximum=100)
        if capability not in AI_SUPPORTED_CAPABILITIES:
            raise DomainValidation("unsupported AI capability")
        if provider_route is None:
            provider_route = AI_CONNECTION_ROUTE if connection_id else AI_LOCAL_ROUTE
        else:
            provider_route = _ai_text(provider_route, "provider_route", maximum=32)
        if provider_route not in {AI_LOCAL_ROUTE, AI_CONNECTION_ROUTE}:
            raise DomainValidation("unsupported AI route")
        fallback_policy = _ai_text(fallback_policy, "fallback_policy", maximum=32)
        if fallback_policy not in AI_FALLBACK_POLICIES:
            raise DomainValidation("unsupported AI fallback policy")
        if connection_id is not None:
            connection_id = _ai_text(connection_id, "connection_id", maximum=200)
        if provider_route == AI_LOCAL_ROUTE:
            if connection_id is not None:
                raise DomainValidation("local AI route cannot include a connection")
        elif not connection_id:
            raise DomainValidation("connection AI route requires connection_id")
        if expected_generation is not None:
            expected_generation = _ai_positive_int(expected_generation, "expected_generation", maximum=1_000_000_000)
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                generation = self._generation(conn)
                if expected_generation is not None and generation != expected_generation:
                    raise DomainConflict("AI configuration changed; refresh and retry")
                if connection_id is not None:
                    if conn.execute("SELECT 1 FROM ai_connections WHERE id = ?", (connection_id,)).fetchone() is None:
                        raise DomainNotFound("AI connection not found")
                existing = conn.execute(
                    "SELECT revision FROM ai_capability_routes WHERE capability = ?", (capability,)
                ).fetchone()
                revision = int(existing[0]) + 1 if existing is not None else 1
                next_generation = self._advance_generation(conn, now)
                conn.execute(
                    """
                    INSERT INTO ai_capability_routes
                        (capability, provider_route, connection_id, fallback_policy,
                         revision, config_generation, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(capability) DO UPDATE SET
                        provider_route = excluded.provider_route,
                        connection_id = excluded.connection_id,
                        fallback_policy = excluded.fallback_policy,
                        revision = excluded.revision,
                        config_generation = excluded.config_generation,
                        updated_at = excluded.updated_at
                    """,
                    (capability, provider_route, connection_id, fallback_policy, revision, next_generation, now),
                )
        finally:
            conn.close()
        result = self.list_connections()
        return next(route for route in result["routes"] if route["capability"] == capability)


class CoreService:
    """One-service boundary for short-lived SQLite transactions."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _require(self, conn, table: str, identifier: str, label: str, *, live: bool = False):
        condition = "id = ?"
        params: list[object] = [identifier]
        if live:
            condition += " AND deleted_at IS NULL"
        row = conn.execute(
            f"SELECT * FROM {table} WHERE {condition}", params
        ).fetchone()
        if row is None:
            raise DomainNotFound(f"{label} not found")
        return row

    def _list(
        self,
        table: str,
        columns: str,
        *,
        where: Iterable[str] = (),
        params: Iterable[object] = (),
        order_by: str,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise DomainValidation("page must be >= 1 and page_size must be between 1 and 100")
        conn = storage.connect(self.db_path)
        try:
            clauses = list(where)
            query_params = list(params)
            predicate = " AND ".join(clauses) if clauses else "1 = 1"
            total = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {predicate}", query_params
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT {columns} FROM {table} WHERE {predicate} "
                f"ORDER BY {order_by} LIMIT ? OFFSET ?",
                [*query_params, page_size, (page - 1) * page_size],
            ).fetchall()
            return {
                "items": [_as_dict(row) for row in rows],
                "page": page,
                "page_size": page_size,
                "total": total,
            }
        finally:
            conn.close()

    @staticmethod
    def _q_filter(q: Optional[str], fields: tuple[str, ...]) -> tuple[str, list[str]]:
        if not q:
            return "", []
        value = f"%{normalized_text(q)}%"
        return "(" + " OR ".join(f"LOWER({field}) LIKE ?" for field in fields) + ")", [value] * len(fields)

    def _insert(self, conn, table: str, values: Mapping[str, object]) -> None:
        columns = tuple(values)
        placeholders = ", ".join("?" for _ in columns)
        try:
            conn.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(values[column] for column in columns),
            )
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("resource already exists or violates a relationship") from exc

    def _update(self, conn, table: str, identifier: str, values: Mapping[str, object]) -> None:
        if not values:
            raise DomainValidation("at least one field must be supplied")
        assignments = ", ".join(f"{column} = ?" for column in values)
        try:
            result = conn.execute(
                f"UPDATE {table} SET {assignments} WHERE id = ?",
                [*values.values(), identifier],
            )
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("resource already exists or violates a relationship") from exc
        if result.rowcount != 1:
            raise DomainNotFound("resource not found")

    def _soft_delete(self, table: str, identifier: str) -> None:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if conn.execute(
                    f"SELECT 1 FROM {table} WHERE id = ? AND deleted_at IS NULL", (identifier,)
                ).fetchone() is None:
                    raise DomainNotFound("resource not found")
                conn.execute(
                    f"UPDATE {table} SET deleted_at = ?, updated_at = ? WHERE id = ?",
                    (utc_now(), utc_now(), identifier),
                )
        finally:
            conn.close()

    def create_category(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("cat")
        now = utc_now()
        values = {
            "id": identifier,
            "slug": normalized_slug(data["slug"]),
            "name": data["name"].strip(),
            "description": data.get("description", ""),
            "display_order": data.get("display_order", 0),
            "enabled": int(data.get("enabled", True)),
            "priority": data.get("priority", "normal"),
            "max_stories_per_run": data.get("max_stories_per_run"),
            "created_at": now,
            "updated_at": now,
        }
        if not values["name"]:
            raise DomainValidation("name must not be empty")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._insert(conn, "categories", values)
        finally:
            conn.close()
        return self.get_category(identifier, include_deleted=True)

    def list_categories(self, *, q=None, slug=None, include_deleted=False, page=1, page_size=25):
        clauses: list[str] = [] if include_deleted else ["deleted_at IS NULL"]
        params: list[object] = []
        if slug:
            clauses.append("slug = ?")
            params.append(normalized_slug(slug))
        query, query_params = self._q_filter(q, ("name", "slug"))
        if query:
            clauses.append(query)
            params.extend(query_params)
        return self._list(
            "categories",
            "id, slug, name, description, display_order, enabled, priority, max_stories_per_run, created_at, updated_at, deleted_at",
            where=clauses,
            params=params,
            order_by="display_order ASC, slug ASC, id ASC",
            page=page,
            page_size=page_size,
        )

    def get_category(self, identifier: str, *, include_deleted=False) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return _as_dict(self._require(conn, "categories", identifier, "category", live=not include_deleted))
        finally:
            conn.close()

    def update_category(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"name", "description", "display_order", "enabled", "priority", "max_stories_per_run"}
        values = {key: value for key, value in data.items() if key in allowed}
        if "name" in values:
            values["name"] = values["name"].strip()
            if not values["name"]:
                raise DomainValidation("name must not be empty")
        values["updated_at"] = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "categories", identifier, "category", live=True)
                self._update(conn, "categories", identifier, values)
        finally:
            conn.close()
        return self.get_category(identifier, include_deleted=True)

    def delete_category(self, identifier: str) -> None:
        self._soft_delete("categories", identifier)

    def create_topic(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("top")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                category = self._require(conn, "categories", data["category_id"], "category")
                if category["deleted_at"] is not None:
                    raise DomainConflict("category is deleted")
                self._insert(
                    conn,
                    "topics",
                    {
                        "id": identifier,
                        "category_id": data["category_id"],
                        "slug": normalized_slug(data["slug"]),
                        "name": data["name"].strip(),
                        "description": data.get("description", ""),
                        "enabled": int(data.get("enabled", True)),
                        "priority": data.get("priority", "normal"),
                        "max_queries_per_run": data.get("max_queries_per_run"),
                        "max_stories_per_run": data.get("max_stories_per_run"),
                        "created_at": now,
                        "updated_at": now,
                    },
                )
        finally:
            conn.close()
        return self.get_topic(identifier, include_deleted=True)

    def list_topics(self, *, category_id=None, q=None, include_deleted=False, page=1, page_size=25):
        clauses: list[str] = [] if include_deleted else ["deleted_at IS NULL"]
        params: list[object] = []
        if category_id:
            clauses.append("category_id = ?")
            params.append(category_id)
        query, query_params = self._q_filter(q, ("name", "slug"))
        if query:
            clauses.append(query)
            params.extend(query_params)
        return self._list(
            "topics",
            "id, category_id, slug, name, description, enabled, priority, max_queries_per_run, max_stories_per_run, created_at, updated_at, deleted_at",
            where=clauses,
            params=params,
            order_by="name COLLATE NOCASE ASC, id ASC",
            page=page,
            page_size=page_size,
        )

    def get_topic(self, identifier: str, *, include_deleted=False) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return _as_dict(self._require(conn, "topics", identifier, "topic", live=not include_deleted))
        finally:
            conn.close()

    def update_topic(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"name", "description", "enabled", "priority", "max_queries_per_run", "max_stories_per_run"}
        values = {key: value for key, value in data.items() if key in allowed}
        if "name" in values:
            values["name"] = values["name"].strip()
            if not values["name"]:
                raise DomainValidation("name must not be empty")
        values["updated_at"] = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "topics", identifier, "topic", live=True)
                self._update(conn, "topics", identifier, values)
        finally:
            conn.close()
        return self.get_topic(identifier, include_deleted=True)

    def delete_topic(self, identifier: str) -> None:
        self._soft_delete("topics", identifier)

    def create_vocabulary(self, topic_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("term")
        term = data["term"].strip()
        if not term:
            raise DomainValidation("term must not be empty")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "topics", topic_id, "topic", live=True)
                self._insert(
                    conn,
                    "topic_terms",
                    {
                        "id": identifier,
                        "topic_id": topic_id,
                        "term": term,
                        "term_normalized": normalized_text(term),
                        "term_type": data.get("term_type", "include"),
                        "weight": data.get("weight", 1.0),
                        "created_at": now,
                        "concept_kind": data.get("concept_kind", "term"),
                    },
                )
        finally:
            conn.close()
        # A direct user vocabulary edit is an explicit scope change. Persist it
        # for existing topic monitors without making pending AI suggestions active.
        from .monitoring import MonitorService
        MonitorService(self.db_path).refresh_topic_scopes(topic_id, change_type="manual")
        return self.get_vocabulary_item(identifier)

    def get_vocabulary_item(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM topic_terms WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("vocabulary term not found")
            return _as_dict(row)
        finally:
            conn.close()

    def list_vocabulary(self, topic_id: str, *, page=1, page_size=100):
        conn = storage.connect(self.db_path)
        try:
            self._require(conn, "topics", topic_id, "topic", live=True)
        finally:
            conn.close()
        return self._list(
            "topic_terms",
            "id, topic_id, term, term_normalized, term_type, weight, concept_kind, created_at",
            where=["topic_id = ?"],
            params=[topic_id],
            order_by="term_type ASC, concept_kind ASC, term_normalized ASC, id ASC",
            page=page,
            page_size=page_size,
        )

    def list_scope_suggestions(self, topic_id: str, *, page=1, page_size=25):
        conn = storage.connect(self.db_path)
        try:
            self._require(conn, "topics", topic_id, "topic", live=True)
        finally:
            conn.close()
        return self._list(
            "topic_scope_suggestions",
            "id, topic_id, suggestion_type, value, value_normalized, rationale, source, status, created_at, reviewed_at, reviewed_by",
            where=["topic_id = ?"],
            params=[topic_id],
            order_by="created_at DESC, id DESC",
            page=page,
            page_size=page_size,
        )

    def create_scope_suggestion(self, topic_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        suggestion_type = data["suggestion_type"]
        value = data["value"].strip()
        if not value:
            raise DomainValidation("suggestion value must not be empty")
        identifier = new_id("scope")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "topics", topic_id, "topic", live=True)
                self._insert(
                    conn,
                    "topic_scope_suggestions",
                    {
                        "id": identifier,
                        "topic_id": topic_id,
                        "suggestion_type": suggestion_type,
                        "value": value,
                        "value_normalized": normalized_text(value),
                        "rationale": data.get("rationale", ""),
                        "source": data.get("source", "ai"),
                        "status": "pending",
                        "created_at": now,
                    },
                )
        finally:
            conn.close()
        return self.get_scope_suggestion(identifier)

    def get_scope_suggestion(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM topic_scope_suggestions WHERE id = ?", (identifier,)
            ).fetchone()
            if row is None:
                raise DomainNotFound("scope suggestion not found")
            return _as_dict(row)
        finally:
            conn.close()

    def review_scope_suggestion(self, identifier: str, *, approved: bool, reviewed_by: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute(
                    "SELECT * FROM topic_scope_suggestions WHERE id = ?", (identifier,)
                ).fetchone()
                if row is None:
                    raise DomainNotFound("scope suggestion not found")
                if row[7] != "pending":
                    raise DomainConflict("scope suggestion has already been reviewed")
                now = utc_now()
                if approved:
                    mapping = {
                        "term": ("include", "term"),
                        "alias": ("alias", "term"),
                        "acronym": ("alias", "acronym"),
                        "related_concept": ("include", "related_concept"),
                        "exclude": ("exclude", "term"),
                    }
                    term_type, concept_kind = mapping[row[2]]
                    self._insert(
                        conn,
                        "topic_terms",
                        {
                            "id": new_id("term"),
                            "topic_id": row[1],
                            "term": row[3],
                            "term_normalized": row[4],
                            "term_type": term_type,
                            "weight": 1.0,
                            "created_at": now,
                            "concept_kind": concept_kind,
                        },
                    )
                conn.execute(
                    "UPDATE topic_scope_suggestions SET status = ?, reviewed_at = ?, reviewed_by = ? WHERE id = ?",
                    ("approved" if approved else "rejected", now, reviewed_by, identifier),
                )
        finally:
            conn.close()
        if approved:
            from .monitoring import MonitorService
            MonitorService(self.db_path).refresh_topic_scopes(row[1], changed_by=reviewed_by, change_type="approved")
        return self.get_scope_suggestion(identifier)

    def create_subject(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("sub")
        now = utc_now()
        try:
            canonical_url = normalize_url(data["canonical_url"]) if data.get("canonical_url") else None
        except ValueError as exc:
            raise DomainValidation(str(exc)) from exc
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._insert(
                    conn,
                    "subjects",
                    {
                        "id": identifier,
                        "canonical_name": data["canonical_name"].strip(),
                        "subject_type": data["subject_type"],
                        "description": data.get("description", ""),
                        "canonical_url": canonical_url,
                        "canonical_id": data.get("canonical_id"),
                        "enabled": int(data.get("enabled", True)),
                        "priority": data.get("priority", "normal"),
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                for alias in data.get("aliases", []):
                    alias = alias.strip()
                    if not alias:
                        raise DomainValidation("alias must not be empty")
                    self._insert(
                        conn,
                        "subject_aliases",
                        {
                            "id": new_id("alias"),
                            "subject_id": identifier,
                            "alias": alias,
                            "alias_normalized": normalized_text(alias),
                            "created_at": now,
                        },
                    )
                for topic_id in data.get("topic_ids", []):
                    self._require(conn, "topics", topic_id, "topic", live=True)
                    self._insert(
                        conn,
                        "topic_subjects",
                        {"topic_id": topic_id, "subject_id": identifier},
                    )
        finally:
            conn.close()
        return self.get_subject(identifier, include_deleted=True)

    def list_subjects(self, *, q=None, subject_type=None, include_deleted=False, page=1, page_size=25):
        clauses: list[str] = [] if include_deleted else ["deleted_at IS NULL"]
        params: list[object] = []
        if subject_type:
            clauses.append("subject_type = ?")
            params.append(subject_type)
        query, query_params = self._q_filter(q, ("canonical_name", "canonical_id"))
        if query:
            clauses.append(query)
            params.extend(query_params)
        return self._list(
            "subjects",
            "id, canonical_name, subject_type, description, canonical_url, canonical_id, enabled, priority, created_at, updated_at, deleted_at",
            where=clauses,
            params=params,
            order_by="canonical_name COLLATE NOCASE ASC, id ASC",
            page=page,
            page_size=page_size,
        )

    def get_subject(self, identifier: str, *, include_deleted=False) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = self._require(conn, "subjects", identifier, "subject", live=not include_deleted)
            result = _as_dict(row)
            result["aliases"] = [
                item[0]
                for item in conn.execute(
                    "SELECT alias FROM subject_aliases WHERE subject_id = ? ORDER BY alias_normalized, id",
                    (identifier,),
                )
            ]
            return result
        finally:
            conn.close()

    def update_subject(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"canonical_name", "description", "canonical_url", "canonical_id", "enabled", "priority"}
        values = {key: value for key, value in data.items() if key in allowed}
        if "canonical_name" in values:
            values["canonical_name"] = values["canonical_name"].strip()
        if "canonical_url" in values and values["canonical_url"]:
            try:
                values["canonical_url"] = normalize_url(values["canonical_url"])
            except ValueError as exc:
                raise DomainValidation(str(exc)) from exc
        values["updated_at"] = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                current = self._require(conn, "subjects", identifier, "subject", live=True)
                self._update(conn, "subjects", identifier, values)
                if "canonical_name" in values and values["canonical_name"] != current["canonical_name"]:
                    from .monitoring import MonitorService

                    MonitorService._refresh_need_scopes_tx(
                        conn,
                        "subject",
                        identifier,
                        changed_by=data.get("changed_by"),
                        change_type="approved",
                        created_at=values["updated_at"],
                    )
        finally:
            conn.close()
        return self.get_subject(identifier, include_deleted=True)

    def add_subject_alias(self, identifier: str, alias: str) -> dict[str, Any]:
        alias = alias.strip()
        if not alias:
            raise DomainValidation("alias must not be empty")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "subjects", identifier, "subject", live=True)
                self._insert(
                    conn,
                    "subject_aliases",
                    {
                        "id": new_id("alias"),
                        "subject_id": identifier,
                        "alias": alias,
                        "alias_normalized": normalized_text(alias),
                        "created_at": utc_now(),
                    },
                )
                from .monitoring import MonitorService

                MonitorService._refresh_need_scopes_tx(
                    conn,
                    "subject",
                    identifier,
                    changed_by=None,
                    change_type="approved",
                )
        finally:
            conn.close()
        return self.get_subject(identifier, include_deleted=True)

    def delete_subject(self, identifier: str) -> None:
        self._soft_delete("subjects", identifier)

    def create_source(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("src")
        now = utc_now()
        try:
            homepage_url = normalize_url(data["homepage_url"]) if data.get("homepage_url") else None
            feed_url = normalize_url(data["feed_url"]) if data.get("feed_url") else None
        except ValueError as exc:
            raise DomainValidation(str(exc)) from exc
        domain = data.get("domain")
        if not domain and homepage_url:
            domain = parse_url(homepage_url)["domain"]
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._insert(
                    conn,
                    "sources",
                    {
                        "id": identifier,
                        "name": data["name"].strip(),
                        "slug": normalized_slug(data["slug"]),
                        "domain": domain,
                        "homepage_url": homepage_url,
                        "feed_url": feed_url,
                        "source_kind": data.get("source_kind", "web"),
                        "default_quality": data.get("default_quality", "unknown"),
                        "created_at": now,
                        "updated_at": now,
                    },
                )
        finally:
            conn.close()
        return self.get_source(identifier, include_deleted=True)

    def list_sources(self, *, q=None, include_deleted=False, page=1, page_size=25):
        clauses: list[str] = [] if include_deleted else ["deleted_at IS NULL"]
        params: list[object] = []
        query, query_params = self._q_filter(
            q, ("name", "slug", "domain", "homepage_url", "feed_url")
        )
        if query:
            clauses.append(query)
            params.extend(query_params)
        return self._list(
            "sources",
            "id, name, slug, domain, homepage_url, feed_url, source_kind, default_quality, created_at, updated_at, deleted_at",
            where=clauses,
            params=params,
            order_by="name COLLATE NOCASE ASC, id ASC",
            page=page,
            page_size=page_size,
        )

    def get_source(self, identifier: str, *, include_deleted=False) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return _as_dict(self._require(conn, "sources", identifier, "source", live=not include_deleted))
        finally:
            conn.close()

    def update_source(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"name", "domain", "homepage_url", "feed_url", "source_kind", "default_quality"}
        values = {key: value for key, value in data.items() if key in allowed}
        if "homepage_url" in values and values["homepage_url"]:
            try:
                values["homepage_url"] = normalize_url(values["homepage_url"])
            except ValueError as exc:
                raise DomainValidation(str(exc)) from exc
        if "feed_url" in values and values["feed_url"]:
            try:
                values["feed_url"] = normalize_url(values["feed_url"])
            except ValueError as exc:
                raise DomainValidation(str(exc)) from exc
        values["updated_at"] = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "sources", identifier, "source", live=True)
                self._update(conn, "sources", identifier, values)
        finally:
            conn.close()
        return self.get_source(identifier, include_deleted=True)

    def delete_source(self, identifier: str) -> None:
        self._soft_delete("sources", identifier)

    def create_document(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("doc")
        now = utc_now()
        try:
            canonical_url = normalize_url(data["canonical_url"])
        except ValueError as exc:
            raise DomainValidation(str(exc)) from exc
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "sources", data["source_id"], "source", live=True)
                self._insert(
                    conn,
                    "documents",
                    {
                        "id": identifier,
                        "source_id": data["source_id"],
                        "canonical_url": canonical_url,
                        "canonical_url_hash": url_fingerprint(canonical_url),
                        "title": data["title"].strip(),
                        "title_normalized": normalized_text(data["title"]),
                        "published_at": data.get("published_at"),
                        "first_seen_at": now,
                        "created_at": now,
                    },
                )
        finally:
            conn.close()
        return self.get_document(identifier)

    def list_documents(self, *, source_id=None, q=None, page=1, page_size=25):
        clauses: list[str] = []
        params: list[object] = []
        if source_id:
            clauses.append("source_id = ?")
            params.append(source_id)
        query, query_params = self._q_filter(q, ("title", "canonical_url"))
        if query:
            clauses.append(query)
            params.extend(query_params)
        return self._list(
            "documents",
            "id, source_id, canonical_url, canonical_url_hash, title, title_normalized, published_at, first_seen_at, created_at",
            where=clauses,
            params=params,
            order_by="created_at DESC, id DESC",
            page=page,
            page_size=page_size,
        )

    def get_document(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return _as_dict(self._require(conn, "documents", identifier, "document"))
        finally:
            conn.close()

    def update_document(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        values = {key: value for key, value in data.items() if key in {"title", "published_at"}}
        if "title" in values:
            values["title"] = values["title"].strip()
            values["title_normalized"] = normalized_text(values["title"])
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "documents", identifier, "document")
                self._update(conn, "documents", identifier, values)
        finally:
            conn.close()
        return self.get_document(identifier)

    def update_vocabulary(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        values = {key: value for key, value in data.items() if key in {"term", "term_type", "concept_kind", "weight"}}
        if "term" in values:
            values["term"] = values["term"].strip()
            if not values["term"]:
                raise DomainValidation("term must not be empty")
            values["term_normalized"] = normalized_text(values["term"])
        conn = storage.connect(self.db_path)
        topic_id = None
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT topic_id FROM topic_terms WHERE id = ?", (identifier,)).fetchone()
                if row is None:
                    raise DomainNotFound("vocabulary term not found")
                topic_id = row[0]
                self._update(conn, "topic_terms", identifier, values)
        finally:
            conn.close()
        from .monitoring import MonitorService
        MonitorService(self.db_path).refresh_topic_scopes(topic_id, change_type="manual")
        return self.get_vocabulary_item(identifier)

    def delete_vocabulary(self, identifier: str) -> None:
        conn = storage.connect(self.db_path)
        topic_id = None
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT topic_id FROM topic_terms WHERE id = ?", (identifier,)).fetchone()
                if row is None:
                    raise DomainNotFound("vocabulary term not found")
                topic_id = row[0]
                result = conn.execute("DELETE FROM topic_terms WHERE id = ?", (identifier,))
                if result.rowcount != 1:
                    raise DomainNotFound("vocabulary term not found")
        finally:
            conn.close()
        from .monitoring import MonitorService
        MonitorService(self.db_path).refresh_topic_scopes(topic_id, change_type="manual")

    def create_story(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("st")
        revision_id = new_id("rev")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                for topic_id in data.get("topic_ids", []):
                    self._require(conn, "topics", topic_id, "topic", live=True)
                for subject_id in data.get("subject_ids", []):
                    self._require(conn, "subjects", subject_id, "subject", live=True)
                self._insert(
                    conn,
                    "stories",
                    {
                        "id": identifier,
                        "lifecycle": data.get("lifecycle", "developing"),
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                self._insert(
                    conn,
                    "story_revisions",
                    {
                        "id": revision_id,
                        "story_id": identifier,
                        "revision_number": 1,
                        "headline": data["headline"].strip(),
                        "headline_normalized": normalized_text(data["headline"]),
                        "summary": data.get("summary", ""),
                        "why_it_matters": data.get("why_it_matters", ""),
                        "material_change": int(data.get("material_change", False)),
                        "claim_set_hash": data.get("claim_set_hash"),
                        "created_at": now,
                    },
                )
                self._insert(
                    conn,
                    "story_review",
                    {"story_id": identifier, "updated_at": now},
                )
                for topic_id in data.get("topic_ids", []):
                    self._insert(conn, "story_topics", {"story_id": identifier, "topic_id": topic_id})
                for subject_id in data.get("subject_ids", []):
                    self._insert(conn, "story_subjects", {"story_id": identifier, "subject_id": subject_id})
        finally:
            conn.close()
        return self.get_story(identifier, include_deleted=True)

    def list_stories(self, *, q=None, lifecycle=None, include_deleted=False, page=1, page_size=25):
        clauses: list[str] = [] if include_deleted else ["deleted_at IS NULL"]
        params: list[object] = []
        if lifecycle:
            clauses.append("lifecycle = ?")
            params.append(lifecycle)
        if q:
            clauses.append(
                "(LOWER(stories.id) LIKE ? OR EXISTS (SELECT 1 FROM story_revisions WHERE story_revisions.story_id = stories.id AND LOWER(story_revisions.headline) LIKE ?))"
            )
            value = f"%{normalized_text(q)}%"
            params.extend([value, value])
        return self._list(
            "stories",
            "id, lifecycle, created_at, updated_at, deleted_at",
            where=clauses,
            params=params,
            order_by="updated_at DESC, id DESC",
            page=page,
            page_size=page_size,
        )

    def get_story(self, identifier: str, *, include_deleted=False) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = self._require(conn, "stories", identifier, "story", live=not include_deleted)
            result = _as_dict(row)
            revision = conn.execute(
                "SELECT * FROM story_revisions WHERE story_id = ? ORDER BY revision_number DESC, id DESC LIMIT 1",
                (identifier,),
            ).fetchone()
            result["current_revision"] = _as_dict(revision)
            review = conn.execute(
                "SELECT * FROM story_review WHERE story_id = ?", (identifier,)
            ).fetchone()
            if review is not None:
                review_result = _as_dict(review)
                reviewed_number = 0
                if review_result["last_reviewed_revision_id"]:
                    reviewed = conn.execute(
                        "SELECT revision_number FROM story_revisions WHERE id = ? AND story_id = ?",
                        (review_result["last_reviewed_revision_id"], identifier),
                    ).fetchone()
                    reviewed_number = reviewed["revision_number"] if reviewed else 0
                review_result["new_update"] = conn.execute(
                    """
                    SELECT 1 FROM story_revisions
                    WHERE story_id = ? AND material_change = 1 AND revision_number > ?
                    LIMIT 1
                    """,
                    (identifier, reviewed_number),
                ).fetchone() is not None
                result["review"] = review_result
            result["subject_ids"] = [
                item[0] for item in conn.execute(
                    "SELECT subject_id FROM story_subjects WHERE story_id = ? ORDER BY subject_id", (identifier,)
                )
            ]
            result["topic_ids"] = [
                item[0] for item in conn.execute(
                    "SELECT topic_id FROM story_topics WHERE story_id = ? ORDER BY topic_id", (identifier,)
                )
            ]
            result["tag_ids"] = [
                item[0] for item in conn.execute(
                    "SELECT tag_id FROM story_tags WHERE story_id = ? ORDER BY tag_id", (identifier,)
                )
            ]
            return result
        finally:
            conn.close()

    def update_story(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        values = {key: value for key, value in data.items() if key in {"lifecycle"}}
        values["updated_at"] = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "stories", identifier, "story", live=True)
                self._update(conn, "stories", identifier, values)
        finally:
            conn.close()
        return self.get_story(identifier, include_deleted=True)

    def create_story_revision(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        # Keep the legacy service entry point evidence-bound as well as the
        # HTTP route. This prevents callers that still hold CoreService from
        # bypassing the Phase 04 closed-world audit.
        from .evidence import EvidenceService

        return EvidenceService(self.db_path).create_story_revision(identifier, data)

    def delete_story(self, identifier: str) -> None:
        self._soft_delete("stories", identifier)

    def create_tag(self, data: Mapping[str, Any]) -> dict[str, Any]:
        name = data["name"].strip()
        if not name:
            raise DomainValidation("tag name must not be empty")
        namespace = str(data.get("namespace", "user")).strip()
        tag_type = str(data.get("tag_type", "user"))
        if not namespace or len(namespace) > 64 or not re.fullmatch(r"[A-Za-z0-9._:-]+", namespace):
            raise DomainValidation("tag namespace is invalid")
        if tag_type not in {"user", "smart"}:
            raise DomainValidation("tag type must be user or smart")
        identifier = new_id("tag")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                existing = conn.execute(
                    "SELECT id FROM tags WHERE namespace = ? AND normalized_name = ?",
                    (namespace, normalized_text(name)),
                ).fetchone()
                if existing is not None:
                    identifier = existing[0]
                    return self.get_tag(identifier)
                self._insert(
                    conn,
                    "tags",
                    {
                        "id": identifier,
                        "name": name,
                        "normalized_name": normalized_text(name),
                        "namespace": namespace,
                        "tag_type": tag_type,
                        "created_at": utc_now(),
                    },
                )
        finally:
            conn.close()
        return self.get_tag(identifier)

    def list_tags(self, *, q=None, namespace=None, tag_type=None, page=1, page_size=25):
        clauses: list[str] = []
        params: list[object] = []
        if namespace:
            clauses.append("namespace = ?")
            params.append(namespace)
        if tag_type:
            clauses.append("tag_type = ?")
            params.append(tag_type)
        query, query_params = self._q_filter(q, ("name", "normalized_name"))
        if query:
            clauses.append(query)
            params.extend(query_params)
        return self._list(
            "tags",
            "id, name, normalized_name, namespace, tag_type, created_at",
            where=clauses,
            params=params,
            order_by="normalized_name ASC, id ASC",
            page=page,
            page_size=page_size,
        )

    def get_tag(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return _as_dict(self._require(conn, "tags", identifier, "tag"))
        finally:
            conn.close()

    def update_tag(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        name = data.get("name", "").strip()
        if not name:
            raise DomainValidation("tag name must not be empty")
        namespace = data.get("namespace")
        tag_type = data.get("tag_type")
        if namespace is not None and (not str(namespace).strip() or not re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", str(namespace).strip())):
            raise DomainValidation("tag namespace is invalid")
        if tag_type is not None and tag_type not in {"user", "smart"}:
            raise DomainValidation("tag type must be user or smart")
        values = {"name": name, "normalized_name": normalized_text(name)}
        if namespace is not None:
            values["namespace"] = str(namespace).strip()
        if tag_type is not None:
            values["tag_type"] = tag_type
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._update(
                    conn,
                    "tags",
                    identifier,
                    values,
                )
        finally:
            conn.close()
        return self.get_tag(identifier)

    def delete_tag(self, identifier: str) -> None:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if conn.execute("SELECT 1 FROM tags WHERE id = ?", (identifier,)).fetchone() is None:
                    raise DomainNotFound("tag not found")
                if conn.execute("SELECT 1 FROM story_tags WHERE tag_id = ?", (identifier,)).fetchone() is not None:
                    raise DomainConflict("tag is still attached to a story")
                conn.execute("DELETE FROM tags WHERE id = ?", (identifier,))
        finally:
            conn.close()

    def tag_story(self, story_id: str, tag_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "stories", story_id, "story", live=True)
                self._require(conn, "tags", tag_id, "tag")
                self._insert(
                    conn,
                    "story_tags",
                    {"story_id": story_id, "tag_id": tag_id, "created_at": utc_now()},
                )
                if conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'tag_assignments'").fetchone() is not None:
                    conn.execute(
                        "INSERT OR IGNORE INTO tag_assignments(id, tag_id, object_type, object_id, origin, reason, created_at) VALUES (?, ?, 'story', ?, 'user', 'legacy story tag assignment', ?)",
                        (new_id("tagassign"), tag_id, story_id, utc_now()),
                    )
        finally:
            conn.close()
        return self.get_story(story_id, include_deleted=True)

    def set_setting(self, key: str, value: str) -> dict[str, Any]:
        key = key.strip()
        if not key or len(key) > 120 or SENSITIVE_SETTING_RE.search(key):
            raise DomainValidation("setting key is invalid or sensitive")
        if len(value) > 4000:
            raise DomainValidation("setting value is too long")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    """
                    INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                    """,
                    (key, value, now),
                )
        finally:
            conn.close()
        return {"key": key, "value": value, "updated_at": now}

    def list_settings(self, *, page=1, page_size=100):
        result = self._list(
            "settings",
            "key, value, updated_at",
            where=[
                "LOWER(key) NOT LIKE '%password%'",
                "LOWER(key) NOT LIKE '%secret%'",
                "LOWER(key) NOT LIKE '%token%'",
                "LOWER(key) NOT LIKE '%api_key%'",
                "LOWER(key) NOT LIKE '%credential%'",
                "LOWER(key) NOT LIKE '%private%'",
            ],
            order_by="key ASC",
            page=page,
            page_size=page_size,
        )
        return result


__all__ = [
    "AIConfigurationService",
    "AI_SUPPORTED_CAPABILITIES",
    "CoreService",
    "CredentialNotFound",
    "CredentialStore",
    "CredentialStoreError",
    "InMemoryCredentialStore",
    "OSCredentialStore",
    "DomainConflict",
    "DomainError",
    "DomainNotFound",
    "DomainValidation",
    "is_loopback_ai_base_url",
    "normalize_ai_base_url",
]
