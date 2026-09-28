# SPDX-License-Identifier: GPL-3.0-or-later
"""
Regression test for open_lab_db() (scripts/modules/db.py): attaching an
encrypted medicine.db to an encrypted health.db connection.

Background: ATTACH DATABASE never passed a KEY clause for the attached
database. Under SQLCipher this always failed ("hmac check failed") and
silently fell back to health.db-only — reproducing, via a different
mechanism, the exact "analyse_synthesis/analyse_lab_verlauf/
analyse_longevity see zero lab_manual values" bug this function's own
docstring says it was built to fix. Found dogfooding: a real query against
a real encrypted install returned 0 rows from medicine.db despite 64+ real
lab_manual entries existing there.
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


def _make_encrypted_db(path, key, script):
    conn = sqlcipher3.connect(str(path))
    conn.execute(f"PRAGMA key='{key}'")
    conn.executescript(script)
    conn.commit()
    conn.close()


class _FakeConfig:
    """Minimal stand-in for health_config.Config, pointing db_path/
    medicine_db_path at the test's temp encrypted files."""

    _cfg = {}

    def __init__(self, health_path, medicine_path):
        self._health_path = health_path
        self._medicine_path = medicine_path

    @property
    def db_path(self):
        return self._health_path

    @property
    def medicine_db_path(self):
        return self._medicine_path


def test_open_lab_db_attaches_encrypted_medicine_db(tmp_path, monkeypatch):
    key = "test-key-open-lab-db"
    health_path = tmp_path / "health.db"
    medicine_path = tmp_path / "medicine.db"

    _make_encrypted_db(health_path, key, """
        CREATE TABLE lab_values (
            date TEXT, parameter TEXT, value REAL, value_text TEXT, unit TEXT,
            range_min REAL, range_max REAL, lab TEXT, status TEXT,
            ref_text TEXT, person TEXT
        );
    """)
    _make_encrypted_db(medicine_path, key, """
        CREATE TABLE lab_manual (
            date TEXT, parameter TEXT, kategorie TEXT, wert TEXT, wert_num REAL,
            einheit TEXT, ref_min REAL, ref_max REAL, labor TEXT, status TEXT,
            kommentar TEXT, person TEXT, source TEXT
        );
        INSERT INTO lab_manual (date, parameter, wert_num, person)
        VALUES ('2026-01-01', 'HbA1c', 5.4, 'PER-test');
    """)

    monkeypatch.setenv("KYORO_DB_KEY", key)
    fake_config = _FakeConfig(health_path, medicine_path)
    monkeypatch.setattr(health_config, "Config", lambda: fake_config)
    monkeypatch.setattr(health_config, "load", lambda: {})

    conn = db.open_lab_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT parameter, wert_num FROM med.lab_manual")
        assert cur.fetchall() == [("HbA1c", 5.4)]
    finally:
        conn.close()


def test_open_lab_db_falls_back_when_medicine_db_missing(tmp_path, monkeypatch):
    """No medicine.db file at all -> returns the plain health.db connection
    instead of raising, matching the documented graceful-degradation
    behavior for the no-medicine.db case."""
    key = "test-key-open-lab-db-2"
    health_path = tmp_path / "health.db"
    missing_medicine_path = tmp_path / "does_not_exist.db"

    _make_encrypted_db(health_path, key, """
        CREATE TABLE lab_values (
            date TEXT, parameter TEXT, value REAL, value_text TEXT, unit TEXT,
            range_min REAL, range_max REAL, lab TEXT, status TEXT,
            ref_text TEXT, person TEXT
        );
    """)

    monkeypatch.setenv("KYORO_DB_KEY", key)
    fake_config = _FakeConfig(health_path, missing_medicine_path)
    monkeypatch.setattr(health_config, "Config", lambda: fake_config)
    monkeypatch.setattr(health_config, "load", lambda: {})

    conn = db.open_lab_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM lab_values")
        assert cur.fetchone() == (0,)
    finally:
        conn.close()
