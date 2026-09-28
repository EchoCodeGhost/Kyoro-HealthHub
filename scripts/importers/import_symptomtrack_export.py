#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Kyoro SymptomTrack JSON-Export → health.db (symptoms)

@tier        infrastructure
@purpose.de  Importiert Kyoro SymptomTrack-JSON-Exporte (GET /api/export) in die gemeinsame
             symptoms-Tabelle. Ermöglicht Symptom-Daten von einem zweiten Gerät
             (z.B. Familienmitglied) mit einer separaten --person-ID einzuspielen,
             ohne das Kyoro SymptomTrack-Backend zu verändern.
@purpose.en  Imports Kyoro SymptomTrack JSON exports (GET /api/export) into the shared symptoms
             table. Allows symptom data from a second device (e.g. family member)
             to be ingested under a separate --person ID, without modifying the
             Kyoro SymptomTrack backend.
@method.de   Liest symptomtrack_export_*.json Dateien (Feld symptom_entries[]). Felder:
             id, timestamp (ISO 8601), symptom, kategorie, wert_num, wert_text,
             note, source. Schreibt in symptoms mit source='symptomtrack_export'
             (INSERT OR IGNORE auf PRIMARY KEY (date, symptom, person, source)).
             Migräne- und AFib-Einträge (migraine_entries, afib_entries) sind
             Kyoro SymptomTrack-interne Sondertabellen ohne Entsprechung in health.db und
             werden übersprungen.
@method.en   Reads symptomtrack_export_*.json files (field symptom_entries[]). Fields:
             id, timestamp (ISO 8601), symptom, kategorie, wert_num, wert_text,
             note, source. Writes to symptoms with source='symptomtrack_export'
             (INSERT OR IGNORE on PRIMARY KEY (date, symptom, person, source)).
             Migraine and AFib entries (migraine_entries, afib_entries) are
             Kyoro SymptomTrack-internal specialist tables with no equivalent in health.db and
             are skipped.
@reads       symptomtrack_export_YYYY-MM-DD.json (Kyoro SymptomTrack /api/export output)
@writes      symptoms
@limits.de   Kein Re-Import von Migräne/AFib-Episoden. Nur tagesweise Deduplizierung
             per PRIMARY KEY — mehrere Einträge desselben Symptoms am selben Tag
             werden übersprungen nach dem ersten INSERT.

@relevance.de  Ermöglicht den Import von Symptomdaten, essentiell für die klinische Analyse
@relevance.en  Enables import of symptom data, essential for clinical analysis
@limits.en   No re-import of migraine/AFib episodes. Day-level deduplication only
             via PRIMARY KEY — multiple entries for the same symptom on the same day
             are skipped after the first INSERT.
@usage
    python3 import_symptomtrack_export.py symptomtrack_export_2026-07-08.json
    python3 import_symptomtrack_export.py symptomtrack_export.json --person oma
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.base import ImportResult, log_import, resolve_person
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

SOURCE = "symptomtrack_export"


def _extend_symptoms(conn) -> None:
    """Adds ts and notes columns to symptoms if not yet present."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(symptoms)").fetchall()}
    for col, typedef in [("ts", "TEXT"), ("notes", "TEXT")]:
        if col not in existing:
            conn.execute(f"ALTER TABLE symptoms ADD COLUMN {col} {typedef}")
    conn.commit()


def run(conn, data_path: str | Path, lang: str = "de", person: str | None = None) -> ImportResult:
    """
    Import Kyoro SymptomTrack JSON export into the symptoms table.

    Args:
        conn: Open SQLite connection to health.db
        data_path: Path to symptomtrack_export_*.json
        lang: Display language ('de' or 'en')
        person: Person ID; falls back to OWN_PERSON_ID if None

    Returns:
        ImportResult with rows_inserted / rows_skipped counts
    """
    result = ImportResult(source=SOURCE)
    person_id = resolve_person(person)
    path = Path(data_path)

    if not path.exists():
        result.errors.append(t(f"Datei nicht gefunden: {path}", f"File not found: {path}"))
        return result

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        result.errors.append(str(exc))
        return result

    entries = data.get("symptom_entries", [])
    if not isinstance(entries, list):
        result.errors.append(t("symptom_entries ist keine Liste", "symptom_entries is not a list"))
        return result

    _extend_symptoms(conn)

    for e in entries:
        ts = e.get("timestamp") or ""
        date = ts[:10] if len(ts) >= 10 else e.get("date", "")
        symptom = e.get("symptom") or e.get("symptomId", "")
        if not date or not symptom:
            result.rows_skipped += 1
            continue
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO symptoms
                    (date, symptom, value_num, value_text, category, person, source, ts, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    date,
                    symptom,
                    e.get("wert_num"),
                    e.get("wert_text"),
                    e.get("kategorie"),
                    person_id,
                    SOURCE,
                    ts or None,
                    e.get("note"),
                ),
            )
            if conn.execute("SELECT changes()").fetchone()[0]:
                result.rows_inserted += 1
            else:
                result.rows_skipped += 1
        except Exception as exc:
            result.errors.append(str(exc))
            result.rows_skipped += 1

    log_import(conn, SOURCE, str(path.name), result.rows_inserted, result.rows_skipped)
    conn.commit()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t(
            "Kyoro SymptomTrack JSON-Export → health.db importieren",
            "Import Kyoro SymptomTrack JSON export → health.db",
        )
    )
    add_lang_arg(parser)
    parser.add_argument("file", help=t("Pfad zur JSON-Exportdatei", "Path to JSON export file"))
    parser.add_argument(
        "--person",
        default=None,
        help=t("Person-ID (Standard: OWN_PERSON_ID)", "Person ID (default: OWN_PERSON_ID)"),
    )
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    try:
        result = run(conn, args.file, lang=args.lang, person=args.person)
        print(t(
            f"{result.rows_inserted} Einträge importiert, {result.rows_skipped} übersprungen",
            f"{result.rows_inserted} entries imported, {result.rows_skipped} skipped",
        ))
        for err in result.errors:
            print(t(f"Fehler: {err}", f"Error: {err}"), file=sys.stderr)
        if result.errors:
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
