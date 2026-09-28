#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Orthostatik-Protokoll (kurz + voll) → health.db (sessions + session_metrics)

@tier        infrastructure
@purpose.de  Importiert manuell erfasste Orthostatik-Protokolle in zwei
             Varianten: kurzes Morning-Routine-Protokoll (HR-only) und
             volles Schellong-/NASA-Lean-Test-Protokoll (HR + Blutdruck,
             0/1/2/3/5/7/10 min stehend, siehe docs/test_protocols/ORTHOSTATIC_TEST_PROTOCOL.md).
@purpose.en  Imports manually recorded orthostatic protocols in two variants:
             short morning-routine protocol (HR-only) and full Schellong/NASA
             Lean Test protocol (HR + blood pressure, 0/1/2/3/5/7/10 min
             standing, see docs/test_protocols/ORTHOSTATIC_TEST_PROTOCOL.md).
@method.de   Einfaches Morning-Routine-Protokoll: 3 min liegen to aufstehen to HR bei
             1/3/5/10 min stehend messen. Kein Kubios noetig - beliebiger HR-Sensor
             (Brustgurt, BP-Monitor oder Smartwatch-Display).
             Unterschied zu import_kubios_orthostatic.py:
               - Kein Kubios-Export erforderlich
               - Schneller Morgenworkflow (< 15 min)
               - HR bei mehreren Zeitpunkten (Zeitverlauf des HR-Anstiegs)
               - Optionale Symptom-Erfassung direkt beim Test
             Kurz-CSV-Format: ts,hr_supine,hr_stand_1m,hr_stand_3m,hr_stand_5m,hr_stand_10m,hr_peak,
             spo2_supine,spo2_stand,dizzy,fatigue,notes
             Volles Protokoll (--template-full): zusätzlich hr_stand_0m,hr_stand_2m,hr_stand_7m,
             hr_supine_2m sowie Blutdruck-Spalten bp_sys_*/bp_dia_* für liegend
             (2 Messungen, 1 Min Abstand) und stehend (0/1/2/3/5/7/10 min) —
             geräteagnostisch, beliebiges Blutdruckmessgerät (manuell oder mit
             automatischer Serienmessung wie Withings BPM Core START-3). Alle
             Spalten optional (leer = nicht gemessen), beide Varianten teilen
             sich dasselbe Schema — kein Modus-Flag beim Import nötig, nur
             beim Template-Export (--template vs --template-full).
@method.en   Simple morning routine protocol: 3 min lying down -> stand up -> HR at
             1/3/5/10 min standing. No Kubios required - any HR sensor
             (chest strap, BP monitor or smartwatch display).
             Differences from import_kubios_orthostatic.py:
               - No Kubios export required
               - Faster morning workflow (< 15 min)
               - HR at multiple time points (HR rise curve)
               - Optional symptom recording during test
             Short CSV format: ts,hr_supine,hr_stand_1m,hr_stand_3m,hr_stand_5m,hr_stand_10m,hr_peak,
             spo2_supine,spo2_stand,dizzy,fatigue,notes
             Full protocol (--template-full): additionally hr_stand_0m,hr_stand_2m,hr_stand_7m,
             hr_supine_2m plus blood pressure columns bp_sys_*/bp_dia_* for
             supine (2 readings, 1 min apart) and standing (0/1/2/3/5/7/10 min)
             — device-agnostic, any blood pressure monitor (manual or with
             automatic series measurement like Withings BPM Core START-3). All
             columns optional (empty = not measured), both variants share the
             same schema — no mode flag needed on import, only on template
             export (--template vs --template-full).
@reads       CSV-Dateien aus ~/Kyoro-HealthHub/imports/orthostatic_manual/
@writes      sessions, session_metrics
@limits.de   hr_peak wichtig fuer POTS-Bewertung. Blutdruckwerte landen als
             session_metrics (mmHg), nicht in der geräteübergreifenden
             blood_pressure-Tabelle — für Auswertung dieses einen Tests
             ausreichend, aber nicht Teil allgemeiner BP-Trendauswertungen.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   hr_peak important for POTS evaluation. Blood pressure values land
             as session_metrics (mmHg), not in the cross-device blood_pressure
             table — sufficient for evaluating this one test, but not part of
             general BP trend analysis.
