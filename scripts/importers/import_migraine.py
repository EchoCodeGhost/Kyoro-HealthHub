#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Migraine-App → health.db

@tier        infrastructure
@purpose.de  Importiert Migräne- und Kopfschmerz-Daten aus der Migraine-App in die health.db.
             Ermöglicht detaillierte Dokumentation von Anfällen und Bewertung der Beeintächtigung.
@purpose.en  Imports migraine and headache data from the Migraine-App into health.db.
             Enables detailed documentation of attacks and assessment of impairment.
@method.de   Liest .mbu-Backup-Dateien aus ~/Kyoro-HealthHub/imports/migraene_app/.
             Mapping: Migräne-Anfälle → sessions (type='migraine') + session_metrics,
             HIT-6 / MIDAS Fragebögen → assessments. Intensität und Typ werden
             nach vordefinierten Mappings übersetzt.
@method.en   Reads .mbu backup files from ~/Kyoro-HealthHub/imports/migraene_app/.
             Mapping: Migraine attacks → sessions (type='migraine') +
             session_metrics, HIT-6 / MIDAS questionnaires → assessments.
             Intensity and type are translated according to predefined mappings.
@reads       {imports/migraene_app/}*.mbu (Migraine-App Backup)
@writes      health.db (sessions, session_metrics, assessments)
@limits.de   Keine Validierung der Migraine-App-Datenqualität. Keine medizinische
             Bewertung aus den Daten. HIT-6 und MIDAS sind validierte Fragebögen.

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en   No validation of Migraine-App data quality. No medical assessment
             from the data. HIT-6 and MIDAS are validated questionnaires.
@usage
    python3 import_migraine.py           # all .mbu files
    python3 import_migraine.py --update  # only neue Daten
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person
_cfg = _Cfg()

DB_PATH = _cfg.db_path
MIGRAINE_DIR = _cfg.migraine_dir
MIGRAINE_DIR.mkdir(parents=True, exist_ok=True)

INTENSITY = {0: "keine", 1: "leicht", 2: "mittel", 3: "stark", 4: "sehr stark"}
TYPE_MAP  = {1: "Kopfschmerz", 2: "Migräne", 3: "Clusterkopfschmerz"}


def _to_utc(dt_local: str, date: str) -> str | None:
    """Approximate CET/CEST → UTC: subtract 2h Apr-Sep, 1h otherwise."""
    if not dt_local:
        return None
    try:
        month = int(date[5:7])
        offset_h = 2 if 4 <= month <= 9 else 1
        dt = datetime.fromisoformat(dt_local[:19])
        dt_utc = dt - timedelta(hours=offset_h)
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    except Exception:
        return dt_local[:19] + "+00:00"


def _add_seconds(ts_utc: str, seconds: int) -> str | None:
    if not ts_utc or not seconds:
        return None
    try:
        dt = datetime.fromisoformat(ts_utc)
        return (dt + timedelta(seconds=seconds)).isoformat()
    except Exception:
        return None


def _metrics(cursor, session_id: str, pairs: list) -> int:
    n = 0
    for metric, value, value_text, unit in pairs:
        if value is None and value_text is None:
            continue
        cursor.execute(
            "INSERT OR IGNORE INTO session_metrics(session_id, metric, value, value_text, unit) "
            "VALUES (?,?,?,?,?)",
            (session_id, metric, value, value_text, unit)
        )
        n += 1
    return n


def get_last_import(conn) -> str | None:
    r = conn.execute(
        "SELECT MAX(date) FROM sessions WHERE type='migraine' AND source_app='migraene_app'"
    ).fetchone()
    return r[0] if r and r[0] else None


