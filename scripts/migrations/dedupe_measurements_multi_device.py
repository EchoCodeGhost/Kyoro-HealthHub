#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
dedupe_measurements_multi_device.py — Removes measurements rows that are the
same real-world reading duplicated across two device_id tags

@tier        infrastructure
@purpose.de  Bereinigt `measurements`-Zeilen, die exakt dieselbe reale Messung
             sind, aber unter ZWEI verschiedenen device_id-Werten gespeichert
             wurden (identisches ts, metric, value/value_text, source_app,
             person -- nur device_id unterscheidet sich). Groesster Befund:
             ein erheblicher Anteil der heart_rate-Zeilen aus
             source_app='polar_connect' sind solche Zwillingspaare.
@purpose.en  Cleans up `measurements` rows that are the exact same real-world
             reading stored under TWO different device_id values (identical
             ts, metric, value/value_text, source_app, person -- only
             device_id differs). Largest finding: a substantial share of
             heart_rate rows from source_app='polar_connect' are such twin
             pairs.
@method.de   Ursachenanalyse (per identity_resolver.reverse_resolve +
             health_config.device_registry): die betroffenen device_ids sind
             ECHTE, unterschiedliche Geraete desselben Sensortyps (verschiedene,
             im device_registry gefuehrte Seriennummern) -- kein
             Pseudonymisierungs-Bug, der einem Geraet mehrere IDs zugewiesen
             haette. Ein betroffener device_registry-Eintrag dokumentiert
             bereits eigenstaendig zeitliche Ueberschneidungen mit anderen
             Handgelenksgeraeten ("date-basierte Einzelgeraete-Zuordnung
             zeitweise mehrdeutig"). Die Duplikate selbst (identischer Wert auf
             die Dezimalstelle, Sekunde fuer Sekunde ueber laengere
             Zeitraeume) sind fuer zwei unabhaengige optische Handgelenks-
             sensoren physikalisch nicht plausibel -- stattdessen wird ein
             und dieselbe zugrundeliegende Polar-API-Messung beim Import
             (oder bereits in Polars eigenem Export) zwei registrierten
             Geraeten gleichzeitig zugeordnet, vermutlich weil measurements'
             PRIMARY KEY (ts, metric, device_id, person) device_id explizit
             als Teil der Identitaet behandelt -- zwei verschiedene
             device_ids fuer denselben ts+metric sind also aus Schema-Sicht
             kein Konflikt, INSERT OR IGNORE greift nicht. Fix: gruppiert
             nach (person, metric, ts, value, value_text, source_app) --
             bewusst OHNE device_id/unit in der Gruppierung, da genau
             device_id die Fehlerquelle ist. Aus jeder Gruppe (>1 Zeile)
             wird die Zeile mit dem kleinsten rowid behalten (device_id
             spielt fuer keine bekannte Auswertung in diesem Projekt eine
             Rolle -- nur source_app), die uebrigen werden gelöscht.
