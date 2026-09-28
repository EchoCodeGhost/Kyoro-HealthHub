#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
fix_resting_hr_mislabeled_metrics.py — Renames two mislabeled resting-HR
metrics in measurements to their corrected names, so downstream
consumers (compute_canonical.py, compute_daily_context.py) stop
conflating them with genuine daily resting-HR measurements.

@tier        infrastructure
@purpose.de  Zwei Importer schrieben Werte unter generischen/falschen
             Metriknamen, die inhaltlich keine tageweise gemessene
             Ruhe-Herzfrequenz sind: (1) import_oura.py importierte
             Ouras readiness.contributors.resting_heart_rate -- ein
             0-100-Skalen-Score, kein bpm-Wert -- faelschlich mit Einheit
             'bpm' als 'readiness_hr_resting'; (2) import_polar.py
             importierte Polars physicalInformation.restingHeartRate --
             ein selten aktualisiertes Profil-Feld fuer Polars eigene
             HF-Zonen-Berechnung, keine Tagesmessung -- unter dem
             generischen Namen 'resting_hr', identisch zu echten
             Tagesmessungen anderer Geraete (z.B. Garmin). Beide
             Importer sind bereits korrigiert (neue Metriknamen fuer
             kuenftige Importe); diese Migration zieht bereits
             importierte Datenbanken nach, damit
             compute_canonical.build_resting_hr() nicht laenger
             fehlerhafte Werte in health_canonical.resting_heart_rate
             einspeist.
@purpose.en  Two importers wrote values under generic/incorrect metric
             names that are not, in fact, a daily-measured resting heart
             rate: (1) import_oura.py imported Oura's
             readiness.contributors.resting_heart_rate -- a 0-100-scale
             score, not a bpm value -- mislabeled with unit 'bpm' as
             'readiness_hr_resting'; (2) import_polar.py imported Polar's
             physicalInformation.restingHeartRate -- a rarely-updated
             profile field for Polar's own HR-zone calculation, not a
             daily measurement -- under the generic name 'resting_hr',
             identical to genuine daily measurements from other devices
             (e.g. Garmin). Both importers are already fixed (new metric
             names for future imports); this migration brings
             already-imported databases in line so
             compute_canonical.build_resting_hr() stops feeding
             incorrect values into health_canonical.resting_heart_rate.
@method.de   Zwei gezielte UPDATE-Statements auf measurements:
             (1) metric='readiness_hr_resting' AND source_app='oura_app'
             -> metric='readiness_contrib_resting_hr', unit=NULL;
             (2) metric='resting_hr' AND source_app='polar_connect'
             -> metric='polar_profile_resting_hr' (unit bleibt 'bpm',
             ist ein echter bpm-Wert, nur kein Tagesmesswert). Garmins
             'resting_hr'-Zeilen (source_app='garmin_gdpr') bleiben
             unveraendert -- das sind echte Tagesmessungen. Idempotent:
             prueft vorher Zeilenzahl, Wiederholung ist ein No-Op.
@method.en   Two targeted UPDATE statements on measurements:
             (1) metric='readiness_hr_resting' AND source_app='oura_app'
             -> metric='readiness_contrib_resting_hr', unit=NULL;
             (2) metric='resting_hr' AND source_app='polar_connect'
             -> metric='polar_profile_resting_hr' (unit stays 'bpm', it
             is a genuine bpm value, just not a daily measurement).
             Garmin's 'resting_hr' rows (source_app='garmin_gdpr') are
             left untouched -- those are genuine daily measurements.
             Idempotent: checks row count first, re-running is a no-op.
@reads       health.db (measurements)
@writes      health.db (measurements.metric, measurements.unit only --
             no values changed)
@relevance.de  Verhindert, dass zwei fehlklassifizierte Wearable-Felder
               weiterhin als echte Ruhe-Herzfrequenz in abgeleitete
               Tabellen einfliessen -- Datenqualitaet, nicht Funktion.
@relevance.en  Prevents two mislabeled wearable fields from continuing
               to feed into derived tables as genuine resting heart
               rate -- data quality, not a feature.
@limits.de   Nach dem Lauf muessen compute_canonical.py und
             compute_daily_context.py neu ausgefuehrt werden, damit die
             abgeleiteten Tabellen die Korrektur widerspiegeln -- diese
             Migration aendert nur measurements.
@limits.en   After running, compute_canonical.py and
             compute_daily_context.py must be re-run so the derived
             tables reflect the fix -- this migration only changes
             measurements.
@usage
    python3 scripts/migrations/fix_resting_hr_mislabeled_metrics.py --dry-run
    python3 scripts/migrations/fix_resting_hr_mislabeled_metrics.py
    python3 scripts/compute/compute_canonical.py
    python3 scripts/compute/compute_daily_context.py

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

RENAMES = [
    # (old_metric, source_app, new_metric, clear_unit)
    ("readiness_hr_resting", "oura_app", "readiness_contrib_resting_hr", True),
    ("resting_hr", "polar_connect", "polar_profile_resting_hr", False),
]


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Benennt fehlklassifizierte Ruhe-HF-Metriken (Oura-Score, Polar-Profil-Snapshot) um")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    args = ap.parse_args()

    try:
        conn = open_db()
    except Exception as exc:
        print(f"Fehler beim Öffnen der Datenbank: {exc}", file=sys.stderr)
        sys.exit(1)

    total = 0
    for old_metric, source_app, new_metric, clear_unit in RENAMES:
        n = conn.execute(
            "SELECT COUNT(*) FROM measurements WHERE metric=? AND source_app=?",
            (old_metric, source_app),
        ).fetchone()[0]

        if not n:
            print(f"Keine Zeilen für metric='{old_metric}', source_app='{source_app}' — nichts zu tun.")
            continue

        unit_note = ", unit=NULL" if clear_unit else ""
        print(f"  {'Würde umbenennen' if args.dry_run else 'Umbenennen'}: "
              f"{n} Zeile(n) metric='{old_metric}' → '{new_metric}'{unit_note} "
              f"(source_app='{source_app}')")

        if not args.dry_run:
            if clear_unit:
                conn.execute(
                    "UPDATE measurements SET metric=?, unit=NULL WHERE metric=? AND source_app=?",
                    (new_metric, old_metric, source_app),
                )
            else:
                conn.execute(
                    "UPDATE measurements SET metric=? WHERE metric=? AND source_app=?",
                    (new_metric, old_metric, source_app),
                )
            log_import(conn, "fix_resting_hr_mislabeled_metrics", "measurements", n, person=None)
        total += n

    if not args.dry_run and total:
        conn.commit()

    print(f"{'Würden' if args.dry_run else ''} insgesamt {total} Zeile(n) umbenannt.")
    conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
