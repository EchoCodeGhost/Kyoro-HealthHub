#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
backfill_garmin_training_load.py — Adds training_load to already-imported
Garmin activities and resolves cross-device priority against Polar/Oura

@tier        infrastructure
@purpose.de  Wendet die in import_garmin.py::import_activities() eingebaute
             training_load-Ableitung (aus aerobic/anaerobic Training Effect)
             und die Quellen-Prioritätsauflösung (s. claim_training_load_slot,
             modules/base.py — Garmin schlägt Polar/Oura bei Überlappung)
             nachträglich auf bereits importierte Garmin-Sessions an. Die
             Importer-Änderung greift nur für künftige Läufe.
@purpose.en  Retroactively applies the training_load derivation now built into
             import_garmin.py::import_activities() (from aerobic/anaerobic
             Training Effect) and the source priority resolution (see
             claim_training_load_slot, modules/base.py — Garmin beats Polar/
             Oura on overlap) to already-imported Garmin sessions. The
             importer change only affects future runs.
@method.de   Liest jede type='training' AND source_app='garmin_connect'
             Session ohne generische 'other'-Sportart, holt
             aerobic_training_effect/anaerobic_training_effect aus
             session_metrics, ruft claim_training_load_slot auf (verdrängt
             dabei ggf. training_load einer überlappenden, niedriger
             priorisierten Polar-/Oura-Session) und schreibt training_load.
             Idempotent — Sessions mit bereits gesetztem training_load werden
             übersprungen.
@method.en   Reads every type='training' AND source_app='garmin_connect'
             session without a generic 'other' sport, fetches
             aerobic_training_effect/anaerobic_training_effect from
             session_metrics, calls claim_training_load_slot (which may evict
             training_load from an overlapping, lower-priority Polar/Oura
             session), and writes training_load. Idempotent — sessions with
             training_load already set are skipped.
@reads       health.db (sessions, session_metrics)
@writes      health.db (session_metrics.training_load for Garmin sessions;
             possibly DELETEs training_load from lower-priority overlapping
             Polar/Oura sessions via claim_training_load_slot)
@relevance.de  Stellt sicher, dass bereits vor diesem Fix importierte
               Garmin-Aktivitäten denselben Sport-Trigger-Status bekommen wie
               künftig importierte
@relevance.en  Ensures Garmin activities imported before this fix get the
               same exercise-trigger status as future imports
@limits.de   Betrifft nur type='training' AND source_app='garmin_connect'.
             compute_pem.py (beide Modi) sollte danach neu berechnet werden.
@limits.en   Only affects type='training' AND source_app='garmin_connect'.
             compute_pem.py (both modes) should be recomputed afterwards.
@usage
    python3 scripts/migrations/backfill_garmin_training_load.py --dry-run
    python3 scripts/migrations/backfill_garmin_training_load.py

Exit Codes:
    0: Lauf erfolgreich (auch wenn nichts zu tun war)
    1: Fehler beim Datenbankzugriff
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.base import claim_training_load_slot, log_import  # noqa: E402
from modules.db import open_db  # noqa: E402
from health_config import OWN_PERSON_ID  # noqa: E402
from importers.import_garmin import (  # noqa: E402
    GARMIN_NON_SPORT_ACTIVITIES, SOURCE, _garmin_training_load,
)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Traegt training_load fuer bereits importierte Garmin-Aktivitaeten nach")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    args = ap.parse_args()

    try:
        conn = open_db()
    except Exception as exc:
        print(f"Fehler beim Öffnen der Datenbank: {exc}", file=sys.stderr)
        sys.exit(1)

    rows = conn.execute("""
        SELECT id, date, ts_start, ts_end, sport FROM sessions
        WHERE type='training' AND source_app=? AND person=?
    """, (SOURCE, OWN_PERSON_ID)).fetchall()

    filled = skipped_sport = skipped_has_load = skipped_no_effect = blocked = 0
    for sid, date, ts_start, ts_end, sport in rows:
        if (sport or "").lower() in GARMIN_NON_SPORT_ACTIVITIES:
            skipped_sport += 1
            continue
        if conn.execute(
            "SELECT 1 FROM session_metrics WHERE session_id=? AND metric='training_load'", (sid,)
        ).fetchone():
            skipped_has_load += 1
            continue

        aerobic = conn.execute(
            "SELECT value FROM session_metrics WHERE session_id=? AND metric='aerobic_training_effect'", (sid,)
        ).fetchone()
        anaerobic = conn.execute(
            "SELECT value FROM session_metrics WHERE session_id=? AND metric='anaerobic_training_effect'", (sid,)
        ).fetchone()
        load = _garmin_training_load(aerobic[0] if aerobic else None,
                                      anaerobic[0] if anaerobic else None)
        if not load:
            skipped_no_effect += 1
            continue

        if args.dry_run:
            print(f"  würde befüllen: {sid} training_load={load}")
            filled += 1
            continue

        if not claim_training_load_slot(conn, OWN_PERSON_ID, sid, SOURCE, date, ts_start, ts_end):
            blocked += 1
            continue

        conn.execute(
            "INSERT OR IGNORE INTO session_metrics(session_id, metric, value) VALUES (?,?,?)",
            (sid, "training_load", load)
        )
        filled += 1

    if not args.dry_run and filled:
        log_import(conn, "backfill_garmin_training_load", "session_metrics", filled)
        conn.commit()

    print(f"{'Würde befüllen' if args.dry_run else 'Befüllt'}: {filled} — "
          f"{skipped_sport} generische Sportart, {skipped_has_load} bereits gesetzt, "
          f"{skipped_no_effect} ohne Trainingseffekt-Wert, {blocked} von höher priorisierter Quelle blockiert.")
    conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
