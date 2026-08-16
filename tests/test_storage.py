from __future__ import annotations

import sqlite3

from newsroom import storage


def test_connect_applies_foreign_keys_and_busy_timeout(tmp_db):
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        conn.close()


def test_write_tx_commits(tmp_db):
    conn = storage.connect(tmp_db)
    try:
        conn.execute("CREATE TABLE x (id INTEGER PRIMARY KEY, value TEXT)")
        with storage.write_tx(conn):
            conn.execute("INSERT INTO x(value) VALUES ('ok')")
        assert conn.execute("SELECT value FROM x").fetchone()[0] == "ok"
    finally:
        conn.close()


def test_write_tx_rolls_back(tmp_db):
    conn = storage.connect(tmp_db)
    try:
        conn.execute("CREATE TABLE x (id INTEGER PRIMARY KEY, value TEXT)")
        try:
            with storage.write_tx(conn):
                conn.execute("INSERT INTO x(value) VALUES ('nope')")
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert conn.execute("SELECT COUNT(*) FROM x").fetchone()[0] == 0
    finally:
        conn.close()


def test_online_backup_is_integrity_clean(tmp_db, tmp_path):
    conn = storage.connect(tmp_db)
    try:
        conn.execute("CREATE TABLE x (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO x(value) VALUES ('backed up')")
    finally:
        conn.close()
    backup = storage.online_backup(tmp_path / "backup.db", source_path=tmp_db)
    assert storage.integrity_check(backup) == "ok"
    check = sqlite3.connect(backup)
    try:
        assert check.execute("SELECT value FROM x").fetchone()[0] == "backed up"
    finally:
        check.close()
