#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
rename_stale_garmin_sleep_ids.py — Rebuilds garmin_sleep session ids that
still embed the pre-migration person pseudonym

@tier        infrastructure
@purpose.de  import_garmin.py::import_sleep() baut die sessions.id als
             f"garmin_sleep_{date}_{PERSON}" — PERSON war zum Zeitpunkt des
             ursprünglichen Imports die damals gültige, ältere
             Person-Pseudonym-ID (P-F83C73A3), bevor sie auf die aktuelle
             (PER-16b249d1) migriert wurde. Die person-SPALTE wurde bei der
             Migration korrigiert, die in der id eingebettete alte
             Pseudonym-ID aber übersehen, da UPDATE-Anweisungen auf die
             person-Spalte die id-Zeichenkette nicht anfassen.
@purpose.en  import_garmin.py::import_sleep() builds sessions.id as
             f"garmin_sleep_{date}_{PERSON}" — PERSON at the time of the
             original import was the then-valid, older person pseudonym id
             (P-F83C73A3), before it was migrated to the current one
             (PER-16b249d1). The person COLUMN was corrected during that
             migration, but the old pseudonym id embedded in the id string
             was missed, since UPDATE statements on the person column don't
             touch the id string.
@method.de   Für jede sessions-Zeile mit id LIKE '%P-F83C73A3%': neue id mit
             der aktuellen Pseudonym-ID berechnen. Existiert die neue id noch
             nicht, wird umbenannt (id-Spalte + zugehörige
             session_metrics.session_id). Existiert sie bereits (ein späterer
             Re-Import hat die Zeile unter der korrekten id neu angelegt),
             werden die Metriken der alten Zeile per INSERT OR IGNORE in die
             bestehende gemergt und die alte Zeile gelöscht.
@method.en   For every sessions row with id LIKE '%P-F83C73A3%': compute the
             new id using the current pseudonym. If the new id doesn't exist
             yet, rename in place (id column + matching
             session_metrics.session_id). If it already exists (a later
             re-import created the row fresh under the correct id), the old
             row's metrics are merged into the existing one via INSERT OR
             IGNORE and the old row is deleted.
@reads       health.db (sessions, session_metrics)
@writes      health.db (sessions.id, session_metrics.session_id)
@relevance.de  Entfernt eine veraltete Personen-Pseudonym-ID aus
               Primärschlüssel-Strings — betrifft die Datenintegrität, nicht
               nur Kosmetik, da die id sonst zwei verschiedene Pseudonyme für
               dieselbe Person im selben Datensatz mischt
@relevance.en  Removes a stale person pseudonym id from primary-key strings —
               a data-integrity matter, not just cosmetic, since the id
               otherwise mixes two different pseudonyms for the same person
               within the same dataset
@limits.de   Betrifft nur sessions.id — falls andere Tabellen jemals direkt
             auf diese id-Strings verweisen sollten (aktuell nicht der Fall,
             s. grep vor Ausführung), wären die dort nicht mitkorrigiert.
@limits.en   Only affects sessions.id — if any other table were ever to
             reference these id strings directly (not currently the case, see
             grep before running), those would not be corrected here.
@usage
    python3 scripts/migrations/rename_stale_garmin_sleep_ids.py --dry-run
    python3 scripts/migrations/rename_stale_garmin_sleep_ids.py

Exit Codes:
    0: Lauf erfolgreich (auch wenn nichts zu tun war)
    1: Fehler beim Datenbankzugriff
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from health_config import OWN_PERSON_ID  # noqa: E402
from modules.base import log_import  # noqa: E402
from modules.db import open_db  # noqa: E402

STALE_FRAGMENT = "P-F83C73A3"


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Baut veraltete Personen-Pseudonym-IDs in garmin_sleep-session-ids um")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    args = ap.parse_args()

    try:
        conn = open_db()
    except Exception as exc:
        print(f"Fehler beim Öffnen der Datenbank: {exc}", file=sys.stderr)
        sys.exit(1)

    stale_rows = conn.execute(
        "SELECT id FROM sessions WHERE id LIKE ?", (f"%{STALE_FRAGMENT}%",)
    ).fetchall()

    renamed = merged = 0
    for (old_id,) in stale_rows:
        new_id = old_id.replace(STALE_FRAGMENT, OWN_PERSON_ID)
        collides = conn.execute("SELECT 1 FROM sessions WHERE id=?", (new_id,)).fetchone()

        if args.dry_run:
            print(f"  {'mergen' if collides else 'umbenennen'}: {old_id} → {new_id}")
            if collides:
                merged += 1
            else:
                renamed += 1
            continue

        if collides:
            for metric, value, value_text, unit in conn.execute(
                "SELECT metric, value, value_text, unit FROM session_metrics WHERE session_id=?", (old_id,)
            ).fetchall():
                conn.execute(
                    "INSERT OR IGNORE INTO session_metrics(session_id, metric, value, value_text, unit) "
                    "VALUES (?,?,?,?,?)", (new_id, metric, value, value_text, unit)
                )
            conn.execute("DELETE FROM session_metrics WHERE session_id=?", (old_id,))
            conn.execute("DELETE FROM sessions WHERE id=?", (old_id,))
            merged += 1
        else:
            conn.execute("UPDATE session_metrics SET session_id=? WHERE session_id=?", (new_id, old_id))
            conn.execute("UPDATE sessions SET id=? WHERE id=?", (new_id, old_id))
            renamed += 1

    if not args.dry_run and (renamed or merged):
        log_import(conn, "rename_stale_garmin_sleep_ids", "sessions", renamed, merged)
        conn.commit()

    print(f"{'Würde ' if args.dry_run else ''}{renamed} umbenannt, {merged} gemergt "
          f"(gesamt {renamed + merged} von {len(stale_rows)}).")
    conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
