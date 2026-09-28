#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
6-Minuten-Gehtest (6MWT) → health.db

@tier        infrastructure
@purpose.de  Importiert Ergebnisse des 6-Minuten-Gehtests (6MWT) als standardisiertes
             Outcome-Maß für ME/CFS, Long COVID und Herzinsuffizienz. Monatliche
             Durchführung zeigt funktionale Kapazität im Verlauf.
@purpose.en  Imports results of the 6-Minute Walk Test (6MWT) as a standardized
             outcome measure for ME/CFS, Long COVID, and heart failure. Monthly
             execution shows functional capacity over time.
@method.de   Protokoll nach ATS 2002 Standard (modifiziert für Heimgebrauch):
             1) 10 min Sitzen → Ruhe-HR, SpO2, Borg messen
             2) 6 Minuten gehen (flacher Untergrund)
             3) Pausen erlaubt (Zeit läuft weiter, Stopps dokumentieren)
             4) Nach 6 min: Distanz, HR, SpO2, Borg erfassen
             5) 1 min Sitzen: Erholungs-HR messen
             CSV-Format: ts,distance_m,hr_rest,hr_peak,hr_recovery,spo2_pre,
             spo2_post,borg_pre,borg_post,stops,notes
@method.en   Protocol according to ATS 2002 standard (modified for home use):
             1) Sit for 10 min → measure resting HR, SpO2, Borg
             2) Walk as far as possible in 6 minutes (flat surface)
             3) Breaks allowed (time continues, stops documented)
             4) After 6 min: measure distance, HR, SpO2, Borg
             5) Sit for 1 min: measure recovery HR
             CSV format: ts,distance_m,hr_rest,hr_peak,hr_recovery,spo2_pre,
             spo2_post,borg_pre,borg_post,stops,notes
@reads       {imports/6mwt/}*.csv (6MWT Ergebnisse)
@writes      health.db (functional_tests)
@refs        American Thoracic Society (2002). ATS Statement: Guidelines for the Six-Minute Walk Test. American Journal of Respiratory and Critical Care Medicine, 166(1):111-117. doi:10.1164/ajrccm.166.1.at1102


@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.de   Keine automatische Bewertung der 6MWT-Ergebnisse. Referenzwerte
             dienen nur zur Orientierung. Keine medizinische Diagnose.
@limits.en   No automatic evaluation of 6MWT results. Reference values are for
             orientation only. No medical diagnosis.
@usage
    python3 import_6mwt.py                    # alle CSVs
    python3 import_6mwt.py --manual           # interaktive Eingabe
    python3 import_6mwt.py --template         # CSV-Vorlage ausgeben
    python3 import_6mwt.py --file test.csv    # einzelne Datei
"""

import argparse
import csv
import sqlite3
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db, DB_ERRORS
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import
_cfg = _Cfg()

DB_PATH = _cfg.db_path
CSV_DIR = Path(_cfg._cfg.get("paths", {}).get("sixmwt_dir",
          str(Path.home() / "Kyoro-HealthHub" / "imports" / "6mwt")))
CSV_DIR.mkdir(parents=True, exist_ok=True)

# Referenzwert (ATS-Formel für Frauen): 2,11 × Körpergröße (cm) – 2,29 × Gewicht (kg) – 5,78 × Alter + 667
# Ohne Angaben verwenden wir ~560 m als Richtwert für gesunde 40-J-Frau, ~170 cm, 75 kg
REFERENCE_HEALTHY = 560.0

CSV_TEMPLATE = """\
# 6-Minuten-Gehtest (6MWT) — CSV-Vorlage
# Protokoll: 10 min sitzen → 6 min gehen → 1 min sitzen (Erholung)
# Spalten: ts,distance_m,hr_rest,hr_peak,hr_recovery,spo2_pre,spo2_post,borg_pre,borg_post,stops,notes
#
# ts          : YYYY-MM-DDTHH:MM:SS (Testbeginn)
# distance_m  : Zurückgelegte Strecke in Metern
# hr_rest     : Ruhe-HR vor Test (bpm)
# hr_peak     : höchste HR während Test (bpm)
# hr_recovery : HR nach 1 min Pause (bpm)
# spo2_pre    : SpO2 vor Test (%)
# spo2_post   : SpO2 direkt nach Test (%)
# borg_pre    : Borg-RPE vor Test (6=keine Anstrengung, 20=Maximal)
# borg_post   : Borg-RPE direkt nach Test
# stops       : Anzahl der Pausen während 6 min
# notes       : Freitext (Ort, Strecke, Besonderheiten)
#
ts,distance_m,hr_rest,hr_peak,hr_recovery,spo2_pre,spo2_post,borg_pre,borg_post,stops,notes
"""

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS functional_tests (
    ts          TEXT NOT NULL,
    date        TEXT NOT NULL,
    test_type   TEXT NOT NULL,
    distance_m  REAL,
    hr_rest     REAL,
    hr_peak     REAL,
    hr_recovery REAL,
    spo2_pre    REAL,
    spo2_post   REAL,
    borg_pre    INTEGER,
    borg_post   INTEGER,
    duration_s  INTEGER,
    stops       INTEGER,
    session_id  INTEGER,
    notes       TEXT,
    person      TEXT NOT NULL DEFAULT 'unknown',
    source      TEXT,
    PRIMARY KEY (ts, test_type, person)
)
"""


