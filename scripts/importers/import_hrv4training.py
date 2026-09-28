#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
HRV4Workout → health.db (hrv4training_daily)

@tier        infrastructure
@purpose.de  Importiert HRV4Workout CSV-Exporte
@purpose.en  Imports HRV4Workout CSV exports
@method.de   Importiert den CSV-Export aus der HRV4Workout-App in hrv4training_daily.
             Export-Path in der App: Profiles -> Export -> "Export CSV".
             Typische columns: Date, HRV4T, Morning Readiness, RMSSD, HR, day, Comment,
             + beliebige Kontext-Variablen (Sleep, Erschoepfung, etc.).
@method.en   Imports the CSV export from the HRV4Workout app into hrv4training_daily.
             Export path in app: Profiles -> Export -> "Export CSV".
             Typical columns: Date, HRV4T, Morning Readiness, RMSSD, HR, day, Comment,
             + any context variables (Sleep, Fatigue, etc.).
@reads       HRV4Workout CSV-Dateien
@writes      hrv4training_daily
@limits.de   Abhaengig von App-Version und Exportformat.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   Dependent on app version and export format.
@usage
    python import_hrv4training.py --file export.csv
    python import_hrv4training.py --dir ~/Downloads/
    python import_hrv4training.py --file export.csv --dry-run
"""

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person
_cfg = _Cfg()
DB_PATH = _cfg.db_path

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS hrv4training_daily (
    date              TEXT PRIMARY KEY,   -- YYYY-MM-DD
    rmssd_ms          REAL,               -- RMSSD (ms)
    ln_rmssd          REAL,               -- ln(RMSSD) falls App so exportiert
    hr_bpm            REAL,               -- Morgen-HR
    hrv4t_score       REAL,               -- proprietärer HRV4T-Score (0–100)
    readiness         REAL,               -- Morning Readiness Score
    -- Kontext-Variablen (Nutzereingabe in der App)
    sleep_quality     REAL,               -- Schlafqualität (app-skaliert)
    fatigue           REAL,               -- Erschöpfung
    mood              REAL,               -- Stimmung
    motivation        REAL,               -- Motivation
    muscle_soreness   REAL,               -- Muskelkater
    -- Freitext
    tags              TEXT,
    comment           TEXT,
    -- Rohe Zusatzspalten als JSON (falls App mehr Kontext-Vars hat)
    context_json      TEXT,
    source            TEXT DEFAULT 'hrv4training'
)
"""

# columnsnamen-Mapping: was die App exportieren kann → unsere Felder
# All Varianten die über Versionen hinweg beobachtet wurden
FIELD_MAP = {
    # Datum
    "date":                      "date",
    # RMSSD
    "rmssd":                     "rmssd_ms",
    "rmssd (ms)":                "rmssd_ms",
    "hrv (rmssd)":               "rmssd_ms",
    "hrv":                       "rmssd_ms",
    # ln(RMSSD)
    "ln rmssd":                  "ln_rmssd",
    "lnrmssd":                   "ln_rmssd",
    "hrv (ln rmssd)":            "ln_rmssd",
    "hrv4t":                     "hrv4t_score",
    "hrv4training":              "hrv4t_score",
    # HR
    "hr":                        "hr_bpm",
    "heart rate":                "hr_bpm",
    "hr (bpm)":                  "hr_bpm",
    # Readiness
    "morning readiness":         "readiness",
    "readiness":                 "readiness",
    # Kontext
    "sleep quality":             "sleep_quality",
    "sleep":                     "sleep_quality",
    "fatigue":                   "fatigue",
    "tiredness":                 "fatigue",
    "mood":                      "mood",
    "motivation":                "motivation",
    "muscle soreness":           "muscle_soreness",
    "soreness":                  "muscle_soreness",
    # Freitext
    "tag":                       "tags",
    "tags":                      "tags",
    "comment":                   "comment",
    "comments":                  "comment",
    "notes":                     "comment",
}

# Kontext-Variablen die NICHT direkt gemappt werden but trotzdem erhalten bleiben
KNOWN_FIELDS = set(FIELD_MAP.values())


def _norm_col(name: str) -> str:
    return name.strip().lower().replace("-", " ").replace("_", " ")


