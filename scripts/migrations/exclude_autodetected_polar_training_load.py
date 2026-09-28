#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
exclude_autodetected_polar_training_load.py — Removes training_load from
already-imported Polar sessions that were automatically detected, not
manually started

@tier        infrastructure
@purpose.de  Wendet die in import_polar.py::import_polar_trainings() eingebaute
             Ausschluss-Logik (kein training_load für startTrigger=
             TRAINING_START_AUTOMATIC_TRAINING_DETECTION) nachträglich auf
             bereits importierte sessions-Zeilen an — die Importer-Änderung
             greift nur für künftige Läufe, bestehende Zeilen behalten ihren
             alten training_load-Wert, bis dieses Skript einmal läuft.
@purpose.en  Retroactively applies the exclusion logic now built into
             import_polar.py::import_polar_trainings() (no training_load for
             startTrigger=TRAINING_START_AUTOMATIC_TRAINING_DETECTION) to
             sessions rows imported before the fix — the importer change only
             affects future runs, existing rows keep their old training_load
             value until this script runs once.
@method.de   Liest jede training-session_*.json erneut, prüft
             is_polar_auto_detected(); wo True, wird die passende sessions-Zeile
             über (date, ts_start, ts_end) gesucht — nicht über die
             dateinamen-basierte id, die vor dem Identifier-Fix (s.
             import_polar.py::training_session_identifier) noch in der DB
             steht. Existiert dort eine training_load-Zeile in
             session_metrics, wird diese gelöscht und durch auto_detected=1.0
             ersetzt (Audit-Trail, warum training_load fehlt). Idempotent —
             bereits bereinigte Zeilen werden übersprungen.
@method.en   Re-reads every training-session_*.json, checks
             is_polar_auto_detected(); where True, looks up the matching
             sessions row via (date, ts_start, ts_end) — not the
             filename-based id still stored in the DB for rows imported
             before the identifier fix (see
             import_polar.py::training_session_identifier). Where a
             training_load row exists in session_metrics, it is deleted and
             replaced with auto_detected=1.0 (audit trail for why
             training_load is absent).
             Idempotent — already-cleaned rows are skipped.
@reads       {polar_dir}/training-session_*.json, sessions, session_metrics
@writes      health.db (DELETE training_load / INSERT auto_detected in
             session_metrics for auto-detected sessions)
@relevance.de  Verhindert, dass automatisch erkannte Alltagsaktivität als
               Sport-Trigger in abgeleitete Auswertungen (PEM Evidence Score)
               einfließt
@relevance.en  Prevents auto-detected everyday activity from feeding into
               derived analyses (PEM Evidence Score) as an exercise trigger
@limits.de   Betrifft nur type='training' AND source_app='polar_connect'.
             compute_pem.py (beide Modi) sollte danach neu berechnet werden.
@limits.en   Only affects type='training' AND source_app='polar_connect'.
             compute_pem.py (both modes) should be recomputed afterwards.
@usage
    python3 scripts/migrations/exclude_autodetected_polar_training_load.py --dry-run
    python3 scripts/migrations/exclude_autodetected_polar_training_load.py

Exit Codes:
    0: Lauf erfolgreich (auch wenn nichts zu tun war)
    1: Fehler beim Datenbankzugriff
"""

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.base import log_import  # noqa: E402
from modules.db import open_db  # noqa: E402
from importers.import_polar import (  # noqa: E402
    POLAR_DIR, TRAINING_SESSION_GLOB, is_polar_auto_detected,
)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Entfernt training_load bei bereits importierten, automatisch "
                    "erkannten Polar-Sessions")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    ap.add_argument("--polar-dir", default=None, type=Path,
                    help="Alternatives Polar-Exportverzeichnis (Default: konfigurierter polar_dir)")
    args = ap.parse_args()

    try:
        conn = open_db()
    except Exception as exc:
        print(f"Fehler beim Öffnen der Datenbank: {exc}", file=sys.stderr)
        sys.exit(1)

    effective_dir = args.polar_dir or POLAR_DIR
    cur = conn.cursor()

    cleaned = already_clean = no_session = not_auto = 0
    for f in sorted(glob.glob(str(effective_dir / TRAINING_SESSION_GLOB))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        if not is_polar_auto_detected(d):
            not_auto += 1
            continue

        # Zeitraum statt id als Suchschluessel: Sessions, die vor dem
        # Identifier-Fix (s. training_session_identifier) importiert wurden,
        # tragen noch die alte dateinamen-basierte id in der DB, nicht die
        # jetzt aus dieser JSON-Datei berechnete. ts_start/ts_end identifiziert
        # dieselbe physische Session unabhaengig vom ID-Schema (s. auch
        # dedupe_polar_training_sessions.py, das denselben Schluessel nutzt).
        start = d.get('startTime') or ''
        stop = d.get('stopTime')
        date_s = start[:10] if start else ''
        row = cur.execute("""
            SELECT id FROM sessions
            WHERE type='training' AND source_app='polar_connect'
              AND date=? AND ts_start=? AND (ts_end=? OR (ts_end IS NULL AND ? IS NULL))
        """, (date_s, start, stop, stop)).fetchone()
        if not row:
            no_session += 1
            continue
        sid = row[0]

        has_load = cur.execute(
            "SELECT 1 FROM session_metrics WHERE session_id=? AND metric='training_load'", (sid,)
        ).fetchone()
        if not has_load:
            already_clean += 1
            continue

        if args.dry_run:
            print(f"  würde bereinigen: {sid}")
            cleaned += 1
            continue

        cur.execute("DELETE FROM session_metrics WHERE session_id=? AND metric='training_load'", (sid,))
        cur.execute(
            "INSERT OR IGNORE INTO session_metrics(session_id, metric, value) VALUES (?,?,?)",
            (sid, "auto_detected", 1.0)
        )
        cleaned += 1

    if not args.dry_run and cleaned:
        log_import(conn, "exclude_autodetected_polar_training_load", "session_metrics",
                  0, cleaned)
        conn.commit()

    print(f"{'Würde bereinigen' if args.dry_run else 'Bereinigt'}: {cleaned} Session(en) "
          f"— {already_clean} bereits sauber, {no_session} ohne DB-Session, "
          f"{not_auto} nicht automatisch erkannt.")
    conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