def _parse_row(row: dict) -> dict | None:
    ts = row.get("ts", "").strip()
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        print(t(f"  Ungültiges Datum: {ts}", f"  Invalid date: {ts}"))
        return None

    def _f(k):
        v = row.get(k, "").strip()
        return float(v) if v else None

    def _i(k):
        v = row.get(k, "").strip()
        return int(v) if v else None

    return {
        "ts":          ts,
        "date":        dt.strftime("%Y-%m-%d"),
        "test_type":   "6mwt",
        "distance_m":  _f("distance_m"),
        "hr_rest":     _f("hr_rest"),
        "hr_peak":     _f("hr_peak"),
        "hr_recovery": _f("hr_recovery"),
        "spo2_pre":    _f("spo2_pre"),
        "spo2_post":   _f("spo2_post"),
        "borg_pre":    _i("borg_pre"),
        "borg_post":   _i("borg_post"),
        "duration_s":  360,
        "stops":       _i("stops"),
        "notes":       row.get("notes", "").strip() or None,
    }


def _percent_predicted(dist_m: float | None) -> str:
    if dist_m is None:
        return ""
    pct = dist_m / REFERENCE_HEALTHY * 100
    if pct >= 80:
        label = t("normal", "normal")
    elif pct >= 60:
        label = t("leicht eingeschränkt", "mildly impaired")
    elif pct >= 40:
        label = t("mäßig eingeschränkt", "moderately impaired")
    else:
        label = t("stark eingeschränkt", "severely impaired")
    return t(f"{pct:.0f}% des Referenzwerts ({label})",
             f"{pct:.0f}% of reference ({label})")


