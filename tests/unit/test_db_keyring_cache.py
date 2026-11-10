# SPDX-License-Identifier: GPL-3.0-or-later
"""
Tests for the once-per-process keyring cache in scripts/modules/db.py:
the system keyring is asked at most once
per process — one worker thread, one wait on the timeout, also under
concurrent calls — while KYORO_DB_KEY is still checked first on every
_load_db_key() call and never touches the keyring.
"""

import sys
import threading
import time
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import health_config
import modules.db as db


@pytest.fixture(autouse=True)
def _hermetic_key_lookup(monkeypatch):
    monkeypatch.setattr(health_config, "load", lambda: {})
    monkeypatch.delenv("KYORO_DB_KEY", raising=False)
    monkeypatch.setattr(db, "_KEY_FILE", Path("/nonexistent-dir-for-tests/db.key"))
    monkeypatch.setattr(db, "_keyring_timeout_logged", False)
    # the keyring is asked at most once per process — reset that cache per test
    monkeypatch.setattr(db, "_keyring_result", db._KEYRING_UNSET)


def _install_fake_keyring(monkeypatch, get_password):
    fake = types.ModuleType("keyring")
    fake.get_password = get_password
    monkeypatch.setitem(sys.modules, "keyring", fake)


def test_blocking_keyring_asked_once_across_multiple_load_db_key_calls(monkeypatch):
    calls = []
    release = threading.Event()

    def blocking_get_password(service, username):
        calls.append((service, username))
        release.wait(60)  # simulates a locked keyring waiting on an unlock prompt
        return None

    _install_fake_keyring(monkeypatch, blocking_get_password)
    orig = db._load_keyring_key
    monkeypatch.setattr(db, "_load_keyring_key", lambda *a, **k: orig(0.2))

    start = time.monotonic()
    results = [db._load_db_key({}) for _ in range(5)]
    elapsed = time.monotonic() - start
    release.set()

    assert results == [None] * 5
    assert len(calls) == 1  # keyring asked exactly once ...
    assert elapsed < 0.9    # ... and only one wait (five 0.2 s waits would be >= 1 s)


def test_answering_keyring_result_is_cached(monkeypatch):
    calls = []

    def get_password(service, username):
        calls.append(1)
        return "keyring-key"

    _install_fake_keyring(monkeypatch, get_password)

    assert db._load_db_key({}) == "keyring-key"
    assert db._load_db_key({}) == "keyring-key"
    assert db._load_db_key({}) == "keyring-key"
    assert len(calls) == 1


def test_env_key_is_checked_first_on_every_call_and_skips_keyring(monkeypatch):
    calls = []

    def get_password(service, username):
        calls.append(1)
        return "keyring-key"

    _install_fake_keyring(monkeypatch, get_password)
    monkeypatch.setenv("KYORO_DB_KEY", "env-key")

    assert db._load_db_key({}) == "env-key"
    assert db._load_db_key({}) == "env-key"
    assert calls == []  # env key short-circuits before the keyring, every time


def test_concurrent_calls_ask_the_keyring_only_once(monkeypatch):
    calls = []
    release = threading.Event()

    def blocking_get_password(service, username):
        calls.append(1)
        release.wait(30)
        return None

    _install_fake_keyring(monkeypatch, blocking_get_password)
    orig = db._load_keyring_key
    monkeypatch.setattr(db, "_load_keyring_key", lambda *a, **k: orig(0.2))

    results: list = []

    def worker():
        results.append(db._load_db_key({}))

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    release.set()

    assert results == [None] * 10
    assert len(calls) == 1  # one worker thread despite ten concurrent lookups
