"""Explicit process entrypoints for the Windows production runtime."""
from __future__ import annotations

import argparse
import logging
import signal
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import uvicorn

from .app import create_app
from .config import RuntimeConfig
from .document_processing import (
    DocumentProcessingExecutionService,
    document_version_processing_rerun_factory,
)
from .jobs import JobService, compose_completion_hooks, compose_rerun_factories
from .migrations import apply_migrations
from .monitoring import MonitorExecutionService, monitor_job_completion_hook
from .research_questions import (
    research_job_completion_hook,
    research_job_rerun_factory,
    ResearchQuestionExecutionService,
    research_job_recovery_hook,
)
from .scheduler import SchedulerProcess
from .worker import WorkerProcess, merge_handlers


def _positive_interval(value: str) -> float:
    try:
        interval = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("interval must be numeric") from exc
    if not 0.1 <= interval <= 3600:
        raise argparse.ArgumentTypeError("interval must be between 0.1 and 3600 seconds")
    return interval


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _worker_id(value: str) -> str:
    worker_id = value.strip()
    if not worker_id or len(worker_id) > 200:
        raise argparse.ArgumentTypeError("worker-id must be 1-200 characters")
    return worker_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Newsroom Windows runtime processes")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("api", "worker", "scheduler"):
        command = commands.add_parser(name)
        command.add_argument("--environment", choices=("dev", "prod"), required=True)
        command.add_argument("--root", type=Path, required=True)
        command.add_argument("--interval", type=_positive_interval, default=None)
    api = commands.choices["api"]
    api.add_argument("--host", choices=("127.0.0.1", "::1"), default="127.0.0.1")
    api.add_argument("--port", type=_port, default=8127)
    worker = commands.choices["worker"]
    worker.add_argument("--worker-id", default="newsroom-worker", type=_worker_id)
    return parser


def runtime_config_from_options(options: Any) -> RuntimeConfig:
    return RuntimeConfig.for_environment(options.environment, root=options.root)


def _configure_logging(config: RuntimeConfig, process_name: str) -> None:
    config.logs_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        config.logs_dir / f"{process_name}.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler],
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _stop_event() -> threading.Event:
    event = threading.Event()

    def stop(_signum, _frame) -> None:
        event.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(signum, stop)
        except (ValueError, OSError):
            pass
    return event


def build_worker_handlers(db_path: str | Path) -> dict[str, Any]:
    """Compose the complete production handler set for every schedulable job type."""
    return merge_handlers(
        MonitorExecutionService(db_path).handlers(),
        ResearchQuestionExecutionService(db_path).handlers(),
        DocumentProcessingExecutionService(db_path).handlers(),
    )


def build_worker_queue(db_path: str | Path) -> JobService:
    """Build the production worker queue with centrally composed domain hooks.

    Research Question and Monitor completion hooks are composed independently:
    both run inside the same write transaction as the durable job-state
    transition they accompany, and each ignores job types it does not own.
    Rerun factories are chained the same way: the first factory that rebuilds
    the job wins and all others fall through to the generic clone semantics.
    """
    return JobService(
        db_path,
        recovery_hook=research_job_recovery_hook,
        completion_hook=compose_completion_hooks(
            research_job_completion_hook,
            monitor_job_completion_hook,
        ),
        rerun_factory=compose_rerun_factories(
            research_job_rerun_factory,
            document_version_processing_rerun_factory,
        ),
    )


def _run_worker(config: RuntimeConfig, options: Any) -> int:
    _configure_logging(config, "worker")
    handlers = build_worker_handlers(config.database_path)
    queue = build_worker_queue(config.database_path)
    process = WorkerProcess(
        config.database_path,
        handlers,
        worker_id=options.worker_id,
        queue=queue,
    )
    process.run_forever(_stop_event(), interval_seconds=options.interval or 1.0)
    return 0


def _run_scheduler(config: RuntimeConfig, options: Any) -> int:
    _configure_logging(config, "scheduler")
    process = SchedulerProcess(config.database_path)
    process.run_forever(_stop_event(), interval_seconds=options.interval or 30.0)
    return 0


def _run_api(config: RuntimeConfig, options: Any) -> int:
    _configure_logging(config, "api")
    uvicorn.run(
        create_app(config=config),
        host=options.host,
        port=options.port,
        log_level="info",
        access_log=False,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    options = build_parser().parse_args(argv)
    config = runtime_config_from_options(options)
    config.ensure_runtime_dirs()
    apply_migrations(config.database_path)
    if options.command == "api":
        return _run_api(config, options)
    if options.command == "worker":
        return _run_worker(config, options)
    return _run_scheduler(config, options)


if __name__ == "__main__":  # pragma: no cover - exercised by Windows task launchers
    raise SystemExit(main())


__all__ = ["build_parser", "build_worker_handlers", "build_worker_queue", "main", "runtime_config_from_options"]