@method.en   Root-cause analysis (via identity_resolver.reverse_resolve +
             health_config.device_registry): the affected device_ids are
             REAL, distinct devices of the same sensor type (different
             serial numbers on record in device_registry) -- not a
             pseudonymization bug that assigned one device multiple IDs. An
             affected device_registry entry already independently documents
             overlapping wear periods with other wrist devices ("date-based
             single-device attribution occasionally ambiguous"). The
             duplicates themselves
             (identical value to the decimal, second by second over
             extended periods) are not physically plausible for two
             independent optical wrist sensors -- instead, one and the same
             underlying Polar API reading gets attributed to two registered
             devices at import time (or already in Polar's own export),
             likely because measurements' PRIMARY KEY (ts, metric, device_id,
             person) treats device_id as part of the identity -- two
             different device_ids for the same ts+metric are therefore not a
             schema conflict, INSERT OR IGNORE does not catch it. Fix: group
             by (person, metric, ts, value, value_text, source_app) --
             deliberately WITHOUT device_id/unit in the grouping key, since
             device_id is exactly the source of the error. From each group
             (>1 row) the row with the smallest rowid is kept (device_id is
             not used by any known analysis in this project -- only
             source_app is), the rest are deleted.
@reads       health.db (measurements)
@writes      health.db (DELETE auf measurements fuer Duplikat-Zeilen)
@relevance.de  Betrifft primaer heart_rate/polar_connect (hohe Duplikatrate)
               und fliesst in praktisch jede HF-basierte Auswertung im
               Projekt ein (Schlaf-/Tag-HF-Vergleich, Orthostase-Erkennung,
               PEM-Score, ...). Mittelwerte sind bei gleichmaessiger
               2-fach-Duplizierung rechnerisch unveraendert, aber jede
               stichprobengroessen-abhaengige Logik (Mindest-n-Schwellen)
               zaehlte bislang doppelt.
@relevance.en  Primarily affects heart_rate/polar_connect (high duplicate
               rate) and feeds into practically every HR-based analysis in
               the project (sleep/day HR comparison, orthostatic detection,
               PEM score, ...). Averages are arithmetically unaffected under
               uniform 2x duplication, but any sample-size-dependent logic
               (minimum-n thresholds) has been counting double.
@limits.de   Betrifft nur die in METRICS_TO_CHECK gelisteten Metriken (dort
             wurde die Duplikation konkret nachgewiesen) -- kein globaler
             Scan ueber alle measurements-Metriken, um die Laufzeit auf
             einer 40+ Mio.-Zeilen-Tabelle uebersehbar zu halten. Nach dem
             Lauf sollten HF-abhaengige compute-/analyse-Skripte neu
             laufen (compute_orthostatic_detection.py, analyse_sleep_day_hr.py,
             compute_pem.py, ...).
@limits.en   Only covers the metrics listed in METRICS_TO_CHECK (where the
             duplication was concretely demonstrated) -- not a global scan
             over all measurements metrics, to keep runtime manageable on a
             40+ million row table. HR-dependent compute/analysis scripts
             should be rerun afterwards (compute_orthostatic_detection.py,
             analyse_sleep_day_hr.py, compute_pem.py, ...).
@usage
    python3 scripts/migrations/dedupe_measurements_multi_device.py --dry-run
    python3 scripts/migrations/dedupe_measurements_multi_device.py

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

# Metriken, fuer die die Zwillings-device_id-Duplikation konkret nachgewiesen
# wurde (s. @purpose). Neue Metriken mit demselben Muster koennen ergaenzt
# werden, sobald sie geprueft sind.
METRICS_TO_CHECK = (
    "heart_rate", "steps", "body_mass", "body_weight", "weight_kg",
)


def _excess_count(conn, metric: str) -> int:
    row = conn.execute("""
        SELECT COALESCE(SUM(c - 1), 0) FROM (
            SELECT COUNT(*) AS c
            FROM measurements
            WHERE metric = ?
            GROUP BY person, metric, ts, value, value_text, source_app
            HAVING c > 1
        )
    """, (metric,)).fetchone()
    return row[0]


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Bereinigt Mehrfach-Geraete-Duplikate in measurements")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    args = ap.parse_args()

    try:
        conn = open_db()
    except Exception as exc:
        print(f"Fehler beim Öffnen der Datenbank: {exc}", file=sys.stderr)
        sys.exit(1)

    total_deleted = 0
    for metric in METRICS_TO_CHECK:
        excess = _excess_count(conn, metric)
        print(f"{metric}: {excess} Duplikat-Zeile(n) gefunden.")
        if excess == 0:
            continue
        if args.dry_run:
            total_deleted += excess
            continue
        conn.execute("""
            DELETE FROM measurements
            WHERE metric = ?
              AND rowid NOT IN (
                  SELECT MIN(rowid)
                  FROM measurements
                  WHERE metric = ?
                  GROUP BY person, metric, ts, value, value_text, source_app
              )
        """, (metric, metric))
        total_deleted += excess

    if not args.dry_run and total_deleted:
        # person=None explizit: die Duplikation stammt aus einer
        # Mehrgeraete-Zuordnungs-Eigenheit, nicht aus einem
        # personen-spezifischen Fehler.
        log_import(conn, "dedupe_measurements_multi_device", "measurements", 0,
                   total_deleted, person=None)
        conn.commit()

    print(f"{'Würde löschen' if args.dry_run else 'Gelöscht'}: {total_deleted} Zeile(n) insgesamt.")
    conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
