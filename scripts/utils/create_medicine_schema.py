#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
create_medicine_schema.py — medicine.db initialisieren

@tier        infrastructure
@purpose.de  Initialisiert medicine.db mit Tabellen für medizinische Daten.
@purpose.en  Initializes medicine.db with tables for medical data.
@method.de   Tabellen (identische Schemas wie in health.db zur verlustfreien Migration):
             lab_manual (manuelle Laborbefunde), lab_results (strukturierte Laborbefunde),
             medications (Medikamente), assessments (Klinische Scores / Beurteilungen),
             findings (Befunde mit ICD-Code). Läuft bei jedem Aufruf zusätzlich
             ``_migrate_medications_is_chronic`` — fügt is_chronic per ALTER TABLE
             nach, falls eine ältere medicine.db die Spalte noch nicht hat (idempotent,
             per PRAGMA table_info geprüft).
@method.en   Tables (identical schemas as in health.db for lossless migration):
             lab_manual (manual lab results), lab_results (structured lab results),
             medications, assessments (clinical scores), findings (with ICD codes).
             Also runs ``_migrate_medications_is_chronic`` on every call — adds
             is_chronic via ALTER TABLE if an older medicine.db is missing it
             (idempotent, checked via PRAGMA table_info).
@reads       Keine (erstellt neues Schema)
@writes      medicine.db (Tabellen: lab_manual, lab_results, medications, assessments, findings)
@limits.de   Einmalig aufrufen. Wiederholte Ausfuehrung ist idempotent (CREATE IF NOT EXISTS).

@relevance.de  Ermöglicht die Erstellung von Datenbank-Schemata, essentiell für die Datenorganisation und -struktur
@relevance.en  Enables creation of database schemas, essential for data organization and structure
@limits.en   Call once. Repeated execution is idempotent (CREATE IF NOT EXISTS).
@usage
    python3 scripts/utils/create_medicine_schema.py
    python3 scripts/utils/create_medicine_schema.py --force
"""

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.db import open_medicine_db

NOW   = datetime.now(timezone.utc).isoformat()
PHASE = "medicine-1.0"

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    phase       TEXT PRIMARY KEY,
    ts          TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS import_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_run        TEXT NOT NULL,
    source        TEXT NOT NULL,
    rows_inserted INTEGER DEFAULT 0,
    notes         TEXT
);

-- ── Laborbefunde (manuell, aus Arztbriefen / Laborausdrucken) ─────────────────
-- Schema identisch mit health.db.lab_manual für verlustfreie Migration
CREATE TABLE IF NOT EXISTS lab_manual (
    date       TEXT NOT NULL,
    parameter  TEXT NOT NULL,
    kategorie  TEXT,
    wert       TEXT,
    wert_num   REAL,
    einheit    TEXT,
    ref_min    REAL,
    ref_max    REAL,
    labor      TEXT NOT NULL DEFAULT '',
    status     TEXT,
    kommentar  TEXT,
    person     TEXT NOT NULL,
    source     TEXT DEFAULT 'manual',
    PRIMARY KEY (date, parameter, labor, person)
);

-- ── Laborbefunde (strukturiert, z.B. Oura) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS lab_results (
    id              TEXT NOT NULL,
    test_type       TEXT NOT NULL,
    ts              TEXT NOT NULL,
    date            TEXT NOT NULL,
    status          TEXT,
    abnormal_result INTEGER,
    observations    TEXT,
    person          TEXT NOT NULL,
    source          TEXT DEFAULT 'oura',
    PRIMARY KEY (id, person)
);

-- ── Medikamente ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS medications (
    ts             TEXT NOT NULL,
    date           TEXT NOT NULL,
    medication_id  TEXT,
    drug_name      TEXT,
    dose_value     REAL,
    dose_unit      TEXT,
    route          TEXT,
    injection_site TEXT,
    is_skipped     INTEGER DEFAULT 0,
    is_chronic     INTEGER DEFAULT 1,
    notes          TEXT,
    person         TEXT NOT NULL,
    source         TEXT,
    PRIMARY KEY (ts, person, source)
);

-- ── Klinische Scores / Beurteilungen ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS assessments (
    ts         TEXT NOT NULL,
    date       TEXT NOT NULL,
    instrument TEXT NOT NULL,
    score      REAL,
    details    TEXT,
    person     TEXT NOT NULL,
    source     TEXT,
    PRIMARY KEY (ts, instrument, person)
);

-- ── Diagnosen (neu) ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS diagnoses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    person        TEXT    NOT NULL,
    date          TEXT    NOT NULL,
    icd_code      TEXT,
    description   TEXT    NOT NULL,
    status        TEXT    DEFAULT 'confirmed',
    certainty     REAL,
    source        TEXT,
    notes         TEXT,
    ts_import     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE (person, icd_code, date)
);

CREATE INDEX IF NOT EXISTS idx_lab_manual_date   ON lab_manual (date);
CREATE INDEX IF NOT EXISTS idx_lab_manual_param  ON lab_manual (parameter);
CREATE INDEX IF NOT EXISTS idx_medications_date  ON medications (date);
CREATE INDEX IF NOT EXISTS idx_assessments_date  ON assessments (date);
"""


def _migrate_medications_is_chronic(conn: sqlite3.Connection) -> None:
    """Add is_chronic to medications on DBs created before this column existed."""
    if not _table_exists(conn, "medications"):
        return
    cols = {row[1] for row in conn.execute("PRAGMA table_info(medications)")}
    if "is_chronic" not in cols:
        conn.execute("ALTER TABLE medications ADD COLUMN is_chronic INTEGER DEFAULT 1")


def main() -> None:
    ap = argparse.ArgumentParser(description="medicine.db initialisieren")
    ap.add_argument("--force", action="store_true",
                    help="Auch wenn Schema bereits existiert ausführen")
    args = ap.parse_args()

    conn = open_medicine_db()
    _migrate_medications_is_chronic(conn)
    conn.commit()
    existing = conn.execute(
        "SELECT phase FROM schema_version WHERE phase=?", (PHASE,)
    ).fetchone() if _table_exists(conn, "schema_version") else None

    if existing and not args.force:
        print(f"medicine.db: Schema {PHASE} bereits vorhanden. --force zum Neuaufbau.")
        conn.close()
        return

    conn.executescript(SCHEMA)
    conn.execute("INSERT OR REPLACE INTO schema_version VALUES (?,?,?)",
                 (PHASE, NOW, "medicine.db Initialschema"))
    conn.execute("INSERT INTO import_log (ts_run, source, rows_inserted) VALUES (?,?,?)",
                 (NOW, "create_medicine_schema", 1))
    conn.commit()
    conn.close()
    print(f"medicine.db: Schema {PHASE} angelegt.")


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone())


if __name__ == "__main__":
    main()
