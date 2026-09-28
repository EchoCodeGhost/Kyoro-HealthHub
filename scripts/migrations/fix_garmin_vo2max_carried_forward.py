#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
fix_garmin_vo2max_carried_forward.py — Separates carried-forward Garmin
Connect VO2max rows from genuine estimate updates.

@tier        infrastructure
@purpose.de  import_garmin.py schrieb mostRecentVO2Max (den zuletzt
             ermittelten Schaetzwert) taeglich mit dem Abrufdatum. Jeder Tag
             ohne neue Schaetzung erschien dadurch als eigene Messung: ein
             unveraenderter Wert wirkte wie eine dichte Messreihe, und Zeilen
             spaeterer Abruftage trugen ein Datum, an dem Garmin nichts
             ermittelt hatte. Der Importer ist korrigiert (Datum aus
             calendarDate); diese Migration zieht bestehende Datenbanken nach.
@purpose.en  import_garmin.py wrote mostRecentVO2Max (the most recently
             determined estimate) daily under the fetch date. Every day without
             a new estimate therefore looked like a measurement of its own: an
             unchanged value looked like a dense series, and rows from later
             fetch days carried a date on which Garmin determined nothing. The
             importer is fixed (date from calendarDate); this migration brings
             existing databases in line.
@method.de   Je Person und Geraet werden die Zeilen metric='vo2max',
             source_app='garmin_connect' nach Datum sortiert. Die erste Zeile
             jeder Folge identischer Werte bleibt 'vo2max' (fruehester Tag, an
             dem der Wert sichtbar war); alle Folgezeilen derselben Folge werden
             in 'vo2max_carried_forward' umbenannt. Keine Werte geaendert, keine
             Zeilen geloescht. Einmalig: ein vorhandener import_log-Eintrag
             dieser Migration beendet jeden weiteren Lauf ohne Aenderung.
@method.en   Per person and device, rows with metric='vo2max',
             source_app='garmin_connect' are sorted by date. The first row of
             each run of identical values stays 'vo2max' (earliest day the value
             was visible); all later rows of the same run are renamed to
             'vo2max_carried_forward'. No values changed, no rows deleted.
             Runs once: an existing import_log entry of this migration ends any
             further run without changes.
@reads       health.db (measurements)
@writes      health.db (measurements.metric only)
@relevance.de  Verhindert, dass abgeleitete VO2max-Verlaeufe fortgeschriebene
               Werte als neue Messungen zaehlen — Datenqualitaet.
@relevance.en  Prevents derived VO2max trends from counting carried-forward
               values as new measurements — data quality.
@limits.de   Das Datum der verbleibenden Zeile ist eine Obergrenze: Garmin kann
             den Wert schon vor dem ersten Abruftag ermittelt haben. Ein
             Wertwechsel auf denselben Wert (z. B. neue Schaetzung = bisheriger Wert)
             ist nicht von einer Fortschreibung unterscheidbar und wird als
             Fortschreibung behandelt. Garmin-Datenschutz-Export (garmin_gdpr,
             biometricVo2Max) ist eine andere Schaetzung und bleibt unberuehrt.
@limits.en   The remaining row's date is an upper bound: Garmin may have
             determined the value before the first fetch day. A new estimate
             equal to the previous value cannot be distinguished from a
             carry-forward and is treated as one. The Garmin data export
             (garmin_gdpr, biometricVo2Max) is a different estimate and is left
             untouched.
@usage
    python3 scripts/migrations/fix_garmin_vo2max_carried_forward.py --dry-run
    python3 scripts/migrations/fix_garmin_vo2max_carried_forward.py

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

SOURCE_APP = "garmin_connect"
OLD_METRIC = "vo2max"
NEW_METRIC = "vo2max_carried_forward"
LOG_SOURCE = "migration_fix_garmin_vo2max_carried_forward"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Trennt fortgeschriebene Garmin-Connect-VO2max-Zeilen von echten Wertwechseln")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    args = ap.parse_args()

    try:
        conn = open_db()
    except Exception as exc:
        print(f"Fehler beim Öffnen der Datenbank: {exc}", file=sys.stderr)
        sys.exit(1)

    # Einmalig: der korrigierte Importer schreibt kuenftige Schaetzungen mit ihrem
    # calendarDate — auch eine neue Schaetzung mit gleichem Wert. Ein zweiter Lauf
    # koennte die nicht von einer Fortschreibung unterscheiden und wuerde echte
    # Aktualisierungen umbenennen. Der import_log-Eintrag des ersten Laufs sperrt das.
    done = conn.execute(
        "SELECT 1 FROM import_log WHERE source=? LIMIT 1", (LOG_SOURCE,)
    ).fetchone()
    if done:
        print("  Bereits angewendet (import_log) — nichts zu tun.")
        conn.close()
        return

    rows = conn.execute(
        "SELECT rowid, person, device_id, date, value FROM measurements "
        "WHERE metric=? AND source_app=? ORDER BY person, device_id, date, ts",
        (OLD_METRIC, SOURCE_APP),
    ).fetchall()

    carried = []
    prev_key, prev_val = None, None
    for rowid, person, device_id, _date, value in rows:
        key = (person, device_id)
        if key == prev_key and value == prev_val:
            carried.append(rowid)
        prev_key, prev_val = key, value

    kept = len(rows) - len(carried)
    verb = "Würde umbenennen" if args.dry_run else "Umbenennen"
    print(f"  {verb}: {len(carried)} von {len(rows)} Zeile(n) '{OLD_METRIC}' → '{NEW_METRIC}' "
          f"(source_app='{SOURCE_APP}'); {kept} Wertwechsel bleiben '{OLD_METRIC}'.")

    if args.dry_run or not carried:
        conn.close()
        return

    conn.executemany(
        "UPDATE measurements SET metric=? WHERE rowid=?",
        [(NEW_METRIC, rid) for rid in carried],
    )
    log_import(conn, LOG_SOURCE, "", len(carried))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
