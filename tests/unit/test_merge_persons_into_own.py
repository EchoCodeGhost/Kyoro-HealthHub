# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for assigning all data to the own person, and for the weather importer's person.

@tier        unit
@purpose.de  Prüft Zuordnung, Duplikate, Probelauf, Kopie und Audit-Spur der Migration, und dass
             der Wetter-Import die eigene Person schreibt.
@purpose.en  Checks assignment, duplicates, dry run, copy and audit trail of the migration, and
             that the weather import writes the own person.
@method.de   Echte temporäre SQLite-Dateien über das echte open_db, mit erfundenen Werten.
@method.en   Real temporary SQLite files through the real open_db, with made-up values.
@reads       temporäre Dateien
@writes      temporäre Dateien
@limits.de   SQLCipher-Dateien werden hier nicht getestet.
@limits.en   SQLCipher files are not tested here.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from importers import import_dwd_brightsky as brightsky
from migrations import merge_persons_into_own as merge
from modules import db

OWN = "PER-aaaaaaaa"
OLD = "PER-bbbbbbbb"


@pytest.fixture(autouse=True)
def _no_key(monkeypatch):
    monkeypatch.setattr(db, "_load_db_key", lambda cfg: None)
    monkeypatch.setattr("health_config.load", lambda *a, **k: {})


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "health.db"
    conn = sqlite3.connect(path)
    conn.executescript(f"""
        CREATE TABLE keyed (date TEXT, value INT, person TEXT, PRIMARY KEY (date, person));
        CREATE TABLE free (value INT, person TEXT);
        CREATE TABLE no_person (value INT);
        CREATE TABLE import_log (id INTEGER PRIMARY KEY, ts_run TEXT, source TEXT, data_path TEXT,
                                 rows_inserted INT, rows_skipped INT, person TEXT, git_commit TEXT);
        INSERT INTO keyed VALUES ('d1', 1, '{OWN}'), ('d1', 99, '{OLD}'), ('d2', 2, 'unknown');
        INSERT INTO free VALUES (1, '{OLD}'), (2, NULL), (3, '{OWN}');
        INSERT INTO no_person VALUES (1);
        INSERT INTO import_log (ts_run, source, person) VALUES ('t', 'x', '{OLD}');
    """)
    conn.commit()
    conn.close()
    return path


def _rows(path, sql):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_rows_are_assigned_and_own_row_wins_on_collision(database):
    conn = db.open_db(database)
    assert merge.run_database(conn, database, OWN, apply=True) == {"keyed": (1, 1), "free": (1, 0)}
    conn.close()
    assert _rows(database, "SELECT date, value, person FROM keyed ORDER BY date") == [
        ("d1", 1, OWN), ("d2", 2, OWN)]


def test_null_and_logs_stay_unchanged(database):
    conn = db.open_db(database)
    merge.run_database(conn, database, OWN, apply=True)
    conn.close()
    assert sorted(_rows(database, "SELECT value, person FROM free"), key=lambda r: r[0]) == [
        (1, OWN), (2, None), (3, OWN)]
    assert (OLD,) in _rows(database, "SELECT person FROM import_log")


def test_dry_run_reports_the_same_and_changes_nothing(database):
    before = _rows(database, "SELECT * FROM keyed"), _rows(database, "SELECT * FROM free")
    conn = db.open_db(database)
    assert merge.run_database(conn, database, OWN, apply=False) == {"keyed": (1, 1), "free": (1, 0)}
    conn.close()
    assert (_rows(database, "SELECT * FROM keyed"), _rows(database, "SELECT * FROM free")) == before
    assert not list(database.parent.glob("*.before-person-merge-*"))


def test_copy_holds_the_old_state_and_is_private(database):
    conn = db.open_db(database)
    merge.run_database(conn, database, OWN, apply=True)
    conn.close()
    copies = list(database.parent.glob("health.db.before-person-merge-*"))
    assert len(copies) == 1
    assert copies[0].stat().st_mode & 0o777 == 0o600
    assert ("d1", 99, OLD) in _rows(copies[0], "SELECT date, value, person FROM keyed")


def test_second_run_finds_nothing_and_makes_no_copy(database):
    conn = db.open_db(database)
    merge.run_database(conn, database, OWN, apply=True)
    assert merge.run_database(conn, database, OWN, apply=True) == {}
    conn.close()
    assert len(list(database.parent.glob("health.db.before-person-merge-*"))) == 1


def test_changed_and_deleted_rows_are_in_the_audit_log(database):
    conn = db.open_db(database)
    merge.run_database(conn, database, OWN, apply=True)
    conn.close()
    operations = _rows(database, "SELECT table_name, operation FROM audit_log WHERE table_name='keyed'")
    assert ("keyed", "UPDATE") in operations and ("keyed", "DELETE") in operations
    assert any("99" in row[0] for row in _rows(database, "SELECT old_data FROM audit_log WHERE operation='DELETE'"))


def test_run_is_logged_without_changing_person_rows(database):
    conn = db.open_db(database)
    merge.run_database(conn, database, OWN, apply=True)
    conn.close()
    assert _rows(database, "SELECT rows_inserted, rows_skipped FROM import_log WHERE source='merge_persons_into_own'") \
        == [(2, 1)]


def test_weather_import_writes_the_own_person(tmp_path, monkeypatch):
    monkeypatch.setattr(brightsky, "resolve_person", lambda person: person or OWN)
    monkeypatch.setattr(brightsky, "log_import", lambda *a, **k: None)
    conn = sqlite3.connect(tmp_path / "x.db")
    cols = ("date, station_id, station_name, uv_index, solar_wm2, solar_wm2_mean, sunshine_h, cloud_pct, temp_c, "
            "temp_min, temp_max, dewpoint_c, humidity, humidity_min, humidity_max, pressure_hpa, pressure_min, "
            "pressure_max, wind_speed_kmh, wind_gust_max, wind_dir_deg, rain_mm, snow_cm, evap_mm, source")
    conn.execute(f"CREATE TABLE weather_dwd_station ({cols}, person TEXT NOT NULL DEFAULT 'unknown', PRIMARY KEY (date))")
    data = {"weather": [{"timestamp": "2000-01-01T12:00:00+00:00", "temperature": 1.0}],
            "sources": [{"id": 1, "dwd_station_id": "00001", "station_name": "Teststation"}]}
    assert brightsky.import_brightsky_from_raw(conn, data) == 1
    assert conn.execute("SELECT person FROM weather_dwd_station").fetchall() == [(OWN,)]