def parse_csv(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        # Encoding-Probe: Skip mögliche Kommentar-rows am Anfang
        lines = f.readlines()

    # Header-Zeile finden (erste Zeile die "date" or "Date" enthält)
    header_idx = 0
    for i, line in enumerate(lines):
        if re.search(r'\bdate\b', line, re.IGNORECASE):
            header_idx = i
            break

    reader = csv.DictReader(lines[header_idx:])

    for row in reader:
        if not any(row.values()):
            continue

        record: dict = {}
        extra: dict = {}

        for col, val in row.items():
            if col is None or val is None:
                continue
            col_norm = _norm_col(col)
            val = val.strip()
            mapped = FIELD_MAP.get(col_norm)

            if mapped == "date" or col_norm == "date":
                # Datum normalisieren: MM/DD/YYYY, DD.MM.YYYY, YYYY-MM-DD
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d.%m.%Y", "%d/%m/%Y"):
                    try:
                        record["date"] = datetime.strptime(val, fmt).strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        pass
            elif mapped and mapped != "date":
                try:
                    record[mapped] = float(val) if val else None
                except ValueError:
                    record[mapped] = val if val else None
            elif val:
                # Unbekannte column → in context_json
                extra[col.strip()] = val

        if "date" not in record:
            continue

        # ln(RMSSD) → RMSSD ableiten if RMSSD fehlt
        if record.get("rmssd_ms") is None and record.get("ln_rmssd") is not None:
            import math
            try:
                record["rmssd_ms"] = round(math.exp(record["ln_rmssd"]), 2)
            except Exception:
                pass

        if extra:
            import json
            record["context_json"] = json.dumps(extra, ensure_ascii=False)

        records.append(record)

    return records


def _save(conn, records: list[dict], dry_run: bool = False, person: str | None = None) -> int:
    person = resolve_person(person)
    neu = 0
    for r in records:
        existing = conn.execute(
            "SELECT date FROM hrv4training_daily WHERE date = ?", (r["date"],)
        ).fetchone()
        if existing:
            continue

        if dry_run:
            print(t(f"  [DRY] {r['date']}  RMSSD={r.get('rmssd_ms')} ms  "
                    f"HR={r.get('hr_bpm')} bpm  Bereitschaft={r.get('readiness')}",
                    f"  [DRY] {r['date']}  RMSSD={r.get('rmssd_ms')} ms  "
                    f"HR={r.get('hr_bpm')} bpm  Readiness={r.get('readiness')}"))
            neu += 1
            continue

        conn.execute("""
            INSERT INTO hrv4training_daily
              (date, rmssd_ms, ln_rmssd, hr_bpm, hrv4t_score, readiness,
               sleep_quality, fatigue, mood, motivation, muscle_soreness,
               tags, comment, context_json, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            r["date"], r.get("rmssd_ms"), r.get("ln_rmssd"), r.get("hr_bpm"),
            r.get("hrv4t_score"), r.get("readiness"), r.get("sleep_quality"),
            r.get("fatigue"), r.get("mood"), r.get("motivation"),
            r.get("muscle_soreness"), r.get("tags"), r.get("comment"),
            r.get("context_json"), "hrv4training"
        ))
        if r.get("comment") or r.get("tags"):
            conn.execute(
                "INSERT OR IGNORE INTO user_context"
                " (id, date, ts_start, ts_end, person, source, source_app, tag, note)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (f"hrv4training:{r['date']}", r["date"], None, None,
                 person, 'hrv4training', 'hrv4training',
                 r.get("tags") or None, r.get("comment") or None),
            )
        neu += 1

    if not dry_run and neu > 0:
        conn.commit()
    return neu


def main():
    parser = argparse.ArgumentParser(description=t("HRV4Training CSV importieren", "Import HRV4Training CSV"))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", metavar="CSV",    help="HRV4Workout CSV-Export")
    group.add_argument("--dir",  metavar="ORDNER", help="Folder with CSV-Exporten")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    paths = [Path(args.file)] if args.file else sorted(Path(args.dir).glob("*.csv"))
    if not paths:
        print(t("Keine CSV-Dateien gefunden.", "No CSV files found."))
        return

    conn = open_db()
    row = conn.execute("SELECT type FROM sqlite_master WHERE name='hrv4training_daily'").fetchone()
    if row and row[0] == "view":
        conn.execute("DROP VIEW hrv4training_daily")
    conn.execute(CREATE_TABLE)
    conn.commit()

    total_neu = 0
    for p in paths:
        records = parse_csv(p)
        if not records:
            print(t(f"  ⚠ Keine Datensätze in {p.name}", f"  ⚠ No records in {p.name}"))
            continue
        n = _save(conn, records, dry_run=args.dry_run, person=person)
        print(t(f"  {p.name}: {len(records)} gelesen, {n} neu importiert", f"  {p.name}: {len(records)} read, {n} newly imported"))
        total_neu += n

    if not args.dry_run:
        log_import(conn, 'hrv4training', str(paths[0].parent) if paths else '', total_neu, person=person)
        conn.commit()
    conn.close()
    print(t(f"\nGesamt: {total_neu} neue Einträge", f"\nTotal: {total_neu} new entries") +
          (" (DRY-RUN)" if args.dry_run else ""))
    if total_neu > 0 and not args.dry_run:
        print(t("Analyse: python analyse/analyse_hrv_fatigue.py --symptom Erschöpfung", "Analysis: python analyse/analyse_hrv_fatigue.py --symptom Erschöpfung"))


if __name__ == "__main__":
    main()