@usage
    python3 import_orthostatic_manual.py                  # alle CSVs
    python3 import_orthostatic_manual.py --update          # nur neue Daten
    python3 import_orthostatic_manual.py --manual           # interaktive Eingabe (Kurzprotokoll)
    python3 import_orthostatic_manual.py --template          # CSV-Vorlage Kurzprotokoll
    python3 import_orthostatic_manual.py --template-full     # CSV-Vorlage volles Schellong-/NASA-Lean-Test-Protokoll
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
CSV_DIR = Path(_cfg._cfg.get("paths", {}).get("orthostatic_manual_dir",
          str(Path.home() / "Kyoro-HealthHub" / "imports" / "orthostatic_manual")))
CSV_DIR.mkdir(parents=True, exist_ok=True)

OI_HR_THRESHOLD = 30.0
OI_HR_BORDERLINE = 20.0

CSV_TEMPLATE = """\
# Tägliches Orthostatik-Protokoll
# Protokoll: 3 min liegen → aufstehen → HR bei 1/3/5/10 min messen
# Spalten: ts,hr_supine,hr_stand_1m,hr_stand_3m,hr_stand_5m,hr_stand_10m,hr_peak,spo2_supine,spo2_stand,dizzy,fatigue,notes
#
# ts         : YYYY-MM-DDTHH:MM:SS (Beginn liegend)
# hr_*       : Herzfrequenz in bpm (leer = nicht gemessen)
# hr_peak    : höchster HR-Wert in ersten 30 s nach Aufstehen (POTS-sensitiv)
# spo2_*     : Sauerstoffsättigung in % (leer = nicht gemessen)
# dizzy      : Schwindel/Benommenheit 0=keine 1=leicht 2=mäßig 3=stark 4=Präsynkope
# fatigue    : Erschöpfung beim Aufstehen 0–4
# notes      : Freitext
#
ts,hr_supine,hr_stand_1m,hr_stand_3m,hr_stand_5m,hr_stand_10m,hr_peak,spo2_supine,spo2_stand,dizzy,fatigue,notes
"""

# Steh-Zeitpunkte des vollen Schellong-/NASA-Lean-Test-Protokolls (siehe
# docs/test_protocols/ORTHOSTATIC_TEST_PROTOCOL.md) — 0/1/2/3/5/7/10 Min; Liegend-Phase hat
# 2 Messungen (1 Min Abstand), direkt als *_supine/*_supine_2m benannt.
_STAND_TIMES = ["0m", "1m", "2m", "3m", "5m", "7m", "10m"]

# (csv_key, metric_name, unit) — geräteagnostisch: HR, SpO2 und Blutdruck
# (sys/dia) an jedem Zeitpunkt, alles optional (leer = nicht gemessen).
METRICS = [
    ("hr_supine",    "hr_supine",        "bpm"),
    ("hr_stand_1m",  "hr_stand_1min",    "bpm"),
    ("hr_stand_3m",  "hr_stand_3min",    "bpm"),
    ("hr_stand_5m",  "hr_stand_5min",    "bpm"),
    ("hr_stand_10m", "hr_stand_10min",   "bpm"),
    ("hr_peak",      "hr_standup_peak",  "bpm"),
    ("spo2_supine",  "spo2_supine",      "%"),
    ("spo2_stand",   "spo2_stand",       "%"),
    ("dizzy",        "dizzy",            "score"),
    ("fatigue",      "fatigue_orthostatic", "score"),
]

