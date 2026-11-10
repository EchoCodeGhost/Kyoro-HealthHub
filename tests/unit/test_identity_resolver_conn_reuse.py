# SPDX-License-Identifier: GPL-3.0-or-later
"""
Tests for the per-thread connection reuse in scripts/modules/identity_resolver.py:
1,000 resolve_device() calls with varying
and repeated values must open identity.db at most once per thread (counted via
a monkeypatched open_identity_db), a second thread opens exactly once more, and
resolve/reverse results stay exactly as before.
"""

import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import health_config
import modules.db as db
import modules.identity_resolver as ir


@pytest.fixture()
def resolver_env(tmp_path, monkeypatch):
    """identity.db redirected to tmp_path, hermetic key lookup (plain sqlite)."""
    monkeypatch.setattr(ir, "IDENTITY_DB_PATH", tmp_path / "identity.db")
    monkeypatch.setattr(ir, "REGISTRY_PATH", tmp_path / "registry.json")
    monkeypatch.setattr(health_config, "load", lambda: {})
    monkeypatch.delenv("KYORO_DB_KEY", raising=False)
    monkeypatch.setattr(db, "_KEY_FILE", Path("/nonexistent-dir-for-tests/db.key"))
    monkeypatch.setattr(db, "_load_keyring_key", lambda *a, **k: None)
    return tmp_path


def _counting_open(monkeypatch):
    """Count open_identity_db calls; _connect_identity_db imports the opener
    from modules.db at call time, so patching the attribute is effective."""
    calls = []
    real_open = db.open_identity_db

    def counting(path=None):
        calls.append(path)
        return real_open(path)

    monkeypatch.setattr(db, "open_identity_db", counting)
    return calls


def test_1000_resolve_device_calls_open_db_at_most_once_per_thread(resolver_env, monkeypatch):
    calls = _counting_open(monkeypatch)
    resolver = ir.IdentityResolver()
    after_init = len(calls)
    assert after_init <= 1  # __init__ opens at most once

    values = [f"dev-{i % 37}" for i in range(1000)]  # varying and repeated values
    for v in values:
        resolver.resolve("device", v)

    assert len(calls) == after_init  # no further open in this thread


def test_second_thread_opens_exactly_once_more(resolver_env, monkeypatch):
    calls = _counting_open(monkeypatch)
    resolver = ir.IdentityResolver()
    after_init = len(calls)

    def work():
        for i in range(100):
            resolver.resolve("device", f"thread-{i % 10}")

    t = threading.Thread(target=work)
    t.start()
    t.join()

    assert len(calls) - after_init == 1  # exactly one open in the new thread

    resolver.resolve("device", "main-thread")  # main thread keeps its own connection
    assert len(calls) - after_init == 1


def test_resolve_reverse_results_unchanged_with_shared_connection(resolver_env, monkeypatch):
    _counting_open(monkeypatch)
    resolver = ir.IdentityResolver()

    p1 = resolver.resolve("device", "polar_test")
    p2 = resolver.resolve("device", "polar_test")
    assert p1 == p2 and p1.startswith("DEV-")
    assert resolver.reverse(p1) == "polar_test"
    assert resolver.get_all_mappings("device")["device"]["polar_test"] == p1

    # a fresh resolver on the same DB sees the same mapping (write was committed)
    resolver2 = ir.IdentityResolver()
    assert resolver2.resolve("device", "polar_test") == p1
    assert resolver2.reverse(p1) == "polar_test"


def test_get_all_mappings_on_encrypted_identity_db(resolver_env, monkeypatch):
    """sqlite3.Row fails on sqlcipher3 cursors; mappings must work encrypted."""
    pytest.importorskip("sqlcipher3")
    monkeypatch.setenv("KYORO_DB_KEY", "test-key-not-a-secret")
    resolver = ir.IdentityResolver()
    pseudo = resolver.resolve("device", "bench-device-a")
    with open(ir.IDENTITY_DB_PATH, "rb") as f:
        assert not f.read(16).startswith(b"SQLite format 3")
    mappings = resolver.get_all_mappings()
    assert mappings["device"]["bench-device-a"] == pseudo
    assert set(mappings) == {"device", "person", "provider", "sourcefile", "serial", "account"}
    assert resolver.get_all_mappings("device") == {"device": mappings["device"]}
