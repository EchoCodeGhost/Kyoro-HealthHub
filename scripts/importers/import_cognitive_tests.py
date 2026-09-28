#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Kognitive Kurztests → health.db (cognitive_tests)

@tier        infrastructure
@purpose.de  Importiert Ergebnisse kognitiver Kurztests
@purpose.en  Imports results of cognitive short tests
@method.de   Importiert kognitive Testdaten in die Tabelle cognitive_tests.
             Unterstuetzte Testformate:
             - reaction_time (Reaktionszeit in ms)
             - sdmt (Symbol Digit Modalities Test)
             - digit_span (Zahlennachsprechen vorwaerts/rueckwaerts)
             - spatial_memory (Raumliches Gedaechtnis)
             - stroop (Stroop-Interferenz)
             - n_back (N-Back Working Memory Score)
             - pvt (Psychomotor Vigilance Task)
             - go_nogo (Go/No-Go Inhibitionskontrolle)
             App-Exports werden automatisch erkannt und konvertiert.
@method.en   Imports cognitive test data into the cognitive_tests table.
             Supported test formats:
             - reaction_time (reaction time in ms)
             - sdmt (Symbol Digit Modalities Test)
             - digit_span (digit span forward/backward)
             - spatial_memory (spatial memory)
             - stroop (Stroop interference)
             - n_back (N-Back Working Memory Score)
             - pvt (Psychomotor Vigilance Task)
             - go_nogo (Go/No-Go inhibition control)
             App exports are automatically detected and converted.
@reads       CSV-Dateien aus ~/Kyoro-HealthHub/imports/cognitive/
@writes      cognitive_tests
@limits.de   Abhaengig von Test-App-Exportformat.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Dependent on test app export format.
@usage
    python3 import_cognitive_tests.py              # alle CSVs
    python3 import_cognitive_tests.py --update     # nur neue Daten
    python3 import_cognitive_tests.py --manual     # interaktive Eingabe
    python3 import_cognitive_tests.py --template   # CSV-Vorlage ausgeben
