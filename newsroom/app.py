"""FastAPI application factory for the standalone Newsroom shell."""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.exceptions import HTTPException

from . import __version__
from .auth import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    AuthService,
    InvalidCredentials,
    LoginThrottled,
    SESSION_TTL,
    SetupUnavailable,
    USERNAME_PATTERN,
)
from .config import RuntimeConfig
from .domain import CoreService, DomainError
from .domain_api import create_domain_router
from .evidence import EvidenceService
from .integrity import check_database
from .migrations import apply_migrations
from .runtime_status import RuntimeControlAction, RuntimeControlUnavailable, RuntimeStatusService
from .security import RequestLimiter, subsystem_for_path
from .telemetry import OperationalTelemetry


LOGGER = logging.getLogger("newsroom.api")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
MAX_REQUEST_BYTES = 1_048_576
GENERAL_REQUESTS_PER_MINUTE = 120
AUTH_REQUESTS_PER_MINUTE = 20
METRICS_REQUESTS_PER_MINUTE = 30


class AuthCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("username must be a string")
        return value.strip().lower()


class RuntimeControlRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: RuntimeControlAction


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _error_payload(request: Request, code: str, message: str, **extra) -> dict:
    error = {
        "code": code,
        "message": message,
        "request_id": _request_id(request),
    }
    error.update(extra)
    return {"error": error}


def _log_event(event: str, **fields: object) -> None:
    LOGGER.info(json.dumps({"event": event, **fields}, sort_keys=True, default=str))


def _safe_validation_errors(errors: list[dict]) -> list[dict]:
    """Return validation locations/messages without echoing submitted values."""
    safe: list[dict] = []
    for error in errors:
        safe_error = {
            key: value
            for key, value in error.items()
            if key not in {"input", "ctx"}
        }
        safe.append(safe_error)
    return safe


