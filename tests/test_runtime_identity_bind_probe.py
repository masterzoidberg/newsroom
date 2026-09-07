from __future__ import annotations

import socket

from newsroom import runtime_identity
from newsroom.runtime_identity import EndpointStatus, diagnose_endpoint


def _unused_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _inconclusive_connect(*_args, **_kwargs):
    raise OSError("inconclusive connect probe")


def _unexpected_connect(*_args, **_kwargs):
    raise AssertionError("free endpoint must be proven by bind before connect probing")


def test_free_loopback_port_is_proven_before_connect_probe(monkeypatch):
    port = _unused_loopback_port()
    monkeypatch.setattr(runtime_identity.socket, "create_connection", _unexpected_connect)

    diagnosis = diagnose_endpoint(
        "127.0.0.1",
        port,
        expected_installation_id="11111111-1111-4111-8111-111111111111",
        expected_release_id="release-test",
    )

    assert diagnosis.status is EndpointStatus.AVAILABLE


def test_inconclusive_connect_stays_unknown_when_exact_port_is_bound(monkeypatch):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = int(listener.getsockname()[1])
    monkeypatch.setattr(runtime_identity.socket, "create_connection", _inconclusive_connect)
    try:
        diagnosis = diagnose_endpoint(
            "127.0.0.1",
            port,
            expected_installation_id="11111111-1111-4111-8111-111111111111",
            expected_release_id="release-test",
        )
    finally:
        listener.close()

    assert diagnosis.status is EndpointStatus.UNKNOWN