"""

import argparse
import csv
import re
import sqlite3
import statistics
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db, DB_ERRORS
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import
_cfg = _Cfg()

DB_PATH  = _cfg.db_path
CSV_DIR  = Path(_cfg._cfg.get("paths", {}).get("cognitive_dir",
           str(Path.home() / "Kyoro-HealthHub" / "imports" / "cognitive")))
CSV_DIR.mkdir(parents=True, exist_ok=True)

VALID_TESTS = {
    "reaction_time", "sdmt", "digit_span", "spatial_memory",
    "stroop", "n_back", "trail_making", "word_recall",
    "pvt", "go_nogo",
}


# ── App-spezifische Format-Erkennung ─────────────────────────────────────────

def _detect_format(path: Path) -> str:
    """Gibt 'nback' | 'stroop' | 'pvt' | 'gonogo' | 'kyoro' zurück."""
    try:
        with open(path, encoding="utf-8") as f:
            head = [f.readline() for _ in range(3)]
    except Exception:
        return "kyoro"
    first = head[0].strip()
    if re.match(r"N-Back Level:\s*\d+", first):
        return "nback"
    if first.startswith("# Go/No-Go Buddy"):
        return "gonogo"
    if "Color text" in first and "Color value" in first:
        return "stroop"
    if first.startswith("Task,TapTime") or (len(head) > 1 and head[1].strip().startswith("Task,")):
        return "pvt"
    return "kyoro"


def _session_type_from_ts(ts_str: str) -> str:
    try:
        h = datetime.fromisoformat(ts_str.replace("Z", "")).hour
        if h < 12:  return "morning"
        if h < 17:  return "afternoon"
        if h < 21:  return "evening"
        return "night"
    except Exception:
        return ""


# ── N-Back (Research Buddies N-Back Buddy) ───────────────────────────────────

def _parse_nback(path: Path, person: str) -> dict | None:
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    level_match = re.match(r"N-Back Level:\s*(\d+)", lines[0].strip())
    level = int(level_match.group(1)) if level_match else None
    reader = csv.DictReader(lines[1:])
    rts, correct, total = [], 0, 0
    ts_min = None
    for row in reader:
        raw_ts = (row.get("Timestamp") or "").strip()
        if not raw_ts:
            continue  # summary row
        try:
            dt = datetime.fromisoformat(raw_ts)
            if ts_min is None or dt < ts_min:
                ts_min = dt
        except Exception:
            continue
        total += 1
        if (row.get("Correct") or "").strip().lower() == "true":
            correct += 1
        rt_s = (row.get("Response Time (ms)") or "").strip()
        if rt_s:
            try:
                rt = float(rt_s)
                if rt > 0:
                    rts.append(rt)
            except ValueError:
                pass
    if total == 0 or ts_min is None:
        return None
    ts = ts_min.strftime("%Y-%m-%dT%H:%M:%S")
    score = round(correct / total * 100, 1)
    reaction = round(statistics.median(rts), 1) if rts else None
    errors = total - correct
    notes = f"N-Back Level {level}" if level else "N-Back"
    return {
        "ts": ts, "date": ts[:10], "test_name": "n_back",
        "score": score, "reaction_ms": reaction, "errors": errors,
        "duration_s": None, "percentile": None,
        "session_type": _session_type_from_ts(ts), "device": "nback_buddy",
        "notes": notes, "person": person, "source": "nback_buddy_csv",
    }


# ── Stroop (Research Buddies Stroop) ─────────────────────────────────────────

def _parse_stroop(path: Path, person: str) -> dict | None:
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return None
    rts_con, rts_inc = [], []
    correct = total = 0
    ts_min = None
    for row in rows:
        raw_ts = (row.get("Answer time") or "").strip()
        if not raw_ts:
            continue  # summary row
        try:
            dt = datetime.fromisoformat(raw_ts)
            if ts_min is None or dt < ts_min:
                ts_min = dt
        except Exception:
            continue
        is_correct = (row.get("Correct") or "").strip().lower() == "true"
        if is_correct:
            correct += 1
        total += 1
        rt_s = (row.get("Time taken in milliseconds") or "").strip()
        try:
            rt = float(rt_s)
            if rt > 0:
                congruent = (row.get("Color text") or "").strip() == (row.get("Color value") or "").strip()
                (rts_con if congruent else rts_inc).append(rt)
        except ValueError:
            pass
    if ts_min is None:
        return None
    ts = ts_min.strftime("%Y-%m-%dT%H:%M:%S")
    total = len(rows)
    score = round(correct / total * 100, 1) if total else None
    all_rts = rts_con + rts_inc
    reaction = round(statistics.median(all_rts), 1) if all_rts else None
    errors = total - correct
    parts = []
    if rts_con and rts_inc:
        parts.append(f"Interferenz {statistics.mean(rts_inc):.0f}−{statistics.mean(rts_con):.0f}ms")
    notes = "; ".join(parts) if parts else "Stroop"
    return {
        "ts": ts, "date": ts[:10], "test_name": "stroop",
        "score": score, "reaction_ms": reaction, "errors": errors,
        "duration_s": None, "percentile": None,
        "session_type": _session_type_from_ts(ts), "device": "stroop_buddy",
        "notes": notes, "person": person, "source": "stroop_buddy_csv",
    }


# ── PVT / Vagiliance ─────────────────────────────────────────────────────────

def _parse_pvt(path: Path, person: str) -> dict | None:
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return None
    # Summary rows: TapTime is a text label (not a time string)
    summary = {}
    rts = []
    ts_date = None
    for row in rows:
        tap = row.get("TapTime", "").strip()
        ms_s = row.get("Milliseconds", "").strip()
        task_s = row.get("Task", "").strip()
        if ts_date is None and task_s:
            try:
                datetime.fromisoformat(task_s)
                ts_date = task_s
            except Exception:
                pass
        try:
            float(tap.replace(":", ""))  # time-like
            ms = float(ms_s)
            if ms > 0:
                rts.append(ms)
        except (ValueError, AttributeError):
            # summary row
            if ms_s:
                try:
                    summary[tap] = float(ms_s)
                except ValueError:
                    summary[tap] = ms_s
    if ts_date is None:
        return None
    ts = ts_date.replace(" ", "T") if "T" not in ts_date else ts_date
    duration = int(summary.get("Test Duration in seconds", 0)) or None
    false_pos = int(summary.get("Number of False Positives", 0))
    slow = int(summary.get("Slow responses (>500ms) ", summary.get("Slow responses (>500ms)", 0)))
    lapses = int(summary.get("Total lapses (false positives + slow responses) ",
                             summary.get("Total lapses (false positives + slow responses)", 0)))
    avg_rt = summary.get("Average response time ")
    if avg_rt is None:
        avg_rt = summary.get("Average response time")
    reaction = round(float(avg_rt), 1) if avg_rt else (round(statistics.mean(rts), 1) if rts else None)
    notes = f"Lapses:{lapses} FP:{false_pos} Slow:{slow}"
    return {
        "ts": ts, "date": ts[:10], "test_name": "pvt",
        "score": None, "reaction_ms": reaction, "errors": false_pos,
        "duration_s": duration, "percentile": None,
        "session_type": _session_type_from_ts(ts), "device": "vagiliance",
        "notes": notes, "person": person, "source": "vagiliance_csv",
    }


# ── Go/No-Go (Research Buddies Go/No-Go Buddy) ───────────────────────────────

def _parse_gonogo(path: Path, person: str) -> dict | None:
    meta = {}
    data_rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                m = re.match(r"#\s*([^:]+):\s*(.+)", line)
                if m:
                    meta[m.group(1).strip()] = m.group(2).strip()
            else:
                data_rows.append(line)
    ts_raw = meta.get("Timestamp", "")
    if not ts_raw:
        return None
    try:
        ts = datetime.fromisoformat(ts_raw).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        ts = ts_raw[:19]
    # Parse trial data for median RT on hits
    rts_hit = []
    reader = csv.DictReader(data_rows)
    for row in reader:
        if row.get("outcome", "").strip() == "HIT":
            rt_s = row.get("reaction_time_ms", "").strip()
            try:
                rt = float(rt_s)
                if rt > 0:
                    rts_hit.append(rt)
            except ValueError:
                pass
    reaction = round(statistics.median(rts_hit), 1) if rts_hit else None
    # Scores from meta
    inhibition_s = meta.get("Inhibition score", "0%").rstrip("%")
    try:
        score = float(inhibition_s)
    except ValueError:
        score = None
    hits_s = meta.get("Hits", "0").split()[0]
    misses_s = meta.get("Misses", "0").split()[0] if "Misses" in meta else "0"
    fa_s = meta.get("False alarms", "0").split()[0] if "False alarms" in meta else "0"
    # Hits/Misses/FA are all in one line "Hits: 43    Misses: 2    False alarms: 3..."
    # Try to parse from the combined line
    combined = next((v for k, v in meta.items() if k.startswith("Hits")), "")
    hits_m = re.search(r"(\d+)", combined)
    miss_m = re.search(r"Misses[^\d]*(\d+)", combined)
    fa_m   = re.search(r"False alarms[^\d]*(\d+)", combined)
    hits   = int(hits_m.group(1)) if hits_m else int(hits_s)
    misses = int(miss_m.group(1)) if miss_m else int(misses_s)
    fa     = int(fa_m.group(1))   if fa_m   else int(fa_s)
    errors = fa + misses
    total  = meta.get("Total trials", "?")
    notes  = f"Hits:{hits} Misses:{misses} FA:{fa} n={total}"
    return {
        "ts": ts, "date": ts[:10], "test_name": "go_nogo",
        "score": score, "reaction_ms": reaction, "errors": errors,
        "duration_s": None, "percentile": None,
        "session_type": _session_type_from_ts(ts), "device": "gonogo_buddy",
        "notes": notes, "person": person, "source": "gonogo_buddy_csv",
    }

CSV_TEMPLATE = """\
# Kognitive Kurztests — CSV-Vorlage
# Spalten: ts,test_name,score,reaction_ms,errors,duration_s,percentile,session_type,device,notes
#
# ts           : YYYY-MM-DDTHH:MM:SS (Messzeitpunkt)
# test_name    : reaction_time | sdmt | digit_span | spatial_memory | stroop | n_back | trail_making | word_recall
# score        : Punktzahl (SDMT=richtige Symbole, digit_span=Spanne, n_back=% korrekt)
# reaction_ms  : Mediane Reaktionszeit in ms (für reaction_time und stroop)
# errors       : Fehleranzahl
# duration_s   : Testdauer in Sekunden (SDMT=90, reaction_time=varies)
# percentile   : Normative Percentile (0–100), falls von der App angegeben
# session_type : morning | afternoon | evening
# device       : humanbenchmark | cambridge_brain | cognifit | manuell | smartphone
# notes        : Freitext
#
# Beispiele:
# 2026-06-12T08:15:00,reaction_time,,287.4,,30,42,morning,humanbenchmark,
# 2026-06-12T08:17:00,sdmt,48,,2,90,,morning,manuell,Konzentration gut
# 2026-06-12T08:19:00,digit_span,7,,,,,morning,manuell,
ts,test_name,score,reaction_ms,errors,duration_s,percentile,session_type,device,notes
"""


def _parse_row(row: dict, person: str) -> dict | None:
    ts = row.get("ts", "").strip()
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
    except ValueError:
        print(t(f"  Ungültiges Datum: {ts}", f"  Invalid date: {ts}"))
        return None
    date = dt.strftime("%Y-%m-%d")
    test_name = row.get("test_name", "").strip().lower()
    if not test_name:
        return None

    def _f(key):
        v = row.get(key, "").strip()
        return float(v) if v else None

    def _i(key):
        v = row.get(key, "").strip()
        return int(v) if v else None

    return {
        "ts":           ts,
        "date":         date,
        "test_name":    test_name,
        "score":        _f("score"),
        "reaction_ms":  _f("reaction_ms"),
        "errors":       _i("errors"),
        "duration_s":   _i("duration_s"),
        "percentile":   _f("percentile"),
        "session_type": row.get("session_type", "").strip() or None,
        "device":       row.get("device", "").strip() or None,
        "notes":        row.get("notes", "").strip() or None,
        "person":       person,
        "source":       "csv",
    }


def _insert(conn: sqlite3.Connection, rec: dict) -> bool:
    try:
        conn.execute("""
            INSERT OR IGNORE INTO cognitive_tests
            (ts, date, test_name, score, reaction_ms, errors, duration_s,
             percentile, session_type, device, notes, person, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            rec["ts"], rec["date"], rec["test_name"], rec["score"],
            rec["reaction_ms"], rec["errors"], rec["duration_s"],
            rec["percentile"], rec["session_type"], rec["device"],
            rec["notes"], rec["person"], rec["source"],
        ))
        inserted = conn.total_changes > 0
        if inserted and rec.get("notes"):
            conn.execute(
                "INSERT OR IGNORE INTO user_context"
                " (id, date, ts_start, ts_end, person, source, source_app, tag, note)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (f"cognitive:{rec['ts']}", rec["date"], rec["ts"], None,
                 rec["person"], 'cognitive_tests', rec.get("device") or 'cognitive_tests',
                 rec.get("test_name"), rec["notes"]),
            )
        return inserted
    except DB_ERRORS as e:
        print(t(f"  DB-Fehler: {e}", f"  DB error: {e}"))
        return False