def create_app(
    config: RuntimeConfig | None = None,
    *,
    frontend_dist: str | Path | None = None,
    runtime_identity: dict[str, object] | None = None,
) -> FastAPI:
    runtime = config or RuntimeConfig.for_environment("dev")
    runtime.ensure_runtime_dirs()
    apply_migrations(runtime.database_path)
    auth = AuthService(runtime.database_path)
    runtime_status_service = RuntimeStatusService(runtime, runtime_identity)

    app = FastAPI(title="Newsroom", version=__version__)
    app.state.runtime_config = runtime
    app.state.telemetry = OperationalTelemetry()
    request_limiter = RequestLimiter()

    def _security_headers(response, request_id: str, request: Request) -> None:
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'"
        )
        if runtime.environment == "prod":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        if (
            request.url.path.startswith("/api/v1/auth/")
            or request.url.path == "/api/v1/metrics"
            or request.url.path.startswith("/api/v1/runtime/")
        ):
            response.headers["Cache-Control"] = "no-store"

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        started = time.perf_counter()
        supplied = request.headers.get("X-Request-ID", "")
        request.state.request_id = supplied if _REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        client_host = request.client.host if request.client else "unknown"
        is_auth_route = request.url.path in {"/api/v1/auth/setup", "/api/v1/auth/login"}
        is_metrics_route = request.url.path == "/api/v1/metrics"
        if is_auth_route:
            rate_bucket, rate_limit = "auth", AUTH_REQUESTS_PER_MINUTE
        elif is_metrics_route:
            rate_bucket, rate_limit = "metrics", METRICS_REQUESTS_PER_MINUTE
        else:
            rate_bucket, rate_limit = "api", GENERAL_REQUESTS_PER_MINUTE
        decision = request_limiter.check(f"{client_host}:{rate_bucket}", rate_limit)
        if not decision.allowed:
            response = JSONResponse(
                status_code=429,
                content=_error_payload(request, "rate_limited", "request rate limit exceeded"),
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )
            response.headers["X-RateLimit-Limit"] = str(rate_limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            _security_headers(response, request.state.request_id, request)
            app.state.telemetry.observe(
                method=request.method,
                path=request.url.path,
                status_code=429,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            return response
        declared_length = request.headers.get("Content-Length")
        if declared_length:
            try:
                too_large = int(declared_length) > MAX_REQUEST_BYTES
            except ValueError:
                too_large = True
            if too_large:
                response = JSONResponse(
                    status_code=413,
                    content=_error_payload(request, "request_too_large", "request body exceeds the configured limit"),
                )
                response.headers["X-RateLimit-Limit"] = str(rate_limit)
                response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
                _security_headers(response, request.state.request_id, request)
                app.state.telemetry.observe(
                    method=request.method,
                    path=request.url.path,
                    status_code=413,
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
                return response
        elif request.method in {"POST", "PUT", "PATCH"}:
            received = 0
            chunks: list[bytes] = []
            original_receive = request._receive
            async for chunk in request.stream():
                received += len(chunk)
                if received > MAX_REQUEST_BYTES:
                    response = JSONResponse(
                        status_code=413,
                        content=_error_payload(request, "request_too_large", "request body exceeds the configured limit"),
                    )
                    response.headers["X-RateLimit-Limit"] = str(rate_limit)
                    response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
                    _security_headers(response, request.state.request_id, request)
                    app.state.telemetry.observe(
                        method=request.method,
                        path=request.url.path,
                        status_code=413,
                        duration_ms=(time.perf_counter() - started) * 1000,
                    )
                    return response
                chunks.append(chunk)
            request._body = b"".join(chunks)
            replayed = False

            async def replay_body():
                nonlocal replayed
                if not replayed:
                    replayed = True
                    return {"type": "http.request", "body": request._body, "more_body": False}
                return await original_receive()

            request._receive = replay_body
        try:
            response = await call_next(request)
        except Exception:
            app.state.telemetry.observe(
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            _log_event(
                "http_request",
                method=request.method,
                path=request.url.path,
                request_id=request.state.request_id,
                status_code=500,
                subsystem=subsystem_for_path(request.url.path),
            )
            raise
        response.headers["X-RateLimit-Limit"] = str(rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        _security_headers(response, request.state.request_id, request)
        app.state.telemetry.observe(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        _log_event(
            "http_request",
            method=request.method,
            path=request.url.path,
            request_id=request.state.request_id,
            status_code=response.status_code,
            subsystem=subsystem_for_path(request.url.path),
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        code = "not_found" if exc.status_code == 404 else "http_error"
        message = str(exc.detail) if exc.detail else "request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(request, code, message),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                request,
                "validation_error",
                "request validation failed",
                fields=_safe_validation_errors(exc.errors()),
            ),
        )

    @app.exception_handler(DomainError)
    async def domain_exception_handler(request: Request, exc: DomainError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(request, exc.code, exc.message),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        _log_event(
            "unhandled_request_error",
            request_id=_request_id(request),
            error_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content=_error_payload(request, "internal_error", "internal server error"),
        )

    api = APIRouter(prefix="/api/v1")

    @api.get("/health")
    async def health(request: Request):
        return {
            "service": "newsroom",
            "status": "ok",
            "version": __version__,
            "request_id": _request_id(request),
        }

    @api.get("/runtime/identity")
    async def runtime_identity_status(request: Request):
        if runtime_identity is None:
            return {
                "service": "newsroom",
                "managed": False,
                "version": __version__,
                "request_id": _request_id(request),
            }
        return {
            "service": "newsroom",
            "managed": True,
            "version": __version__,
            "request_id": _request_id(request),
            **runtime_identity,
        }

    @api.get("/readiness")
    async def readiness(request: Request):
        report = check_database(runtime.database_path)
        if not report.ok:
            return JSONResponse(
                status_code=503,
                content={
                    "database": "error",
                    "request_id": _request_id(request),
                    "status": "not_ready",
                    "issues": [issue.code for issue in report.issues],
                },
            )
        return {
            "database": "ok",
            "request_id": _request_id(request),
            "status": "ready",
        }

    def require_user(request: Request):
        user = auth.authenticate(request.cookies.get(SESSION_COOKIE))
        if user is None:
            raise HTTPException(status_code=401, detail="authentication required")
        return user

    def require_csrf(request: Request, user) -> None:
        if not auth.valid_csrf(
            request.cookies.get(SESSION_COOKIE),
            request.headers.get("X-CSRF-Token"),
            request.cookies.get(CSRF_COOKIE),
        ):
            raise HTTPException(status_code=403, detail="csrf validation failed")

    @api.get("/runtime/status")
    async def runtime_status(request: Request):
        require_user(request)
        return {
            "request_id": _request_id(request),
            **runtime_status_service.snapshot(),
        }

    @api.post("/runtime/control", status_code=202)
    async def runtime_control(
        payload: RuntimeControlRequest,
        request: Request,
        background_tasks: BackgroundTasks,
    ):
        user = require_user(request)
        require_csrf(request, user)
        try:
            owner = runtime_status_service.prepare_control(payload.action)
        except RuntimeControlUnavailable as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        background_tasks.add_task(runtime_status_service.dispatch_control, owner)
        return {
            "accepted": True,
            "action": payload.action,
            "transition": "stopping" if payload.action == "stop_newsroom" else "restarting",
            "request_id": _request_id(request),
        }

    @api.get("/metrics")
    async def metrics(request: Request):
        require_user(request)
        return app.state.telemetry.snapshot()

    domain_service = CoreService(runtime.database_path)
    evidence_service = EvidenceService(runtime.database_path)

    @api.post("/auth/setup", status_code=201)
    async def setup(payload: AuthCredentials):
        try:
            username = auth.setup(payload.username, payload.password)
        except SetupUnavailable as exc:
            raise HTTPException(status_code=409, detail="setup unavailable") from exc
        return {"username": username}

    @api.post("/auth/login")
    async def login(payload: AuthCredentials):
        try:
            session = auth.login(payload.username, payload.password)
        except LoginThrottled as exc:
            raise HTTPException(
                status_code=429,
                detail="too many login attempts",
                headers={"Retry-After": "300"},
            ) from exc
        except InvalidCredentials as exc:
            raise HTTPException(status_code=401, detail="invalid credentials") from exc
        response = JSONResponse({"username": session.username})
        secure = runtime.environment == "prod"
        response.set_cookie(
            SESSION_COOKIE,
            session.session_token,
            max_age=int(SESSION_TTL.total_seconds()),
            httponly=True,
            secure=secure,
            samesite="lax",
            path="/",
        )
        response.set_cookie(
            CSRF_COOKIE,
            session.csrf_token,
            max_age=int(SESSION_TTL.total_seconds()),
            httponly=False,
            secure=secure,
            samesite="lax",
            path="/",
        )
        return response

    @api.get("/auth/me")
    async def me(request: Request):
        user = require_user(request)
        return {"username": user.username}

    @api.post("/auth/logout", status_code=204)
    async def logout(request: Request):
        user = require_user(request)
        require_csrf(request, user)
        auth.revoke(request.cookies.get(SESSION_COOKIE))
        response = JSONResponse(content=None, status_code=204)
        response.delete_cookie(SESSION_COOKIE, path="/")
        response.delete_cookie(CSRF_COOKIE, path="/")
        return response

    app.include_router(api)
    app.include_router(
        create_domain_router(
            domain_service,
            require_user,
            require_csrf,
            evidence_service=evidence_service,
        ),
        prefix="/api/v1",
    )

    dist = (
        Path(frontend_dist)
        if frontend_dist is not None
        else Path(__file__).resolve().parents[1] / "frontend" / "dist"
    )
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
    else:

        @app.get("/")
        async def shell_placeholder():
            return {"service": "newsroom", "status": "frontend_not_built"}

    return app


__all__ = ["create_app"]
