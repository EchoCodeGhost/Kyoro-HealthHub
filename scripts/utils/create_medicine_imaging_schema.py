#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
create_medicine_imaging_schema.py — medicine_imaging.db initialisieren

@tier        infrastructure
@purpose.de  Initialisiert medicine_imaging.db für medizinische Bilddaten.
@purpose.en  Initializes medicine_imaging.db for medical imaging data.
@method.de   Tabellen: imaging_studies (übergeordnete Untersuchungen),
             imaging_files (einzelne Bilddateien), imaging_analysis (VLM-Analyse-Ergebnisse).
             Modularität: Fundus, Röntgen, MRT, CT, Echo folgen alle diesem Schema.
             body_part + modality unterscheiden den Bildtyp. Kernlogik liegt in
             ensure_schema(force=False) OHNE argparse — main() ist nur noch ein
             duenner CLI-Wrapper darum. Grund: andere Skripte (z.B. import_fundus.py)
             riefen vorher main() direkt auf, dessen ap.parse_args() dabei den
             AUFRUFER-Prozess' sys.argv einlas (z.B. import_fundus.py --person X
             datei.dcm) und mit "unrecognized arguments" abstuerzte, da dieses
             Skript nur --force kennt.
@method.en   Tables: imaging_studies (parent studies), imaging_files (individual files),
             imaging_analysis (VLM analysis results). Modular: Fundus, X-ray, MRI,
             CT, Echo all follow this schema. body_part + modality distinguish image type.
             Core logic lives in ensure_schema(force=False) WITHOUT argparse — main()
             is now just a thin CLI wrapper around it. Reason: other scripts (e.g.
             import_fundus.py) used to call main() directly, whose ap.parse_args()
             read the CALLING process's sys.argv (e.g. import_fundus.py --person X
             file.dcm) and crashed with "unrecognized arguments" since this script
             only knows --force.
@reads       Keine (erstellt neues Schema)
@writes      medicine_imaging.db (Tabellen: imaging_studies, imaging_files, imaging_analysis)
@limits.de   Einmalig aufrufen. Wiederholte Ausfuehrung ist idempotent (CREATE IF NOT EXISTS).
             import_log hatte bis vor kurzem nicht dieselben Spalten wie health.dbs
             import_log (data_path/rows_skipped fehlten) — modules/base.py's
             log_import() erwartet diese und stuerzte deshalb bei jedem echten
             medicine_imaging.db-Import ab, VOR dem commit, sodass auch die eigentlich
             importierten Zeilen verlorengingen. _migrate() gleicht das jetzt per
             ALTER TABLE an.

@relevance.de  Ermöglicht die Erstellung von Datenbank-Schemata, essentiell für die Datenorganisation und -struktur
@relevance.en  Enables creation of database schemas, essential for data organization and structure
@limits.en   Call once. Repeated execution is idempotent (CREATE IF NOT EXISTS).
             Until recently, import_log didn't have the same columns as health.db's
             import_log (data_path/rows_skipped were missing) — modules/base.py's
             log_import() expects these and crashed on every real medicine_imaging.db
             import, before the commit, losing the actually-imported rows too.
             _migrate() now aligns it via ALTER TABLE.
@usage
    python3 scripts/utils/create_medicine_imaging_schema.py
    python3 scripts/utils/create_medicine_imaging_schema.py --force
