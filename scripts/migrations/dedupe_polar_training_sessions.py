#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
dedupe_polar_training_sessions.py — Removes duplicate and phantom Polar
training sessions created by two bugs fixed in import_polar.py

@tier        infrastructure
@purpose.de  Bereinigt `sessions`-Zeilen (type='training', source_app='polar_connect')
             aus zwei behobenen Import-Bugs: (1) Duplikate, weil die Session-ID
             bislang aus dem Dateinamen statt der stabilen Polar-`identifier.id`
             gebildet wurde (s. import_polar.py::training_session_identifier) —
             jeder Re-Sync/Re-Export desselben physischen Trainings erzeugte
             einen neuen Dateinamen und damit eine neue sessions-Zeile,
             INSERT OR IGNORE griff nicht, weil die IDs verschieden waren.
             (2) Phantom-Zeilen aus training-target-*.json — geplante, laut
             eigenem 'done': false NIE durchgeführte Trainingsziele aus Polars
             Trainingstagebuch, die der frühere zu breite Datei-Glob
             ('training*.json') ebenfalls als echte Sessions importierte.
@purpose.en  Cleans up `sessions` rows (type='training', source_app='polar_connect')
             from two fixed import bugs: (1) duplicates, because the session ID
             used to be derived from the filename instead of the stable Polar
             `identifier.id` (see import_polar.py::training_session_identifier)
             — every re-sync/re-export of the same physical training produced
             a new filename and therefore a new sessions row, INSERT OR IGNORE
             never caught it because the IDs differed. (2) phantom rows from
             training-target-*.json — planned, per their own 'done': false
             NEVER completed workout targets from Polar's training diary,
             which the previously too-broad file glob ('training*.json') also
             imported as if they were real sessions.
@method.de   Phase 1: löscht alle Zeilen mit id LIKE 'polar_training_training-target-%'
             (immer training_load=NULL, kein stopTime/deviceId — nie echte
             Ereignisse). Phase 2: gruppiert die verbleibenden Zeilen nach
             (person, date, ts_start, ts_end) — zwei real unabhängige
             Trainings starten und enden nicht auf dieselbe Sekunde, das ist
             ein robuster Duplikat-Schlüssel. Aus jeder Gruppe (>1 Zeile) wird
             eine Zeile behalten (bevorzugt: device_id beginnt mit 'DEV-',
             sonst kleinste id als deterministischer Tie-Breaker), die übrigen
             inkl. ihrer session_metrics gelöscht.
@method.en   Phase 1: deletes all rows with id LIKE 'polar_training_training-target-%'
             (always training_load=NULL, no stopTime/deviceId — never real
             events). Phase 2: groups the remaining rows by (person, date,
             ts_start, ts_end) — two genuinely independent trainings do not
             start and end on the exact same second, making this a robust
             duplicate key. From each group (>1 row) one row is kept
             (preferring a device_id starting with 'DEV-', otherwise the
             smallest id as a deterministic tie-breaker); the rest, including
             their session_metrics, are deleted.
@reads       health.db (sessions, session_metrics)
@writes      health.db (DELETE auf sessions + session_metrics für Duplikat- und
             Phantom-Zeilen)
@relevance.de  Bereinigt aufgeblähte Trainings-Auslöser (training_load), die in
               abgeleitete Auswertungen wie den PEM Evidence Score einfließen
@relevance.en  Cleans up inflated training triggers (training_load) that feed
               into derived analyses such as the PEM Evidence Score
@limits.de   Betrifft nur type='training' AND source_app='polar_connect' —
             andere Quellen (Apple Health etc.) nutzen eine andere ID-Bildung
             und sind von den behobenen Bugs nicht betroffen. Nach dem Lauf
             sollte compute_pem.py (beide Modi) neu berechnet werden, da tl_d
             (SUM(training_load) pro Tag) sich ändern kann.