# Zusätzliche Spalten für --template-full (volles Schellong-/NASA-Lean-Test-
# Protokoll): weitere HR-Zeitpunkte + Blutdruck/SpO2 an jedem Zeitpunkt.
# hr_supine/hr_stand_1m/3m/5m/10m/spo2_supine aus METRICS (oben) werden für
# Messung 1 wiederverwendet — nur echte Zusatz-Zeitpunkte/-Werte kommen hier
# rein, um keine doppelt-benannten Spalten für dieselbe Messung 1 zu haben.
# spo2_stand (bare, aus METRICS) bleibt exklusiv dem kurzen Protokoll
# vorbehalten (dort ein einzelner undifferenzierter Wert) — das volle
# Protokoll nutzt stattdessen ausschließlich die zeitpunktgenauen
# spo2_stand_{0,1,2,3,5,7,10}m-Spalten unten, keine Vermischung.
# In METRICS_FULL statt METRICS, damit das kurze Morgenprotokoll (METRICS,
# oben) unverändert bleibt — beide Listen werden beim Import zusammen
# durchlaufen (siehe _insert), Spalten die in der jeweiligen CSV fehlen
# werden einfach als "nicht gemessen" übersprungen.
METRICS_FULL = [
    ("hr_supine_2m", "hr_supine_2min", "bpm"),
    ("hr_stand_0m",  "hr_stand_0min",  "bpm"),
    ("hr_stand_2m",  "hr_stand_2min",  "bpm"),
    ("hr_stand_7m",  "hr_stand_7min",  "bpm"),
    ("spo2_supine_2m", "spo2_supine_2min", "%"),
    ("bp_sys_supine", "bp_sys_supine", "mmHg"),
    ("bp_dia_supine", "bp_dia_supine", "mmHg"),
    ("bp_sys_supine_2m", "bp_sys_supine_2min", "mmHg"),
    ("bp_dia_supine_2m", "bp_dia_supine_2min", "mmHg"),
]
for _t in _STAND_TIMES:
    METRICS_FULL.append((f"spo2_stand_{_t}", f"spo2_stand_{_t}", "%"))
    METRICS_FULL.append((f"bp_sys_stand_{_t}", f"bp_sys_stand_{_t}", "mmHg"))
    METRICS_FULL.append((f"bp_dia_stand_{_t}", f"bp_dia_stand_{_t}", "mmHg"))

# Explizite, chronologisch sortierte Spaltenreihenfolge für die von Hand
# auszufüllende CSV — bewusst nicht aus METRICS/METRICS_FULL zusammengesetzt,
# da deren Reihenfolge (kurzes Protokoll zuerst, dann Zusatzspalten) für
# Menschen beim Ausfüllen verwirrend wäre.
_FULL_COLUMNS = (
    ["ts", "hr_supine", "hr_supine_2m", "spo2_supine", "spo2_supine_2m",
     "bp_sys_supine", "bp_dia_supine", "bp_sys_supine_2m", "bp_dia_supine_2m"]
    + [f"{prefix}_stand_{_t}" for _t in _STAND_TIMES
       for prefix in ("hr", "spo2", "bp_sys", "bp_dia")]
    + ["hr_peak", "dizzy", "fatigue", "notes"]
)

CSV_TEMPLATE_FULL = """\
# Volles Schellong-/NASA-Lean-Test-Protokoll (siehe docs/test_protocols/ORTHOSTATIC_TEST_PROTOCOL.md)
# Protokoll: 10 min liegen -> 2 Messungen liegend (1 Min Abstand) ->
#            aufstehen -> Messungen stehend bei 0/1/2/3/5/7/10 min
# Geräteagnostisch: beliebiges Blutdruckmessgerät (manuell oder mit
# automatischer Serienmessung wie Withings BPM Core START-3/Advanced Mode).
# Alle Spalten optional, leer = nicht gemessen.
#
# ts               : YYYY-MM-DDTHH:MM:SS (Beginn liegend, 10-Min-Ruhephase davor)
# hr_supine        : HF liegend, Messung 1 (nach 10 Min Ruhe)
# hr_supine_2m     : HF liegend, Messung 2 (1 Min nach Messung 1)
# hr_stand_{0,1,2,3,5,7,10}m : HF stehend zum jeweiligen Zeitpunkt
# hr_peak          : höchster HR-Wert in ersten 30 s nach Aufstehen (POTS-sensitiv)
# spo2_supine[_2m] : SpO2 liegend (%), Messung 1 / 2
# spo2_stand_{0,1,2,3,5,7,10}m : SpO2 stehend (%) zum jeweiligen Zeitpunkt
# bp_sys_supine[_2m] / bp_dia_supine[_2m] : Blutdruck liegend (mmHg), Messung 1 / 2
# bp_sys_stand_{0,1,2,3,5,7,10}m / bp_dia_stand_{...} : Blutdruck stehend (mmHg)
# dizzy            : Schwindel/Benommenheit 0=keine 1=leicht 2=mäßig 3=stark 4=Präsynkope
# fatigue          : Erschöpfung beim Aufstehen 0–4
# notes            : Freitext
#
{header}
""".replace("{header}", ",".join(_FULL_COLUMNS))


