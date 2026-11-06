# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tests for the region column of location_registry.

@tier        unit
@purpose.de  Prüft, dass record() die Region aus dem ungerundeten Punkt
             speichert, bei Einheiten kleiner als die Rasterzelle nur den
             Ländercode, bei store: "region" keine Koordinaten, dass Duplikate
             auch ohne Koordinaten erkannt werden, dass for_prompt die
             gespeicherte Region liefert und dass eine alte location.db ohne
             region-Spalte verlustfrei umgebaut wird.
@purpose.en  Checks that record() stores the region of the unrounded point,
             only the country code for units smaller than the grid cell, no
             coordinates under store: "region", that duplicates are detected
             without coordinates, that for_prompt returns the stored region
             and that an old location.db without region column is rebuilt
             without losing entries.
@method.de   Temporäre Konfiguration und location.db; öffentlich bekannte
             Stadtkoordinaten bzw. erfundene Punkte.
@method.en   Temporary configuration and location.db; publicly known town
             coordinates or made-up points.
@reads       (temporäre Dateien)
@writes      (temporäre Dateien)
@limits.de   Keine echten Ortsdaten.
@limits.en   No real location data.
"""

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

PERSON = "PER-00000000"
ASCHAFFENBURG = (49.97, 9.15)   # DE-BY; auf 0 Stellen gerundet (50, 9) läge in DE-HE
BASEL = (47.56, 7.59)           # CH-BS, etwa 40 km²


def _setup(tmp_path, monkeypatch, importers):
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    policy = {
        "default": {"store": "none"},
        "importers": importers,
        "zones": {"enabled": False},
        "llm": {"default": "none", "allow": {"region_caller": "region", "raster_caller": 2}},
    }
    (config_dir / "location_privacy.json").write_text(json.dumps(policy))
    monkeypatch.setattr("health_config.KYORO_CONFIG_DIR", config_dir)
    path = tmp_path / "data" / "location.db"

    def _open(p=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(path)
    return path, _open


def _rows(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            "SELECT lat, lon, precision, region FROM location_registry ORDER BY id").fetchall()
    finally:
        conn.close()


def test_region_from_unrounded_point(tmp_path, monkeypatch):
    path, opener = _setup(tmp_path, monkeypatch, {"imp": {"*": {"precision": 0}}})
    from modules.location_store import record
    with patch("modules.location_store.open_location_db", opener):
        assert record("imp", None, *ASCHAFFENBURG, None, "2026-01-01", person=PERSON)
    assert _rows(path) == [(50.0, 9.0, 0, "DE-BY")]


def test_small_unit_stores_country_code(tmp_path, monkeypatch):
    path, opener = _setup(tmp_path, monkeypatch, {
        "coarse": {"*": {"precision": 1}}, "fine": {"*": {"precision": 2}}})
    from modules.location_store import record
    with patch("modules.location_store.open_location_db", opener):
        record("coarse", None, *BASEL, None, "2026-01-01", person=PERSON)
        record("fine", None, *BASEL, None, "2026-01-01", person=PERSON)
    regions = [row[3] for row in _rows(path)]
    assert regions == ["CH", "CH-BS"]


def test_region_only_entry(tmp_path, monkeypatch):
    path, opener = _setup(tmp_path, monkeypatch, {"imp": {"*": {"store": "region"}}})
    from modules.location_store import record
    with patch("modules.location_store.open_location_db", opener):
        assert record("imp", ".jpg", 48.12345, 11.54321, None, "2026-01-01",
                      source_file="imports/x/a.jpg", person=PERSON)
    assert _rows(path) == [(None, None, None, "DE-BY")]


def test_region_only_duplicate(tmp_path, monkeypatch):
    path, opener = _setup(tmp_path, monkeypatch, {"imp": {"*": {"store": "region"}}})
    from modules.location_store import record
    with patch("modules.location_store.open_location_db", opener):
        for ts in ("2026-01-01T10:00:00+00:00", "2026-01-02T10:00:00+00:00"):
            record("imp", ".jpg", 48.12345, 11.54321, ts, "2026-01-01",
                   source_file="imports/x/a.jpg", person=PERSON)
    assert len(_rows(path)) == 1


def test_invalid_coordinates_are_skipped(tmp_path, monkeypatch):
    path, opener = _setup(tmp_path, monkeypatch, {"imp": {"*": {"precision": 2}}})
    from modules.location_store import record
    with patch("modules.location_store.open_location_db", opener), pytest.warns(UserWarning):
        assert not record("imp", None, None, None, None, "2026-01-01", person=PERSON)
    assert not path.exists()


def test_for_prompt_returns_stored_region(tmp_path, monkeypatch):
    _path, opener = _setup(tmp_path, monkeypatch, {
        "imp": {"*": {"precision": 0}}, "reg": {"*": {"store": "region"}}})
    from modules.location_store import for_prompt, record
    with patch("modules.location_store.open_location_db", opener):
        record("imp", None, *ASCHAFFENBURG, None, "2026-01-01", person=PERSON)
        record("reg", None, *BASEL, None, "2026-01-02", person=PERSON)
        out = for_prompt("region_caller", refs=[1, 2])
        raster = for_prompt("raster_caller", refs=[2])
    # Gespeicherte Region, nicht die der gerundeten Koordinaten (50, 9) → DE-HE
    assert out == [{"id": 1, "date": "2026-01-01", "region": "DE-BY"},
                   {"id": 2, "date": "2026-01-02", "region": "CH-BS"}]
    assert raster == [{"id": 2, "date": "2026-01-02"}]


_OLD_SCHEMA = """
CREATE TABLE location_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    importer TEXT NOT NULL, file_type TEXT, source_file TEXT,
    original_sha256 TEXT, stored_sha256 TEXT, ts TEXT, date TEXT NOT NULL,
    lat REAL NOT NULL, lon REAL NOT NULL, precision INTEGER NOT NULL,
    ref_db TEXT, ref_table TEXT, ref_id INTEGER, person TEXT NOT NULL,
    migrated_from TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX uq_location_registry_entry ON location_registry (
    importer, COALESCE(file_type, ''), COALESCE(source_file, ''),
    COALESCE(original_sha256, ''), date, lat, lon, precision,
    COALESCE(ref_db, ''), COALESCE(ref_table, ''), COALESCE(ref_id, -1),
    person, COALESCE(migrated_from, ''));
