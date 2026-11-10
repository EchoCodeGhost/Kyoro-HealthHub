# SPDX-License-Identifier: GPL-3.0-or-later
"""
Tests for open_identity_db()/open_master_db() in scripts/modules/db.py
(OpenSpec change encrypt-identity-and-master-db, tasks 1.1).

Covers: encrypted create/reopen with the db_key, the plaintext transition
(a not-yet-encrypted file opens with a warning), and the clear error when
an encrypted file is opened without a key (or with a wrong key).
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import health_config
import modules.db as db

# sqlcipher3 is an optional dependency (only needed when a db_key is
# configured, see onboard.py/requirements.txt) — skip rather than hard-fail
# this file's tests in an environment that doesn't have it installed.
sqlcipher3 = pytest.importorskip("sqlcipher3")

PLAIN_HEADER = b"SQLite format 3\x00"


def _isolate_key_lookup(monkeypatch, key=None):
    """Hermetic key lookup: no env key (unless given), no real keyring, no real db.key file."""
    monkeypatch.setattr(health_config, "load", lambda: {})
    if key is None:
        monkeypatch.delenv("KYORO_DB_KEY", raising=False)
    else:
        monkeypatch.setenv("KYORO_DB_KEY", key)
    monkeypatch.setattr(db, "_KEY_FILE", Path("/nonexistent-dir-for-tests/db.key"))
    monkeypatch.setattr(db, "_load_keyring_key", lambda *a, **k: None)


def _make_plain_db(path: Path) -> None:
    import sqlite3
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (a TEXT)")
    conn.execute("INSERT INTO t VALUES ('invented')")
    conn.commit()
    conn.close()


def test_open_identity_db_creates_encrypted_file_when_key_set(tmp_path, monkeypatch):
    _isolate_key_lookup(monkeypatch, key="test-key-identity")
    path = tmp_path / "identity.db"

    conn = db.open_identity_db(path)
    conn.execute("CREATE TABLE t (a TEXT)")
    conn.execute("INSERT INTO t VALUES ('invented')")
    conn.commit()
    conn.close()

    assert path.read_bytes()[:16] != PLAIN_HEADER  # really encrypted, not plain SQLite
    reopened = db.open_identity_db(path)
    assert reopened.execute("SELECT a FROM t").fetchone()[0] == "invented"
    reopened.close()


def test_open_master_db_creates_encrypted_file_when_key_set(tmp_path, monkeypatch):
    _isolate_key_lookup(monkeypatch, key="test-key-master")
    path = tmp_path / "master.db"

    conn = db.open_master_db(path)
    conn.execute("CREATE TABLE t (a TEXT)")
    conn.commit()
    conn.close()

    assert path.read_bytes()[:16] != PLAIN_HEADER
    reopened = db.open_master_db(path)
    assert reopened.execute("SELECT count(*) FROM sqlite_master").fetchone()[0] >= 1
    reopened.close()


def test_plain_file_opens_with_warning_during_transition(tmp_path, monkeypatch):
    _isolate_key_lookup(monkeypatch, key="test-key-transition")
    path = tmp_path / "identity.db"
    _make_plain_db(path)

    with pytest.warns(UserWarning, match="unverschlüsselt"):
        conn = db.open_identity_db(path)
    assert conn.execute("SELECT a FROM t").fetchone()[0] == "invented"
    conn.close()
    # still plain on disk — the migration script does the conversion, not the opener
    assert path.read_bytes()[:16] == PLAIN_HEADER


def test_encrypted_file_without_key_raises_clear_error(tmp_path, monkeypatch):
    _isolate_key_lookup(monkeypatch, key="test-key-nofallback")
    path = tmp_path / "identity.db"
    conn = db.open_identity_db(path)
    conn.execute("CREATE TABLE t (a TEXT)")
    conn.commit()
    conn.close()

    _isolate_key_lookup(monkeypatch, key=None)
    with pytest.raises(RuntimeError, match="kein Schlüssel"):
        db.open_identity_db(path)


def test_encrypted_file_with_wrong_key_raises_clear_error(tmp_path, monkeypatch):
    _isolate_key_lookup(monkeypatch, key="test-key-right")
    path = tmp_path / "master.db"
    conn = db.open_master_db(path)
    conn.execute("CREATE TABLE t (a TEXT)")
    conn.commit()
    conn.close()

    _isolate_key_lookup(monkeypatch, key="test-key-wrong")
    with pytest.raises(RuntimeError, match="nicht"):
        db.open_master_db(path)


def test_no_key_plain_file_still_opens_plain(tmp_path, monkeypatch):
    _isolate_key_lookup(monkeypatch, key=None)
    path = tmp_path / "identity.db"
    _make_plain_db(path)

    conn = db.open_identity_db(path)  # no key configured -> plain mode, as for health.db
    assert conn.execute("SELECT a FROM t").fetchone()[0] == "invented"
    conn.close()


def test_default_paths_follow_config_dirs(tmp_path, monkeypatch):
    _isolate_key_lookup(monkeypatch, key="test-key-defaults")
    cfg_dir = tmp_path / "cfg"
    master_dir = tmp_path / "kyoro-master"
    monkeypatch.setattr(health_config, "KYORO_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(health_config, "KYORO_MASTER_DIR", master_dir)

    conn = db.open_identity_db()
    conn.execute("CREATE TABLE t (a TEXT)")
    conn.commit()
    conn.close()
    conn = db.open_master_db()
    conn.execute("CREATE TABLE t (a TEXT)")
    conn.commit()
    conn.close()

    assert (cfg_dir / "identity.db").exists()
    assert (master_dir / "master.db").exists()
