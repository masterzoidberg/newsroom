from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from newsroom.config import RuntimeConfig
from newsroom.runtime_supervisor import RuntimeSupervisor


ROOT = Path(__file__).resolve().parents[1]
INSTALLATION_ID = "11111111-1111-4111-8111-111111111111"
RELEASE_ID = "git:test-release"


def _managed_child_command(config: RuntimeConfig, role: str, *, ignore_stop_seconds: float = 0.0):
    code = f'''
import threading,time,sys
from newsroom.config import RuntimeConfig
from newsroom.runtime_supervisor import ManagedRoleContext
config=RuntimeConfig.for_environment(sys.argv[1], root=sys.argv[2])
stop=threading.Event()
with ManagedRoleContext(config, installation_id=sys.argv[3], release_id=sys.argv[4], role=sys.argv[5], stop_event=stop, heartbeat_interval_seconds=0.05):
    if {ignore_stop_seconds!r} > 0:
        while not stop.is_set(): time.sleep(0.02)
        time.sleep({ignore_stop_seconds!r})
    else:
        while not stop.wait(0.02): pass
'''
    return [sys.executable, "-c", code, config.environment, str(config.root), INSTALLATION_ID, RELEASE_ID, role]


def _supervisor_process_command(config: RuntimeConfig):
    child_code = """
import threading,time,sys
from newsroom.config import RuntimeConfig
from newsroom.runtime_supervisor import ManagedRoleContext
config=RuntimeConfig.for_environment(sys.argv[1], root=sys.argv[2])
stop=threading.Event()
with ManagedRoleContext(config, installation_id=sys.argv[3], release_id=sys.argv[4], role=sys.argv[5], stop_event=stop, heartbeat_interval_seconds=0.05):
    while not stop.wait(0.02): pass
"""
    code = f"""
import sys,threading
from newsroom.config import RuntimeConfig
from newsroom.runtime_supervisor import RuntimeSupervisor
config=RuntimeConfig.for_environment(sys.argv[1], root=sys.argv[2])
installation_id=sys.argv[3]; release_id=sys.argv[4]
child_code={child_code!r}
def child(role):
    return [sys.executable,'-c',child_code,config.environment,str(config.root),installation_id,release_id,role]
supervisor=RuntimeSupervisor(
    config, installation_id=installation_id, release_id=release_id, host='127.0.0.1', port=18127,
    command_factory=child, heartbeat_timeout_seconds=0.3, startup_timeout_seconds=2.0,
    shutdown_timeout_seconds=2.0, restart_limit=3, restart_backoff_seconds=0.01, poll_interval_seconds=0.02,
    api_readiness=lambda: (True,'fixture ready'),
)
raise SystemExit(supervisor.run_forever(threading.Event()))
"""
    return [sys.executable, "-c", code, config.environment, str(config.root), INSTALLATION_ID, RELEASE_ID]


def _supervisor(config: RuntimeConfig, *, command_factory=None, restart_limit=3, startup_timeout=2.0):
    return RuntimeSupervisor(
        config,
        installation_id=INSTALLATION_ID,
        release_id=RELEASE_ID,
        host="127.0.0.1",
        port=18127,
        command_factory=command_factory or (lambda role: _managed_child_command(config, role)),
        heartbeat_timeout_seconds=0.3,
        startup_timeout_seconds=startup_timeout,
        shutdown_timeout_seconds=2.0,
        restart_limit=restart_limit,
        restart_backoff_seconds=0.01,
        poll_interval_seconds=0.02,
        api_readiness=lambda: (True, "fixture ready"),
    )


