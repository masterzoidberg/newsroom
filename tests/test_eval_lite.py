"""Tests for the frozen Lite benchmark execution contract."""
from __future__ import annotations

import sqlite3

import pytest

from newsroom.evals.lite import (
    LiteBenchmarkError,
    LiteHarness,
    bind_contract,
    frozen_corpus_binding,
    load_contract,
)


def _snapshot(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sources (id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE documents (id TEXT PRIMARY KEY, source_id TEXT, title TEXT);
        CREATE TABLE document_versions (id TEXT PRIMARY KEY, document_id TEXT, content_hash TEXT);
        INSERT INTO sources VALUES ('src_1', 'Official');
        INSERT INTO documents VALUES ('doc_1', 'src_1', 'A document');
        INSERT INTO document_versions VALUES ('ver_1', 'doc_1', 'hash-1');
        """
    )
    conn.commit()
    conn.close()


def test_lite_contract_is_fixed_and_unbound_by_default():
    contract = load_contract()
    assert contract["blinding"]["case_ids"] == "opaque_until_scored"
    assert len(contract["questions"]) == 20


def test_lite_refuses_mutable_or_mismatched_corpus(tmp_path):
    db = tmp_path / "snapshot.sqlite"
    _snapshot(db)
    contract = bind_contract(load_contract(), db)
    harness = LiteHarness(db, contract=contract)
    assert harness.binding["manifest_hash"] == frozen_corpus_binding(db)["manifest_hash"]

    conn = sqlite3.connect(db)
    conn.execute("UPDATE document_versions SET content_hash = 'hash-2'")
    conn.commit()
    conn.close()
    with pytest.raises(LiteBenchmarkError, match="manifest"):
        LiteHarness(db, contract=contract)


def test_lite_rejects_arbitrary_model_callable(tmp_path):
    db = tmp_path / "snapshot.sqlite"
    _snapshot(db)
    harness = LiteHarness(db, contract=bind_contract(load_contract(), db))
    with pytest.raises(LiteBenchmarkError, match="provider/model"):
        harness.run("q01", lambda question, documents: {"text": "test"})
