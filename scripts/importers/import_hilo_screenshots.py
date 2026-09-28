#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Hilo-App Blutdruckdaten Einmalimport

@tier        infrastructure
@purpose.de  Einmalimport von Hilo-App Blutdruckdaten aus Screenshots
@purpose.en  One-time import of Hilo app blood pressure data from screenshots
@method.de   Einmalimport der Hilo-App-Blutdruckdaten aus manuell abgelesenen Screenshots.
             Zeitraum: 23. - 28. Juni 2026, Zeitzonenannahme: CEST (UTC+2).
             Daten wurden bereits importiert (INSERT OR IGNORE idempotent, erneutes
             Ausfuehren daher gefahrlos).
             RAW-Liste aus Privacy-Gruenden geleert.
@method.en   One-time import of Hilo app blood pressure data from manually read screenshots.
             Period: June 23-28, 2026, timezone assumption: CEST (UTC+2).
             Data has already been imported (INSERT OR IGNORE idempotent, so
             re-running is safe).
             RAW list cleared for privacy reasons.
@reads       Hilo App Screenshots
@writes      blood_pressure
@limits.de   Einmaliger Import. Zeitraum bereits abgeschlossen. Nutzerin verwendete im
             Importzeitraum sowohl das manschettenlose Hilo Band als auch die Hilo-Manschette
             parallel; die Screenshots erlauben keine verlaessliche Zuordnung pro Messung zu
             einem der beiden Geraete, daher device_id="hilo_unspecified" statt einer
             fälschlich spezifischen Zuordnung (frueher irrtuemlich "omron_bp").

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   One-time import. Period already completed. User used both the cuffless Hilo
             Band and the Hilo Cuff in parallel during the import period; screenshots don't
             reliably indicate which device produced which reading, hence
             device_id="hilo_unspecified" rather than a falsely specific attribution
             (previously incorrectly "omron_bp").
@usage
    python3 import_hilo_screenshots.py
    python3 import_hilo_screenshots.py --lang en
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config
from modules.base import log_import, resolve_person
from modules.db import open_db
from modules.i18n import add_lang_arg, apply_lang_from_args

_cfg = Config()

DEVICE_ID = "hilo_unspecified"
SOURCE    = "hilo_app_screenshot"
CEST      = timezone(timedelta(hours=2))

# Rohdaten: (datum, uhrzeit, sys, dia, puls)
# Datum: YYYY-MM-DD (Juni 2026)
# Alle Werte aus Screenshots manuell erfasst + dedupliziert
RAW: list[tuple[str, str, int, int, int]] = []


def local_to_utc(date_str: str, time_str: str) -> str:
    local_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    local_dt = local_dt.replace(tzinfo=CEST)
    return local_dt.astimezone(timezone.utc).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Hilo-App Blutdruckdaten (Einmalimport)")
    add_lang_arg(parser)
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    conn = open_db()
    inserted = skipped = 0

    for date_str, time_str, sys_val, dia_val, pulse in RAW:
        ts   = local_to_utc(date_str, time_str)
        date = date_str  # lokaler Kalendertag (CEST), wie in der Hilo-App angezeigt

        cur = conn.execute(
            """
            INSERT OR IGNORE INTO blood_pressure
              (ts, date, systolic, diastolic, pulse, person, device_id, source)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (ts, date, sys_val, dia_val, pulse,
             person, DEVICE_ID, SOURCE),
        )
        if cur.rowcount:
            inserted += 1
        else:
            skipped += 1

    log_import(conn, SOURCE, "hilo_screenshots", inserted, skipped, person=person)
    conn.commit()
    conn.close()

    print(f"Importiert: {inserted}  |  Übersprungen (Duplikat): {skipped}")
    print(f"Gesamt in RAW: {len(RAW)}")


if __name__ == "__main__":
    main()
