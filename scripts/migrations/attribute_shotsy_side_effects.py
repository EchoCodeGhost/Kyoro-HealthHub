#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
attribute_shotsy_side_effects.py — Backfills medication attribution for
already-imported Shotsy side effects

@tier        infrastructure
@purpose.de  Wendet import_shotsy.py::attribute_side_effects_to_medication()
             nachträglich auf bereits importierte symptoms-Zeilen (source='shotsy')
             an — die Importer-Änderung greift nur für künftige Läufe.
@purpose.en  Retroactively applies import_shotsy.py::
             attribute_side_effects_to_medication() to already-imported symptoms
             rows (source='shotsy') — the importer change only affects future runs.
@method.de   Ruft dieselbe Funktion wie der Importer auf: symptoms.value_text
             wird auf den Namen der zeitlich zuletzt vorangegangenen (oder
             gleichtägigen) Shotsy-Injektion gesetzt, wo noch NULL. Best-effort,
             keine exakte Kausalität — s. Docstring der Funktion.
@method.en   Calls the same function the importer uses: symptoms.value_text is
             set to the name of the most recent preceding (or same-day) Shotsy
             injection, where still NULL. Best-effort, not exact causality — see
             the function's docstring.
@reads       health.db (symptoms, medications)
@writes      health.db (symptoms.value_text für source='shotsy')
@relevance.de  Macht sichtbar, welches Medikament wahrscheinlich fuer eine
               geloggte Nebenwirkung verantwortlich war — direkt genutzt in
               compute_pem.py::alt_explanation_hint
@relevance.en  Surfaces which medication was likely responsible for a logged
               side effect — used directly by
               compute_pem.py::alt_explanation_hint
@limits.de   Betrifft nur symptoms mit source='shotsy'. compute_pem.py sollte
             danach neu berechnet werden, falls alt_explanation_hint genutzt wird.
@limits.en   Only affects symptoms with source='shotsy'. compute_pem.py should be
             recomputed afterwards if alt_explanation_hint is used.
@usage
    python3 scripts/migrations/attribute_shotsy_side_effects.py --dry-run
    python3 scripts/migrations/attribute_shotsy_side_effects.py

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
from importers.import_shotsy import attribute_side_effects_to_medication  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Traegt Medikamenten-Zuordnung fuer bereits importierte Shotsy-Nebenwirkungen nach")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    args = ap.parse_args()

    try:
        conn = open_db()
    except Exception as exc:
        print(f"Fehler beim Öffnen der Datenbank: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        rows = conn.execute("""
            SELECT date, symptom FROM symptoms
            WHERE source='shotsy' AND person=? AND value_text IS NULL
        """, (OWN_PERSON_ID,)).fetchall()
        print(f"Würde {len(rows)} Nebenwirkungs-Zeile(n) zuordnen:")
        for date, symptom in rows:
            print(f"  {date}  {symptom}")
        sys.exit(0)

    cur = conn.cursor()
    n = attribute_side_effects_to_medication(cur, OWN_PERSON_ID)
    if n:
        log_import(conn, "attribute_shotsy_side_effects", "symptoms", n)
    conn.commit()
    print(f"{n} Nebenwirkungs-Zeile(n) mit Medikamentenname verknüpft.")
    conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
