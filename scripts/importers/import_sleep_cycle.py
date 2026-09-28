#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Sleep Cycle CSV → health.db (sessions, session_metrics)

@tier infrastructure
@purpose.de Import von Schlafdaten aus der Sleep Cycle App (iOS) für Schlafanalysen
@purpose.en Import sleep data from Sleep Cycle app (iOS) for sleep analysis
@method.de Parsen von Semikolon-separierten CSV-Dateien mit Schlafmetriken.
           Erstellt sessions-Einträge (type='sleep') und speichert Metriken in session_metrics.
           Unterstützt Update-Modus zum Ergänzen neuer Nächte.
@method.en Parse semicolon-separated CSV files with sleep metrics.
           Create sessions entries (type='sleep') and store metrics in session_metrics.
           Supports update mode to add new nights.
@reads ~/Kyoro-HealthHub/data/sleep_cycle/sleepdata*.csv
@writes health.db:sessions, health.db:session_metrics, health.db:user_context, health.db:import_log
@limits.de Verarbeitet nur sleepdata*.csv Dateien. Zeitstempel werden von lokaler zu UTC konvertiert.
           Historische Daten werden nicht überschrieben (INSERT OR IGNORE).

@relevance.de  Ermöglicht den Import von Gesundheitsdaten, essentiell für die umfassende Datenanalyse
@relevance.en  Enables import of health data, essential for comprehensive data analysis
@limits.en Only processes sleepdata*.csv files. Timestamps are converted from local to UTC.
           Historical data is not overwritten (INSERT OR IGNORE).
@usage python3 import_sleep_cycle.py           # all CSVs
       python3 import_sleep_cycle.py --update  # only neue Nights ergänzen
