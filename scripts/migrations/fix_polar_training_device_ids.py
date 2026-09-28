#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
fix_polar_training_device_ids.py — Reassigns sessions.device_id for Polar
trainings using the real deviceId embedded in each training JSON file

@tier        infrastructure
@purpose.de  Korrigiert `sessions`-Zeilen (type='training', source_app='polar_connect'),
             deren device_id bisher aus der unsicheren Datums-Ratelogik
             (_polar_device_for_date()) stammte, obwohl die Trainings-JSON-Dateien
             die tatsächliche Geräte-Seriennummer im Feld 'deviceId' mitliefern.
@purpose.en  Corrects `sessions` rows (type='training', source_app='polar_connect')
             whose device_id previously came from the unreliable date-guessing
             logic (_polar_device_for_date()), even though the training JSON
             files carry the real device serial in the 'deviceId' field.
@method.de   Liest jede training-session_*.json erneut, mappt deviceId über
             _POLAR_SERIAL_TO_DEVICE_ID (device_registry) auf die richtige
             device_id, UPDATEt die passende sessions-Zeile (ID =
             'polar_training_{identifier}'). Dateien ohne deviceId (ältere
             Exporte) werden übersprungen, nicht auf die Datums-Regel
             zurückgefallen — diese Zeilen bleiben unverändert.
@method.en   Re-reads every training-session_*.json, maps deviceId via
             _POLAR_SERIAL_TO_DEVICE_ID (device_registry) to the correct
             device_id, UPDATEs the matching sessions row (ID =
             'polar_training_{identifier}'). Files without deviceId (older
             exports) are skipped, not falling back to the date rule — those
             rows are left unchanged.
@reads       {polar_dir}/training-session_*.json, sessions
@writes      sessions (UPDATE device_id where the JSON's real deviceId maps
             to a different device than currently stored)
@limits.de   Setzt eine vollständige device_registry mit allen Polar-
             Wrist-Seriennummern voraus (s. fix_polar_wrist_device_attribution.py
             für den zugehörigen Fix der Datums-Fallback-Logik). Sicher
             wiederholt ausführbar (idempotent, UPDATE nur bei Abweichung).

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Requires a complete device_registry with all Polar wrist serials
             (see fix_polar_wrist_device_attribution.py for the companion fix
             to the date-fallback logic). Safe to re-run (idempotent, UPDATE
             only on mismatch).
@usage
    python3 scripts/migrations/fix_polar_training_device_ids.py
    python3 migrations/fix_polar_training_device_ids.py  # from inside scripts/
"""
import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.base import log_import, resolve_person
from modules.db import open_db
from importers.import_polar import (
    POLAR_DIR, TRAINING_SESSION_GLOB, polar_serial_to_device_id_for_person,
    training_session_identifier,
)


def _scalar(v):
    return v if not isinstance(v, (dict, list)) else None


def run(person: "str | None" = None, polar_dir: "Path | None" = None):
    target_person = resolve_person(person)
    effective_dir = polar_dir or POLAR_DIR
    serial_map = polar_serial_to_device_id_for_person(person)

    conn = open_db()
    cursor = conn.cursor()

    fixed = no_serial = unmapped = 0
    for f in sorted(glob.glob(str(effective_dir / TRAINING_SESSION_GLOB))):
        try:
            d = json.load(open(f))
        except Exception:
            continue

        identifier = training_session_identifier(d, f)
        sid = f"polar_training_{identifier}"

        raw_serial = _scalar(d.get("deviceId"))
        if not raw_serial:
            no_serial += 1
            continue

        device_id = serial_map.get(raw_serial)
        if not device_id:
            unmapped += 1
            continue

        cursor.execute(
            "UPDATE sessions SET device_id=? WHERE id=? AND person=? AND device_id!=?",
            (device_id, sid, target_person, device_id),
        )
        if cursor.rowcount:
            fixed += 1

    log_import(conn, "fix_polar_training_device_ids", "sessions", fixed,
              person=target_person)
    conn.commit()
    conn.close()
    print(f"✓ {fixed} Session(en) korrigiert — {no_serial} Datei(en) ohne deviceId "
          f"übersprungen, {unmapped} mit unbekannter Seriennummer")


if __name__ == "__main__":
    _ap = argparse.ArgumentParser(description="Korrigiert Polar-Trainings-device_id anhand echter deviceId-Werte")
    _ap.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    _ap.add_argument("--polar-dir", default=None, type=Path,
                     help="Alternatives Polar-Exportverzeichnis (Default: konfigurierter polar_dir)")
    _args = _ap.parse_args()
    run(person=_args.person, polar_dir=_args.polar_dir)
