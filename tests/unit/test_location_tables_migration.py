# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for moving tracks, stays and location history to location.db.

@tier        unit
@purpose.de  Prüft Stufe 3 des Ortsregisters: das Migrationsskript kopiert die
             vier Tabellen unverändert, gleicht sie ab, verschiebt die
             Audit-Log-Kopien und löscht die Tabellen erst danach; ein
             Trockenlauf ändert nichts; fremde Aufenthalte in location.db
             führen zum Abbruch; ein fehlgeschlagener Abgleich löscht nichts.
             Außerdem die Schreib-Funktionen (Policy, Zonen), die Zeitzonen-
             Suche über Aufenthalte und die Koordinaten-Prüfung.
@purpose.en  Checks stage 3 of the location registry: the migration script
             copies the four tables unchanged, verifies them, moves the
             audit-log copies and only then drops the tables; a dry run changes
             nothing; foreign stays in location.db abort it; a failed
             verification deletes nothing. Also the write helpers (policy,
             zones), the timezone lookup over stays and the coordinate check.
@method.de   Temporäre unverschlüsselte health.db und location.db, gemockte
             Verbindungen und Konfiguration, erfundene Koordinaten.
@method.en   Temporary unencrypted health.db and location.db, mocked
             connections and configuration, made-up coordinates.
@reads       (temporäre Dateien)
@writes      (temporäre Dateien)
@limits.de   Keine echten Ortsdaten; SQLCipher wird nicht geprüft.
@limits.en   No real location data; SQLCipher is not exercised.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

PERSON = "PER-00000000"
HOME = (48.12345, 11.54321)


