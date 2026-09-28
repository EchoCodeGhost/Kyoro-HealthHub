#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
rename_ecowitt_source_tag.py — Renames weather_station.source
'ecowitt_gw3000a' to the brand-only 'ecowitt'

@tier        infrastructure
@purpose.de  import_homeassistant.py taggte Ecowitt-Wetterstationsdaten mit
             dem exakten Gateway-Modellnamen ('ecowitt_gw3000a') statt nur
             der Marke. Anders als bei Geraeteklassen-Tags, die fuer die
             Kalibrierungslogik technisch gebraucht werden (z.B.
             polar_h10/polar_v3), ist das exakte Wetterstations-Gateway-
             Modell fuer nichts im Code funktional relevant — nur die Marke
             zaehlt. Der Importer verwendet jetzt 'ecowitt', diese Migration
             zieht bereits importierte Datenbanken nach.
@purpose.en  import_homeassistant.py tagged Ecowitt weather station data
             with the exact gateway model name ('ecowitt_gw3000a') instead
             of just the brand. Unlike device-class tags that are
             technically needed for calibration logic (e.g.
             polar_h10/polar_v3), the exact weather-station gateway model
             isn't functionally relevant to anything in the code — only the
             brand matters. The importer now uses 'ecowitt', this migration
             brings already-imported databases in line.
@method.de   UPDATE weather_station SET source='ecowitt' WHERE
             source='ecowitt_gw3000a'. Idempotent: prueft vorher, ob
             ueberhaupt Zeilen mit dem alten Tag existieren.
@method.en   UPDATE weather_station SET source='ecowitt' WHERE
             source='ecowitt_gw3000a'. Idempotent: checks first whether any
             rows with the old tag exist.
@reads       health.db (weather_station.source)
@writes      health.db (weather_station.source only, no other columns changed)
@relevance.de  Entfernt eine unnoetig spezifische Geraeteangabe aus einem
               DB-Wert -- betrifft Datenschutz/Datenhygiene, nicht Funktion.
@relevance.en  Removes an unnecessarily specific device designation from a
               DB value -- a privacy/data-hygiene matter, not functionality.
@limits.de   Betrifft nur weather_station.source — falls andere Tabellen
             jemals direkt auf diesen String verweisen sollten (aktuell nicht
             der Fall), wären die dort nicht mitkorrigiert.
@limits.en   Only affects weather_station.source — if any other table were
             ever to reference this string directly (not currently the
             case), those would not be corrected here.
@usage
    python3 scripts/migrations/rename_ecowitt_source_tag.py --dry-run
    python3 scripts/migrations/rename_ecowitt_source_tag.py

Exit Codes:
    0: Lauf erfolgreich (auch wenn nichts zu tun war)
    1: Fehler beim Datenbankzugriff
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.base import log_import  # noqa: E402
from modules.db import open_db  # noqa: E402

OLD_SOURCE = "ecowitt_gw3000a"
NEW_SOURCE = "ecowitt"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Benennt weather_station.source von 'ecowitt_gw3000a' in 'ecowitt' um")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    args = ap.parse_args()

    try:
        conn = open_db()
    except Exception as exc:
        print(f"Fehler beim Öffnen der Datenbank: {exc}", file=sys.stderr)
        sys.exit(1)

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "weather_station" not in tables:
        print("weather_station existiert nicht — nichts zu tun.")
        conn.close()
        sys.exit(0)

    n = conn.execute(
        "SELECT COUNT(*) FROM weather_station WHERE source=?", (OLD_SOURCE,)
    ).fetchone()[0]

    if not n:
        print("Keine Zeilen mit dem alten Source-Tag — nichts zu tun.")
        conn.close()
        sys.exit(0)

    print(f"  {'Würde umbenennen' if args.dry_run else 'Umbenennen'}: "
          f"{n} Zeile(n) '{OLD_SOURCE}' → '{NEW_SOURCE}'")

    if not args.dry_run:
        conn.execute(
            "UPDATE weather_station SET source=? WHERE source=?", (NEW_SOURCE, OLD_SOURCE)
        )
        log_import(conn, "rename_ecowitt_source_tag", "weather_station", n, person=None)
        conn.commit()

    print(f"{'Würden' if args.dry_run else ''} {n} Zeile(n) umbenannt.")
    conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
