#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
backfill_travel_environment_person.py — pollen/biometeo/air_quality: person='unknown' → real pseudonym

@tier        infrastructure
@purpose.de  Setzt historische Zeilen in pollen, biometeo und air_quality, die noch
             den Schema-Default person='unknown' tragen, rückwirkend auf die echte
             Personen-Pseudonym-ID — auf ausdrücklichen Wunsch der Nutzerin, nach
             Abwägung gegen die generelle Ausschlussregel für 'unknown' in
             pseudonymize_device_person_identifiers.py (s. @limits).
@purpose.en  Backfills historical rows in pollen, biometeo and air_quality that
             still carry the schema default person='unknown' to the real person
             pseudonym ID — on the user's explicit request, after weighing it
             against the general exclusion rule for 'unknown' in
             pseudonymize_device_person_identifiers.py (see @limits).
@method.de   import_airquality.py (der alleinige Schreiber dieser drei Tabellen)
             defaultet person bereits korrekt auf OWN_PERSON_ID — die 'unknown'-
             Zeilen sind historisch (Bug längst behoben, seither durchgehend
             korrekt), kein aktiver Code-Bug mehr. Kein PK-Konflikt
             möglich: der Primärschlüssel dieser drei Tabellen ist (date, lat, lon)
             ohne person, ein einfaches UPDATE reicht (anders als z.B.
             rename_kiste_export_source.py, wo person Teil des PK ist und deshalb
             gegen Kollisionen geprüft werden muss).
@method.en   import_airquality.py (the sole writer of these three tables) already
             defaults person to OWN_PERSON_ID correctly — the 'unknown' rows are
             historical (bug fixed long ago, everything since has been
             correct), not an active code bug anymore. No PK conflict possible:
             these three tables' primary key is (date, lat, lon) without person,
             so a plain UPDATE suffices (unlike e.g. rename_kiste_export_source.py,
             where person is part of the PK and collisions must be checked for).
@reads       pollen, biometeo, air_quality (person column)
@writes      pollen, biometeo, air_quality (UPDATE person='unknown' → real pseudonym)
@limits.de   Weicht bewusst von der generellen Regel in
             pseudonymize_device_person_identifiers.py ab, die 'unknown' NICHT
             pseudonymisiert (dortige Begründung: 'unknown' bedeutet "keine Person
             erfasst", nicht "eine bestimmte Person" — eine Umwandlung würde einen
             fehlenden Wert als echte Identität ausgeben). Für DIESE drei Tabellen
             ist die Lage anders: es gab in diesem Projekt bisher ausschließlich
             Daten einer einzigen Person, und die betroffenen Zeilen stammen
             nachweislich aus Aufenthalten/Abrufen für die Nutzerin selbst (nicht
             aus einer geteilten oder unbekannten Quelle) — deshalb hier auf
             ausdrücklichen Wunsch rückwirkend korrigiert. Diese Ausnahme gilt NUR
             für diese drei Tabellen, nicht generell für 'unknown' im Projekt.
             Einmalig gedacht; sicher wiederholt ausführbar (kein Effekt mehr,
             sobald keine 'unknown'-Zeilen mehr existieren).
@limits.en   Deliberately deviates from the general rule in
             pseudonymize_device_person_identifiers.py, which does NOT
             pseudonymize 'unknown' (rationale there: 'unknown' means "no person
             recorded", not "a specific person" — converting it would misrepresent
             a missing value as a real identity). For THESE three tables the
             situation differs: this project has so far only ever held one
             person's data, and the affected rows demonstrably originate from
             stays/fetches for the user herself (not a shared or genuinely
             unknown source) — hence backfilled here on her explicit request.
             This exception applies ONLY to these three tables, not to 'unknown'
             project-wide. Meant to run once; safe to re-run (no-op once no
             'unknown' rows remain).

@relevance.de  Behebt eine historische Datenlücke, die person-gefilterte Abfragen
               (das projektweite Standardmuster) für einen Großteil der
               Umweltdaten-Zeilen unsichtbar machte
@relevance.en  Fixes a historical data gap that made person-filtered queries (the
               project-wide standard pattern) blind to a large share of
               environmental data rows
@usage
    python3 scripts/migrations/backfill_travel_environment_person.py
    python3 migrations/backfill_travel_environment_person.py  # from inside scripts/
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.base import log_import, resolve_person
from modules.db import open_db

TABLES = ("pollen", "biometeo", "air_quality")
SENTINEL = "unknown"


def run(person: str | None = None) -> None:
    target_person = resolve_person(person)
    conn = open_db()
    cursor = conn.cursor()
    total_updated = 0

    for tbl in TABLES:
        before = cursor.execute(
            f"SELECT COUNT(*) FROM {tbl} WHERE person=?", (SENTINEL,)
        ).fetchone()[0]
        if before == 0:
            print(f"  {tbl}: keine '{SENTINEL}'-Zeilen — nichts zu tun")
            continue
        cursor.execute(
            f"UPDATE {tbl} SET person=? WHERE person=?",
            (target_person, SENTINEL),
        )
        total_updated += cursor.rowcount
        print(f"  {tbl}: {cursor.rowcount} von {before} Zeile(n) auf {target_person} migriert")

    log_import(conn, "backfill_travel_environment_person", ",".join(TABLES), total_updated,
              person=target_person)
    conn.commit()
    conn.close()
    print("\n✓ Migration abgeschlossen")


if __name__ == "__main__":
    _ap = argparse.ArgumentParser(description="Backfill person fuer pollen/biometeo/air_quality")
    _ap.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    run(person=_ap.parse_args().person)