_APP_PARSERS = {
    "nback":  _parse_nback,
    "stroop": _parse_stroop,
    "pvt":    _parse_pvt,
    "gonogo": _parse_gonogo,
}


def _import_csv(conn: sqlite3.Connection, path: Path, person: str,
                update_only: bool) -> tuple[int, int]:
    fmt = _detect_format(path)
    if fmt in _APP_PARSERS:
        rec = _APP_PARSERS[fmt](path, person)
        if rec is None:
            return 0, 1
        if update_only:
            latest = conn.execute(
                "SELECT MAX(ts) FROM cognitive_tests WHERE person=? AND test_name=?",
                (person, rec["test_name"]),
            ).fetchone()[0] or "1900-01-01"
            if rec["ts"] <= latest:
                return 0, 1
        return (1, 0) if _insert(conn, rec) else (0, 1)

    inserted = skipped = 0
    if update_only:
        latest = conn.execute(
            "SELECT MAX(ts) FROM cognitive_tests WHERE person=?", (person,)
        ).fetchone()[0] or "1900-01-01"
    else:
        latest = None

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(row for row in f if not row.startswith("#"))
        for row in reader:
            if latest and row.get("ts", "") <= latest:
                skipped += 1
                continue
            rec = _parse_row(row, person)
            if rec is None:
                skipped += 1
                continue
            if _insert(conn, rec):
                inserted += 1
            else:
                skipped += 1
    return inserted, skipped