"""

import argparse
import csv
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import, resolve_person

_cfg = _Cfg()
DB_PATH   = _cfg.db_path
SLEEP_DIR = _cfg.data_root / "sleep_cycle"
SLEEP_DIR.mkdir(parents=True, exist_ok=True)


def _to_utc(dt_local: str, date: str) -> str:
    """Konvertierung eines lokalen Zeitstempels zu UTC.
    
    @purpose.de Anpassung von Sleep Cycle Zeitstempeln (lokal, CET/CEST) zu UTC
    @purpose.en Convert Sleep Cycle timestamps (local, CET/CEST) to UTC
    @method.de Berücksichtigt Sommer- und Winterzeit (CEST: +2h, CET: +1h) basierend auf Monat
    @method.en Accounts for daylight saving time (CEST: +2h, CET: +1h) based on month
    @param dt_local Lokaler Zeitstempel (ISO-Format mit Zeit)
    @param date Datum im ISO-Format (YYYY-MM-DD) zur Monatsbestimmung
    @returns UTC-Zeitstempel als ISO-String
    """
    try:
        month = int(date[5:7])
        offset_h = 2 if 4 <= month <= 9 else 1
        dt = datetime.fromisoformat(dt_local[:19])
        return (dt - timedelta(hours=offset_h)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    except Exception:
        return dt_local[:19] + "+00:00"


def _pct(v: str) -> float | None:
    """Parsen eines Prozentwerts aus String.
    
    @purpose.de Konvertierung von Prozentstrings (z.B. '85%') zu Float-Werten
    @purpose.en Convert percentage strings (e.g. '85%') to float values
    @method.de Entfernt %-Zeichen und konvertiert zu float. Leere Werte ergeben None.
    @method.en Remove % sign and convert to float. Empty values return None.
    @param v Prozentstring oder numerischer String
    @returns Float-Wert (0.0-100.0) oder None
    """
    if not v or v.strip() == '':
        return None
    return float(v.strip().rstrip('%')) if '%' in v else (float(v) if v else None)


def _num(v: str) -> float | None:
    """Parsen eines numerischen Werts aus String.
    
    @purpose.de Sichere Konvertierung von Strings zu Float-Werten
    @purpose.en Safe conversion of strings to float values
    @method.de Gibt None zurück bei Parse-Fehlern oder leeren Strings
    @method.en Returns None on parse errors or empty strings
    @param v Numerischer String
    @returns Float-Wert oder None
    """
    v = v.strip() if v else ''
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _metrics(cursor, session_id: str, pairs: list) -> None:
    """Speichern von Metrik-Werten in session_metrics-Tabelle.
    
    @purpose.de Batch-Insert von Schlafmetriken für eine Session
    @purpose.en Batch insert of sleep metrics for a session
    @method.de Filtert None-Werte und fügt nur gültige Einträge ein (INSERT OR IGNORE)
    @method.en Filters None values and inserts only valid entries (INSERT OR IGNORE)
    @param cursor SQLite-Cursor
    @param session_id Session-ID (z.B. 'sleep_cycle_2024-01-15')
    @param pairs Liste von Tuples (metric, value, value_text, unit)
    """
    for metric, value, value_text, unit in pairs:
        if value is None and value_text is None:
            continue
        cursor.execute(
            "INSERT OR IGNORE INTO session_metrics(session_id, metric, value, value_text, unit) "
            "VALUES (?,?,?,?,?)",
            (session_id, metric, value, value_text, unit)
        )


def import_sleep_cycle(conn: sqlite3.Connection, sleep_dir: Path = SLEEP_DIR,
                       update_only: bool = False, person: str | None = None) -> int:
    """Import aller Sleep Cycle CSV-Dateien aus einem Verzeichnis.
    
    @purpose.de Hauptfunktion für den Import von Schlafdaten
    @purpose.en Main function for importing sleep data
    @method.de Durchsucht Verzeichnis nach sleepdata*.csv, parst jede Datei,
               erstellt sessions und session_metrics Einträge
    @method.en Scans directory for sleepdata*.csv, parses each file,
               creates sessions and session_metrics entries
    @param conn SQLite-Datenbankverbindung
    @param sleep_dir Verzeichnis mit Sleep Cycle CSV-Dateien (Standard: SLEEP_DIR)
    @param update_only Nur neue Nächte importieren (bestehende überspringen)
    @returns Anzahl der verarbeiteten Nächte
    """
    csv_files = sorted(sleep_dir.glob("sleepdata*.csv"))
    if not csv_files:
        print(t(f"  Keine sleepdata*.csv in {sleep_dir}", f"  No sleepdata*.csv in {sleep_dir}"))
        return 0

    person = resolve_person(person)
    cur   = conn.cursor()
    count = 0

    for csv_path in csv_files:
        with open(csv_path, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                start = row.get('Start', '').strip()
                end   = row.get('End', '').strip()
                if not start:
                    continue

                date      = start[:10]
                sid       = f"sleep_cycle_{date}"
                ts_start  = _to_utc(start, date)
                ts_end    = _to_utc(end, date) if end else None

                if update_only:
                    existing = cur.execute("SELECT id FROM sessions WHERE id=?", (sid,)).fetchone()
                    if existing:
                        continue

                cur.execute(
                    "INSERT OR IGNORE INTO sessions"
                    "(id, type, ts_start, ts_end, date, device_id, person, source_app) "
                    "VALUES (?, 'sleep', ?, ?, ?, NULL, ?, 'sleep_cycle')",
                    (sid, ts_start, ts_end, date, person)
                )

                note = row.get('Notes', '').strip() or None
                if note:
                    cur.execute(
                        "INSERT OR IGNORE INTO user_context"
                        "(id, date, ts_start, ts_end, person, source, source_app, tag, note) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (f"sleep_cycle:{date}", date, ts_start, ts_end,
                         person, "sleep_cycle", "sleep_cycle", None, note),
                    )

                time_bed_s = _num(row.get('Time in bed (seconds)', ''))
                _metrics(cur, sid, [
                    ("time_asleep_s",    _num(row.get('Time asleep (seconds)', '')),    None, "s"),
                    ("time_bed_s",       time_bed_s,                                    None, "s"),
                    ("awake_s",          _num(row.get('Awake (seconds)', '')),          None, "s"),
                    ("latency_s",        _num(row.get('Time before sleep (seconds)', '')), None, "s"),
                    ("rem_s",            _num(row.get('Dream (seconds)', '')),          None, "s"),
                    ("light_s",          _num(row.get('Light (seconds)', '')),          None, "s"),
                    ("deep_s",           _num(row.get('Deep (seconds)', '')),           None, "s"),
                    ("snore_s",          _num(row.get('Snore time (seconds)', '')),     None, "s"),
                    ("sleep_quality_pct", _pct(row.get('Sleep Quality', '')),           None, "%"),
                    ("regularity_pct",   _pct(row.get('Regularity', '')),              None, "%"),
                    ("hr_avg",           _num(row.get('Heart rate (bpm)', '')),         None, "bpm"),
                    ("respiration_avg",  _num(row.get('Respiratory rate (breaths per minute)', '')), None, "rpm"),
                    ("movements_per_h",  _num(row.get('Movements per hour', '')),      None, "/h"),
                    ("breathing_disrupt", _num(row.get('Breathing disruptions (per hour)', '')), None, "/h"),
                    ("coughs_per_h",     _num(row.get('Coughs (per hour)', '')),          None, "/h"),
                    ("ambient_noise_db", _num(row.get('Ambient Noise (dB)', '')),      None, "dB"),
                    ("body_temp_dev",    _num(row.get('Body temperature deviation (degrees Celsius)', '')), None, "°C"),
                    ("mood",             None, row.get('Mood', '').strip() or None,   None),
                ])
                count += 1

    log_import(conn, 'sleep_cycle', str(sleep_dir), count, person=person)
    conn.commit()
    return count


def main():
    """Hauptfunktion für den Sleep Cycle Import.
    
    @purpose.de Orchestrierung des Import-Prozesses mit Argument-Parsing
    @purpose.en Orchestrate import process with argument parsing
    @method.de Parsen von CLI-Argumenten, Öffnen der DB, Aufruf von import_sleep_cycle,
               Anzeige von Statistiken
    @method.en Parse CLI arguments, open DB, call import_sleep_cycle,
               display statistics
    """
    parser = argparse.ArgumentParser(description=t("Sleep Cycle CSV → health.db", "Sleep Cycle CSV → health.db"))
    parser.add_argument("--update", action="store_true",
                        help="Nur neue Nächte ergänzen (kein Überschreiben)")
    parser.add_argument("--sleep-dir", metavar="DIR", default=None)
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    sleep_dir = Path(args.sleep_dir) if args.sleep_dir else SLEEP_DIR

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    print(t("\n── Sleep Cycle ────────────────────────────────────────", "\n── Sleep Cycle ────────────────────────────────────────"))
    n = import_sleep_cycle(conn, sleep_dir, update_only=args.update, person=person)
    print(t(f"  {n} Nächte verarbeitet", f"  {n} nights processed"))

    r = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM sessions WHERE source_app='sleep_cycle'"
    ).fetchone()
    print(t(f"  Gesamt: {r[0]} | {r[1]}–{r[2]}", f"  Total: {r[0]} | {r[1]}–{r[2]}"))

    conn.close()


if __name__ == "__main__":
    main()
