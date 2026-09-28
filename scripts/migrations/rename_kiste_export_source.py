#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
rename_kiste_export_source.py — source='kiste_export' → 'symptomtrack_export'

@tier        infrastructure
@purpose.de  Migriert bestehende symptoms-Zeilen von der alten Quellkennung
             ``kiste_export`` (Abkürzung "KiSTe") auf ``symptomtrack_export``,
             nachdem der Importer in ``import_symptomtrack_export.py``
             umbenannt wurde.
@purpose.en  Migrates existing symptoms rows from the old source tag
             ``kiste_export`` (abbreviation "KiSTe") to ``symptomtrack_export``,
             following the importer rename to ``import_symptomtrack_export.py``.
@method.de   Prüft vor dem UPDATE, ob eine Zeile mit gleichem (date, symptom,
             person) bereits unter source='symptomtrack_export' existiert
             (PRIMARY KEY (date, symptom, person, source) würde sonst
             verletzt) — solche Zeilen werden übersprungen und gemeldet statt
             stillschweigend verworfen.
@method.en   Before the UPDATE, checks whether a row with the same (date,
             symptom, person) already exists under source='symptomtrack_export'
             (would otherwise violate PRIMARY KEY (date, symptom, person,
             source)) — such rows are skipped and reported instead of being
             silently dropped.
@reads       symptoms (source)
@writes      symptoms (UPDATE source='kiste_export' → 'symptomtrack_export')
@limits.de   Einmalig gedacht; sicher wiederholt ausführbar (kein Effekt mehr,
             sobald keine kiste_export-Zeilen mehr existieren).

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Meant to run once; safe to re-run (no-op once no kiste_export
             rows remain).
@usage
    python3 scripts/migrations/rename_kiste_export_source.py
    python3 migrations/rename_kiste_export_source.py  # from inside scripts/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.base import log_import
from modules.db import open_db

OLD_SOURCE = "kiste_export"
NEW_SOURCE = "symptomtrack_export"


def run():
    conn = open_db()
    cursor = conn.cursor()

    collisions = cursor.execute(
        """
        SELECT a.date, a.symptom, a.person FROM symptoms a
        JOIN symptoms b ON a.date=b.date AND a.symptom=b.symptom AND a.person=b.person
        WHERE a.source=? AND b.source=?
        """,
        (OLD_SOURCE, NEW_SOURCE),
    ).fetchall()

    if collisions:
        print(f"  ⚠ {len(collisions)} Zeile(n) übersprungen (Konflikt mit bestehendem "
              f"'{NEW_SOURCE}'-Eintrag am selben Tag): {collisions}")

    cursor.execute(
        """
        UPDATE symptoms SET source=?
        WHERE source=?
          AND NOT EXISTS (
              SELECT 1 FROM symptoms b
              WHERE b.date=symptoms.date AND b.symptom=symptoms.symptom
                AND b.person=symptoms.person AND b.source=?
          )
        """,
        (NEW_SOURCE, OLD_SOURCE, NEW_SOURCE),
    )
    print(f"  → {cursor.rowcount} Zeile(n) von '{OLD_SOURCE}' auf '{NEW_SOURCE}' migriert")
    # person=None explizit: benennt einen Quellen-Tag um, unabhaengig davon,
    # welcher Person die betroffenen symptoms-Zeilen gehoeren — kein Einzelziel.
    log_import(conn, "rename_kiste_export_source", "symptoms", cursor.rowcount,
              len(collisions), person=None)
    conn.commit()
    conn.close()
    print("\n✓ Migration abgeschlossen")


if __name__ == "__main__":
    run()