def _parse_row(row: dict) -> dict | None:
    ts = row.get("ts", "").strip()
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        print(t(f"  Ungültiges Datum: {ts}", f"  Invalid date: {ts}"))
        return None
    date = dt.strftime("%Y-%m-%d")

    def _f(key):
        v = row.get(key, "").strip()
        return float(v) if v else None

    values = {m[0]: _f(m[0]) for m in METRICS + METRICS_FULL}
    values["ts"]    = ts
    values["date"]  = date
    values["notes"] = row.get("notes", "").strip() or None
    return values


def _insert(conn: sqlite3.Connection, rec: dict, person: str, source: str) -> bool:
    # Berechne hr_delta aus dem besten verfügbaren Stehwert
    hr_s = rec.get("hr_supine")
    hr_peak = rec.get("hr_peak")
    hr_3m   = rec.get("hr_stand_3m")
    hr_1m   = rec.get("hr_stand_1m")
    hr_stand_ref = hr_peak or hr_1m or hr_3m
    hr_delta = round(hr_stand_ref - hr_s, 1) if (hr_stand_ref and hr_s) else None

    ts   = rec["ts"]
    date = rec["date"]

    # Session anlegen — sessions-Schema ist (id, type, ts_start, ts_end, date,
    # device_id, person, source_app, sport, wear_location, mode), kein
    # eigenes notes-Feld (Notizen gehen stattdessen nach user_context, s.u.).
    # Korrektur eines Bestandsfehlers: vorherige Version referenzierte
    # nicht-existente Spalten (start_ts/end_ts/source/device/notes) und ohne
    # id — INSERT schlug bisher immer fehl, ohne dass Testläufe das
    # bemerkten (except DB_ERRORS faengt sqlcipher3-Exceptions in
    # diesem Setup nicht, s. offene Frage zu open_db()-Fehlerbehandlung).
    sid = f"orthostatic_manual_{ts}_{person}"
    try:
        conn.execute("""
            INSERT OR IGNORE INTO sessions
            (id, type, ts_start, ts_end, date, person, source_app)
            VALUES (?,'orthostatic',?,?,?,?,?)
        """, (sid, ts, ts, date, person, source))
        if rec.get("notes"):
            conn.execute(
                "INSERT OR IGNORE INTO user_context"
                " (id, date, ts_start, ts_end, person, source, source_app, tag, note)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (f"orthostatic:{ts}", date, ts, None,
                 person, 'orthostatic_manual', 'orthostatic_manual',
                 'orthostatic', rec["notes"]),
            )
    except DB_ERRORS as e:
        print(t(f"  sessions-Fehler: {e}", f"  sessions error: {e}"))
        return False

    session_id = conn.execute(
        "SELECT id FROM sessions WHERE id=? AND type='orthostatic' AND person=?",
        (sid, person)
    ).fetchone()
    if not session_id:
        return False
    sid = session_id[0]

    # Metriken eintragen
    for csv_key, metric_name, unit in METRICS + METRICS_FULL:
        val = rec.get(csv_key)
        if val is not None:
            conn.execute("""
                INSERT OR IGNORE INTO session_metrics (session_id, metric, value, unit)
                VALUES (?,?,?,?)
            """, (sid, metric_name, val, unit))

    if hr_delta is not None:
        conn.execute("""
            INSERT OR IGNORE INTO session_metrics (session_id, metric, value, unit)
            VALUES (?,?,?,?)
        """, (sid, "hr_delta", hr_delta, "bpm"))

    return True


def _flag_pots(hr_supine, hr_stand):
    if hr_supine is None or hr_stand is None:
        return ""
    delta = hr_stand - hr_supine
    if delta >= OI_HR_THRESHOLD:
        return t(f"⚠ POTS-Kriterium ΔHR={delta:.0f} bpm", f"⚠ POTS criterion ΔHR={delta:.0f} bpm")
    if delta >= OI_HR_BORDERLINE:
        return t(f"△ Grenzwertig ΔHR={delta:.0f} bpm", f"△ Borderline ΔHR={delta:.0f} bpm")
    return t(f"✓ ΔHR={delta:.0f} bpm", f"✓ ΔHR={delta:.0f} bpm")


