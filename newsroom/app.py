"""FastAPI application factory for the standalone Newsroom shell."""
from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from . import __version__
from .config import RuntimeConfig
from .integrity import check_database
from .migrations import apply_migrations


LOGGER = logging.getLogger("newsroom.api")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


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


def create_app(
    config: RuntimeConfig | None = None,
    *,
    frontend_dist: str | Path | None = None,
) -> FastAPI:
    runtime = config or RuntimeConfig.for_environment("dev")
    runtime.ensure_runtime_dirs()
    apply_migrations(runtime.database_path)

    app = FastAPI(title="Newsroom", version=__version__)
    app.state.runtime_config = runtime

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        supplied = request.headers.get("X-Request-ID", "")
        request.state.request_id = supplied if _REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        _log_event(
            "http_request",
            method=request.method,
            path=request.url.path,
            request_id=request.state.request_id,
            status_code=response.status_code,
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        code = "not_found" if exc.status_code == 404 else "http_error"
        message = str(exc.detail) if exc.detail else "request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(request, code, message),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                request,
                "validation_error",
                "request validation failed",
                fields=exc.errors(),
            ),
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

    app.include_router(api)

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
