#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
fix_polar_247hr_device_ids.py — Reassigns measurements.device_id for Polar
24/7 heart_rate rows using the real per-day deviceId in the 247ohr_*.json files

@tier        infrastructure
@purpose.de  Korrigiert `measurements`-Zeilen (metric='heart_rate',
             source_app='polar_connect'), deren device_id bisher aus der
             unsicheren Datums-Ratelogik (_polar_device_for_date()) stammte,
             obwohl die 247ohr_*.json-Dateien die tatsächliche Geräte-
             Seriennummer pro Tag im Feld 'deviceId' (je deviceDays-Eintrag)
             mitliefern.
@purpose.en  Corrects `measurements` rows (metric='heart_rate',
             source_app='polar_connect') whose device_id previously came
             from the unreliable date-guessing logic
             (_polar_device_for_date()), even though the 247ohr_*.json files
             carry the real device serial per day (in each deviceDays
             entry's 'deviceId' field).
@method.de   Scannt zuerst alle 247ohr_*.json-Dateien und baut eine
             Datum→device_id-Zuordnung aus den echten deviceId-Werten
             (schnell, nur die Tages-Header, nicht die Samples). Führt dann
             ein UPDATE pro Datum aus (nicht pro Zeile — bei ~20 Mio.
             betroffenen Zeilen wäre zeilenweises Matching unpraktikabel
             langsam). Tage mit unbekannter/unmapbarer Seriennummer werden
             übersprungen, nicht auf die Datums-Regel zurückgefallen.
@method.en   First scans all 247ohr_*.json files and builds a date→device_id
             mapping from the real deviceId values (fast, only reads the
             per-day headers, not the samples). Then runs one UPDATE per
             date (not per row — with ~20M affected rows, row-by-row
             matching would be impractically slow). Days with an unknown/
             unmappable serial are skipped, not falling back to the date
             rule.
@reads       {polar_dir}/247ohr_*.json, measurements
@writes      measurements (UPDATE device_id where the real per-day deviceId
             maps to a different device than currently stored)
@limits.de   Setzt eine vollständige device_registry mit allen Polar-
             Wrist-Seriennummern voraus (s. fix_polar_wrist_device_attribution.py).
             Falls an einem Tag zwei 247ohr-Dateien mit unterschiedlichem
             deviceId existieren (z.B. Geräteinstallation überschnitten),
             gewinnt die zuletzt gelesene Datei — seltener Grenzfall.
             UPDATE OR IGNORE statt UPDATE: (ts, metric, device_id, person)
             ist UNIQUE — existiert fuer denselben Zeitstempel bereits eine
             Zeile unter der Ziel-device_id (z.B. durch echtes Parallel-
             Tragen zweier Geraete am selben Tag), wuerde ein einfaches
             UPDATE mit IntegrityError abbrechen. OR IGNORE ueberspringt nur
             die kollidierende Einzelzeile und meldet die Anzahl am Ende,
             der Rest des Tages wird trotzdem korrigiert. Sicher wiederholt
             ausführbar (idempotent, UPDATE nur bei Abweichung).

@relevance.de  Bietet Gesundheitsdatenfunktionen, essentiell für die medizinische Datenverarbeitung
@relevance.en  Provides health data functions, essential for medical data processing
@limits.en   Requires a complete device_registry with all Polar wrist
             serials (see fix_polar_wrist_device_attribution.py). If two
             247ohr files for the same day carry different deviceId values
             (e.g. overlapping device setup), the last one read wins — a
             rare edge case. Uses UPDATE OR IGNORE instead of UPDATE:
             (ts, metric, device_id, person) is UNIQUE — if a row already
             exists under the target device_id for the same timestamp (e.g.
             from genuinely wearing two devices in parallel on the same
             day), a plain UPDATE would abort with an IntegrityError. OR
             IGNORE skips only the colliding row and reports the count at
             the end; the rest of that day is still corrected. Safe to
             re-run (idempotent, UPDATE only on mismatch).
@usage
    python3 scripts/migrations/fix_polar_247hr_device_ids.py
    python3 migrations/fix_polar_247hr_device_ids.py  # from inside scripts/
"""
import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.base import log_import, resolve_person
from modules.db import open_db
from importers.import_polar import POLAR_DIR, polar_serial_to_device_id_for_person


def _build_date_device_map(polar_dir: Path, serial_map: dict[str, str]) -> dict[str, str]:
    date_to_device: dict[str, str] = {}
    unmapped_serials: set[str] = set()
    for f in sorted(glob.glob(str(polar_dir / "247ohr_*.json"))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        for day in d.get("deviceDays", []):
            date = day.get("date", "")
            raw_serial = day.get("deviceId")
            if not date or not raw_serial:
                continue
            device_id = serial_map.get(raw_serial)
            if not device_id:
                unmapped_serials.add(raw_serial)
                continue
            date_to_device[date] = device_id
    if unmapped_serials:
        print(f"  ⚠ Unbekannte Seriennummer(n), übersprungen: {sorted(unmapped_serials)}")
    return date_to_device


def run(person: "str | None" = None, polar_dir: "Path | None" = None):
    target_person = resolve_person(person)
    effective_dir = polar_dir or POLAR_DIR
    # Personen-bewusste Seriennummer-Zuordnung nur wenn --person explizit
    # angegeben wurde (echte Wirkung, nicht kosmetisch) — sonst der bestehende,
    # unveraenderte globale Dict (s. import_polar.polar_serial_to_device_id_for_person).
    serial_map = polar_serial_to_device_id_for_person(person)
    date_to_device = _build_date_device_map(effective_dir, serial_map)
    print(f"  {len(date_to_device)} Tage mit bekannter Geräte-ID gefunden")

    conn = open_db()
    cursor = conn.cursor()

    fixed_days = 0
    fixed_rows = 0
    collisions = 0
    for date, device_id in date_to_device.items():
        # UPDATE OR IGNORE statt UPDATE: (ts, metric, device_id, person) ist
        # UNIQUE — falls fuer denselben Zeitstempel bereits eine Zeile unter
        # der Ziel-device_id existiert (z.B. weil an einem Tag zwei Geraete
        # ueberlappend Werte lieferten), wuerde ein einfaches UPDATE mit
        # einem IntegrityError abbrechen. OR IGNORE ueberspringt nur die
        # kollidierende Einzelzeile, der Rest des Tages wird trotzdem
        # korrigiert — sicherer als den ganzen Lauf abzubrechen.
        cursor.execute(
            "UPDATE OR IGNORE measurements SET device_id=? "
            "WHERE date=? AND metric='heart_rate' AND source_app='polar_connect' "
            "AND person=? AND device_id!=?",
            (device_id, date, target_person, device_id),
        )
        if cursor.rowcount:
            fixed_days += 1
            fixed_rows += cursor.rowcount
        # Verbleibende (nicht aktualisierte) Zeilen mit derselben Bedingung
        # sind Kollisionen, keine echten Fehler — nur zaehlen, nicht erneut
        # versuchen (OR IGNORE hat sie bereits bewusst uebersprungen).
        remaining = cursor.execute(
            "SELECT COUNT(*) FROM measurements WHERE date=? AND metric='heart_rate' "
            "AND source_app='polar_connect' AND person=? AND device_id!=?",
            (date, target_person, device_id),
        ).fetchone()[0]
        collisions += remaining

    log_import(conn, "fix_polar_247hr_device_ids", "measurements (heart_rate, polar_connect)",
               fixed_rows, person=target_person)
    conn.commit()
    conn.close()
    print(f"✓ {fixed_rows} Zeile(n) an {fixed_days} Tag(en) korrigiert"
          + (f" — {collisions} Zeile(n) wegen UNIQUE-Kollision uebersprungen" if collisions else ""))


if __name__ == "__main__":
    _ap = argparse.ArgumentParser(description="Korrigiert Polar-24/7hr-device_id anhand echter deviceId-Werte")
    _ap.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    _ap.add_argument("--polar-dir", default=None, type=Path,
                     help="Alternatives Polar-Exportverzeichnis (Default: konfigurierter polar_dir)")
    _args = _ap.parse_args()
    run(person=_args.person, polar_dir=_args.polar_dir)
