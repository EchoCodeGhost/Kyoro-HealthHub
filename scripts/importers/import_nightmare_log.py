#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
import_nightmare_log.py — Kyoro-SleepGuard Nightmare-Log importieren

@tier        infrastructure
@purpose.de  Importiert manuell abgelesene Alptraum-Alarme der Kyoro-SleepGuard-App aus CSV in die Datenbank.
@purpose.en  Imports manually transcribed nightmare alarms from the Kyoro SleepGuard app via CSV into the database.
@method.de   Liest CSV (Template: templates/nightmare_log_template.csv); schreibt nightmare_hr und nightmare_baseline in measurements sowie nightmare_alarm in symptoms.
@method.en   Reads CSV (template: templates/nightmare_log_template.csv); writes nightmare_hr and nightmare_baseline into measurements, and nightmare_alarm into symptoms.
@reads       CSV-Datei (Template: templates/nightmare_log_template.csv)
@writes      measurements (nightmare_hr, nightmare_baseline), symptoms (nightmare_alarm), import_log
@limits.de   Manuelle Dateneingabe — Zeitstempel müssen vom Uhrendisplay (nmLogTs) abgelesen und korrekt in UTC übertragen werden. Freitext-Notizen aus der CSV werden nicht gespeichert (kein notes-Feld in symptoms).
             run() reichte person schon vorher korrekt durch (resolve_person());
             das CLI-Skript rief run() aber ohne --person-Option auf — jetzt ergaenzt.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Manual data entry — timestamps must be read from the watch display (nmLogTs) and correctly transcribed as UTC. Free-text notes from the CSV are not persisted (symptoms table has no notes field).
             run() already threaded person through correctly (resolve_person());
             the CLI script called run() with no --person option — now added.
@usage
    python3 scripts/importers/import_nightmare_log.py nightmare_events.csv
    python3 scripts/importers/import_nightmare_log.py templates/nightmare_log_template.csv
    python3 scripts/importers/import_nightmare_log.py events.csv --person PER-xxxxxxxx

Eingabe: CSV mit Spalten ts_utc, hr_bpm, baseline_bpm[, notes]
(Template: templates/nightmare_log_template.csv)

Schreibt in:
  measurements  metric='nightmare_hr'       value=HR in bpm
  measurements  metric='nightmare_baseline' value=Baseline in bpm
  symptoms      symptom='nightmare_alarm'   value=HR in bpm (für Symptom-Korrelation)
"""

import csv
import sys
from datetime import timezone
from pathlib import Path
from dateutil import parser as dtparser

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.base import ImportResult, resolve_person, resolve_timezone, log_import


def run(conn, data_path, lang="de", person=None) -> ImportResult:
    person = resolve_person(person)
    path = Path(data_path)
    if not path.exists():
        return ImportResult(source="nightmare_log", rows_inserted=0,
                            errors=[f"Datei nicht gefunden: {path}"])

    inserted = 0
    errors = []

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(row for row in fh if not row.startswith("#"))
        for lineno, row in enumerate(reader, start=2):
            try:
                ts_raw = row["ts_utc"].strip()
                hr = float(row["hr_bpm"].strip())
                base = float(row["baseline_bpm"].strip())

                dt = dtparser.parse(ts_raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                ts = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                date = dt.astimezone(timezone.utc).strftime("%Y-%m-%d")

                for metric, value in [
                    ("nightmare_hr",       hr),
                    ("nightmare_baseline", base),
                ]:
                    conn.execute(
                        """INSERT OR IGNORE INTO measurements
                           (ts, date, metric, value, person, source_app)
                           VALUES (?, ?, ?, ?, ?, 'nightmare_log')""",
                        (ts, date, metric, value, person),
                    )

                conn.execute(
                    """INSERT OR IGNORE INTO symptoms
                       (date, symptom, value_num, person, source)
                       VALUES (?, 'nightmare_alarm', ?, ?, 'nightmare_log')""",
                    (date, hr, person),
                )
                inserted += 1

            except Exception as exc:
                errors.append(f"Zeile {lineno}: {exc}")

    log_import(conn, source="nightmare_log", data_path=str(path),
              rows_inserted=inserted, rows_skipped=len(errors))
    conn.commit()
    return ImportResult(source="nightmare_log", rows_inserted=inserted, errors=errors)


if __name__ == "__main__":
    import argparse
    from health_config import Config
    from modules.db import open_db

    ap = argparse.ArgumentParser(description="Kyoro-SleepGuard Nightmare-Log importieren")
    ap.add_argument("csv_file", metavar="nightmare_log.csv")
    ap.add_argument("--person", default=None, metavar="PERSON_ID",
                    help="Person-ID (Standard: eigene Person aus Config)")
    args = ap.parse_args()

    with open_db() as db:
        result = run(db, args.csv_file, person=args.person)
    print(f"Importiert: {result.rows_inserted} Einträge")
    if result.errors:
        for e in result.errors:
            print(f"  FEHLER: {e}", file=sys.stderr)
