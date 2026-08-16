"""Tests for deterministic replay: determinism, integrity, and no-network."""
from __future__ import annotations

import json
import socket

import pytest

from newsroom.evals.replay import (
    load_fixture,
    validate_fixture,
    ReplayResult,
    NormalizedCandidate,
)
from newsroom.evals.schema import ValidationError
from newsroom.evals.corpus import fixtures_dir


def _fixture(**overrides):
    fx = {
        "schema_version": 1,
        "fixture_id": "fx-1",
        "case_id": "case-1",
        "channel": "simulated_search",
        "query": {"text": "q", "topic_ref": "demo"},
        "captured_at": "2026-08-15T00:00:00Z",
        "documents": [
            {
                "candidate_id": "cand-1",
                "canonical_url": "https://corp-official.test/press/1",
                "title": "Acme launches X",
                "source": "official",
                "publisher": "Acme",
                "published_at": "2026-08-14T09:00:00Z",
                "retrieved_at": "2026-08-14T10:00:00Z",
                "content_type": "metadata",
                "excerpt": "Acme launched X today.",
                "proposed_event_key": "acme-x-launch",
            }
        ],
    }
    from newsroom.evals.schema import content_hash
    fx["content_hash"] = content_hash(fx["documents"])
    fx.update(overrides)
    return fx


def test_replay_loads_and_normalizes():
    result = validate_fixture(_fixture())
    assert isinstance(result, ReplayResult)
    assert result.case_id == "case-1"
    assert len(result.documents) == 1
    doc = result.documents[0]
    assert isinstance(doc, NormalizedCandidate)
    assert doc.normalized_url == "https://corp-official.test/press/1"
    assert doc.domain == "corp-official.test"
    assert doc.normalized_headline == "acme launches x"
    assert doc.event_key == "acme-x-launch"


def test_replay_is_deterministic():
    fx = _fixture()
    r1 = validate_fixture(fx)
    r2 = validate_fixture(fx)
    assert r1.replay_hash == r2.replay_hash


def test_replay_produces_equivalent_normalized_inputs():
    fx = _fixture()
    r1 = validate_fixture(fx)
    r2 = validate_fixture(fx)
    assert [d.normalized_url for d in r1.documents] == [
        d.normalized_url for d in r2.documents
    ]
    assert [d.normalized_headline for d in r1.documents] == [
        d.normalized_headline for d in r2.documents
    ]


def test_replay_rejects_tampered_content_hash():
    fx = _fixture()
    fx["content_hash"] = "0" * 64
    with pytest.raises(ValidationError, match="content_hash mismatch"):
        validate_fixture(fx)


def test_replay_rejects_unsupported_schema_version():
    fx = _fixture(schema_version=99)
    with pytest.raises(ValidationError, match="schema_version"):
        validate_fixture(fx)


def test_replay_rejects_missing_documents():
    fx = _fixture(documents=[])
    with pytest.raises(ValidationError, match="documents"):
        validate_fixture(fx)


def test_replay_rejects_duplicate_candidate_ids():
    fx = _fixture()
    fx["documents"] = fx["documents"] + fx["documents"]
    from newsroom.evals.schema import content_hash
    fx["content_hash"] = content_hash(fx["documents"])
    with pytest.raises(ValidationError, match="duplicate candidate_id"):
        validate_fixture(fx)


def test_replay_no_network_access(monkeypatch):
    """Replay must not touch the network.

    Patch ``socket.create_connection`` to raise if called; replay should still
    complete because it only reads local fixture data and hashes strings.
    """
    def _no_net(*args, **kwargs):
        raise AssertionError("network access attempted during replay")

    monkeypatch.setattr(socket, "create_connection", _no_net)
    monkeypatch.setattr(socket.socket, "connect", _no_net)

    fx = _fixture()
    result = validate_fixture(fx)
    assert result.documents[0].candidate_id == "cand-1"


def test_committed_fixtures_replay_deterministically():
    """Every committed fixture must replay twice with a stable hash."""
    for path in fixtures_dir().glob("*.json"):
        r1 = load_fixture(str(path))
        r2 = load_fixture(str(path))
        assert r1.replay_hash == r2.replay_hash
        assert r1.case_id == r2.case_id


def test_committed_fixture_content_hash_matches_documents():
    from newsroom.evals.schema import content_hash
    for path in fixtures_dir().glob("*.json"):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["content_hash"] == content_hash(data["documents"])
