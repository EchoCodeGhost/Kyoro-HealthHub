#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Gewicht aus measurements → body_composition — Brücke für Profil-Gewichtswerte.

@tier        infrastructure
@purpose.de  Überträgt weight_kg-Werte aus der measurements-Tabelle (aktuell:
             Polars physicalInformation-Profil-Snapshot, s. import_polar.py
             ::import_polar_activity) nach body_composition, damit
             Gewichtsverläufe/-analysen, die body_composition lesen, nicht auf
             die deutlich lückenhaftere Waagen-Historie (FDDB/Beurer/Renpho)
             beschränkt bleiben.
@purpose.en  Bridges weight_kg values from the measurements table (currently:
             Polar's physicalInformation profile snapshot, see
             import_polar.py::import_polar_activity) into body_composition,
             so weight trends/analyses reading body_composition aren't limited
             to the much sparser scale history (FDDB/Beurer/Renpho).
@method.de   Liest measurements WHERE metric='weight_kg', gruppiert nach
             source_app (nicht auf Polar hartkodiert — jede Quelle, die
             künftig weight_kg nach measurements schreibt, wird automatisch
             mitgenommen). Nutzt ts/date direkt aus measurements (Polar:
             {date}T00:00:00+00:00) statt eines eigenen Zeitstempels — bei
             Überschneidung mit einer bestehenden body_composition-Zeile zum
             exakt gleichen (ts, person) gewinnt die zuerst geschriebene
             (INSERT OR IGNORE), das ist unwahrscheinlich, da FDDB/Beurer/
             Renpho bislang T12:00:00 nutzen, keine T00:00:00-Zeitstempel.
@method.en   Reads measurements WHERE metric='weight_kg', grouped by source_app
             (not hardcoded to Polar — any future source writing weight_kg to
             measurements is picked up automatically). Uses ts/date directly
             from measurements (Polar: {date}T00:00:00+00:00) instead of its
             own timestamp — on collision with an existing body_composition
             row at the exact same (ts, person), the first-written one wins
             (INSERT OR IGNORE); unlikely in practice since FDDB/Beurer/Renpho
             currently use T12:00:00, not T00:00:00 timestamps.
@reads       measurements (metric='weight_kg')
@writes      body_composition (nur weight_kg gesetzt, übrige Spalten NULL)
@limits.de   Nur weight_kg — die übrigen physicalInformation-Werte (VO2max,
             HFmax, Ruhepuls, aerobe/anaerobe Schwelle) bleiben bewusst in
             measurements, weil body_composition dafür keine Spalten hat und
             es sich um andere Konzepte handelt (Fitness-/HF-Kennwerte, keine
             Körperzusammensetzung). Kein Duplikat-Check gegen andere
             body_composition-Quellen am selben Tag — falls z.B. eine
             Waagen-Messung und ein Polar-Profil-Wert für denselben Tag
             abweichen, bleiben beide als separate Zeilen bestehen (andere
             Ruhr-Uhrzeit), keine Auflösung/Mittelung.
@limits.en   Only weight_kg — the other physicalInformation values (VO2max,
             HRmax, resting HR, aerobic/anaerobic threshold) deliberately stay
             in measurements, since body_composition has no columns for them
             and they're a different concept (fitness/HR metrics, not body
             composition). No duplicate check against other body_composition
             sources on the same day — if e.g. a scale measurement and a
             Polar profile value differ for the same day, both remain as
             separate rows (different time-of-day), no reconciliation/averaging.
@relevance.de  Schließt Lücken in der Gewichts-Historie außerhalb der
               Waagen-Importe, relevant für Trend-Analysen und die
               Belastungs-/Kapazitäts-Einordnung
@relevance.en  Closes gaps in weight history outside scale imports, relevant
               for trend analyses and exertion/capacity context
@usage
    python3 scripts/compute/compute_body_composition_from_measurements.py
    python3 scripts/compute/compute_body_composition_from_measurements.py --lang en
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from health_config import OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args


def run(conn) -> int:
    person = OWN_PERSON_ID
    rows = conn.execute("""
        SELECT ts, date, value, source_app FROM measurements
        WHERE metric='weight_kg' AND person=? AND value IS NOT NULL
    """, (person,)).fetchall()

    out_rows = [
        (ts, date, value, person, source_app or "measurements_bridge")
        for ts, date, value, source_app in rows
    ]

    if out_rows:
        conn.executemany("""
            INSERT OR IGNORE INTO body_composition (ts, date, weight_kg, person, source)
            VALUES (?,?,?,?,?)
        """, out_rows)
        conn.commit()
    return len(out_rows)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(
        description=t("Gewicht aus measurements in body_composition übertragen",
                       "Bridge weight from measurements into body_composition"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    n = run(conn)
    print(t(f"{n:,} Gewichtswerte übertragen (INSERT OR IGNORE, Duplikate übersprungen).",
            f"{n:,} weight values bridged (INSERT OR IGNORE, duplicates skipped)."))


if __name__ == "__main__":
    main()
