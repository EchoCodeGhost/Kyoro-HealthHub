#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Stryd (Laufleistungsmesser) → health.db

@tier        infrastructure
@purpose.de  Importiert sekundengenaue Laufdynamik-Daten (Leistung, Kadenz,
             Bodenkontaktzeit, vertikale Oszillation, Herzfrequenz) aus Stryd-
             CSV-Exporten. Objektiviert die Belastungskosten von Alltags-
             bewegung bei ausgeprägtem aerobem Defizit — insbesondere das
             Missverhältnis zwischen minimaler Wattzahl und überproportionaler
             Herzfrequenz-Antwort, das mit Standard-Pace/Speed-Metriken allein
             nicht sichtbar wird.
@purpose.en  Imports second-by-second running dynamics data (power, cadence,
             ground contact time, vertical oscillation, heart rate) from Stryd
             CSV exports. Objectifies the exertion cost of everyday movement
             under a pronounced aerobic deficit — in particular the mismatch
             between minimal wattage and a disproportionate heart rate
             response, which plain pace/speed metrics alone don't reveal.
@method.de   CSV-Format (ein Header, danach eine Zeile pro Sekunde): Timestamp
             (Unix-Epoch, Sekunden) + 20 Stryd-Spalten (Power/Form Power/Air
             Power in W/kg, Watch- und Stryd-Speed/Distance, Stiffness,
             Ground Time, Cadence, Vertical Oscillation, Watch- und Stryd-
             Elevation, Heart Rate, vier Balance-Metriken, Vertical Ratio).
             Unix-Timestamp wird als UTC interpretiert (Stryd-Export enthält
             keine Zeitzone) und nach ISO 8601 konvertiert. session_id = ISO-
             Timestamp der ersten Zeile. Footpod-Gerät wird über
             cfg.footpod_device_id aufgelöst (sensor_type=='footpod' in
             device_registry, sonst generischer Fallback 'footpod_1' —
             Marke bewusst nicht hartkodiert, s. cross-cutting-conventions).
@method.en   CSV format (one header row, then one row per second): Timestamp
             (Unix epoch, seconds) + 20 Stryd columns (Power/Form Power/Air
             Power in W/kg, watch and Stryd speed/distance, stiffness, ground
             time, cadence, vertical oscillation, watch and Stryd elevation,
             heart rate, four balance metrics, vertical ratio). Unix timestamp
             is treated as UTC (the Stryd export carries no timezone) and
             converted to ISO 8601. session_id = ISO timestamp of the first
             row. Footpod device resolved via cfg.footpod_device_id
             (sensor_type=='footpod' in device_registry, otherwise a generic
             'footpod_1' fallback — brand deliberately not hardcoded, see
             cross-cutting-conventions).
@reads       {imports/stryd/}*.csv (Stryd-Sekunden-Export)
@writes      health.db (stryd_sessions, stryd_samples)
@limits.de   Kein GPS/Lat-Lon im Stryd-Export — nur Elevation. Balance-Metriken
             (Ground Time/Vertical Oscillation/Leg Spring Stiffness/Impact
             Loading Rate Balance) erfordern einen Dual-Footpod-Aufbau und
             sind bei Single-Pod-Nutzung durchgehend 0 — kein Fehler, keine
             fehlende Beinsymmetrie-Aussage möglich. Keine automatische
             Verknüpfung zu einer parallel importierten Uhren-Session (z.B.
             Apple Watch) — beide bleiben unabhängige Datensätze, kein
             Duplikat-Risiko, aber auch keine automatische Merge-Ansicht.
@limits.en   No GPS lat/lon in the Stryd export — elevation only. Balance
             metrics (ground time/vertical oscillation/leg spring stiffness/
             impact loading rate balance) require a dual-footpod setup and
             are consistently 0 with a single pod — not an error, no
             leg-symmetry statement possible in that case. No automatic
             linking to a separately imported watch session (e.g. Apple
             Watch) — both remain independent records, no duplicate risk but
             also no automatic merged view.

@relevance.de  Ermöglicht den Import von Laufdynamik-Daten, wichtig für die Belastungsanalyse bei aerobem Defizit
@relevance.en  Enables import of running dynamics data, important for exertion analysis under aerobic deficit
@usage
    python3 import_stryd.py --file lauf.csv
    python3 import_stryd.py --dir imports/stryd/
    python3 import_stryd.py --file lauf.csv --person PER-xxxx
