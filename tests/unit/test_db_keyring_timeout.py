# SPDX-License-Identifier: GPL-3.0-or-later
"""
Tests for the keyring timeout in scripts/modules/db.py::_load_db_key
(OpenSpec change encrypt-identity-and-master-db, task 1.4).

A locked system keyring blocks keyring.get_password() indefinitely; the
lookup must give up after a short timeout (worker thread), log once without
the key, and continue with db.key.
"""

import sys
import time
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import health_config
import modules.db as db


def _fake_keyring(monkeypatch, behavior):
    """Install a fake `keyring` module. behavior: 'block' or a return value."""
    fake = types.ModuleType("keyring")
    if behavior == "block":
        def get_password(service, username):
            time.sleep(60)  # simulates a locked keyring waiting on an unlock prompt
            return None
    else:
        def get_password(service, username):
            return behavior
    fake.get_password = get_password
    monkeypatch.setitem(sys.modules, "keyring", fake)


def _isolate(monkeypatch, key_file: Path | None):
    monkeypatch.setattr(health_config, "load", lambda: {})
    monkeypatch.delenv("KYORO_DB_KEY", raising=False)
    monkeypatch.setattr(db, "_KEY_FILE", key_file or Path("/nonexistent-dir-for-tests/db.key"))
    monkeypatch.setattr(db, "_keyring_timeout_logged", False)
    # the keyring is asked at most once per process — reset that cache per test
    monkeypatch.setattr(db, "_keyring_result", db._KEYRING_UNSET)


def test_blocked_keyring_times_out_and_falls_back_to_db_key(tmp_path, monkeypatch, capsys):
    _fake_keyring(monkeypatch, "block")
    key_file = tmp_path / "db.key"
    key_file.write_text("db-key-from-file\n", encoding="utf-8")
    _isolate(monkeypatch, key_file)

    orig = db._load_keyring_key
    monkeypatch.setattr(
        db, "_load_keyring_key",
        lambda *a, **k: orig(0.2),  # short timeout for the test
    )

    start = time.monotonic()
    key = db._load_db_key({})
    elapsed = time.monotonic() - start

    assert key == "db-key-from-file"
    assert elapsed < 5  # did not wait for the blocked keyring
    err = capsys.readouterr().err
    assert "[Hinweis] System-Keyring" in err
    assert "db-key-from-file" not in err  # log line must not contain the key


def test_keyring_timeout_is_logged_once_per_process(tmp_path, monkeypatch, capsys):
    _fake_keyring(monkeypatch, "block")
    _isolate(monkeypatch, None)

    assert db._load_keyring_key(0.1) is None
    assert db._load_keyring_key(0.1) is None
    err = capsys.readouterr().err
    assert err.count("[Hinweis] System-Keyring") == 1


def test_answering_keyring_wins_over_db_key(tmp_path, monkeypatch):
    _fake_keyring(monkeypatch, "keyring-key")
    key_file = tmp_path / "db.key"
    key_file.write_text("db-key-from-file", encoding="utf-8")
    _isolate(monkeypatch, key_file)

    assert db._load_db_key({}) == "keyring-key"


def test_env_key_wins_over_keyring(monkeypatch):
    _fake_keyring(monkeypatch, "keyring-key")
    _isolate(monkeypatch, None)
    monkeypatch.setenv("KYORO_DB_KEY", "env-key")

    assert db._load_db_key({}) == "env-key"