def _insert(conn: sqlite3.Connection, rec: dict, person: str, source: str) -> bool:
    try:
        conn.execute("""
            INSERT OR IGNORE INTO functional_tests
            (ts, date, test_type, distance_m, hr_rest, hr_peak, hr_recovery,
             spo2_pre, spo2_post, borg_pre, borg_post, duration_s, stops,
             session_id, notes, person, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            rec["ts"], rec["date"], rec["test_type"],
            rec.get("distance_m"), rec.get("hr_rest"), rec.get("hr_peak"),
            rec.get("hr_recovery"), rec.get("spo2_pre"), rec.get("spo2_post"),
            rec.get("borg_pre"), rec.get("borg_post"),
            rec.get("duration_s", 360), rec.get("stops"),
            rec.get("session_id"), rec.get("notes"),
            person, source,
        ))
        inserted = conn.total_changes > 0
        if inserted and rec.get("notes"):
            conn.execute(
                "INSERT OR IGNORE INTO user_context"
                " (id, date, ts_start, ts_end, person, source, source_app, tag, note)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (f"6mwt:{rec['ts']}", rec["date"], rec["ts"], None,
                 person, '6mwt', '6mwt', rec.get("test_type"), rec["notes"]),
            )
        return inserted
    except DB_ERRORS as e:
        print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))
        return False


def _import_csv(conn, path, person, source):
    inserted = skipped = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(row for row in f if not row.startswith("#"))
        for row in reader:
            rec = _parse_row(row)
            if rec is None:
                skipped += 1
                continue
            if _insert(conn, rec, person, source):
                inserted += 1
                pct = _percent_predicted(rec.get("distance_m"))
                dist = rec.get("distance_m")
                print(t(f"    {rec['date']}  {dist} m  {pct}",
                        f"    {rec['date']}  {dist} m  {pct}"))
            else:
                skipped += 1
    return inserted, skipped


def _manual_entry(conn, person):
    print(t("\n── 6-Minuten-Gehtest Eingabe ───────────────────────────────────",
            "\n── 6-Minute Walk Test Entry ────────────────────────────────────"))
    ts_str = input(t("Testbeginn (YYYY-MM-DDTHH:MM, Enter=jetzt): ",
                     "Test start (YYYY-MM-DDTHH:MM, Enter=now): ")).strip()
    if not ts_str:
        ts_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    elif len(ts_str) == 16:
        ts_str += ":00"

    def ask(label, cast=float):
        v = input(t(f"  {label} (leer=unbekannt): ", f"  {label} (empty=unknown): ")).strip()
        try:
            return cast(v) if v else None
        except (ValueError, TypeError):
            return None

    rec = {
        "ts":          ts_str,
        "date":        ts_str[:10],
        "test_type":   "6mwt",
        "distance_m":  ask("Gehstrecke in Metern"),
        "hr_rest":     ask("Ruhe-HR vor Test (bpm)"),
        "hr_peak":     ask("Peak-HR während Test (bpm)"),
        "hr_recovery": ask("HR nach 1 min Pause (bpm)"),
        "spo2_pre":    ask("SpO2 vor Test (%)"),
        "spo2_post":   ask("SpO2 nach Test (%)"),
        "borg_pre":    ask("Borg-Skala vor Test (6–20)", int),
        "borg_post":   ask("Borg-Skala nach Test (6–20)", int),
        "duration_s":  360,
        "stops":       ask("Anzahl Pausen", int),
        "notes":       input(t("Notizen (Ort, Strecke, ...): ", "Notes (location, route, ...): ")).strip() or None,
    }
    if _insert(conn, rec, person, "manual"):
        pct = _percent_predicted(rec.get("distance_m"))
        print(t(f"  ✓ {rec['distance_m']} m gespeichert  {pct}",
                f"  ✓ {rec['distance_m']} m saved  {pct}"))
        conn.commit()
    else:
        print(t("  Bereits vorhanden oder Fehler.", "  Already exists or error."))


def main():
    """
    Hauptfunktion: Koordiniert den Import der 6MWT-Daten.

    Command-Line-Argumente:
        --manual: Interaktive Eingabe
        --template: CSV-Vorlage ausgeben
        --file: Einzelne CSV-Datei
        --person: Personen-ID
    """
    parser = argparse.ArgumentParser(
        description=t("6-Minuten-Gehtest importieren", "Import 6-minute walk test"))
    parser.add_argument("--manual",   action="store_true")
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--file",     type=str, default=None)
    parser.add_argument("--person",   type=str, default=None)
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.template:
        print(CSV_TEMPLATE)
        return

    person = args.person or OWN_PERSON_ID
    conn   = open_db()
    conn.execute(CREATE_TABLE_SQL)

    if args.manual:
        _manual_entry(conn, person)
        conn.close()
        return

    files = [Path(args.file)] if args.file else sorted(CSV_DIR.glob("*.csv"))
    if not files:
        print(t(f"Keine CSV-Dateien in {CSV_DIR}. Vorlage: --template",
                f"No CSV files in {CSV_DIR}. Template: --template"))
        conn.close()
        return

    total_ins = total_skip = 0
    for f in files:
        ins, skip = _import_csv(conn, f, person, "csv")
        total_ins += ins
        total_skip += skip
        print(t(f"  {f.name}: {ins} neu, {skip} übersprungen",
                f"  {f.name}: {ins} new, {skip} skipped"))

    log_import(conn, '6mwt', str(CSV_DIR), total_ins, total_skip)
    conn.commit()
    conn.close()
    print(t(f"\n6MWT: {total_ins} Tests importiert, {total_skip} übersprungen.",
            f"\n6MWT: {total_ins} tests imported, {total_skip} skipped."))


if __name__ == "__main__":
    main()
