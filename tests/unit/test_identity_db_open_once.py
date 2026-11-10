# SPDX-License-Identifier: GPL-3.0-or-later
"""
Per-call readers of identity.db must not re-open it on every call (an
encrypted open costs ~70 ms): location_store's salt lookup runs per
coordinate, name_redaction's known-name lookup per redaction call.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import health_config
import modules.db as db
import modules.location_store as ls
import modules.name_redaction as nr


@pytest.fixture()
def identity_db(tmp_path, monkeypatch):
    path = tmp_path / "identity.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE pseudonym_salt (id INTEGER PRIMARY KEY, salt_hex TEXT)")
    con.execute("INSERT INTO pseudonym_salt VALUES (1, 'abc123')")
    con.execute("CREATE TABLE person_name_map (name_real TEXT, alias1 TEXT, alias2 TEXT, alias3 TEXT)")
    con.execute("INSERT INTO person_name_map VALUES ('Erika Beispiel', 'Eri', NULL, NULL)")
    con.commit()
    con.close()
    monkeypatch.setattr(health_config, "KYORO_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(nr, "_config_path", lambda: tmp_path / "missing.json")
    monkeypatch.setattr(nr, "_identity_db_path", lambda: path)
    monkeypatch.setattr(ls, "_salt_cache", {})
    monkeypatch.setattr(health_config, "load", lambda: {})
    monkeypatch.delenv("KYORO_DB_KEY", raising=False)
    monkeypatch.setattr(db, "_KEY_FILE", Path("/nonexistent-dir-for-tests/db.key"))
    monkeypatch.setattr(db, "_load_keyring_key", lambda *a, **k: None)
    calls = []
    real_open = db.open_identity_db

    def counting(p, *a, **k):
        calls.append(p)
        return real_open(p, *a, **k)

    monkeypatch.setattr(db, "open_identity_db", counting)
    return calls


def test_location_salt_read_once(identity_db):
    tokens = {ls.location_token(48.1 + i / 1000, 11.5, 2) for i in range(200)}
    assert all(t and t.startswith("LOC-") for t in tokens)
    assert len(identity_db) == 1


def test_known_names_open_identity_db_once(identity_db):
    for _ in range(50):
        assert "Erika Beispiel" in nr.load_known_names()
    assert len(identity_db) == 1