CREATE INDEX idx_location_registry_person ON location_registry(person);
"""


def _old_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(_OLD_SCHEMA)
    conn.executemany(
        "INSERT INTO location_registry (id, importer, date, lat, lon, precision, person, ref_id)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(7, "import_skin", "2026-01-01", 48.12, 11.54, 2, PERSON, 3),
         (9, "import_skin", "2026-01-02", 47.56, 7.59, 1, PERSON, None)])
    conn.commit()
    return conn


def test_migration_keeps_entries_and_fills_region(tmp_path):
    from utils.create_location_schema import ensure_location_schema
    conn = _old_db(tmp_path / "location.db")
    ensure_location_schema(conn)

    rows = conn.execute(
        "SELECT id, lat, lon, precision, region, ref_id FROM location_registry ORDER BY id").fetchall()
    assert rows == [(7, 48.12, 11.54, 2, "DE-BY", 3), (9, 47.56, 7.59, 1, "CH", None)]
    notnull = {r[1]: r[3] for r in conn.execute("PRAGMA table_info(location_registry)")}
    assert notnull["lat"] == 0 and notnull["lon"] == 0
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "location_registry_pre_region" not in tables

    # Zweiter Lauf: nichts mehr zu tun, Duplikatschutz greift weiterhin
    ensure_location_schema(conn)
    conn.execute("INSERT OR IGNORE INTO location_registry (importer, date, lat, lon, precision,"
                 " region, person, ref_id) VALUES ('import_skin', '2026-01-01', 48.12, 11.54, 2,"
                 " 'DE-BY', ?, 3)", (PERSON,))
    assert conn.execute("SELECT COUNT(*) FROM location_registry").fetchone()[0] == 2
    conn.close()


def test_migration_reinstalls_audit_triggers(tmp_path):
    from modules.db import _install_audit_log_triggers
    from utils.create_location_schema import ensure_location_schema
    conn = _old_db(tmp_path / "location.db")
    _install_audit_log_triggers(conn)
    ensure_location_schema(conn)

    triggers = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='location_registry'")}
    assert "_audit_location_registry_delete" in triggers
    conn.execute("DELETE FROM location_registry WHERE id = 9")
    assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1
    conn.close()
