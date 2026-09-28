#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
migrate_health_to_medicine — Migration klinischer Daten von health.db nach medicine.db

@tier        infrastructure
@purpose.de  Migriert klinische Tabellen von der health.db in die spezielle medicine.db.
              Betroffene Tabellen: lab_manual, lab_results, medications und assessments.
              Die Daten bleiben in health.db erhalten (kein Löschen).
@purpose.en  Migrates clinical tables from health.db to the dedicated medicine.db.
              Affected tables: lab_manual, lab_results, medications and assessments.
              Data remains in health.db (no deletion).
@method.de   Verwendet INSERT OR IGNORE für alle Tabellen, um Duplikate zu vermeiden und die Migration wiederholbar zu machen.
              Vor der Migration wird sichergestellt, dass das medicine.db-Schema existiert (Aufruf von create_medicine_schema).
              Unterstützt Dry-Run-Modus (--dry-run) zur Vorschau ohne Schreiboperationen.
              Spalten werden dynamisch aus der Quelltabelle extrahiert.
@method.en   Uses INSERT OR IGNORE for all tables to avoid duplicates and make migration repeatable.
              Before migration, ensures that the medicine.db schema exists (calls create_medicine_schema).
              Supports dry-run mode (--dry-run) for preview without write operations.
              Columns are dynamically extracted from the source table.
@reads       health.db.lab_manual, health.db.lab_results, health.db.medications, health.db.assessments
@writes      medicine.db.lab_manual, medicine.db.lab_results, medicine.db.medications, medicine.db.assessments
@limits.de   Daten werden nicht aus health.db gelöscht - manuelles Löschen nach Verifikation erforderlich.
              Erfordert Zugriff auf beide Datenbanken (health.db und medicine.db).
              Dry-Run-Modus zeigt nur die Anzahl der zu migrierenden Zeilen an, ohne diese zu schreiben.

@relevance.de  Bietet Migrationsfunktionen für Daten, essentiell für die Datenaktualisierung und -umstrukturierung
@relevance.en  Provides data migration functions, essential for data updates and restructuring
@limits.en   Data is not deleted from health.db - manual deletion required after verification.
              Requires access to both databases (health.db and medicine.db).
              Dry-run mode only shows the number of rows to be migrated without writing them.
@usage
    python scripts/utils/migrate_health_to_medicine.py
    python scripts/utils/migrate_health_to_medicine.py --dry-run
    # Vorraussetzung: health.db und medicine.db müssen existieren
    # --dry-run: Zeigt an, welche Daten migriert würden, ohne sie zu schreiben
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.db import open_db, open_medicine_db
from utils.create_medicine_schema import main as ensure_schema, _table_exists

TABLES = ["lab_manual", "lab_results", "medications", "assessments"]


def migrate(dry_run: bool = False) -> None:
    src  = open_db()
    # Schema sicherstellen
    dst  = open_medicine_db()
    if not _table_exists(dst, "lab_manual"):
        dst.close()
        ensure_schema()
        dst = open_medicine_db()

    total = 0
    for table in TABLES:
        if not _table_exists(src, table):
            print(f"  {table}: nicht in health.db vorhanden — übersprungen")
            continue

        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"  {table}: leer — übersprungen")
            continue

        cols = [d[0] for d in src.execute(f"SELECT * FROM {table} LIMIT 0").description]
        placeholders = ", ".join(["?"] * len(cols))
        sql = f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"

        if dry_run:
            print(f"  {table}: würde {len(rows)} Zeilen einfügen (dry-run)")
        else:
            dst.executemany(sql, rows)
            dst.commit()
            print(f"  {table}: {len(rows)} Zeilen migriert → medicine.db")
        total += len(rows)

    src.close()
    dst.close()
    print(f"\nGesamt: {total} Zeilen{'  [dry-run, nichts geschrieben]' if dry_run else ' nach medicine.db migriert'}.")
    if not dry_run:
        print("Daten bleiben in health.db erhalten — nach Verifikation manuell entfernen.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Klinische Tabellen health.db → medicine.db")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts schreiben")
    args = ap.parse_args()
    migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
