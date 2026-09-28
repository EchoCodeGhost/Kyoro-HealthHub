#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
generate_pseudonyms_for_existing_data.py — Pseudonyme für bestehende Daten generieren

@tier        infrastructure
@purpose.de  Durchsucht health.db und medicine.db nach allen eindeutigen Geräte- und
             Personen-Identifikatoren und generiert deterministische Pseudonyme dafür
             mithilfe des identity_resolver-Moduls. Reiner Backfill-Schritt (Aufgabe
             4.2) — die eigentliche Datenmigration (Aufgabe 4.3,
             pseudonymize_device_person_identifiers.py) legt beim Auflösen ohnehin
             automatisch neue identity.db-Einträge an; dieses Skript erlaubt es,
             die Pseudonyme VOR der Migration einzusehen (z.B. für einen Report).
@purpose.en  Scans health.db and medicine.db for all unique device and person
             identifiers and generates deterministic pseudonyms for them using the
             identity_resolver module. Pure backfill step (task 4.2) — the actual
             data migration (task 4.3, pseudonymize_device_person_identifiers.py)
             creates new identity.db entries automatically as a side effect of
             resolving anyway; this script lets you inspect the pseudonyms BEFORE
             migration (e.g. for a report).
@method.de   1. Liest alle eindeutigen Werte aus den Zielspalten — pro Spaltenname
             bekannt (device_id/device → Gerät, person → Person), KEINE Heuristik
             auf den Wert selbst (eine frühere Version riet anhand von Substrings
             wie 'polar'/'apple' im Wert, ob es ein Gerät oder eine Person ist —
             das kann bei unbekannten Gerätenamen falsch pseudonymisieren, ohne
             dass es auffällt).
             2. Generiert Pseudonyme mit resolve_device() / resolve_person().
             3. Speichert die Zuordnungen in identity.db (Seiteneffekt von resolve()).
@method.en   1. Reads all unique values from target columns — known per column name
             (device_id/device → device, person → person), NO heuristic on the
             value itself (an earlier version guessed device vs. person from
             substrings like 'polar'/'apple' in the value — that can silently
             mispseudonymize an unfamiliar device name).
             2. Generates pseudonyms with resolve_device() / resolve_person().
             3. Stores mappings in identity.db (side effect of resolve()).
@reads       health.db, medicine.db (über Config-Pfad, alle Tabellen mit
             device_id/device/person-Spalten)
@writes      ~/.config/kyoro/identity.db (device_id_map, person_map Tabellen)
@limits.de   Nur semantische Werte werden pseudonymisiert; bereits vorhandene
             Pseudonyme (DEV-*, PER-*) werden ignoriert.

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Only semantic values are pseudonymized; existing pseudonyms (DEV-*, PER-*)
             are ignored.
@usage
    python3 scripts/migrations/generate_pseudonyms_for_existing_data.py
    python3 migrations/generate_pseudonyms_for_existing_data.py  # from inside scripts/
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.db import open_db, open_medicine_db
from modules.identity_resolver import resolve_device, resolve_person

# column name -> ("device" | "person", resolver)
HEALTH_DB_TABLES: Dict[str, List[str]] = {
    "devices": ["device_id"],
    "measurements": ["device_id", "person"],
    "ppi_raw": ["device", "person"],
    "blood_pressure": ["person"],
    "heart_rate": ["person"],
    "ecg_sessions": ["person"],
    "sleep_sessions": ["person"],
    "activity_sessions": ["person"],
    "nutrition_entries": ["person"],
    "symptoms": ["person"],
    "medication_intake": ["person"],
}

MEDICINE_DB_TABLES: Dict[str, List[str]] = {
    "clinical_events": ["person"],
    "medication_history": ["person"],
    "lab_results": ["person"],
    "diagnoses": ["person"],
    "allergies": ["person"],
}


def scan_database(conn, tables_and_columns: Dict[str, List[str]]) -> Dict[str, Tuple[str, str]]:
    """Return {real_value: (column_kind, table.column)} — column_kind is
    'device' for device_id/device columns, 'person' for person columns."""
    found: Dict[str, Tuple[str, str]] = {}
    cursor = conn.cursor()

    for table, columns in tables_and_columns.items():
        exists = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue

        table_columns = [row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()]

        for column in columns:
            if column not in table_columns:
                continue
            kind = "person" if column == "person" else "device"
            for (value,) in cursor.execute(
                f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL"
            ).fetchall():
                if isinstance(value, str) and value.strip() and not value.startswith(("DEV-", "PER-")):
                    found[value] = (kind, f"{table}.{column}")

    return found


def main():
    print("=== Generating Pseudonyms for Existing Data ===\n")

    print("Scanning health.db for unique identifiers...")
    health_conn = open_db()
    try:
        health_values = scan_database(health_conn, HEALTH_DB_TABLES)
    finally:
        health_conn.close()

    print("Scanning medicine.db for unique identifiers...")
    medicine_conn = open_medicine_db()
    try:
        medicine_values = scan_database(medicine_conn, MEDICINE_DB_TABLES)
    finally:
        medicine_conn.close()

    all_values: Dict[str, Tuple[str, str]] = {**health_values, **medicine_values}
    print(f"\nFound {len(all_values)} unique identifiers to pseudonymize:")

    device_mappings = {}
    person_mappings = {}
    for value, (kind, origin) in sorted(all_values.items(), key=lambda kv: kv[0]):
        if kind == "device":
            pseudo = resolve_device(value)
            device_mappings[value] = pseudo
        else:
            pseudo = resolve_person(value)
            person_mappings[value] = pseudo
        print(f"  {origin}: {value!r} -> {pseudo}")

    print(f"\n=== Summary ===")
    print(f"Total unique identifiers processed: {len(all_values)}")
    print(f"Device pseudonyms generated: {len(device_mappings)}")
    print(f"Person pseudonyms generated: {len(person_mappings)}")
    print(f"\nPseudonyms have been stored in ~/.config/kyoro/identity.db")
    print(f"You can inspect them with: sqlite3 ~/.config/kyoro/identity.db")

    return device_mappings, person_mappings


if __name__ == "__main__":
    main()