def _health_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE sessions (id TEXT PRIMARY KEY, date TEXT);
        CREATE TABLE session_tracks (session_id TEXT, ts TEXT NOT NULL, lat REAL, lon REAL,
            elevation_m REAL, speed_ms REAL, PRIMARY KEY (session_id, ts));
        CREATE TABLE location_history (datetime TEXT NOT NULL, date TEXT, hour INTEGER,
            state TEXT, lat REAL, lon REAL, gps_accuracy REAL, zone TEXT, city TEXT,
            person TEXT NOT NULL DEFAULT 'unknown', source TEXT, PRIMARY KEY (datetime, person));
        CREATE TABLE location_stays (id INTEGER PRIMARY KEY, start_ts TEXT, end_ts TEXT,
            lat REAL, lon REAL, is_home INTEGER, timezone TEXT,
            person TEXT NOT NULL DEFAULT 'unknown', source TEXT);
        CREATE TABLE location_stays_geocoded (stay_id INTEGER PRIMARY KEY, country TEXT,
            country_iso TEXT, state TEXT, county TEXT, city TEXT, subregion TEXT,
            climate_zone TEXT, geocoded_at TEXT NOT NULL);
        CREATE TABLE photo_locations (date TEXT, lat REAL, lon REAL, source TEXT, person TEXT);
        CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,
            table_name TEXT NOT NULL, operation TEXT NOT NULL, old_data TEXT, new_data TEXT);
        CREATE TABLE air_quality (date TEXT, lat REAL, lon REAL, PRIMARY KEY (date, lat, lon));
    """)
    conn.executemany("INSERT INTO session_tracks VALUES (?,?,?,?,?,?)", [
        ("s1", f"2026-01-01T10:0{i}:00+00:00", 48.12345 + i / 1e4, 11.54321, 500.0, 2.5)
        for i in range(5)])
    conn.execute("INSERT INTO location_history VALUES ('2026-01-01 10:00:00','2026-01-01',10,"
                 "'not_home',48.15,11.6,10,NULL,'Musterort',?,'ha_iphone')", (PERSON,))
    conn.executemany("INSERT INTO location_stays VALUES (?,?,?,?,?,?,?,?,?)", [
        (1, "2026-01-01T00:00:00", "2026-01-05T00:00:00", 48.1234, 11.5432, 1, "tz-home", PERSON, None),
        (2, "2026-02-01T00:00:00", "2026-02-07T00:00:00", 28.5, -13.9, 0, "tz-trip", PERSON, None),
    ])
    conn.execute("INSERT INTO location_stays_geocoded VALUES (2,'Spanien','ES','Kanaren',NULL,"
                 "'Beispielort','Kanaren','subtropisch','2026-02-08')")
    conn.execute("INSERT INTO audit_log (ts, table_name, operation, old_data, new_data) "
                 "VALUES ('2026-02-08', 'location_stays', 'UPDATE', '{\"lat\": 28.5}', '{\"lat\": 28.5}')")
    conn.execute("INSERT INTO audit_log (ts, table_name, operation, old_data, new_data) "
                 "VALUES ('2026-02-08', 'sessions', 'UPDATE', '{}', '{}')")
    conn.execute("INSERT INTO air_quality VALUES ('2026-01-01', 48.1, 11.5)")
    conn.commit()
    conn.close()


@pytest.fixture
def dbs(tmp_path, monkeypatch):
    import migrations.migrate_location_tables_to_location_db as mig
    from modules import db
    from utils.create_location_schema import ensure_location_schema

    health = tmp_path / "health.db"
    loc = tmp_path / "location.db"
    _health_db(health)
    conn = sqlite3.connect(loc)
    ensure_location_schema(conn)
    db._install_audit_log_triggers(conn)
    conn.commit()
    conn.close()
    backup = tmp_path / "health.bak"
    src = sqlite3.connect(health)
    dst = sqlite3.connect(backup)
    src.backup(dst)
    src.close()
    dst.close()

    def _attach(conn, alias="loc"):
        if alias not in {r[1] for r in conn.execute("PRAGMA database_list")}:
            if conn.in_transaction:
                conn.commit()
            conn.execute(f"ATTACH DATABASE ? AS {alias}", (str(loc),))
        return conn

    monkeypatch.setattr(mig, "open_db", lambda: sqlite3.connect(health))
    monkeypatch.setattr(mig, "attach_location_db", _attach)
    monkeypatch.setattr(mig, "_open_encrypted", lambda p: sqlite3.connect(p))
    monkeypatch.setattr(mig, "_pseudonymize_person_sql", _fake_pseudonym)
    return mig, health, loc, backup


def _fake_pseudonym(value):
    if not isinstance(value, str) or value.startswith(("DEV-", "PER-")):
        return value
    return "PER-" + value


def _tables(path):
    return {r[0] for r in sqlite3.connect(path).execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _rows(path, sql):
    return sqlite3.connect(path).execute(sql).fetchall()


def test_dry_run_changes_nothing(dbs):
    mig, health, loc, _ = dbs
    stats, backup = mig.migrate(execute=False)
    assert backup is None
    assert stats["session_tracks:health"] == 5 and stats["location_stays:health"] == 2
    assert stats["audit_rows"] == 1
    assert "session_tracks" in _tables(health)
    assert _rows(loc, "SELECT COUNT(*) FROM session_tracks") == [(0,)]


def test_execute_moves_tables_and_audit_copies(dbs):
    mig, health, loc, backup = dbs
    tables = ("session_tracks", "location_stays", "location_history", "location_stays_geocoded")
    before = {t: _rows(health, f"SELECT * FROM {t} ORDER BY 1, 2") for t in tables}
    stats, used = mig.migrate(execute=True, backup=backup)
    assert stats["ok"] == 1 and used == backup
    remaining = _tables(health)
    for table, rows in before.items():
        assert table not in remaining
        assert _rows(loc, f"SELECT * FROM {table} ORDER BY 1, 2") == rows
    assert "photo_locations" not in remaining          # leer → mit entfernt
    assert "air_quality" in remaining                   # Umwelttabelle bleibt
    audit = _rows(health, "SELECT table_name, old_data FROM audit_log ORDER BY id")
    assert ("location_stays", '{"lat": 28.5}') not in audit
    assert any(t == "sessions" for t, _ in audit)
    assert any(t == "location_tables" and "28.5" not in (d or "") for t, d in audit)
    moved = _rows(loc, "SELECT table_name, old_data FROM audit_log WHERE table_name='location_stays'")
    assert moved == [("location_stays", '{"lat": 28.5}')]


def test_rerun_after_success_is_a_no_op(dbs):
    mig, _, _, backup = dbs
    mig.migrate(execute=True, backup=backup)
    stats, _ = mig.migrate(execute=True, backup=backup)
    assert not stats["ok"] and not stats["dropped"]


def test_foreign_stays_abort(dbs):
    mig, health, loc, backup = dbs
    conn = sqlite3.connect(loc)
    conn.execute("INSERT INTO location_stays (id, start_ts, lat, lon, person) "
                 "VALUES (1, '2026-03-01T00:00:00', 50.0, 8.0, ?)", (PERSON,))
    conn.commit()
    conn.close()
    stats, _ = mig.migrate(execute=True, backup=backup)
    assert stats["stay_conflict"] == 1 and not stats["ok"]
    assert "location_stays" in _tables(health)


def _plain_person_stay(health, loc, backup):
    """Klartext-person in health.db, Trigger in location.db pseudonymisiert."""
    conn = sqlite3.connect(health)
    conn.execute("INSERT INTO location_stays VALUES (3, '2026-03-01T00:00:00', "
                 "'2026-03-02T00:00:00', 48.2, 11.6, 0, 'tz-home', 'unknown', NULL)")
    conn.commit()
    conn.close()
    src = sqlite3.connect(health)
    dst = sqlite3.connect(backup)
    src.backup(dst)
    src.close()
    dst.close()
    conn = sqlite3.connect(loc)
    conn.execute("""
        CREATE TRIGGER _pseudonymize_location_stays_person
        AFTER INSERT ON location_stays
        WHEN NEW.person IS NOT NULL AND NEW.person NOT LIKE 'PER-%'
        BEGIN
            UPDATE location_stays SET person = pseudonymize_person(NEW.person)
                WHERE rowid = NEW.rowid;
        END""")
    conn.commit()
    conn.close()


def test_plain_person_rewritten_by_trigger_still_verifies(dbs):
    mig, health, loc, backup = dbs
    _plain_person_stay(health, loc, backup)
    stats, _ = mig.migrate(execute=True, backup=backup)
    assert stats["ok"] == 1 and stats["location_stays:missing"] == 0
    assert "location_stays" not in _tables(health)
    assert _rows(loc, "SELECT person FROM location_stays WHERE id = 3") == [("PER-unknown",)]


def test_rerun_after_copy_without_drop_is_no_conflict(dbs, monkeypatch):
    """Abbruch nach dem Kopieren: erneuter Lauf zählt die Kopien nicht als fremd."""
    mig, health, loc, backup = dbs
    _plain_person_stay(health, loc, backup)
    verify = mig._verify
    monkeypatch.setattr(mig, "_verify", lambda conn, table, cols: (False, {"missing": 1}))
    with pytest.raises(SystemExit):
        mig.migrate(execute=True, backup=backup)
    monkeypatch.setattr(mig, "_verify", verify)
    stats, _ = mig.migrate(execute=True, backup=backup)
    assert stats["stay_conflict"] == 0 and stats["ok"] == 1
    assert "location_stays" not in _tables(health)


def test_failed_verification_deletes_nothing(dbs, monkeypatch):
    mig, health, _, backup = dbs
    monkeypatch.setattr(mig, "_verify", lambda conn, table, cols: (False, {"missing": 1}))
    with pytest.raises(SystemExit):
        mig.migrate(execute=True, backup=backup)
    assert {"session_tracks", "location_stays"} <= _tables(health)
    assert _rows(health, "SELECT COUNT(*) FROM audit_log WHERE table_name='location_stays'") == [(1,)]


def test_backup_with_wrong_counts_aborts(dbs, tmp_path):
    mig, health, _, _ = dbs
    bad = tmp_path / "bad.bak"
    sqlite3.connect(bad).execute("CREATE TABLE session_tracks (session_id TEXT)").connection.commit()
    with pytest.raises(SystemExit):
        mig.migrate(execute=True, backup=bad)
    assert "session_tracks" in _tables(health)


# ── Schreib-Funktionen ───────────────────────────────────────────────────────

@pytest.fixture
def store(tmp_path, monkeypatch):
    import modules.location_store as ls
    path = tmp_path / "location.db"
    state = {"policy": {
        "default": {"store": "none"},
        "importers": {"import_tracks": {"*": {"precision": 5}},
                      "import_oura_csv": {"*": {"precision": 4}},
                      "track_location": {"*": {"precision": 2}}},
        "zones": {"enabled": True, "radius_m": 500, "zone_precision": 2,
                  "centres": {"Musterort": {"lat": HOME[0], "lon": HOME[1]}}},
    }}
    monkeypatch.setattr(ls, "_load_location_privacy", lambda: state["policy"])
    monkeypatch.setattr(ls, "_personal_places", lambda: ([], [], None))
    monkeypatch.setattr(ls, "_get_pseudonym_salt", lambda: "")
    monkeypatch.setattr(ls, "_no_salt_warned", True)
    monkeypatch.setattr(ls, "open_location_db", lambda p=None: sqlite3.connect(path))
    return ls, path, state


def test_track_points_hidden_in_zone_and_rounded_outside(store):
    ls, path, _ = store
    n = ls.store_track_points("import_tracks", "s1", [
        ("2026-01-01T10:00:00+00:00", 48.1236, 11.5434, 500.0, 2.0),          # in Zone
        ("2026-01-01T10:01:00+00:00", 48.1500012, 11.6000034, 510.0, 2.1),    # außerhalb
    ])
    assert n == 1
    assert _rows(path, "SELECT session_id, lat, lon, elevation_m FROM session_tracks") == [
        ("s1", 48.15, 11.6, 510.0)]


def test_track_points_without_policy_store_nothing(store):
    ls, _, _ = store
    assert ls.store_track_points("unknown_importer", "s1",
                                 [("2026-01-01T10:00:00+00:00", 48.15, 11.6, None, None)]) == 0


def test_stays_in_zone_are_coarsened_not_hidden(store):
    ls, path, _ = store
    n = ls.store_stays("import_oura_csv", [
        ("2026-01-01T00:00:00", "2026-01-02T00:00:00", 48.12361, 11.54341, 1, None, PERSON, "oura_gps"),
        ("2026-02-01T00:00:00", "2026-02-02T00:00:00", 28.51234, -13.91234, 0, None, PERSON, "oura_gps"),
    ])
    assert n == 2
    assert _rows(path, "SELECT lat, lon, is_home FROM location_stays ORDER BY start_ts") == [
        (48.12, 11.54, 1), (28.5123, -13.9123, 0)]


def test_location_history_keeps_rows_without_coordinates(store):
    ls, path, _ = store
    n = ls.store_location_history("track_location", [
        ("2026-01-01 10:00:00", "2026-01-01", 10, "home", None, None, None, None, "Zuhause", PERSON, "ha"),
        ("2026-01-01 11:00:00", "2026-01-01", 11, "not_home", 48.15678, 11.60123, 5, None, None, PERSON, "ha"),
    ])
    assert n == 2
    assert _rows(path, "SELECT lat, lon FROM location_history ORDER BY datetime") == [
        (None, None), (48.16, 11.6)]


# ── Zeitzone über Aufenthalte ────────────────────────────────────────────────

def test_stay_timezone_lookup(store):
    ls, path, _ = store
    from utils.create_location_schema import ensure_location_schema
    conn = sqlite3.connect(path)
    ensure_location_schema(conn)
    conn.executemany(
        "INSERT INTO location_stays (start_ts, end_ts, lat, lon, is_home, timezone, person) "
        "VALUES (?,?,?,?,?,?,?)", [
            ("2026-01-01T00:00:00", None, 48.1, 11.5, 1, "tz-home", PERSON),
            ("2026-02-01T00:00:00", "2026-02-07T00:00:00", 28.5, -13.9, 0, "tz-trip", PERSON),
            ("2026-03-01T00:00:00", "2026-03-02T00:00:00", 40.4, -3.7, 0, None, PERSON),
        ])
    conn.commit()
    conn.close()
    ls.clear_read_caches()
    try:
        from health_config import Config
        orig = Config.location_db_path
        Config.location_db_path = property(lambda self: path)
        assert ls.stay_timezone(PERSON, "2026-02-03T12:00:00") == "tz-trip"
        assert ls.stay_timezone(PERSON, "2026-02-10T12:00:00") == "tz-home"
        assert ls.stay_timezone(PERSON, "2025-12-31T12:00:00") is None
        assert ls.stay_timezone("PER-11111111", "2026-02-03T12:00:00") is None
    finally:
        Config.location_db_path = orig
        ls.clear_read_caches()


# ── Koordinaten-Prüfung ──────────────────────────────────────────────────────

def test_check_location_columns_scan():
    from utils.check_location_columns import scan
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE air_quality (date TEXT, lat REAL, lon REAL);
        CREATE TABLE pollen (date TEXT, lat REAL, lon REAL);
        CREATE TABLE outbreak_events (id INTEGER, lat REAL, lon REAL);
        CREATE TABLE trips (id INTEGER, trip_lat REAL, trip_lon REAL);
        CREATE TABLE empty_geo (id INTEGER, latitude REAL, longitude REAL);
        CREATE TABLE audit_log (id INTEGER, table_name TEXT, old_data TEXT, new_data TEXT);
        INSERT INTO air_quality VALUES ('2026-01-01', 48.12, 11.54);
        INSERT INTO pollen VALUES ('2026-01-01', 48.123, 11.54);
        INSERT INTO outbreak_events VALUES (1, 12.3456789, 45.6789012);
        INSERT INTO trips VALUES (1, 48.1, 11.5);
        INSERT INTO audit_log VALUES (1, 'session_tracks', '{}', NULL);
    """)
    found = {r["table"]: r["finding"] for r in scan(conn)}
    assert found == {"air_quality": False, "pollen": True, "outbreak_events": False,
                     "trips": True, "empty_geo": False, "audit_log": True}