"""

import argparse
import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import ImportResult, resolve_person, resolve_timezone, local_date, log_import

_cfg = _Cfg()

CSV_DIR = Path(_cfg._cfg.get("paths", {}).get("stryd_dir",
          str(Path.home() / "Kyoro-HealthHub" / "imports" / "stryd")))

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stryd_sessions (
    session_id   TEXT NOT NULL,
    person       TEXT NOT NULL DEFAULT 'unknown',
    ts_start     TEXT NOT NULL,
    ts_end       TEXT,
    date         TEXT NOT NULL,
    duration_s   INTEGER,
    device_id    TEXT REFERENCES devices(device_id),
    source_file  TEXT,
    PRIMARY KEY (session_id, person)
);
CREATE TABLE IF NOT EXISTS stryd_samples (
    session_id                   TEXT NOT NULL,
    session_person               TEXT NOT NULL DEFAULT 'unknown',
    ts                           TEXT NOT NULL,
    power_wkg                    REAL,
    form_power_wkg                REAL,
    air_power_wkg                REAL,
    watch_speed_ms               REAL,
    stryd_speed_ms                REAL,
    watch_distance_m             REAL,
    stryd_distance_m              REAL,
    stiffness                    REAL,
    stiffness_per_kg             REAL,
    ground_time_ms                REAL,
    cadence_spm                  INTEGER,
    vertical_oscillation_cm      REAL,
    watch_elevation_m            REAL,
    stryd_elevation_m             REAL,
    heart_rate_bpm               INTEGER,
    ground_time_balance          REAL,
    vertical_oscillation_balance REAL,
    leg_spring_stiffness_balance REAL,
    impact_loading_rate_balance  REAL,
    vertical_ratio               REAL,
    PRIMARY KEY (session_id, session_person, ts),
    FOREIGN KEY (session_id, session_person) REFERENCES stryd_sessions(session_id, person)
);
"""

# Stryd-CSV-Spaltenname -> DB-Spaltenname
_COLUMN_MAP = {
    "Power (w/kg)":                    "power_wkg",
    "Form Power (w/kg)":               "form_power_wkg",
    "Air Power (w/kg)":                "air_power_wkg",
    "Watch Speed (m/s)":               "watch_speed_ms",
    "Stryd Speed (m/s)":               "stryd_speed_ms",
    "Watch Distance (meters)":         "watch_distance_m",
    "Stryd Distance (meters)":         "stryd_distance_m",
    "Stiffness":                       "stiffness",
    "Stiffness/kg":                    "stiffness_per_kg",
    "Ground Time (ms)":                "ground_time_ms",
    "Cadence (spm)":                   "cadence_spm",
    "Vertical Oscillation (cm)":       "vertical_oscillation_cm",
    "Watch Elevation (m)":             "watch_elevation_m",
    "Stryd Elevation (m)":             "stryd_elevation_m",
    "Heart Rate (bpm)":                "heart_rate_bpm",
    "Ground Time Balance":             "ground_time_balance",
    "Vertical Oscillation Balance":    "vertical_oscillation_balance",
    "Leg Spring Stiffness Balance":    "leg_spring_stiffness_balance",
    "Impact Loading Rate Balance":     "impact_loading_rate_balance",
    "Vertical Ratio":                  "vertical_ratio",
}


def _ensure_device(conn: sqlite3.Connection) -> str:
    device_id = _cfg.footpod_device_id
    conn.execute(
        "INSERT OR IGNORE INTO devices(device_id, sensor_type, date_from) VALUES (?,'footpod',NULL)",
        (device_id,),
    )
    return device_id


