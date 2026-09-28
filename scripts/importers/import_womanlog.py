#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
WomanLog CSV → health.db

@tier        infrastructure
@purpose.de  Importiert Zyklus- und Gesundheitsdaten aus WomanLog CSV-Exporten
             in die health.db. Unterstützt Menstruationsbeginn, Eisprung, Symptome
             und Gewicht.
@purpose.en  Imports cycle and health data from WomanLog CSV exports into health.db.
             Supports menstruation start, ovulation, symptoms, and weight.
@method.de   Liest CSV-Dateien aus imports/WomanLogApp/ (Muster: womanlog*.csv).
             Format: Datum, Typ, Wert, Einheit. Mapping: Start period →
             reproductive_health (period_start, cycle_length), Ovulation →
             reproductive_health (ovulation), Symptom → symptoms, Weight →
             measurements (body_weight).
@method.en   Reads CSV files from imports/WomanLogApp/ (pattern: womanlog*.csv).
             Format: Date, Type, Value, Unit. Mapping: Start period →
             reproductive_health (period_start, cycle_length), Ovulation →
             reproductive_health (ovulation), Symptom → symptoms, Weight →
             measurements (body_weight).
@reads       {imports/WomanLogApp/}/womanlog*.csv (WomanLog Export)
@writes      health.db (reproductive_health, symptoms, measurements)
@limits.de   Keine Validierung der WomanLog-Datenqualität. Abhängig von der
             Korrektheit des CSV-Exports. Keine medizinische Diagnose.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   No validation of WomanLog data quality. Dependent on the correctness
             of the CSV export. No medical diagnosis.
@usage
    python import_womanlog.py
    python import_womanlog.py --rebuild
"""

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person

_cfg = _Cfg()
DB_PATH  = _cfg.db_path
CSV_PATH = _cfg.data_root / "WomanLogApp"
CSV_PATH.mkdir(parents=True, exist_ok=True)


def find_csv() -> Path | None:
    candidates = sorted(CSV_PATH.glob("womanlog*.csv"), reverse=True)
    return candidates[0] if candidates else None


def import_csv(conn: sqlite3.Connection, csv_path: Path, person: str | None = None) -> dict:
    person = resolve_person(person)
    counts = {"cycles": 0, "symptoms": 0, "ovulation": 0, "weight": 0, "skipped": 0}

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date  = row.get("Date", "").strip()
            rtype = row.get("Type", "").strip()
            value = row.get("Value", "").strip()

            if not date or not rtype:
                counts["skipped"] += 1
                continue

            if rtype == "Start period":
                duration = int(value) if value.isdigit() else None
                conn.execute(
                    "INSERT OR IGNORE INTO reproductive_health"
                    "(date, event_type, value_num, value_text, person, source) "
                    "VALUES (?, 'period_start', NULL, NULL, ?, 'womanlog')",
                    (date, person)
                )
                if duration is not None:
                    conn.execute(
                        "INSERT OR IGNORE INTO reproductive_health"
                        "(date, event_type, value_num, value_text, person, source) "
                        "VALUES (?, 'cycle_length', ?, NULL, ?, 'womanlog')",
                        (date, float(duration), person)
                    )
                counts["cycles"] += 1

            elif rtype == "Symptom":
                conn.execute(
                    "INSERT OR IGNORE INTO symptoms"
                    "(date, symptom, value_num, value_text, category, person, source) "
                    "VALUES (?, ?, NULL, NULL, 'womanlog', ?, 'womanlog')",
                    (date, value, person)
                )
                counts["symptoms"] += 1

            elif rtype == "Ovulation":
                conn.execute(
                    "INSERT OR IGNORE INTO reproductive_health"
                    "(date, event_type, value_num, value_text, person, source) "
                    "VALUES (?, 'ovulation', NULL, NULL, ?, 'womanlog')",
                    (date, person)
                )
                counts["ovulation"] += 1

            elif rtype == "Weight":
                unit = row.get("Unit", "").strip() or "kg"
                try:
                    kg = float(value)
                except ValueError:
                    counts["skipped"] += 1
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO measurements"
                    "(ts, metric, value, unit, device_id, person, source_app) "
                    "VALUES (?, 'body_weight', ?, ?, 'womanlog', ?, 'womanlog')",
                    (date + "T00:00:00+00:00", kg, unit, person)
                )
                counts["weight"] += 1

            else:
                counts["skipped"] += 1

    log_import(conn, 'womanlog', str(csv_path),
               counts['cycles'] + counts['symptoms'] + counts['ovulation'] + counts['weight'],
               counts['skipped'], person=person)
    conn.commit()
    return counts


def main():
    """
    Hauptfunktion: Koordiniert den Import der WomanLog-Daten.

    Command-Line-Argumente:
        --rebuild: WomanLog-Daten leeren und neu aufbauen
        --file: Expliziter CSV-Pfad
        --update: Nur neue Daten
        --from/to: Ignoriert
    """
    parser = argparse.ArgumentParser(description="WomanLog Pro CSV → health.db")
    parser.add_argument("--rebuild", action="store_true",
                        help="Womanlog-Daten leeren und neu aufbauen")
    parser.add_argument("--file",    metavar="PATH")
    parser.add_argument("--update",  action="store_true", help="Nur neue Daten (No-op, Duplikate via PRIMARY KEY verhindert)")
    parser.add_argument("--from",    dest="date_from", metavar="DATE", help="Ignoriert")
    parser.add_argument("--to",      dest="date_to",   metavar="DATE", help="Ignoriert")
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    csv_path = Path(args.file) if args.file else find_csv()
    if not csv_path or not csv_path.exists():
        print(t(f"Keine WomanLog-CSV gefunden in {CSV_PATH} — übersprungen.",
                f"No WomanLog CSV found in {CSV_PATH} — skipped."))
        sys.exit(0)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")

    if args.rebuild:
        conn.execute("DELETE FROM reproductive_health WHERE source='womanlog'")
        conn.execute("DELETE FROM symptoms WHERE source='womanlog'")
        conn.commit()
        print(t("WomanLog-Daten geleert — vollständiger Neuaufbau.",
                "WomanLog data cleared — full rebuild."))

    print(t(f"Importiere: {csv_path.name}", f"Importing: {csv_path.name}"))
    counts = import_csv(conn, csv_path, person)

    print(t(f"  Periodenstart:  {counts['cycles']:4d}", f"  Period start:   {counts['cycles']:4d}"))
    print(t(f"  Symptome:       {counts['symptoms']:4d}", f"  Symptoms:       {counts['symptoms']:4d}"))
    print(t(f"  Ovulation:      {counts['ovulation']:4d}", f"  Ovulation:      {counts['ovulation']:4d}"))
    print(t(f"  Gewicht:        {counts['weight']:4d}", f"  Weight:         {counts['weight']:4d}"))
    if counts["skipped"]:
        print(t(f"  Übersprungen:   {counts['skipped']:4d}", f"  Skipped:        {counts['skipped']:4d}"))

    r = conn.execute(
        "SELECT MIN(date), MAX(date) FROM reproductive_health WHERE source='womanlog' AND event_type='period_start'"
    ).fetchone()
    print(t(f"\nZeitraum Zyklen: {r[0]} → {r[1]}", f"\nCycle range: {r[0]} → {r[1]}"))
    conn.close()


if __name__ == "__main__":
    main()