def _import_csv(conn, path, person, update_only, source):
    inserted = skipped = 0
    if update_only:
        latest = conn.execute(
            "SELECT MAX(start_ts) FROM sessions WHERE type='orthostatic' AND person=?",
            (person,)
        ).fetchone()[0] or "1900-01-01"
    else:
        latest = None

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(row for row in f if not row.startswith("#"))
        for row in reader:
            ts = row.get("ts", "").strip()
            if latest and ts <= latest:
                skipped += 1
                continue
            rec = _parse_row(row)
            if rec is None:
                skipped += 1
                continue
            if _insert(conn, rec, person, source):
                inserted += 1
                hr_ref = rec.get("hr_peak") or rec.get("hr_stand_1m") or rec.get("hr_stand_3m")
                flag   = _flag_pots(rec.get("hr_supine"), hr_ref)
                print(t(f"    {ts[:10]}  {flag}", f"    {ts[:10]}  {flag}"))
            else:
                skipped += 1
    return inserted, skipped


def _manual_entry(conn, person):
    print(t("\n── Manuelles Orthostatik-Protokoll ────────────────────────────",
            "\n── Manual orthostatic protocol ────────────────────────────────"))
    ts_str = input(t("Zeitpunkt Messbeginn (YYYY-MM-DDTHH:MM, Enter=jetzt): ",
                     "Measurement start (YYYY-MM-DDTHH:MM, Enter=now): ")).strip()
    if not ts_str:
        ts_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    elif len(ts_str) == 16:
        ts_str += ":00"

    def ask(label):
        return input(t(f"  {label} (bpm/%, leer=übersprungen): ",
                       f"  {label} (bpm/%, empty=skip): ")).strip()

    rec = {
        "ts":          ts_str,
        "date":        ts_str[:10],
        "hr_supine":   ask("HR liegend 3 min") or None,
        "hr_peak":     ask("HR Peak (erste 30 s stehend)") or None,
        "hr_stand_1m": ask("HR stehend 1 min") or None,
        "hr_stand_3m": ask("HR stehend 3 min") or None,
        "hr_stand_5m": ask("HR stehend 5 min") or None,
        "hr_stand_10m":ask("HR stehend 10 min") or None,
        "spo2_supine": ask("SpO2 liegend") or None,
        "spo2_stand":  ask("SpO2 stehend") or None,
        "dizzy":       ask("Schwindel 0–4") or None,
        "fatigue":     ask("Erschöpfung 0–4") or None,
        "notes":       input(t("Notizen: ", "Notes: ")).strip() or None,
    }
    for k in METRICS:
        if rec.get(k[0]) is not None:
            try:
                rec[k[0]] = float(rec[k[0]])
            except (ValueError, TypeError):
                rec[k[0]] = None

    if _insert(conn, rec, person, "manual"):
        hr_ref = rec.get("hr_peak") or rec.get("hr_stand_1m") or rec.get("hr_stand_3m")
        flag   = _flag_pots(rec.get("hr_supine"), hr_ref)
        print(t(f"  ✓ Gespeichert  {flag}", f"  ✓ Saved  {flag}"))
        conn.commit()
    else:
        print(t("  Bereits vorhanden oder Fehler.", "  Already exists or error."))


def main():
    parser = argparse.ArgumentParser(
        description=t("Tägliches Orthostatik-Protokoll importieren",
                      "Import daily orthostatic protocol"))
    parser.add_argument("--update",   action="store_true")
    parser.add_argument("--manual",   action="store_true")
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--template-full", action="store_true",
                        help=t("CSV-Vorlage: volles Schellong-/NASA-Lean-Test-Protokoll (HR+SpO2+RR, 0-10min)",
                               "CSV template: full Schellong/NASA Lean Test protocol (HR+SpO2+BP, 0-10min)"))
    parser.add_argument("--file",     type=str, default=None)
    parser.add_argument("--source",   type=str, default="orthostatic_manual")
    parser.add_argument("--person",   type=str, default=None)
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.template_full:
        print(CSV_TEMPLATE_FULL)
        return

    if args.template:
        print(CSV_TEMPLATE)
        return

    person = args.person or OWN_PERSON_ID
    conn   = open_db()

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
        ins, skip = _import_csv(conn, f, person, args.update, args.source)
        total_ins += ins
        total_skip += skip
        print(t(f"  {f.name}: {ins} neu, {skip} übersprungen",
                f"  {f.name}: {ins} new, {skip} skipped"))

    log_import(conn, 'orthostatic_manual', str(CSV_DIR), total_ins, total_skip)
    conn.commit()
    conn.close()
    print(t(f"\nOrthostatik: {total_ins} Messungen importiert, {total_skip} übersprungen.",
            f"\nOrthostatic: {total_ins} measurements imported, {total_skip} skipped."))


if __name__ == "__main__":
    main()