def import_mbu(conn, filepath: Path, update_from: str | None, person: str) -> dict:
    data = json.loads(filepath.read_text(encoding="utf-8"))
    counts = {"anfaelle": 0, "hit6": 0, "midas": 0}
    cur = conn.cursor()

    for a in data.get("attacks", []):
        dt_raw = a.get("date", "")
        if not dt_raw:
            continue
        dt   = dt_raw[:19]
        date = dt_raw[:10]
        if update_from and date < update_from:
            continue

        typ_val   = a.get("typeValue", 2)
        typ       = TYPE_MAP.get(typ_val, f"Typ {typ_val}")
        intensity = a.get("intensityValue", 0)
        dauer_h   = a.get("duration")

        clean    = dt.replace(":", "").replace("T", "_")[:16]
        sid      = f"migraine_app_{clean}"
        ts_start = _to_utc(dt, date)
        ts_end   = _add_seconds(ts_start, int(dauer_h * 3600)) if dauer_h and ts_start else None

        cur.execute(
            "INSERT OR IGNORE INTO sessions"
            "(id, type, ts_start, ts_end, date, device_id, person, source_app) "
            "VALUES (?, 'migraine', ?, ?, ?, NULL, ?, 'migraene_app')",
            (sid, ts_start, ts_end, date, person)
        )

        _metrics(cur, sid, [
            ("severity",          intensity,                   None, None),
            ("duration_h",        dauer_h,                     None, "h"),
            ("aura",              1 if a.get("aura") else 0,   None, None),
            ("nausea",            1 if a.get("nausea") else 0, None, None),
            ("vomiting",          1 if a.get("sickness") else 0, None, None),
            ("pressure_hpa",      a.get("pressure", 0),        None, "hPa"),
            ("temperature_c",     a.get("temperature", 0),     None, "°C"),
            ("activity_impact",   1 if a.get("activity") else 0, None, None),
            ("impact_home",       a.get("gdbkHomeValue"),      None, None),
            ("impact_work",       a.get("gdbkWorkValue"),      None, None),
            ("impact_leisure",    a.get("gdbkFreetimeValue"),  None, None),
            ("medication_effect", a.get("medicationEffectValue"), None, None),
            ("type",              None, typ,                   None),
            ("medication",        None, a.get("medication"),   None),
            ("notes",             None, a.get("remarks"),      None),
        ])
        if a.get("remarks"):
            cur.execute(
                "INSERT OR IGNORE INTO user_context"
                " (id, date, ts_start, ts_end, person, source, source_app, tag, note)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (f"migraine:{sid}", date, ts_start, ts_end,
                 person, 'migraene_app', 'migraene_app', typ, a["remarks"]),
            )
        counts["anfaelle"] += 1

    # HIT-6 + MIDAS → assessments
    for h in data.get("hit6", []):
        dt_str = h.get("date", "")
        if not dt_str:
            continue
        dt   = dt_str[:19]
        date = dt_str[:10]
        if update_from and date < update_from:
            continue
        score = h.get("score") or h.get("value")
        try:
            cur.execute(
                "INSERT OR IGNORE INTO assessments(ts, date, instrument, score, person, source) "
                "VALUES (?,?,?,?,?,?)",
                (dt, date, "HIT-6", float(score) if score is not None else None, person, "migraene_app")
            )
            counts["hit6"] += 1
        except Exception:
            pass

    for m in data.get("midas", []):
        dt_str = m.get("date", "")
        if not dt_str:
            continue
        dt   = dt_str[:19]
        date = dt_str[:10]
        if update_from and date < update_from:
            continue
        score = m.get("score") or m.get("value")
        try:
            cur.execute(
                "INSERT OR IGNORE INTO assessments(ts, date, instrument, score, person, source) "
                "VALUES (?,?,?,?,?,?)",
                (dt, date, "MIDAS", float(score) if score is not None else None, person, "migraene_app")
            )
            counts["midas"] += 1
        except Exception:
            pass

    conn.commit()
    return counts


def main():
    """
    Hauptfunktion: Koordiniert den Import der Migraine-App-Daten.

    Command-Line-Argumente:
        --update: Nur neue Daten
    """
    parser = argparse.ArgumentParser(description=t("Migräne-App → health.db", "Migraine App → health.db"))
    parser.add_argument("--update", action="store_true", help="Nur neue Daten")
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    update_from = None
    if args.update:
        last = get_last_import(conn)
        if last:
            d = datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)
            update_from = d.strftime("%Y-%m-%d")
            print(t(f"Update-Modus: ab {update_from}", f"Update mode: from {update_from}"))

    files = sorted(MIGRAINE_DIR.glob("*.mbu")) + sorted(MIGRAINE_DIR.glob("*.MBU"))
    if not files:
        print(t(f"Keine .mbu Dateien in {MIGRAINE_DIR}", f"No .mbu files in {MIGRAINE_DIR}"))
        return

    total = {"anfaelle": 0, "hit6": 0, "midas": 0}
    for f in files:
        print(f"  {f.name} ...", flush=True)
        c = import_mbu(conn, f, update_from, person)
        for k in total: total[k] += c[k]
        print(t(f"    Anfälle: {c['anfaelle']} | HIT-6: {c['hit6']} | MIDAS: {c['midas']}",
                f"    Attacks: {c['anfaelle']} | HIT-6: {c['hit6']} | MIDAS: {c['midas']}"))

    r = conn.execute("""
        SELECT COUNT(*), MIN(date), MAX(date)
        FROM sessions WHERE type='migraine' AND source_app='migraene_app'
    """).fetchone()

    print(t("\n── Migräne-Daten ────────────────────────────────────────────", "\n── Migraine data ────────────────────────────────────────────"))
    if r and r[0]:
        print(t(f"  Anfälle: {r[0]} | {r[1]} – {r[2]}", f"  Attacks: {r[0]} | {r[1]} – {r[2]}"))

    log_import(conn, 'migraine', str(MIGRAINE_DIR), total['anfaelle'] + total['hit6'] + total['midas'], person=person)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
