#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Manuelle Laborbefund-CSVs → health.db (lab_manual)

@tier infrastructure
@purpose.de Import von manuell erfassten Laborbefunden aus CSV-Dateien für Longitudinal-Analysen
@purpose.en Import manually recorded lab results from CSV files for longitudinal analysis
@method.de Parsen von CSV-Dateien mit festem Format (Kopfzeile Pflicht).
           Kommentarzeilen (beginnend mit #) werden übersprungen.
           Numerische Werte werden als Float geparst, textuelle Werte als String.
           Speicherung in lab_manual-Tabelle mit PRIMARY KEY (date, parameter, labor, person).
@method.en Parse CSV files with fixed format (header mandatory).
           Comment lines (starting with #) are skipped.
           Numeric values are parsed as float, textual values as string.
           Storage in lab_manual table with PRIMARY KEY (date, parameter, labor, person).
@reads medicine/laborbefunde/*_labor.csv, imports/manual/labor*.csv
@writes health.db:lab_manual, health.db:import_log
@limits.de Verarbeitet nur Dateien mit allen Pflichtfeldern (datum, parameter, wert).
           Doppelte Einträge (gleiches Datum, Parameter, Labor, Person) werden ignoriert.
           OCR-korrigierte Dateien müssen Validierungsregeln einhalten.

@relevance.de  Ermöglicht den Import von Laborergebnissen, essentiell für die Integration klinischer Daten
@relevance.en  Enables import of laboratory results, essential for integration of clinical data
@limits.en Only processes files with all mandatory fields (date, parameter, value).
           Duplicate entries (same date, parameter, lab, person) are ignored.
           OCR-corrected files must comply with validation rules.
@usage python3 import_lab_csv.py                    # alle CSVs in Standardverzeichnissen
       python3 import_lab_csv.py --update           # nur neue (ignoriert via PRIMARY KEY)
       python3 import_lab_csv.py --file /pfad.csv   # einzelne Datei
       python3 import_lab_csv.py --dry-run          # Vorschau ohne DB-Schreibzugriff
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_medicine_db as open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person

_cfg = _Cfg()
DB_PATH = _cfg.db_path

_REPO_ROOT   = Path(__file__).parents[2]
_MED_DIR     = _REPO_ROOT / "medicine" / "laborbefunde"
_MANUAL_DIR  = Path(_cfg._cfg.get("paths", {}).get("manual_dir",
               str(Path.home() / "Kyoro-HealthHub" / "imports" / "manual")))

REQUIRED_COLS = {"datum", "parameter", "wert"}


def _parse_float(val: str) -> float | None:
    """Parsen eines numerischen Werts aus String mit Komma-Unterstützung.
    
    @purpose.de Konvertierung von deutschen Zahlenformaten (Komma als Dezimaltrennzeichen) zu Float
    @purpose.en Convert German number formats (comma as decimal separator) to float
    @method.de Ersetzt Komma durch Punkt vor der Float-Konvertierung.
               Leere Strings ergeben None.
    @method.en Replace comma with period before float conversion.
               Empty strings return None.
    @param val Numerischer String (z.B. '14,2' oder '14.2')
    @returns Float-Wert oder None bei Parse-Fehler
    """
    if not val or val.strip() == "":
        return None
    try:
        return float(val.replace(",", "."))
    except ValueError:
        return None


def _find_csvs(extra_file: Path | None) -> list[Path]:
    """Suchen von Labor-CSV-Dateien in Standardverzeichnissen.
    
    @purpose.de Ermittelung aller zu verarbeitenden CSV-Dateien
    @purpose.en Determine all CSV files to be processed
    @method.de Durchsucht medicine/laborbefunde/ nach *_labor.csv Dateien
               und imports/manual/ nach labor*.csv Dateien.
               Bei Angabe von extra_file wird nur diese Datei verarbeitet.
    @method.en Scan medicine/laborbefunde/ for *_labor.csv files
               and imports/manual/ for labor*.csv files.
               With extra_file specified, only that file is processed.
    @param extra_file Optional: Pfad zu einer einzelnen CSV-Datei
    @returns Liste von Pfaden zu CSV-Dateien
    """
    paths: list[Path] = []
    if extra_file:
        paths.append(extra_file)
        return paths
    if _MED_DIR.is_dir():
        paths.extend(sorted(_MED_DIR.glob("*_labor.csv")))
    if _MANUAL_DIR.is_dir():
        paths.extend(sorted(_MANUAL_DIR.glob("labor*.csv")))
    return paths


def _import_csv(conn, path: Path, person: str, dry_run: bool) -> tuple[int, int]:
    """Import einer einzelnen Labor-CSV-Datei.
    
    @purpose.de Verarbeitung einer CSV-Datei und Speicherung der Laborwerte in der DB
    @purpose.en Process a CSV file and store lab values in the database
    @method.de Parsen der CSV mit DictReader, Validierung der Pflichtfelder,
               Konvertierung von numerischen Werten, Speicherung in lab_manual
               mit INSERT OR IGNORE (Doppelte werden ignoriert).
    @method.en Parse CSV with DictReader, validate mandatory fields,
               convert numeric values, store in lab_manual
               with INSERT OR IGNORE (duplicates are ignored).
    @param conn SQLite-Datenbankverbindung
    @param path Pfad zur CSV-Datei
    @param person Personen-ID
    @param dry_run Keine DB-Schreibzugriffe (nur Vorschau)
    @returns Tuple aus (anzahl_importiert, anzahl_übersprungen)
    """
    inserted = skipped = 0
    with open(path, newline="", encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    reader = csv.DictReader(lines)
    if not reader.fieldnames:
        return 0, 0
    cols = {c.strip().lower() for c in reader.fieldnames}
    if not REQUIRED_COLS.issubset(cols):
        missing = REQUIRED_COLS - cols
        print(t(f"  Überspringe {path.name}: fehlende Spalten {missing}",
                f"  Skipping {path.name}: missing columns {missing}"))
        return 0, 0

    rows = []
    for row in reader:
        datum     = (row.get("datum") or "").strip()
        parameter = (row.get("parameter") or "").strip()
        if not datum or not parameter:
            continue
        wert      = (row.get("wert") or "").strip()
        wert_num  = _parse_float(wert)
        rows.append((
            datum,
            parameter,
            (row.get("kategorie") or "").strip() or None,
            wert or None,
            wert_num,
            (row.get("einheit") or "").strip() or None,
            _parse_float(row.get("ref_min") or ""),
            _parse_float(row.get("ref_max") or ""),
            (row.get("labor") or "").strip(),
            (row.get("status") or "").strip() or None,
            (row.get("kommentar") or "").strip() or None,
            person,
            "manual",
        ))

    if dry_run:
        print(t(f"  DRY-RUN {path.name}: {len(rows)} Zeilen",
                f"  DRY-RUN {path.name}: {len(rows)} rows"))
        return len(rows), 0

    for r in rows:
        cur = conn.execute(
            """INSERT OR IGNORE INTO lab_manual
               (date, parameter, kategorie, wert, wert_num, einheit,
                ref_min, ref_max, labor, status, kommentar, person, source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            r,
        )
        if cur.rowcount:
            inserted += 1
        else:
            skipped += 1
    return inserted, skipped



def main() -> None:
    """Hauptfunktion für den Labor-CSV-Import.
    
    @purpose.de Orchestrierung des Import-Prozesses für Laborbefund-Daten
    @purpose.en Orchestrate import process for lab result data
    @method.de Parsen von CLI-Argumenten, Suchen von CSV-Dateien mit _find_csvs,
               Verarbeitung jeder Datei mit _import_csv, Speichern von Import-Logs,
               Anzeige von Statistiken und Commit der DB-Änderungen
    @method.en Parse CLI arguments, find CSV files with _find_csvs,
               process each file with _import_csv, save import logs,
               display statistics and commit DB changes
    """
    parser = argparse.ArgumentParser(
        description=t("Manuelle Laborbefund-CSVs in health.db importieren",
                      "Import manual lab result CSVs into health.db")
    )
    parser.add_argument("--file",    metavar="CSV", help=t("Einzelne CSV-Datei", "Single CSV file"))
    parser.add_argument("--person",  metavar="ID",  help=t("Person-ID (Standard: eigene)", "Person ID (default: own)"))
    parser.add_argument("--dry-run", action="store_true", help=t("Keine DB-Schreibzugriffe", "No DB writes"))
    parser.add_argument("--update",  action="store_true", help=t("Nur neue Einträge (No-op, via PRIMARY KEY)", "New entries only (no-op, via PRIMARY KEY)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    extra = Path(args.file) if args.file else None
    csvs  = _find_csvs(extra)
    if not csvs:
        print(t("Keine Lab-CSVs gefunden.", "No lab CSVs found."))
        return

    conn   = open_db(DB_PATH)
    person = resolve_person(conn, args.person) if args.person else OWN_PERSON_ID

    conn.execute("""CREATE TABLE IF NOT EXISTS lab_manual (
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
    )""")

    total_ins = total_skip = 0
    for path in csvs:
        print(t(f"  Verarbeite {path.name} ...", f"  Processing {path.name} ..."))
        ins, skip = _import_csv(conn, path, person, args.dry_run)
        total_ins  += ins
        total_skip += skip
        print(t(f"    → {ins} importiert, {skip} bereits vorhanden",
                f"    → {ins} imported, {skip} already present"))
        if not args.dry_run:
            log_import(conn, "import_lab_csv", str(path), ins, skip)

    if not args.dry_run:
        conn.commit()

    print(t(f"\nLabor-CSV-Import: {total_ins} neu, {total_skip} übersprungen",
            f"\nLab CSV import: {total_ins} new, {total_skip} skipped"))


if __name__ == "__main__":
    main()
