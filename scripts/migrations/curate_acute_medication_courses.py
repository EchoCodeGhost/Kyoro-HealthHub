#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
curate_acute_medication_courses.py — Markiert bekannte Akutkuren als is_chronic=0

@tier        infrastructure
@purpose.de  Setzt ``is_chronic=0`` für eine manuell kuratierte Liste bekannter
             einmaliger Akutkuren (z.B. Antibiotika), damit sie in Auswertungen
             von laufender Dauermedikation unterschieden werden. Die Spalte
             ``is_chronic`` selbst wird von ``create_medicine_schema.py``
             angelegt/nachmigriert — dieses Skript kuratiert nur Daten, keine
             Struktur.
@purpose.en  Sets ``is_chronic=0`` for a manually curated list of known one-off
             acute courses (e.g. antibiotics) so analyses can distinguish them
             from ongoing long-term medication. The ``is_chronic`` column itself
             is created/migrated by ``create_medicine_schema.py`` — this script
             only curates data, not structure.
@method.de   Reine ``UPDATE``-Anweisungen gegen ``ACUTE_COURSES`` (Liste aus
             (drug_name, date)-Paaren); setzt is_chronic=0 nur für exakt
             passende (person, drug_name, date)-Zeilen. Kein DDL.
@method.en   Plain ``UPDATE`` statements against ``ACUTE_COURSES`` (list of
             (drug_name, date) pairs); sets is_chronic=0 only for exactly
             matching (person, drug_name, date) rows. No DDL.
@reads       medications (drug_name, date, person)
@writes      medications (UPDATE is_chronic=0 for entries in ACUTE_COURSES)
@limits.de   Manuell kuratierte Liste — neue Akutkuren
             müssen künftig beim Import direkt mit ``is_chronic=0`` versehen
             werden, statt hier ergänzt zu werden. Wiederholtes Ausführen ist
             sicher (WHERE-Klausel ist exakt, keine Breitenwirkung).

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Manually curated list — future acute courses
             should be imported with ``is_chronic=0`` directly rather than
             added here. Safe to re-run (WHERE clause is exact, no blast
             radius beyond the listed rows).
@usage
    python3 scripts/migrations/curate_acute_medication_courses.py
    python3 migrations/curate_acute_medication_courses.py  # from inside scripts/
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.base import log_import, resolve_person
from modules.db import open_medicine_db

# (drug_name, date) Paare bekannter einmaliger Akutkuren — manuell kuratiert.
ACUTE_COURSES = [
    ("Ciprofloxacin", "2015-04-05"),
    ("Cefuroxim", "2017-10-02"),
    ("Ampicillin/Sulbactam", "2017-10-28"),
    ("Clarithromycin", "2017-10-28"),
    ("Doxycyclin", "2020-11-25"),
]


def run(person: str | None = None):
    target_person = resolve_person(person)
    conn = open_medicine_db()
    cursor = conn.cursor()
    total_updated = 0

    for drug_name, dt in ACUTE_COURSES:
        cursor.execute(
            "UPDATE medications SET is_chronic=0 WHERE person=? AND drug_name=? AND date=?",
            (target_person, drug_name, dt),
        )
        if cursor.rowcount:
            total_updated += cursor.rowcount
            print(f"  → {drug_name} ({dt}) als Akutkur markiert (is_chronic=0)")

    log_import(conn, "curate_acute_medication_courses", "medications", total_updated,
              person=target_person)
    conn.commit()

    conn.close()
    print("\n✓ Kuratierung abgeschlossen")


if __name__ == "__main__":
    _ap = argparse.ArgumentParser(description="Markiert bekannte Akutkuren als is_chronic=0")
    _ap.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    run(person=_ap.parse_args().person)