def _wait_healthy(supervisor: RuntimeSupervisor, role: str, timeout: float = 2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = supervisor.state(role)
        if state.status == "healthy":
            return state
        time.sleep(0.02)
    raise AssertionError(f"{role} did not become healthy: {supervisor.state(role)}")


def _cleanup(supervisor: RuntimeSupervisor):
    result = supervisor.shutdown(timeout_seconds=2.0)
    if result.drained:
        return
    for process in list(supervisor._children.values()):
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def test_repeated_supervisor_reconciles_existing_children_without_duplicates(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    first = _supervisor(config)
    second = _supervisor(config)
    try:
        first.prepare()
        initial = first.ensure_all()
        assert all(state.status == "healthy" for state in initial.values())
        pids = {role: state.owner.pid for role, state in initial.items() if state.owner}

        second.prepare()  # active managed locks mean no migration write is attempted
        reused = second.ensure_all()
        assert all(state.status == "healthy" for state in reused.values())
        assert {role: state.owner.pid for role, state in reused.items() if state.owner} == pids
        assert second._children == {}
    finally:
        _cleanup(first)


def test_supervisor_process_crash_leaves_children_reconcilable_without_duplicates(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    process = subprocess.Popen(
        _supervisor_process_command(config),
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    adopted = _supervisor(config)
    try:
        original = {role: _wait_healthy(adopted, role, timeout=4.0).owner.pid for role in ("api", "worker", "scheduler")}
        assert process.poll() is None
        process.kill()
        process.wait(timeout=2)

        adopted.prepare()
        reused = adopted.ensure_all()
        assert all(state.status == "healthy" for state in reused.values())
        assert {role: state.owner.pid for role, state in reused.items() if state.owner} == original
        assert adopted._children == {}
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2)
        _cleanup(adopted)


def test_supervisor_crash_reconciliation_reuses_children_then_child_crash_restarts_one(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    first = _supervisor(config)
    first.prepare()
    first.ensure_all()
    states = {role: _wait_healthy(first, role) for role in ("api", "worker", "scheduler")}
    original = {role: state.owner.pid for role, state in states.items() if state.owner}

    adopted = _supervisor(config)
    try:
        adopted.prepare()
        reused = adopted.ensure_all()
        assert {role: state.owner.pid for role, state in reused.items() if state.owner} == original
        assert adopted._children == {}

        worker_pid = original["worker"]
        os.kill(worker_pid, signal.SIGKILL)
        # Reap through the original Popen handle so PID inspection becomes authoritative.
        first._children["worker"].wait(timeout=2)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and adopted.state("worker").status != "missing":
            time.sleep(0.02)
        restarted = adopted.monitor_once()["worker"]
        restarted = _wait_healthy(adopted, "worker") if restarted.status != "healthy" else restarted
        assert restarted.owner is not None
        assert restarted.owner.pid != worker_pid
        assert adopted.state("api").owner.pid == original["api"]
        assert adopted.state("scheduler").owner.pid == original["scheduler"]
    finally:
        _cleanup(adopted)
        _cleanup(first)


@pytest.mark.skipif(os.name == "nt", reason="SIGSTOP is POSIX-only; installed Windows lifecycle is a later gate")
def test_stale_heartbeat_is_degraded_and_never_spawns_duplicate(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    supervisor = _supervisor(config)
    try:
        supervisor.prepare()
        states = supervisor.ensure_all()
        worker = states["worker"].owner
        assert worker is not None
        os.kill(worker.pid, signal.SIGSTOP)
        time.sleep(0.45)
        stale = supervisor.state("worker")
        assert stale.status == "stale"
        before_children = dict(supervisor._children)
        assert supervisor.ensure_role("worker").status == "stale"
        assert supervisor._children == before_children
        os.kill(worker.pid, signal.SIGCONT)
        assert _wait_healthy(supervisor, "worker").owner.pid == worker.pid
    finally:
        try:
            worker = supervisor.state("worker").owner
            if worker is not None:
                os.kill(worker.pid, signal.SIGCONT)
        except OSError:
            pass
        _cleanup(supervisor)


def test_unmanaged_existing_role_blocks_startup_without_spawning_or_stopping_it(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    code = """
import threading,time,sys
from newsroom.config import RuntimeConfig
from newsroom.runtime_supervisor import ManagedRoleContext
config=RuntimeConfig.for_environment(sys.argv[1], root=sys.argv[2])
stop=threading.Event()
with ManagedRoleContext(config, installation_id=sys.argv[3], release_id=sys.argv[4], role="worker", stop_event=stop, heartbeat_interval_seconds=0.05, supervisor_managed=False):
    while not stop.wait(0.02): pass
"""
    process = subprocess.Popen(
        [sys.executable, "-c", code, config.environment, str(config.root), INSTALLATION_ID, RELEASE_ID],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    supervisor = _supervisor(config)
    try:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and supervisor.state("worker").status != "unmanaged":
            time.sleep(0.02)
        assert supervisor.state("worker").status == "unmanaged"
        states = supervisor.ensure_all()
        assert states["worker"].status == "unmanaged"
        assert states["api"].status == "missing"
        assert states["scheduler"].status == "missing"
        assert supervisor._children == {}
        result = supervisor.shutdown(timeout_seconds=0.1)
        assert result.drained is False
        assert result.remaining_roles == ("worker",)
        assert process.poll() is None
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=2)


def test_shutdown_reports_busy_worker_deadline_without_force_kill(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")

    def commands(role: str):
        return _managed_child_command(config, role, ignore_stop_seconds=0.8 if role == "worker" else 0.0)

    supervisor = _supervisor(config, command_factory=commands)
    try:
        supervisor.prepare()
        states = supervisor.ensure_all()
        worker = states["worker"].owner
        assert worker is not None
        result = supervisor.shutdown(timeout_seconds=0.2)
        assert result.drained is False
        assert "worker" in result.remaining_roles
        assert os.kill(worker.pid, 0) is None

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and supervisor.state("worker").status != "missing":
            time.sleep(0.02)
        assert supervisor.state("worker").status == "missing"
        # Finish the remaining API after the busy worker has drained naturally.
        assert supervisor.shutdown(timeout_seconds=1.0).drained is True
    finally:
        _cleanup(supervisor)


def test_bounded_restart_exhaustion_stops_crash_loop(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    supervisor = _supervisor(config, restart_limit=2, startup_timeout=1.0)
    try:
        supervisor.prepare()
        states = supervisor.ensure_all()
        worker = states["worker"].owner
        assert worker is not None
        os.kill(worker.pid, signal.SIGKILL)
        supervisor._children["worker"].wait(timeout=2)

        good_factory = supervisor._command_factory
        supervisor.startup_timeout_seconds = 0.15
        supervisor._command_factory = lambda role: (
            [sys.executable, "-c", "raise SystemExit(17)"] if role == "worker" else good_factory(role)
        )
        seen = []
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            state = supervisor.monitor_once()["worker"]
            seen.append(state.status)
            if state.status == "restart_exhausted":
                break
            time.sleep(0.03)
        assert "restart_exhausted" in seen
        assert supervisor._restart_counts["worker"] == 2
    finally:
        _cleanup(supervisor)


def test_runtime_parser_exposes_supervisor_and_managed_child_flags(tmp_path):
    from newsroom.runtime import build_parser

    parser = build_parser()
    supervisor = parser.parse_args([
        "supervisor", "--environment", "dev", "--root", str(tmp_path / "dev"),
        "--host", "127.0.0.1", "--port", "18127",
    ])
    worker = parser.parse_args([
        "worker", "--environment", "dev", "--root", str(tmp_path / "dev"), "--managed-child",
    ])

    assert supervisor.command == "supervisor"
    assert supervisor.port == 18127
    assert worker.command == "worker"
    assert worker.managed_child is True
