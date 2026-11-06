#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
create_location_schema.py — Erstellt das Schema für location.db

@tier        infrastructure
@purpose.de  Erstellt die location.db mit dem zentralen Location-Registry-Schema.
             Idempotent: kann mehrmals ausgeführt werden.
@purpose.en  Creates location.db with the central location registry schema.
             Idempotent: can be run multiple times.
@method.de   Erstellt die Tabelle location_registry und die Ortsdaten-Tabellen
             session_tracks, location_history, location_stays und
             location_stays_geocoded mit CREATE TABLE IF NOT EXISTS.
             Eine Tabelle ohne region-Spalte (früheres Schema) wird einmalig neu aufgebaut
             (lat/lon nullbar, region aus den gespeicherten Koordinaten).
@method.en   Creates table location_registry and the location data tables
             session_tracks, location_history, location_stays and
             location_stays_geocoded with CREATE TABLE IF NOT EXISTS.
             An older table without the region column is rebuilt once
             (nullable lat/lon, region from the stored coordinates).
@reads       location.db (wenn existiert, zum Prüfen)
@writes      location.db (Tabellen, Indizes; einmaliger Umbau location_registry)
@limits.de   Beim Umbau wird die Region aus bereits gerundeten Koordinaten
             bestimmt; an Grenzen kann sie von der Region des Originalpunkts abweichen.
@limits.en   During the rebuild the region is derived from already rounded
             coordinates; near borders it can differ from the original point's region.

@relevance.de  Wesentlich für die Speicherung von GPS-Daten in einer separaten Datenbank
@relevance.en  Essential for storing GPS data in a separate database
@usage
    # Schema erstellen
    python3 scripts/utils/create_location_schema.py
    
    # Idempotent: kann mehrmals ausgeführt werden
    python3 scripts/utils/create_location_schema.py
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config
from modules.db import _open_encrypted

LOCATION_REGISTRY_SCHEMA = """
CREATE TABLE IF NOT EXISTS location_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    importer TEXT NOT NULL,
    file_type TEXT,
    source_file TEXT,
    original_sha256 TEXT,
    stored_sha256 TEXT,
    ts TEXT,
    date TEXT NOT NULL,
    lat REAL,
    lon REAL,
    precision INTEGER,
    region TEXT,
    ref_db TEXT,
    ref_table TEXT,
    ref_id INTEGER,
    person TEXT NOT NULL,
    migrated_from TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

# Ortsdaten-Tabellen, die früher in health.db lagen (Tracks, Aufenthalte,
# Standortverlauf, Geokodierung der Aufenthalte). Gleiche Spalten wie dort,
# damit Leser ihre Abfragen nur um das Schema-Präfix loc. ergänzen müssen.
# session_id verweist auf health.db::sessions; über Datenbankgrenzen gibt
# es keinen Fremdschlüssel.
LOCATION_DATA_SCHEMA = """
CREATE TABLE IF NOT EXISTS session_tracks (
    session_id  TEXT,
    ts          TEXT NOT NULL,
    lat         REAL,
    lon         REAL,
    elevation_m REAL,
    speed_ms    REAL,
    PRIMARY KEY (session_id, ts)
);

CREATE TABLE IF NOT EXISTS location_history (
    datetime     TEXT NOT NULL,
    date         TEXT,
    hour         INTEGER,
    state        TEXT,
    lat          REAL,
    lon          REAL,
    gps_accuracy REAL,
    zone         TEXT,
    city         TEXT,
    person       TEXT NOT NULL DEFAULT 'unknown',
    source       TEXT,
    PRIMARY KEY (datetime, person)
);
CREATE INDEX IF NOT EXISTS idx_loc_date ON location_history(date);
CREATE INDEX IF NOT EXISTS idx_loc_state ON location_history(state);

CREATE TABLE IF NOT EXISTS location_stays (
    id       INTEGER PRIMARY KEY,
    start_ts TEXT,
    end_ts   TEXT,
    lat      REAL,
    lon      REAL,
    is_home  INTEGER,
    timezone TEXT,
    person   TEXT NOT NULL DEFAULT 'unknown',
    source   TEXT
);
CREATE INDEX IF NOT EXISTS idx_loc_stays_start ON location_stays(start_ts);
CREATE INDEX IF NOT EXISTS idx_loc_stays_end   ON location_stays(end_ts);

CREATE TABLE IF NOT EXISTS location_stays_geocoded (
    stay_id         INTEGER PRIMARY KEY REFERENCES location_stays(id),
    country         TEXT,
    country_iso     TEXT,
    state           TEXT,
    county          TEXT,
    city            TEXT,
    subregion       TEXT,
    climate_zone    TEXT,
    geocoded_at     TEXT NOT NULL
);
"""

LOCATION_DATA_TABLES = ("session_tracks", "location_history", "location_stays",
                        "location_stays_geocoded")

# Duplikat-Schlüssel als Ausdrucks-Index: In SQLite gelten NULL-Werte in einer
# UNIQUE-Bedingung als verschieden, damit würde INSERT OR IGNORE bei Einträgen
# ohne Quelldatei/Verweis nie greifen. ts (Importzeit) gehört bewusst nicht
# dazu, sonst erzeugt jeder erneute Import eine Kopie. lat/lon/precision sind
# bei store: "region" NULL und stehen deshalb ebenfalls in COALESCE.
LOCATION_REGISTRY_UNIQUE = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_location_registry_entry ON location_registry (
    importer,
    COALESCE(file_type, ''),
    COALESCE(source_file, ''),
    COALESCE(original_sha256, ''),
    date,
    COALESCE(lat, ''),
    COALESCE(lon, ''),
    COALESCE(precision, -1),
    COALESCE(region, ''),
    COALESCE(ref_db, ''),
    COALESCE(ref_table, ''),
    COALESCE(ref_id, -1),
    person,
    COALESCE(migrated_from, '')
)
"""

