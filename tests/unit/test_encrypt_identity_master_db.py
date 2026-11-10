# SPDX-License-Identifier: GPL-3.0-or-later
"""
Tests for scripts/migrations/encrypt_identity_master_db.py (OpenSpec change
encrypt-identity-and-master-db, task 2.4) — invented databases in tmp_path only.

Covers: dry run leaves the plain file in place, --yes replaces it atomically
with a working encrypted file, a row-count mismatch stops the migration, an
already-encrypted file is refused, and a missing key is refused.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import health_config
import modules.db as db
from migrations import encrypt_identity_master_db as mig

# sqlcipher3 is needed for the conversion — skip rather than hard-fail in an
# environment without it (same pattern as test_open_lab_db.py).
sqlcipher3 = pytest.importorskip("sqlcipher3")

PLAIN_HEADER = b"SQLite format 3\x00"
KEY = "test-key-migration"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated config dirs in tmp_path + key via environment."""
    cfg_dir = tmp_path / "config" / "kyoro"
    master_dir = tmp_path / "kyoro-master"
    cfg_dir.mkdir(parents=True)
    master_dir.mkdir(parents=True)
    monkeypatch.setattr(health_config, "KYORO_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(health_config, "KYORO_MASTER_DIR", master_dir)
    monkeypatch.setattr(health_config, "load", lambda: {})
    monkeypatch.setattr(db, "_KEY_FILE", tmp_path / "no-such-dir" / "db.key")
    monkeypatch.setattr(db, "_load_keyring_key", lambda *a, **k: None)
    monkeypatch.setenv("KYORO_DB_KEY", KEY)
    return types_simple(cfg_dir, master_dir, tmp_path)


def types_simple(cfg_dir, master_dir, tmp_path):
    class E:
        pass
    e = E()
    e.cfg_dir = cfg_dir
    e.master_dir = master_dir
    e.tmp_path = tmp_path
    e.backup_dir = tmp_path / "kyoro-backups" / "run1"
    return e


def _make_plain_identity(env, rows=3) -> Path:
    path = env.cfg_dir / "identity.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE device_id_map (pseudo_id TEXT PRIMARY KEY, device_id_real TEXT)")
    conn.execute("CREATE TABLE person_map (pseudo_id TEXT PRIMARY KEY, person_real TEXT)")
    for i in range(rows):
        conn.execute("INSERT INTO device_id_map VALUES (?, ?)", (f"DEV-{i:08X}", f"invented_device_{i}"))
        conn.execute("INSERT INTO person_map VALUES (?, ?)", (f"PER-{i:08X}", f"invented_person_{i}"))
    conn.commit()
    conn.close()
    return path


def test_dry_run_leaves_plain_file_and_reports_counts(env, capsys):
    src = _make_plain_identity(env)
    rc = mig.main(["--target", "identity", "--backup-dir", str(env.backup_dir)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "device_id_map: 3 Zeilen" in out
    assert "person_map: 3 Zeilen" in out
    assert "Trockenlauf" in out
    assert "Rückweg" in out
    # original untouched, encrypted copy removed, backup byte-identical
    assert src.read_bytes()[:16] == PLAIN_HEADER
    assert not (env.cfg_dir / "identity.db.encrypted").exists()
    backup = env.backup_dir / "identity.db"
    assert backup.exists()
    assert backup.read_bytes() == src.read_bytes()
    assert (backup.stat().st_mode & 0o777) == 0o600
    assert (env.backup_dir.stat().st_mode & 0o777) == 0o700


def test_yes_replaces_original_with_working_encrypted_file(env):
    src = _make_plain_identity(env)
    rc = mig.main(["--target", "identity", "--backup-dir", str(env.backup_dir), "--yes"])
    assert rc == 0
    assert src.stat().st_mode & 0o777 == 0o600
    assert src.read_bytes()[:16] != PLAIN_HEADER  # now encrypted
    assert not (env.cfg_dir / "identity.db.encrypted").exists()
    # opens through the central opener and holds the same rows
    conn = db.open_identity_db(src)
    assert conn.execute("SELECT COUNT(*) FROM device_id_map").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM person_map").fetchone()[0] == 3
    conn.close()
    # backup still there for the way back
    assert (env.backup_dir / "identity.db").read_bytes()[:16] == PLAIN_HEADER


def test_master_target_roundtrip(env):
    src = env.master_dir / "master.db"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE patient_number_map (patient_pseudo TEXT PRIMARY KEY, instance_dir TEXT)")
    conn.execute("INSERT INTO patient_number_map VALUES ('PT-00000001', '/invented/instance')")
    conn.commit()
    conn.close()
    rc = mig.main(["--target", "master", "--backup-dir", str(env.backup_dir), "--yes"])
    assert rc == 0
    assert src.read_bytes()[:16] != PLAIN_HEADER
    conn = db.open_master_db(src)
    assert conn.execute("SELECT COUNT(*) FROM patient_number_map").fetchone()[0] == 1
    conn.close()


def test_count_mismatch_stops_and_keeps_plain_file(env, monkeypatch):
    src = _make_plain_identity(env)
    orig_counts = mig._table_counts
    calls = {"n": 0}

    def fake_counts(conn):
        counts = dict(orig_counts(conn))
        calls["n"] += 1
        if calls["n"] == 1:  # the encrypted copy is counted first: pretend one row is missing
            counts["device_id_map"] -= 1
        return counts

    monkeypatch.setattr(mig, "_table_counts", fake_counts)
    rc = mig.main(["--target", "identity", "--backup-dir", str(env.backup_dir), "--yes"])
    assert rc == 1
    assert src.read_bytes()[:16] == PLAIN_HEADER  # original kept
    assert not (env.cfg_dir / "identity.db.encrypted").exists()  # enc copy removed


def test_already_encrypted_is_refused_and_changes_nothing(env, capsys):
    src = _make_plain_identity(env)
    mig.main(["--target", "identity", "--backup-dir", str(env.backup_dir), "--yes"])
    assert src.read_bytes()[:16] != PLAIN_HEADER
    before = src.read_bytes()
    capsys.readouterr()
    rc = mig.main(["--target", "identity", "--backup-dir", str(env.backup_dir / "second")])
    assert rc == 0
    assert "bereits verschlüsselt" in capsys.readouterr().out
    assert src.read_bytes() == before
    assert not (env.backup_dir / "second").exists()  # no backup made for a refusal


def test_no_key_is_refused(tmp_path, monkeypatch, capsys):
    cfg_dir = tmp_path / "config" / "kyoro"
    cfg_dir.mkdir(parents=True)
    monkeypatch.setattr(health_config, "KYORO_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(health_config, "load", lambda: {})
    monkeypatch.setattr(db, "_KEY_FILE", tmp_path / "no-such-dir" / "db.key")
    monkeypatch.setattr(db, "_load_keyring_key", lambda *a, **k: None)
    monkeypatch.delenv("KYORO_DB_KEY", raising=False)
    src = cfg_dir / "identity.db"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE t (a TEXT)")
    conn.commit()
    conn.close()
    before = src.read_bytes()

    rc = mig.main(["--target", "identity", "--backup-dir", str(tmp_path / "backups"), "--yes"])
    assert rc == 1
    assert "kein db_key" in capsys.readouterr().err
    assert src.read_bytes() == before
    assert not (tmp_path / "backups").exists()
