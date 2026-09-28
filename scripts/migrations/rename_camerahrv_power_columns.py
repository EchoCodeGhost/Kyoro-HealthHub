#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
rename_camerahrv_power_columns.py — Renames camera_hrv_resting.lf_ms2/hf_ms2
to lf_power/hf_power (unit claim was wrong, not just cosmetic)

@tier        infrastructure
@purpose.de  import_camerahRV.py uebernahm LF/HF aus der App-CSV unveraendert
             und benannte die Zielspalten lf_ms2/hf_ms2, als waeren es
             absolute Leistungswerte in ms². Verifikation gegen einen echten
             All_Features.csv-Export zeigte: die Kopfzeile traegt gar keine
             Einheitenangabe, und die Werte sind rechnerisch normalisierte
             Anteile (ihr Verhaeltnis ergibt exakt die gemeldete LF/HF-Spalte),
             keine ms²-Rohleistung. Andere App-Versionen koennten echte
             ms²-Werte liefern — ohne Einheitenangabe in der Quelle ist das
             nicht unterscheidbar, daher benennt der Importer die Spalten
             jetzt ohne Einheitenclaim (lf_power/hf_power). Diese Migration
             zieht bereits importierte Datenbanken nach.
@purpose.en  import_camerahRV.py carried LF/HF over from the app CSV
             unchanged and named the target columns lf_ms2/hf_ms2, as if
             they were absolute power values in ms². Verification against a
             real All_Features.csv export showed: the header carries no unit
             label at all, and the values are arithmetically normalised
             proportions (their ratio equals the reported LF/HF column
             exactly), not ms² raw power. Other app versions might genuinely
             export ms² -- without a unit label in the source this can't be
             told apart, so the importer now names the columns without a
             unit claim (lf_power/hf_power). This migration brings already-
             imported databases in line.
@method.de   SQL-Spaltenumbenennung via RENAME COLUMN (SQLite >= 3.25) auf
             camera_hrv_resting. Idempotent: prueft vorher, ob lf_ms2/hf_ms2
             ueberhaupt noch existieren (No-Op, falls schon umbenannt oder
             Tabelle nicht vorhanden).
@method.en   SQL column rename via RENAME COLUMN (SQLite >= 3.25) on
             camera_hrv_resting. Idempotent: checks first whether lf_ms2/
             hf_ms2 still exist (no-op if already renamed or the table
             doesn't exist).
@reads       health.db (camera_hrv_resting schema)
@writes      health.db (camera_hrv_resting column names only, no row data changed)
@relevance.de  Korrigiert eine falsche Einheitenbehauptung im Spaltennamen —
               Datenintegritaet, nicht nur Kosmetik, da spaetere Auswertungen
               sonst ms² annehmen koennten, wo keine ms² vorliegen.
@relevance.en  Fixes an incorrect unit claim in the column name — a data-
               integrity matter, not just cosmetic, since later analyses
               could otherwise assume ms² where none is present.
@limits.de   Aendert nur Spaltennamen, keine Werte — falls eine Installation
             tatsaechlich echte ms²-Werte importiert hat (andere
             CameraHRV-App-Version), bleiben die Zahlen unveraendert richtig,
             nur der Spaltenname claimt jetzt keine Einheit mehr.
@limits.en   Renames columns only, no values change — if an installation
             genuinely imported real ms² values (different CameraHRV app
             version), the numbers remain correct, only the column name no
             longer claims a unit.
@usage
    python3 scripts/migrations/rename_camerahrv_power_columns.py --dry-run
    python3 scripts/migrations/rename_camerahrv_power_columns.py

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

RENAMES = [("lf_ms2", "lf_power"), ("hf_ms2", "hf_power")]


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Benennt camera_hrv_resting.lf_ms2/hf_ms2 in lf_power/hf_power um")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    args = ap.parse_args()

    try:
        conn = open_db()
    except Exception as exc:
        print(f"Fehler beim Öffnen der Datenbank: {exc}", file=sys.stderr)
        sys.exit(1)

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "camera_hrv_resting" not in tables:
        print("camera_hrv_resting existiert nicht — nichts zu tun.")
        conn.close()
        sys.exit(0)

    cols = {r[1] for r in conn.execute("PRAGMA table_info(camera_hrv_resting)")}
    todo = [(old, new) for old, new in RENAMES if old in cols]

    if not todo:
        print("Spalten bereits umbenannt (oder nie im alten Namen vorhanden) — nichts zu tun.")
        conn.close()
        sys.exit(0)

    for old, new in todo:
        print(f"  {'Würde umbenennen' if args.dry_run else 'Umbenennen'}: {old} → {new}")
        if not args.dry_run:
            conn.execute(f"ALTER TABLE camera_hrv_resting RENAME COLUMN {old} TO {new}")

    if not args.dry_run:
        log_import(conn, "rename_camerahrv_power_columns", "camera_hrv_resting",
                   len(todo), person=None)
        conn.commit()

    print(f"{'Würden' if args.dry_run else ''} {len(todo)} Spalte(n) umbenannt.")
    conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