def _parse_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            ts_raw = (raw.get("Timestamp") or "").strip()
            if not ts_raw:
                continue
            try:
                ts_unix = int(float(ts_raw))
            except ValueError:
                continue
            ts_iso = datetime.fromtimestamp(ts_unix, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
            rec = {"ts": ts_iso}
            for csv_col, db_col in _COLUMN_MAP.items():
                v = (raw.get(csv_col) or "").strip()
                if v == "":
                    rec[db_col] = None
                    continue
                try:
                    rec[db_col] = int(v) if db_col in ("cadence_spm", "heart_rate_bpm") else float(v)
                except ValueError:
                    rec[db_col] = None
            rows.append(rec)
    return rows


def run(conn: sqlite3.Connection, data_path: str, lang: str = "de", person: str | None = None) -> ImportResult:
    person = resolve_person(person)
    path = Path(data_path)
    files = [path] if path.is_file() else sorted(path.glob("*.csv"))
    if not files:
        return ImportResult(source="stryd", errors=[t(f"Keine CSV-Dateien in {data_path}",
                                                        f"No CSV files in {data_path}")])

    conn.executescript(CREATE_TABLE_SQL)
    device_id = _ensure_device(conn)

    total_ins = total_skip = 0
    errors: list[str] = []

    for f in files:
        rows = _parse_csv(f)
        if not rows:
            errors.append(t(f"  {f.name}: keine gültigen Zeilen", f"  {f.name}: no valid rows"))
            continue

        ts_start = rows[0]["ts"]
        ts_end = rows[-1]["ts"]
        session_id = ts_start
        tz_name = resolve_timezone(conn, person, ts=ts_start)
        date = local_date(ts_start, tz_name)
        duration_s = int((datetime.fromisoformat(ts_end) - datetime.fromisoformat(ts_start)).total_seconds())

        conn.execute("""
            INSERT OR IGNORE INTO stryd_sessions
            (session_id, person, ts_start, ts_end, date, duration_s, device_id, source_file)
            VALUES (?,?,?,?,?,?,?,?)
        """, (session_id, person, ts_start, ts_end, date, duration_s, device_id, f.name))

        for rec in rows:
            cur = conn.execute("""
                INSERT OR IGNORE INTO stryd_samples
                (session_id, session_person, ts, power_wkg, form_power_wkg, air_power_wkg,
                 watch_speed_ms, stryd_speed_ms, watch_distance_m, stryd_distance_m,
                 stiffness, stiffness_per_kg, ground_time_ms, cadence_spm,
                 vertical_oscillation_cm, watch_elevation_m, stryd_elevation_m,
                 heart_rate_bpm, ground_time_balance, vertical_oscillation_balance,
                 leg_spring_stiffness_balance, impact_loading_rate_balance, vertical_ratio)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                session_id, person, rec["ts"],
                rec.get("power_wkg"), rec.get("form_power_wkg"), rec.get("air_power_wkg"),
                rec.get("watch_speed_ms"), rec.get("stryd_speed_ms"),
                rec.get("watch_distance_m"), rec.get("stryd_distance_m"),
                rec.get("stiffness"), rec.get("stiffness_per_kg"), rec.get("ground_time_ms"),
                rec.get("cadence_spm"), rec.get("vertical_oscillation_cm"),
                rec.get("watch_elevation_m"), rec.get("stryd_elevation_m"),
                rec.get("heart_rate_bpm"), rec.get("ground_time_balance"),
                rec.get("vertical_oscillation_balance"), rec.get("leg_spring_stiffness_balance"),
                rec.get("impact_loading_rate_balance"), rec.get("vertical_ratio"),
            ))
            if cur.rowcount:
                total_ins += 1
            else:
                total_skip += 1

        print(t(f"  {f.name}: {len(rows)} Samples ({ts_start} .. {ts_end}, {duration_s}s)",
                f"  {f.name}: {len(rows)} samples ({ts_start} .. {ts_end}, {duration_s}s)"))

    log_import(conn, "stryd", str(path), total_ins, total_skip, person=person)
    conn.commit()
    return ImportResult(source="stryd", rows_inserted=total_ins, rows_skipped=total_skip, errors=errors)


def main():
    """
    Hauptfunktion: Importiert Stryd-CSV-Exporte in health.db.

    Command-Line-Argumente:
        --file: Einzelne CSV-Datei
        --dir: Verzeichnis mit CSV-Dateien (Standard: imports/stryd/)
        --person: Personen-ID
    """
    parser = argparse.ArgumentParser(
        description=t("Stryd-Laufdynamik-Daten importieren", "Import Stryd running dynamics data"))
    parser.add_argument("--file", type=str, default=None)
    parser.add_argument("--dir", type=str, default=None)
    parser.add_argument("--person", type=str, default=None)
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    data_path = args.file or args.dir or str(CSV_DIR)
    conn = open_db()
    result = run(conn, data_path, lang=args.lang, person=args.person)
    conn.close()

    print(t(f"\nStryd: {result}", f"\nStryd: {result}"))
    for err in result.errors:
        print(err)


if __name__ == "__main__":
    main()
