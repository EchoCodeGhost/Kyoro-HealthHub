#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
fix_persons_stale_pseudonym.py — Renames the stale pre-migration person_id
in the persons reference table

@tier        infrastructure
@purpose.de  Die frühere Pseudonymisierung (P-XXXXXXXX -> PER-XXXXXXXX, s.
             docs/PRIVACY_ARCHITECTURE.md) migrierte alle person-Spalten in
             Datentabellen, liess aber die persons-Referenztabelle selbst
             unangetastet -- ihre Primaerschluessel-Zeile trug weiterhin die
             alte ID, waehrend OWN_PERSON_ID im Code laengst auf die neue
             zeigte. Frueher unauffaellig, weil mehrere Importer person=None
             loggten (NULL umgeht FOREIGN-KEY-Pruefungen); seit der
             Importer-Person-Parametrisierung (PR#13) uebergeben sie eine
             aufgeloeste, nicht-NULL Person-ID und deckten die Luecke als
             "FOREIGN KEY constraint failed" beim Logging auf.
@purpose.en  The earlier pseudonymization pass (P-XXXXXXXX -> PER-XXXXXXXX,
             see docs/PRIVACY_ARCHITECTURE.md) migrated every person column
             in data tables, but left the persons reference table itself
             untouched -- its primary-key row still carried the old ID,
             while OWN_PERSON_ID in code had long since pointed at the new
             one. Previously invisible because several importers logged
             person=None (NULL bypasses FOREIGN KEY checks); since the
             importer person parameterization (PR#13) they pass a resolved,
             non-NULL person ID and surfaced the gap as a "FOREIGN KEY
             constraint failed" during logging.
@method.de   UPDATE persons SET person_id=OWN_PERSON_ID WHERE person_id=
             'P-F83C73A3' -- reine Umbenennung der Primaerschluessel-Zeile,
             alle anderen Spalten (Zeitzone, active, ...) bleiben
             unveraendert. Idempotent (WHERE-Klausel greift nur einmal).
@method.en   UPDATE persons SET person_id=OWN_PERSON_ID WHERE person_id=
             'P-F83C73A3' -- pure rename of the primary-key row, all other
             columns (timezone, active, ...) stay unchanged. Idempotent
             (WHERE clause only matches once).
@reads       health.db (persons)
@writes      health.db (persons.person_id)
@limits.de   Betrifft nur die eine bekannte alte ID 'P-F83C73A3'. Falls
             weitere alte ID-Formate existieren sollten, waeren die separat
             zu pruefen.
@limits.en   Only handles the one known old ID 'P-F83C73A3'. If further old
             ID formats exist, they would need separate review.

@relevance.de  Behebt eine strukturelle Luecke in der Personen-Referenztabelle, die stille Foreign-Key-Fehler beim Import-Logging verursachte
@relevance.en  Fixes a structural gap in the person reference table that caused silent foreign-key failures during import logging
@usage
    python3 scripts/migrations/fix_persons_stale_pseudonym.py --dry-run
    python3 scripts/migrations/fix_persons_stale_pseudonym.py

Exit Codes:
    0: Lauf erfolgreich (auch wenn nichts zu tun war)
    1: Fehler beim Datenbankzugriff
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from health_config import OWN_PERSON_ID  # noqa: E402
from modules.base import log_import  # noqa: E402
from modules.db import open_db  # noqa: E402

STALE_PERSON_ID = "P-F83C73A3"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Benennt die veraltete person_id-Zeile in persons auf OWN_PERSON_ID um")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    args = ap.parse_args()

    try:
        conn = open_db()
    except Exception as exc:
        print(f"Fehler beim Öffnen der Datenbank: {exc}", file=sys.stderr)
        sys.exit(1)

    row = conn.execute(
        "SELECT person_id FROM persons WHERE person_id = ?", (STALE_PERSON_ID,)
    ).fetchone()
    n = 1 if row else 0

    if args.dry_run:
        if n:
            print(f"Würde 1 Zeile umbenennen ({STALE_PERSON_ID} → {OWN_PERSON_ID}).")
        else:
            print(f"Nichts zu tun — keine Zeile mit person_id={STALE_PERSON_ID} gefunden.")
        conn.close()
        sys.exit(0)

    if n:
        conn.execute(
            "UPDATE persons SET person_id = ? WHERE person_id = ?",
            (OWN_PERSON_ID, STALE_PERSON_ID),
        )
        log_import(conn, "fix_persons_stale_pseudonym", "persons", n)
    conn.commit()
    print(f"{n} Zeile(n) umbenannt ({STALE_PERSON_ID} → {OWN_PERSON_ID}).")
    conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