def _manual_entry(conn: sqlite3.Connection, person: str):
    print(t("\n── Manuelle Eingabe kognitiver Test ──────────────────────────",
            "\n── Manual cognitive test entry ────────────────────────────────"))
    ts_str = input(t("Zeitpunkt (YYYY-MM-DDTHH:MM:SS, Enter=jetzt): ",
                     "Timestamp (YYYY-MM-DDTHH:MM:SS, Enter=now): ")).strip()
    if not ts_str:
        ts_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    test_name = input(t("Testname (reaction_time/sdmt/digit_span/spatial_memory/stroop/n_back): ",
                        "Test name (reaction_time/sdmt/digit_span/spatial_memory/stroop/n_back): ")).strip().lower()
    score_s      = input(t("Score (Punkte, leer=keiner): ", "Score (points, empty=none): ")).strip()
    reaction_s   = input(t("Reaktionszeit in ms (leer=keiner): ", "Reaction time in ms (empty=none): ")).strip()
    errors_s     = input(t("Fehler (leer=keine): ", "Errors (empty=none): ")).strip()
    duration_s   = input(t("Dauer in Sekunden (leer=unbekannt): ", "Duration in seconds (empty=unknown): ")).strip()
    percentile_s = input(t("Percentile 0–100 (leer=unbekannt): ", "Percentile 0–100 (empty=unknown): ")).strip()
    session_type = input(t("Tageszeit (morning/afternoon/evening): ", "Time of day (morning/afternoon/evening): ")).strip()
    device       = input(t("Gerät/App (humanbenchmark/manuell/...): ", "Device/app (humanbenchmark/manual/...): ")).strip()
    notes        = input(t("Notizen: ", "Notes: ")).strip()

    rec = {
        "ts":           ts_str,
        "date":         ts_str[:10],
        "test_name":    test_name or "unbekannt",
        "score":        float(score_s) if score_s else None,
        "reaction_ms":  float(reaction_s) if reaction_s else None,
        "errors":       int(errors_s) if errors_s else None,
        "duration_s":   int(duration_s) if duration_s else None,
        "percentile":   float(percentile_s) if percentile_s else None,
        "session_type": session_type or None,
        "device":       device or "manuell",
        "notes":        notes or None,
        "person":       person,
        "source":       "manual",
    }
    if _insert(conn, rec):
        print(t(f"  ✓ Eintrag gespeichert: {test_name} @ {ts_str}",
                f"  ✓ Entry saved: {test_name} @ {ts_str}"))
        conn.commit()
    else:
        print(t("  Bereits vorhanden oder Fehler.", "  Already exists or error."))