"""

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.db import open_medicine_imaging_db

NOW   = datetime.now(timezone.utc).isoformat()
PHASE = "medicine-imaging-1.0"

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
    data_path     TEXT,
    person        TEXT,
    rows_inserted INTEGER DEFAULT 0,
    rows_skipped  INTEGER DEFAULT 0,
    errors        INTEGER DEFAULT 0,
    error_detail  TEXT,
    duration_s    REAL,
    notes         TEXT
);

-- ── Untersuchungen (Study-Ebene) ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS imaging_studies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    person          TEXT    NOT NULL,
    study_date      TEXT    NOT NULL,
    modality        TEXT    NOT NULL,  -- OP (Fundus), CR (Röntgen), MR, CT, US, ECG
    body_part       TEXT,              -- RETINA, CHEST, KNEE, ABDOMEN ...
    institution     TEXT,              -- anonymisiert falls nötig
    ordering_reason TEXT,
    notes           TEXT,
    ts_import       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE (person, study_date, modality, body_part)
);

-- ── Einzelne Bilddateien ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS imaging_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id        INTEGER REFERENCES imaging_studies(id),
    person          TEXT    NOT NULL,
    file_path       TEXT    NOT NULL UNIQUE,  -- absoluter Pfad zur JPEG-Kopie auf Disk
    original_format TEXT    DEFAULT 'dcm',    -- 'dcm' oder 'jpeg'
    laterality      TEXT,                     -- L, R, B (beide), NULL
    acquisition_date TEXT,
    modality        TEXT,
    body_part       TEXT,
    manufacturer    TEXT,
    model_name      TEXT,
    rows            INTEGER,
    cols            INTEGER,
    bits_allocated  INTEGER,
    image_type      TEXT,
    source_type     TEXT,   -- 'camera' | 'screenshot' | 'dslr' | 'other'
    lesion_id       INTEGER REFERENCES skin_lesions(id),
    raw_file_path   TEXT,   -- metadatenbereinigtes RAW-Original (NEF/CR2/...), falls vorhanden
    notes           TEXT,
    ts_import       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

-- ── Hautläsionen (Langzeit-Tracking) ────────────────────────────────────────
-- Eine Zeile pro Läsion; Fotos verweisen über lesion_id auf diese Tabelle.
CREATE TABLE IF NOT EXISTS skin_lesions (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    person                   TEXT    NOT NULL,
    body_location            TEXT    NOT NULL,  -- Freitext: "Rücken links, unterhalb Schulterblatt"
    first_seen               TEXT    NOT NULL,  -- YYYY-MM-DD
    last_checked             TEXT,              -- YYYY-MM-DD (wird bei jedem Import aktualisiert)
    app_score                TEXT,              -- "niedrig" / "mittel" / "hoch" / NULL
    app_name                 TEXT,              -- "Skinscreener", "SkinVision", etc.
    dermatologist_assessment TEXT,              -- Freitext Hautarzt-Befund
    dermatologist_date       TEXT,              -- YYYY-MM-DD Hautarzt-Termin
    operated                 INTEGER DEFAULT 0, -- 0 = nein, 1 = ja
    operation_date           TEXT,              -- YYYY-MM-DD
    histology                TEXT,              -- "benigne" / "Basalzellkarzinom" / "Melanom" etc.
    histology_subtype        TEXT,              -- "Clark Level II", "Melanoma in situ", etc.
    histology_date           TEXT,              -- YYYY-MM-DD Befunddatum
    notes                    TEXT,
    ts_import                TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE (person, body_location, first_seen)
);

-- ── VLM-Analysen ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS imaging_analysis (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id         INTEGER NOT NULL REFERENCES imaging_files(id),
    ts              TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    prompt          TEXT,
    response        TEXT,
    laterality      TEXT,
    -- Strukturierte Extraktion (optional, NULL wenn nicht geparst)
    cd_ratio_est    REAL,   -- Cup-to-Disc-Ratio Schätzung
    excavation_flag INTEGER, -- 0/1
    findings_json   TEXT,   -- JSON mit weiteren strukturierten Befunden
    source          TEXT    DEFAULT 'vlm',
    ts_import       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_imaging_files_study   ON imaging_files (study_id);
CREATE INDEX IF NOT EXISTS idx_imaging_files_date    ON imaging_files (acquisition_date);
CREATE INDEX IF NOT EXISTS idx_imaging_files_lesion  ON imaging_files (lesion_id);
CREATE INDEX IF NOT EXISTS idx_imaging_analysis_file ON imaging_analysis (file_id);
CREATE INDEX IF NOT EXISTS idx_skin_lesions_person   ON skin_lesions (person);
CREATE INDEX IF NOT EXISTS idx_skin_lesions_location ON skin_lesions (body_location);
"""


