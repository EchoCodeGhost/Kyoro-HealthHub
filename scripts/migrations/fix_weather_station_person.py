#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
fix_weather_station_person.py — Corrects person attribution for existing
weather_station rows

@tier        infrastructure
@purpose.de  import_homeassistant.py::import_weather_to_db() und
             import_reise_weather() setzten die person-Spalte nie explizit —
             beide INSERT-Anweisungen liessen sie auf den Tabellen-Default
             fallen ('unknown'). Eine spaetere systemweite Pseudonymisierung
             wandelte einen Teil davon in ein frisch gemuenztes Pseudonym um
             (PER-982e9b5c), statt sie der tatsaechlichen Person zuzuordnen —
             weather_station ist Wetterstationsdaten eines Ein-Personen-
             Haushalts, keine echte zweite Identitaet. Der Importer-Bug ist
             mit dem Rest dieses Commits behoben; dieses Skript korrigiert
             die bereits importierten Zeilen.
@purpose.en  import_homeassistant.py::import_weather_to_db() and
             import_reise_weather() never set the person column explicitly —
             both INSERT statements fell back to the table default
             ('unknown'). A later system-wide pseudonymization pass turned
             part of that into a freshly minted pseudonym (PER-982e9b5c)
             instead of resolving it to the actual person — weather_station
             is single-household weather data, not a genuine second
             identity. The importer bug is fixed alongside this commit; this
             script corrects the already-imported rows.
@method.de   UPDATE weather_station SET person=OWN_PERSON_ID WHERE person IN
             ('unknown', 'PER-982e9b5c') — beide bekannten Fehlwerte in einem
             Lauf. Idempotent, sicher wiederholt ausfuehrbar.
@method.en   UPDATE weather_station SET person=OWN_PERSON_ID WHERE person IN
             ('unknown', 'PER-982e9b5c') — both known wrong values in one
             run. Idempotent, safe to re-run.
@reads       health.db (weather_station)
@writes      health.db (weather_station.person)
@relevance.de  Ermoeglicht korrekte personenbezogene Filterung von
               Wetterstationsdaten, u.a. fuer compute_pem.py's Umwelt-Hinweise
@relevance.en  Enables correct person-filtered queries on weather station
               data, including compute_pem.py's environmental hints
@limits.de   Betrifft nur weather_station. Andere Tabellen mit aehnlichem
             Person-Attributionsfehler waeren separat zu pruefen.
@limits.en   Only affects weather_station. Other tables with a similar
             person-attribution defect would need separate review.
@usage
    python3 scripts/migrations/fix_weather_station_person.py --dry-run
    python3 scripts/migrations/fix_weather_station_person.py

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

WRONG_VALUES = ("unknown", "PER-982e9b5c")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Korrigiert die person-Zuordnung bestehender weather_station-Zeilen")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    args = ap.parse_args()

    try:
        conn = open_db()
    except Exception as exc:
        print(f"Fehler beim Öffnen der Datenbank: {exc}", file=sys.stderr)
        sys.exit(1)

    placeholders = ",".join("?" for _ in WRONG_VALUES)
    n = conn.execute(
        f"SELECT COUNT(*) FROM weather_station WHERE person IN ({placeholders})",
        WRONG_VALUES
    ).fetchone()[0]

    if args.dry_run:
        print(f"Würde {n} Zeile(n) korrigieren (person → {OWN_PERSON_ID}).")
        conn.close()
        sys.exit(0)

    conn.execute(
        f"UPDATE weather_station SET person=? WHERE person IN ({placeholders})",
        (OWN_PERSON_ID,) + WRONG_VALUES
    )
    if n:
        log_import(conn, "fix_weather_station_person", "weather_station", n)
    conn.commit()
    print(f"{n} Zeile(n) korrigiert (person → {OWN_PERSON_ID}).")
    conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