def main():
    parser = argparse.ArgumentParser(
        description=t("Kognitive Tests importieren", "Import cognitive tests"))
    parser.add_argument("--update",   action="store_true",
                        help=t("Nur neue Daten (seit letztem Import)", "Only new data"))
    parser.add_argument("--manual",   action="store_true",
                        help=t("Interaktive Eingabe", "Interactive entry"))
    parser.add_argument("--template", action="store_true",
                        help=t("CSV-Vorlage ausgeben", "Print CSV template"))
    parser.add_argument("--file",     type=str, default=None,
                        help=t("Einzelne CSV-Datei", "Single CSV file"))
    parser.add_argument("--person",   type=str, default=None)
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.template:
        print(CSV_TEMPLATE)
        return

    person = args.person or OWN_PERSON_ID
    conn   = open_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cognitive_tests (
            ts TEXT NOT NULL, date TEXT NOT NULL, test_name TEXT NOT NULL,
            score REAL, reaction_ms REAL, errors INTEGER, duration_s INTEGER,
            percentile REAL, session_type TEXT, device TEXT, notes TEXT,
            person TEXT NOT NULL DEFAULT 'unknown', source TEXT,
            PRIMARY KEY (ts, test_name, person)
        )
    """)

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
        ins, skip = _import_csv(conn, f, person, args.update)
        total_ins += ins
        total_skip += skip
        print(t(f"  {f.name}: {ins} neu, {skip} übersprungen",
                f"  {f.name}: {ins} new, {skip} skipped"))

    log_import(conn, 'cognitive_tests', str(CSV_DIR), total_ins, total_skip)
    conn.commit()
    conn.close()
    print(t(f"\nKognitive Tests: {total_ins} importiert, {total_skip} übersprungen.",
            f"\nCognitive tests: {total_ins} imported, {total_skip} skipped."))


if __name__ == "__main__":
    main()
