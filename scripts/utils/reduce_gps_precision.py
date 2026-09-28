#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
reduce_gps_precision — Rundet nachträglich zu hochauflösende GPS-Punkte in session_tracks

@tier        infrastructure
@purpose.de  Rundet bestehende `session_tracks`-Koordinaten mit mehr als 5 Nachkommastellen
             auf 5 Nachkommastellen (~1,1 m Raster) herab. Neue Importe runden bereits beim
             Schreiben (siehe `import_tracks.py`, `round_coords(..., precision=5)`); dieses
             Skript schließt die Lücke für Altdaten, die vor Einführung des Roundings oder
             über einen Pfad ohne `round_coords()`-Aufruf importiert wurden.
@purpose.en  Rounds down existing `session_tracks` coordinates with more than 5 decimal
             places to 5 decimal places (~1.1m grid). New imports already round at write
             time (see `import_tracks.py`, `round_coords(..., precision=5)`); this script
             closes the gap for legacy data imported before rounding was introduced or via
             a path that skipped `round_coords()`.
@method.de   Identifiziert betroffene Zeilen mit derselben SQL-Bedingung wie
             `check_anonymization_compliance()` (utils/anonymize.py, `high_precision_gps`),
             rundet lat/lon via `round_coords(precision=5)` und schreibt sie zurück.
             Erstellt vor Änderungen ein Rolling-Backup der DB-Datei (überschrieben bei
             jedem Lauf), analog zu `scrub_pii.py`.
@method.en   Identifies affected rows using the same SQL condition as
             `check_anonymization_compliance()` (utils/anonymize.py, `high_precision_gps`),
             rounds lat/lon via `round_coords(precision=5)` and writes them back. Creates a
             rolling backup of the DB file before changes (overwritten on each run),
             analogous to `scrub_pii.py`.
@reads       session_tracks (lat, lon)
@writes      session_tracks (lat, lon gerundet), health.db.gps_precision_backup (Rolling-Backup)
@limits.de   Behandelt nur `session_tracks` — die einzige Tabelle, die
             `check_anonymization_compliance()` auf GPS-Präzision prüft. Andere Tabellen mit
             lat/lon-Spalten (z.B. `location_history`) sind nicht Teil dieses Checks und
             werden hier nicht behandelt.

@relevance.de  Bietet Hilfsfunktionen für die Datenverarbeitung, essentiell für die Systemfunktionalität
@relevance.en  Provides utility functions for data processing, essential for system functionality
@limits.en   Only handles `session_tracks` — the only table
             `check_anonymization_compliance()` checks for GPS precision. Other tables with
             lat/lon columns (e.g. `location_history`) are not part of that check and are
             not touched here.
@usage
    python scripts/utils/reduce_gps_precision.py --dry-run
    python scripts/utils/reduce_gps_precision.py
    python scripts/utils/reduce_gps_precision.py --no-backup
"""

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config
from modules.db import open_db
from utils.anonymize import round_coords
from modules.i18n import t, add_lang_arg, apply_lang_from_args

_PRECISION = 5

# Gleiche Bedingung wie check_anonymization_compliance() (utils/anonymize.py,
# high_precision_gps) — mehr als 5 Nachkommastellen.
_HIGH_PRECISION_WHERE = """
    lat IS NOT NULL AND lon IS NOT NULL
    AND (LENGTH(CAST(lat AS TEXT)) - INSTR(CAST(lat AS TEXT), '.') > 6
         OR LENGTH(CAST(lon AS TEXT)) - INSTR(CAST(lon AS TEXT), '.') > 6)
"""


def main():
    parser = argparse.ArgumentParser(
        description=t("Rundet zu hochauflösende GPS-Punkte in session_tracks nachträglich",
                      "Retroactively rounds overly precise GPS points in session_tracks"))
    parser.add_argument("--dry-run", action="store_true",
                        help=t("Zeigt Änderungen ohne sie durchzuführen",
                               "Show changes without applying them"))
    parser.add_argument("--no-backup", action="store_true",
                        help=t("Kein Backup erstellen", "Do not create a backup"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    cfg = Config()
    db_path = cfg.db_path

    if not args.no_backup and not args.dry_run:
        backup_path = db_path.with_suffix(".gps_precision_backup")
        shutil.copy2(db_path, backup_path)
        print(t(f"Backup: {backup_path}", f"Backup: {backup_path}"))

    conn = open_db()
    rows = conn.execute(
        f"SELECT session_id, ts, lat, lon FROM session_tracks WHERE {_HIGH_PRECISION_WHERE}"
    ).fetchall()

    if not rows:
        print(t("Keine zu hochauflösenden GPS-Punkte gefunden.",
                "No overly precise GPS points found."))
        conn.close()
        return

    print(t(f"{len(rows)} Punkte mit mehr als {_PRECISION} Nachkommastellen gefunden.",
            f"{len(rows)} points with more than {_PRECISION} decimal places found."))

    if args.dry_run:
        for session_id, ts, lat, lon in rows[:10]:
            r_lat, r_lon = round_coords(lat, lon, precision=_PRECISION)
            print(f"  {session_id} {ts}: ({lat}, {lon}) → ({r_lat}, {r_lon})")
        if len(rows) > 10:
            print(t(f"  … und {len(rows) - 10} weitere",
                    f"  … and {len(rows) - 10} more"))
        print(t("Dry-Run — keine Änderungen geschrieben.",
                "Dry run — no changes written."))
        conn.close()
        return

    for session_id, ts, lat, lon in rows:
        r_lat, r_lon = round_coords(lat, lon, precision=_PRECISION)
        conn.execute(
            "UPDATE session_tracks SET lat=?, lon=? WHERE session_id=? AND ts=?",
            (r_lat, r_lon, session_id, ts),
        )
    conn.commit()
    conn.close()
    print(t(f"✓ {len(rows)} Punkte gerundet.", f"✓ {len(rows)} points rounded."))


if __name__ == "__main__":
    main()