SKIN_LESIONS_DDL = """
CREATE TABLE IF NOT EXISTS skin_lesions (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    person                   TEXT    NOT NULL,
    body_location            TEXT    NOT NULL,
    first_seen               TEXT    NOT NULL,
    last_checked             TEXT,
    app_score                TEXT,
    app_name                 TEXT,
    dermatologist_assessment TEXT,
    dermatologist_date       TEXT,
    operated                 INTEGER DEFAULT 0,
    operation_date           TEXT,
    histology                TEXT,
    histology_subtype        TEXT,
    histology_date           TEXT,
    notes                    TEXT,
    ts_import                TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE (person, body_location, first_seen)
);
CREATE INDEX IF NOT EXISTS idx_skin_lesions_person   ON skin_lesions (person);
CREATE INDEX IF NOT EXISTS idx_skin_lesions_location ON skin_lesions (body_location);
"""


def _migrate(conn) -> None:
    """Fügt neue Tabellen und Spalten zu bestehenden DBs hinzu (idempotent)."""
    # skin_lesions Tabelle
    conn.executescript(SKIN_LESIONS_DDL)

    # Neue Spalten in imaging_files
    existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(imaging_files)")}
    for col, definition in [
        ("source_type",   "TEXT"),
        ("lesion_id",     "INTEGER REFERENCES skin_lesions(id)"),
        ("raw_file_path", "TEXT"),  # metadatenbereinigtes RAW-Original (NEF/CR2/...), falls vorhanden
    ]:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE imaging_files ADD COLUMN {col} {definition}")

    # import_log auf denselben Spaltensatz wie health.db bringen (modules/base.py's
    # log_import() erwartet data_path + rows_skipped, die hier urspruenglich fehlten
    # — jeder echte Import-Lauf ist deshalb an der Logging-Zeile gecrasht, VOR dem
    # commit, sodass die eigentlich importierten Zeilen (nicht nur der Log-Eintrag)
    # verlorengingen. Gefunden beim Testen der --person-Ergaenzung in import_fundus.py.
    importlog_cols = {r[1] for r in conn.execute("PRAGMA table_info(import_log)")}
    for col, definition in [
        ("data_path",    "TEXT"),
        ("person",       "TEXT"),
        ("rows_skipped", "INTEGER DEFAULT 0"),
        ("errors",       "INTEGER DEFAULT 0"),
        ("error_detail", "TEXT"),
        ("duration_s",   "REAL"),
    ]:
        if col not in importlog_cols:
            conn.execute(f"ALTER TABLE import_log ADD COLUMN {col} {definition}")


def ensure_schema(force: bool = False) -> None:
    """Kernlogik ohne argparse/sys.argv — sicher aus anderen Skripten heraus
    aufrufbar (z.B. import_fundus.py._ensure_db()), ohne den Aufrufer-Prozess'
    eigene CLI-Argumente als die von create_medicine_imaging_schema.py
    misszuinterpretieren (main() tat das vorher via ap.parse_args() ohne
    explizite Argumentliste — ein Aufruf aus import_fundus.py heraus crashte
    dadurch an jedem --person/Dateipfad-Argument mit SystemExit)."""
    conn = open_medicine_imaging_db()
    existing = conn.execute(
        "SELECT phase FROM schema_version WHERE phase=?", (PHASE,)
    ).fetchone() if _table_exists(conn, "schema_version") else None

    if existing and not force:
        _migrate(conn)
        conn.commit()
        print(f"medicine_imaging.db: Schema {PHASE} bereits vorhanden — Migration geprüft. --force zum Neuaufbau.")
        conn.close()
        return

    conn.executescript(SCHEMA)
    conn.execute("INSERT OR REPLACE INTO schema_version VALUES (?,?,?)",
                 (PHASE, NOW, "medicine_imaging.db Initialschema"))
    conn.execute("INSERT INTO import_log (ts_run, source, rows_inserted) VALUES (?,?,?)",
                 (NOW, "create_medicine_imaging_schema", 1))
    conn.commit()
    conn.close()
    print(f"medicine_imaging.db: Schema {PHASE} angelegt.")


def main() -> None:
    ap = argparse.ArgumentParser(description="medicine_imaging.db initialisieren")
    ap.add_argument("--force", action="store_true",
                    help="Auch wenn DB bereits existiert ausführen")
    args = ap.parse_args()
    ensure_schema(force=args.force)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone())


if __name__ == "__main__":
    main()