@limits.en   Only affects type='training' AND source_app='polar_connect' —
             other sources (Apple Health etc.) use different ID generation and
             are unaffected by the fixed bugs. compute_pem.py (both modes)
             should be recomputed afterwards, since tl_d (SUM(training_load)
             per day) can change.
@usage
    python3 scripts/migrations/dedupe_polar_training_sessions.py --dry-run
    python3 scripts/migrations/dedupe_polar_training_sessions.py

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


def _phantom_target_ids(conn) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT id FROM sessions WHERE id LIKE 'polar_training_training-target-%'"
    )]


_NOT_PHANTOM = "id NOT LIKE 'polar_training_training-target-%'"


def _duplicate_groups(conn) -> list[tuple]:
    return list(conn.execute(f"""
        SELECT person, date, ts_start, ts_end
        FROM sessions
        WHERE type='training' AND source_app='polar_connect' AND {_NOT_PHANTOM}
        GROUP BY person, date, ts_start, ts_end
        HAVING COUNT(*) > 1
    """))


def _rows_in_group(conn, person: str, date: str, ts_start: str, ts_end) -> list[str]:
    rows = conn.execute(f"""
        SELECT id, device_id FROM sessions
        WHERE type='training' AND source_app='polar_connect' AND {_NOT_PHANTOM}
          AND person=? AND date=? AND ts_start=?
          AND (ts_end=? OR (ts_end IS NULL AND ? IS NULL))
    """, (person, date, ts_start, ts_end, ts_end)).fetchall()
    # Bevorzugt: device_id beginnt mit 'DEV-' (aufgelöstes Pseudonym), dann
    # kleinste id als deterministischer Tie-Breaker.
    rows.sort(key=lambda r: (0 if (r[1] or "").startswith("DEV-") else 1, r[0]))
    return [r[0] for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Bereinigt doppelt importierte Polar-Trainingssessions")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    args = ap.parse_args()

    try:
        conn = open_db()
    except Exception as exc:
        print(f"Fehler beim Öffnen der Datenbank: {exc}", file=sys.stderr)
        sys.exit(1)

    # Phase 1: training-target-Phantomzeilen — immer und vollstaendig entfernen,
    # nicht nur ihre Duplikate.
    phantom_ids = _phantom_target_ids(conn)
    print(f"{len(phantom_ids)} training-target-Phantomzeile(n) gefunden.")
    if not args.dry_run:
        for sid in phantom_ids:
            conn.execute("DELETE FROM session_metrics WHERE session_id=?", (sid,))
            conn.execute("DELETE FROM sessions WHERE id=?", (sid,))

    # Phase 2: Duplikat-Gruppen unter den verbleibenden echten Sessions.
    groups = _duplicate_groups(conn)
    print(f"{len(groups)} Duplikat-Gruppen gefunden.")

    total_deleted_dupes = 0
    for person, date, ts_start, ts_end in groups:
        ids = _rows_in_group(conn, person, date, ts_start, ts_end)
        keep, drop = ids[0], ids[1:]
        if args.dry_run:
            print(f"  {date} {ts_start}: behalte {keep}, lösche {len(drop)}")
            total_deleted_dupes += len(drop)
            continue
        for sid in drop:
            conn.execute("DELETE FROM session_metrics WHERE session_id=?", (sid,))
            conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
        total_deleted_dupes += len(drop)

    total_deleted = len(phantom_ids) + total_deleted_dupes
    if not args.dry_run:
        # person=None explizit: die betroffenen Zeilen stammen aus zwei
        # Import-Bugs, die unabhaengig von der einzelnen Person sind — analog
        # zu dedupe_plaintext_device_ids.py.
        log_import(conn, "dedupe_polar_training_sessions", "sessions", 0,
                   total_deleted, person=None)
        conn.commit()

    print(f"{'Würde löschen' if args.dry_run else 'Gelöscht'}: {len(phantom_ids)} Phantom-Zeile(n) + "
          f"{total_deleted_dupes} Duplikat-Zeile(n) aus {len(groups)} Gruppe(n) "
          f"(gesamt {total_deleted}).")
    conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