LOCATION_REGISTRY_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_location_registry_importer ON location_registry(importer)",
    "CREATE INDEX IF NOT EXISTS idx_location_registry_source_file ON location_registry(source_file)",
    "CREATE INDEX IF NOT EXISTS idx_location_registry_original_sha256 ON location_registry(original_sha256)",
    "CREATE INDEX IF NOT EXISTS idx_location_registry_person ON location_registry(person)",
    "CREATE INDEX IF NOT EXISTS idx_location_registry_date ON location_registry(date)",
    "CREATE INDEX IF NOT EXISTS idx_location_registry_ref ON location_registry(ref_db, ref_table, ref_id)",
    "CREATE INDEX IF NOT EXISTS idx_location_registry_region ON location_registry(region)",
]

_COPY_COLUMNS = (
    "id", "importer", "file_type", "source_file", "original_sha256",
    "stored_sha256", "ts", "date", "lat", "lon", "precision", "ref_db",
    "ref_table", "ref_id", "person", "migrated_from", "created_at",
)


def _needs_region_migration(conn: sqlite3.Connection) -> bool:
    """True, wenn location_registry noch das Schema ohne region-Spalte hat."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(location_registry)")}
    return bool(columns) and "region" not in columns


def _migrate_region(conn: sqlite3.Connection) -> None:
    """Baut location_registry mit region-Spalte und nullbaren lat/lon neu auf.

    SQLite kann NOT NULL nicht nachträglich entfernen, daher: alte Tabelle
    umbenennen, neue anlegen, Einträge mit derselben id kopieren und die
    Region aus den gespeicherten Koordinaten nachtragen.
    """
    from modules.location_store import stored_region

    had_triggers = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND tbl_name='location_registry'"
    ).fetchone()[0] > 0
    rows = conn.execute(
        f"SELECT {', '.join(_COPY_COLUMNS)} FROM location_registry"
    ).fetchall()

    cols = ", ".join(_COPY_COLUMNS) + ", region"
    marks = ", ".join("?" * (len(_COPY_COLUMNS) + 1))
    lat_i, lon_i, prec_i = (_COPY_COLUMNS.index(c) for c in ("lat", "lon", "precision"))
    try:
        conn.execute("BEGIN")
        conn.execute("ALTER TABLE location_registry RENAME TO location_registry_pre_region")
        # Indexnamen sind datenbankweit eindeutig: alte Indizes zuerst entfernen
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='location_registry_pre_region' AND sql IS NOT NULL"
        ).fetchall():
            conn.execute(f'DROP INDEX "{name}"')
        conn.execute(LOCATION_REGISTRY_SCHEMA)
        conn.executemany(
            f"INSERT INTO location_registry ({cols}) VALUES ({marks})",
            [tuple(row) + (stored_region(row[lat_i], row[lon_i], row[prec_i]),) for row in rows],
        )
        conn.execute("DROP TABLE location_registry_pre_region")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    if had_triggers:
        # Mit der alten Tabelle sind ihre Audit- und Pseudonym-Trigger weg
        from modules.db import _install_audit_log_triggers, _install_pseudonymization_safeguard
        _install_audit_log_triggers(conn)
        _install_pseudonymization_safeguard(conn)


def ensure_location_schema(conn: sqlite3.Connection) -> None:
    """Legt Tabelle und Indizes an, falls sie fehlen (idempotent).

    Wird von location_store.record() vor jedem Schreiben aufgerufen, damit
    eine frische Installation ohne separaten Schema-Lauf funktioniert.
    """
    conn.executescript(LOCATION_REGISTRY_SCHEMA)
    conn.executescript(LOCATION_DATA_SCHEMA)
    if _needs_region_migration(conn):
        _migrate_region(conn)
    conn.execute(LOCATION_REGISTRY_UNIQUE)
    for index_sql in LOCATION_REGISTRY_INDEXES:
        conn.execute(index_sql)
    conn.commit()


def create_location_schema(db_path=None):
    """Erstellt das Schema für location.db.

    Args:
        db_path: Pfad zur location.db. Standardmäßig aus Config.

    Returns:
        sqlite3.Connection: Verbindung zur erstellten/geöffneten Datenbank
    """
    if db_path is None:
        db_path = Config().location_db_path
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Datenbank öffnen (mit Verschlüsselung wenn db_key konfiguriert)
    conn = _open_encrypted(str(db_path))
    ensure_location_schema(conn)

    # Trigger für Audit-Log (wie in db.py für health.db)
    from modules.db import _install_audit_log_triggers, _install_pseudonymization_safeguard
    _install_audit_log_triggers(conn)
    _install_pseudonymization_safeguard(conn)

    return conn


def main():
    cfg = Config()
    db_path = cfg.location_db_path
    
    print(f"Erstelle Schema für location.db: {db_path}")
    conn = create_location_schema(db_path)
    
    # Überprüfen, dass die Tabelle existiert
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='location_registry'"
    )
    if cursor.fetchone():
        print("  Tabelle location_registry existiert")
    else:
        print("  FEHLER: Tabelle location_registry wurde nicht erstellt")
        sys.exit(1)
    
    # Indexes überprüfen
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_location_registry_%'"
    )
    indexes = cursor.fetchall()
    print(f"  {len(indexes)} Indexes erstellt")
    
    conn.close()
    print("Schema erfolgreich erstellt")


if __name__ == "__main__":
    main()
