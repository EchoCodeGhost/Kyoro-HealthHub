#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Blutdruckgeräte-Puls (Hilo/Aktiia, Omron, ...) → measurements (heart_rate)

@tier        infrastructure
@purpose.de  Spiegelt die Pulswerte, die bei jeder Blutdruckmessung
             (Hilo/Aktiia, Omron, ...) miterfasst werden, als eigene
             'heart_rate'-Einträge in measurements. Erst dadurch werden diese
             Pulswerte für den kanonischen Merge (compute_canonical.py) und die
             Quellen-Kalibrierung (compute_calibrate_sources.py) sichtbar —
             beide lesen nur aus measurements, nicht aus blood_pressure.
@purpose.en  Mirrors the pulse values captured alongside each blood pressure
             reading (Hilo/Aktiia, Omron, ...) as standalone 'heart_rate'
             entries in measurements. This is what makes these pulse values
             visible to the canonical merge (compute_canonical.py) and source
             calibration (compute_calibrate_sources.py) — both only read from
             measurements, not blood_pressure.
@method.de   Liest alle blood_pressure-Zeilen mit pulse IS NOT NULL, schreibt
             je eine measurements-Zeile (metric='heart_rate', gleicher
             ts/device_id/person/source). INSERT OR IGNORE — rein additiv,
             kein Update bestehender Werte. Quellenunabhängig — jedes künftig
             importierte BP-Gerät mit Puls-Nebenwert wird automatisch erfasst,
             ohne Codeänderung.
@method.en   Reads all blood_pressure rows with pulse IS NOT NULL, writes one
             measurements row each (metric='heart_rate', same
             ts/device_id/person/source). INSERT OR IGNORE — purely additive,
             no update of existing values. Source-agnostic — any future BP
             device imported with a pulse side-value is picked up automatically,
             no code change needed.
@reads       blood_pressure (pulse IS NOT NULL)
@writes      measurements (metric='heart_rate', source_app = whatever the
             blood_pressure row's source column holds)
@limits.de   BP-Geräte liefern Puls nur zum Zeitpunkt jeder Blutdruckmessung
             (Momentaufnahme), keine kontinuierliche Hintergrund-HF — als
             Kalibrierungsanker daher eher für Ruhe-/Spot-Vergleiche geeignet,
             nicht für 24/7-Trendvergleiche wie Polar H10.

@relevance.de  Ermöglicht die Analyse von Blutdruckdaten, essentiell für die kardiovaskuläre Gesundheitsüberwachung
@relevance.en  Enables blood pressure data analysis, essential for cardiovascular health monitoring
@limits.en   BP devices only provide pulse at the moment of each blood
             pressure reading (spot value), no continuous background HR —
             better suited as a calibration anchor for resting/spot
             comparisons, not for 24/7 trend comparisons like the Polar H10.
@usage
    python3 compute_bp_pulse_bridge.py
    python3 compute_bp_pulse_bridge.py --dry-run
"""

import argparse
import time
from pathlib import Path
import sys as _sys

_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_cfg = _Cfg()
DB_PATH = _cfg.db_path

METRIC_OUT = "heart_rate"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=t("BP-Geräte-Puls → measurements(heart_rate)",
                      "BP device pulse → measurements(heart_rate)"))
    parser.add_argument("--person", default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help=t("Nur anzeigen, nichts schreiben", "Show only, do not write"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = args.person or OWN_PERSON_ID
    conn = open_db()
    t0 = time.time()

    rows = conn.execute("""
        SELECT ts, date, pulse, device_id, source
        FROM blood_pressure
        WHERE pulse IS NOT NULL AND person=?
    """, (person,)).fetchall()

    by_source: dict[str, int] = {}
    for r in rows:
        by_source[r[4]] = by_source.get(r[4], 0) + 1
    print(t(f"Gefunden: {len(rows)} Blutdruckmessungen mit Puls {by_source}",
            f"Found: {len(rows)} blood pressure readings with pulse {by_source}"))

    if args.dry_run:
        for r in sorted(rows, key=lambda r: r[0])[-10:]:
            print(f"  {r[0]}  {r[2]} bpm  ({r[3]}/{r[4]})")
        print(t("\nDry-run — keine Daten geschrieben.", "\nDry-run — no data written."))
        return

    to_insert = [
        (ts, date, METRIC_OUT, float(pulse), "bpm", device_id, person, source)
        for ts, date, pulse, device_id, source in rows
    ]

    # executemany() liefert bei INSERT OR IGNORE kein verlässliches rowcount —
    # daher Einzel-execute() je Zeile, wie in compute_sleep_spo2.py.
    inserted = 0
    for row in to_insert:
        cur = conn.execute("""
            INSERT OR IGNORE INTO measurements
            (ts, date, metric, value, unit, device_id, person, source_app)
            VALUES (?,?,?,?,?,?,?,?)
        """, row)
        inserted += cur.rowcount

    conn.execute("""
        INSERT INTO import_log (ts_run, source, data_path, person, rows_inserted, rows_skipped, duration_s)
        VALUES (datetime('now'), ?, '', ?, ?, ?, ?)
    """, ("compute_bp_pulse_bridge", person, inserted,
          len(to_insert) - inserted, round(time.time() - t0, 2)))
    conn.commit()
    conn.close()

    print(t(f"{inserted} neue heart_rate-Einträge aus BP-Gerät-Pulswerten gespeichert.",
            f"{inserted} new heart_rate entries saved from BP device pulse values."))


if __name__ == "__main__":
    main()
