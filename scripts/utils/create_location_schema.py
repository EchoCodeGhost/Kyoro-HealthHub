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
@method.de   Erstellt die Tabellen location_registry und location_tokens (falls benötigt).
             Nutzt CREATE TABLE IF NOT EXISTS.
@method.en   Creates tables location_registry and location_tokens (if needed).
             Uses CREATE TABLE IF NOT EXISTS.
@reads       location.db (wenn existiert, zum Prüfen)
@writes      location.db (neue Tabellen)
@limits.de   Keine Datenmigration — nur Schema-Erstellung
@limits.en   No data migration — only schema creation

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
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    precision INTEGER NOT NULL,
    ref_db TEXT,
    ref_table TEXT,
    ref_id INTEGER,
    person TEXT NOT NULL,
    migrated_from TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""

# Duplikat-Schlüssel als Ausdrucks-Index: In SQLite gelten NULL-Werte in einer
# UNIQUE-Bedingung als verschieden, damit würde INSERT OR IGNORE bei Einträgen
# ohne Quelldatei/Verweis nie greifen. ts (Importzeit) gehört bewusst nicht
# dazu, sonst erzeugt jeder erneute Import eine Kopie.
LOCATION_REGISTRY_UNIQUE = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_location_registry_entry ON location_registry (
    importer,
    COALESCE(file_type, ''),
    COALESCE(source_file, ''),
    COALESCE(original_sha256, ''),
    date, lat, lon, precision,
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
]


def ensure_location_schema(conn: sqlite3.Connection) -> None:
    """Legt Tabelle und Indizes an, falls sie fehlen (idempotent).

    Wird von location_store.record() vor jedem Schreiben aufgerufen, damit
    eine frische Installation ohne separaten Schema-Lauf funktioniert.
    """
    conn.executescript(LOCATION_REGISTRY_SCHEMA)
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
