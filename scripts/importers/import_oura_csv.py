#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Oura Ring CSV-Export → health.db

@tier        infrastructure
@purpose.de  Importiert Daten aus Oura Ring CSV-Exporten (data.zip) als Ergänzung
             zur API. Bietet granularere Rohdaten und zusätzliche Metriken, die
             nicht über die offizielle API verfügbar sind.
@purpose.en  Imports data from Oura Ring CSV exports (data.zip) as a supplement
             to the API. Provides more granular raw data and additional metrics
             not available through the official API.
@method.de   Liest die data.zip-Datei aus imports/oura/ oder einem expliziten Pfad.
             Importiert: Zyklusdaten (Phasen, Fruchtbarkeit), Tages-Tags, Rohdaten
             (Temperatur, Tagesstress, Schlafmodell), Metriken (VO2max, Workouts,
             Kontrazeption, OMSS-Score) und Aufenthaltsdaten. Workouts landen
             zusätzlich (gefiltert nach Aktivitätstyp, s.
             mirror_workouts_to_sessions) in sessions/session_metrics, damit sie
             wie Polar-Trainings in trainingload-basierte Trigger (compute_pem.py)
             einfließen können — oura_workouts selbst bleibt die vollständige,
             ungefilterte Rohablage.
@method.en   Reads the data.zip file from imports/oura/ or an explicit path.
             Imports: cycle data (phases, fertility), day tags, raw data
             (temperature, daytime stress, sleep model), metrics (VO2max, workouts,
             contraception, OMSS score), and location stays. Workouts are
             additionally mirrored (filtered by activity type, see
             mirror_workouts_to_sessions) into sessions/session_metrics so they
             can feed training-load-based triggers (compute_pem.py) the same
             way Polar trainings do — oura_workouts itself remains the
             complete, unfiltered raw record.
@reads       {imports/oura/}/data.zip (Oura CSV Export)
@writes      health.db (oura_cycle_insights, oura_period_starts,
             oura_cycle_predictions, oura_tags, oura_temperature_raw,
             oura_daytime_stress, oura_sleep_model, oura_vo2max, oura_workouts,
             oura_contraception, oura_survey, location_stays, sessions,
             session_metrics, ...)
@limits.de   Ergänzt die API-Daten, ersetzt sie nicht. Einige Tabellen
             werden nur erstellt, wenn Daten vorhanden sind. Keine medizinische
             Interpretation. training_load für gespiegelte Oura-Workouts ist
             eine grobe kalorienbasierte Näherung (s.
             OURA_TRAINING_LOAD_CAL_FACTOR), nicht herzfrequenzbasiert wie bei
             Polar/Garmin — nur als Trigger-Signal, nicht als exakt
             vergleichbare Trainingslast zu verstehen. Oura hat unter allen
             Quellen die niedrigste Prioritätsstufe (s.
             TRAINING_LOAD_SOURCE_PRIORITY, modules/base.py) — bei
             Überlappung mit Polar oder Garmin verliert Oura seinen
             training_load unabhängig von der Importreihenfolge, auch wenn
             die andere Quelle erst später importiert wird.

@relevance.de  Ermöglicht den Import von Schlaf- und Erholungsdaten aus Oura-Ringen, essentiell für die Schlafanalyse
@relevance.en  Enables import of sleep and recovery data from Oura rings, essential for sleep analysis
@limits.en   Supplements API data, does not replace it. Some tables are only
             created if data is present. No medical interpretation.
             training_load for mirrored Oura workouts is a rough calorie-based
             approximation (see OURA_TRAINING_LOAD_CAL_FACTOR), not
             heart-rate-based like Polar's/Garmin's — usable as a trigger
             signal only, not as an exactly comparable training load. Oura has
             the lowest priority tier of all sources (see
             TRAINING_LOAD_SOURCE_PRIORITY, modules/base.py) — on overlap with
             Polar or Garmin, Oura loses its training_load regardless of
             import order, even if the other source is imported later.
@usage
    python import_oura_csv.py                        # neueste data.zip in imports/oura/
    python import_oura_csv.py --file /pfad/data.zip  # expliziter Path
    python import_oura_csv.py --rebuild              # Tables leeren + neu aufbauen
"""

import argparse
import csv
import io
import json
import math
import re
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
from modules.base import claim_training_load_slot, log_import, resolve_person
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from utils.anonymize import round_coords

_cfg = _Cfg()
DB_PATH   = _cfg.db_path
ZIP_DIR   = _cfg.data_root / "oura"
ZIP_DIR.mkdir(parents=True, exist_ok=True)
APP_DATA  = "App Data"


# ── Schema ────────────────────────────────────────────────────────────────────

def setup_db(conn: sqlite3.Connection):
    _TABLES = [
        "oura_cycle_insights", "oura_period_starts", "oura_cycle_predictions",
        "oura_tags", "oura_temperature_raw", "oura_daytime_stress",
        "oura_sleep_model", "oura_vo2max", "oura_workouts", "oura_contraception",
        "oura_survey", "oura_blood_glucose", "oura_blood_pressure",
        "oura_medications", "oura_lab_results", "location_stays",
    ]
    for tbl in _TABLES:
        row = conn.execute(
            "SELECT type FROM sqlite_master WHERE name=?", (tbl,)
        ).fetchone()
        if row and row[0] == "view":
            conn.execute(f"DROP VIEW {tbl}")
    conn.commit()
    conn.executescript("""

    -- Zyklus
    DROP TABLE IF EXISTS oura_cycle_insights;
    CREATE TABLE IF NOT EXISTS oura_cycle_insights (
        day                     TEXT PRIMARY KEY,
        day_of_cycle            INTEGER,
        cycle_phase             TEXT,
        cycle_event             TEXT,
        fertile_window          TEXT,
        risk                    TEXT,
        reason_for_no_phase     TEXT,
        source                  TEXT DEFAULT 'oura_csv'
    );

    CREATE TABLE IF NOT EXISTS oura_period_starts (
        day                     TEXT PRIMARY KEY,
        is_start                INTEGER,
        menstrual_flow          TEXT,
        timestamp               TEXT,
        median_cycle_length     INTEGER,
        number_of_cycles        INTEGER,
        source                  TEXT DEFAULT 'oura_csv'
    );

    CREATE TABLE IF NOT EXISTS oura_cycle_predictions (
        cycle_period_start      TEXT PRIMARY KEY,
        day_updated             TEXT,
        forecasting_method      TEXT,
        ovulation               INTEGER,
        predicted_ovulations    TEXT,
        predicted_period_starts TEXT,
        source                  TEXT DEFAULT 'oura_csv'
    );

    -- Tags / Symptome
    CREATE TABLE IF NOT EXISTS oura_tags (
        id                      TEXT PRIMARY KEY,
        start_day               TEXT,
        start_time              TEXT,
        end_day                 TEXT,
        end_time                TEXT,
        tag_type_code           TEXT,
        custom_tag_name         TEXT,
        comment                 TEXT,
        source                  TEXT DEFAULT 'oura_csv'
    );
    CREATE INDEX IF NOT EXISTS idx_oura_tags_day ON oura_tags(start_day);

    -- Rohdaten
    CREATE TABLE IF NOT EXISTS oura_temperature_raw (
        timestamp               TEXT PRIMARY KEY,
        skin_temp               REAL,
        source                  TEXT DEFAULT 'oura_csv'
    );
    CREATE INDEX IF NOT EXISTS idx_oura_temp_ts ON oura_temperature_raw(timestamp);

    CREATE TABLE IF NOT EXISTS oura_daytime_stress (
        timestamp               TEXT,
        person                  TEXT NOT NULL,
        stress_value            REAL,
        recovery_value          REAL,
        source                  TEXT DEFAULT 'oura_csv',
        PRIMARY KEY (timestamp, person)
    );
    CREATE INDEX IF NOT EXISTS idx_oura_dtstress_ts ON oura_daytime_stress(timestamp);

    CREATE TABLE IF NOT EXISTS oura_sleep_model (
        id                      TEXT PRIMARY KEY,
        day                     TEXT,
        bedtime_start           TEXT,
        bedtime_end             TEXT,
        sleep_type              TEXT,
        period                  INTEGER,
        average_heart_rate      REAL,
        average_hrv             REAL,
        average_breath          REAL,
        total_sleep_duration    INTEGER,
        time_in_bed             INTEGER,
        deep_sleep_duration     INTEGER,
        light_sleep_duration    INTEGER,
        rem_sleep_duration      INTEGER,
        awake_time              INTEGER,
        efficiency              INTEGER,
        latency                 INTEGER,
        restless_periods        INTEGER,
        lowest_heart_rate       INTEGER,
        readiness_json          TEXT,
        readiness_score_delta   REAL,
        sleep_score_delta       REAL,
        sleep_phase_5_min       TEXT,
        sleep_phase_30_sec      TEXT,
        heart_rate_json         TEXT,
        hrv_json                TEXT,
        movement_30_sec         TEXT,
        source                  TEXT DEFAULT 'oura_csv'
    );

    -- Metriken
    CREATE TABLE IF NOT EXISTS oura_vo2max (
        day                     TEXT PRIMARY KEY,
        timestamp               TEXT,
        vo2_max                 INTEGER,
        source                  TEXT DEFAULT 'oura_csv'
    );

    CREATE TABLE IF NOT EXISTS oura_workouts (
        id                      TEXT PRIMARY KEY,
        day                     TEXT,
        activity                TEXT,
        start_datetime          TEXT,
        end_datetime            TEXT,
        calories                REAL,
        distance                REAL,
        intensity               TEXT,
        source_app              TEXT,
        source                  TEXT DEFAULT 'oura_csv'
    );

    CREATE TABLE IF NOT EXISTS oura_contraception (
        id                      TEXT PRIMARY KEY,
        method                  TEXT,
        method_start_date       TEXT,
        method_end_date         TEXT,
        timestamp               TEXT,
        source                  TEXT DEFAULT 'oura_csv'
    );

    CREATE TABLE IF NOT EXISTS oura_survey (
        id                      TEXT PRIMARY KEY,
        survey_id               TEXT,
        timestamp               TEXT,
        answers_json            TEXT,
        version                 INTEGER,
        source                  TEXT DEFAULT 'oura_csv'
    );

    -- Zukunft: werden befüllt sobald Features in EU freigeschaltet
    CREATE TABLE IF NOT EXISTS oura_blood_glucose (
        timestamp               TEXT PRIMARY KEY,
        value                   REAL,
        source                  TEXT DEFAULT 'oura_csv'
    );

    CREATE TABLE IF NOT EXISTS oura_blood_pressure (
        timestamp               TEXT PRIMARY KEY,
        systolic                INTEGER,
        diastolic               INTEGER,
        source                  TEXT DEFAULT 'oura_csv'
    );

    CREATE TABLE IF NOT EXISTS oura_medications (
        id                      TEXT PRIMARY KEY,
        medication_id           TEXT,
        timestamp               TEXT,
        dose_value              REAL,
        dose_unit               TEXT,
        is_skipped              INTEGER,
        route                   TEXT,
        source                  TEXT DEFAULT 'oura_csv'
    );

    CREATE TABLE IF NOT EXISTS oura_lab_results (
        id                      TEXT PRIMARY KEY,
        test_type               TEXT,
        timestamp               TEXT,
        status                  TEXT,
        abnormal_result         INTEGER,
        observations_json       TEXT,
        source                  TEXT DEFAULT 'oura_csv'
    );

    -- Tägl. Zusammenfassungen (füllen historische Gaps ggü. API)
    -- Schreiben in measurements; Tabellen hier nur als Marker / für Rebuild-Listen.

    -- Guided Sessions (Atemübungen, Meditation)
    CREATE TABLE IF NOT EXISTS oura_guided_sessions (
        id              TEXT PRIMARY KEY,
        day             TEXT,
        type            TEXT,
        start_datetime  TEXT,
        end_datetime    TEXT,
        mood            TEXT,
        motion_count    INTEGER,
        heart_rate_json TEXT,
        hrv_json        TEXT,
        source          TEXT DEFAULT 'oura_csv'
    );
    CREATE INDEX IF NOT EXISTS idx_oura_gs_day ON oura_guided_sessions(day);

    -- Rest Mode
    CREATE TABLE IF NOT EXISTS oura_rest_mode (
        id          TEXT PRIMARY KEY,
        start_day   TEXT,
        start_time  TEXT,
        end_day     TEXT,
        end_time    TEXT,
        episodes    TEXT,
        source      TEXT DEFAULT 'oura_csv'
    );
    CREATE INDEX IF NOT EXISTS idx_oura_rm_day ON oura_rest_mode(start_day);

    -- Empfohlenes Schlaffenster
    CREATE TABLE IF NOT EXISTS oura_sleep_time (
        id              TEXT PRIMARY KEY,
        day             TEXT,
        recommendation  TEXT,
        status          TEXT,
        optimal_bedtime TEXT,
        source          TEXT DEFAULT 'oura_csv'
    );

    -- BP-Risikosignale
    CREATE TABLE IF NOT EXISTS oura_bp_signals (
        id                      TEXT PRIMARY KEY,
        day                     TEXT,
        day_window_start        TEXT,
        is_risk_above_threshold INTEGER,
        source                  TEXT DEFAULT 'oura_csv'
    );

    -- Ernährung
    CREATE TABLE IF NOT EXISTS oura_food_items (
        id      TEXT PRIMARY KEY,
        name    TEXT,
        weight  REAL,
        source  TEXT DEFAULT 'oura_csv'
    );

    CREATE TABLE IF NOT EXISTS oura_meals (
        id                  TEXT PRIMARY KEY,
        day                 TEXT,
        name                TEXT,
        type                TEXT,
        start_time          TEXT,
        weight              REAL,
        food_item_ids       TEXT,
        nutrition_json      TEXT,
        meal_scoring_json   TEXT,
        favorite            INTEGER,
        source              TEXT DEFAULT 'oura_csv'
    );
    CREATE INDEX IF NOT EXISTS idx_oura_meals_day ON oura_meals(day);

    -- GLP-1 Einstellungen
    CREATE TABLE IF NOT EXISTS oura_glp1_settings (
        id                  TEXT PRIMARY KEY,
        enabled             INTEGER,
        start_timestamp     TEXT,
        next_dose_timestamp TEXT,
        source              TEXT DEFAULT 'oura_csv'
    );

    -- Lab-Ergebnis-Insights (KI-Kommentare zu labtestresult)
    CREATE TABLE IF NOT EXISTS oura_lab_insights (
        id                  TEXT PRIMARY KEY,
        lab_test_result_id  TEXT,
        generated_at        TEXT,
        language            TEXT,
        overview_title      TEXT,
        overview_summary    TEXT,
        actions             TEXT,
        questions           TEXT,
        source              TEXT DEFAULT 'oura_csv'
    );

    -- Standort-Aufenthalte (aus rawlocation, Stay-Detection)
    CREATE TABLE IF NOT EXISTS location_stays (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        start_ts    TEXT NOT NULL,
        end_ts      TEXT NOT NULL,
        lat         REAL NOT NULL,
        lon         REAL NOT NULL,
        is_home     INTEGER DEFAULT 0,
        source      TEXT DEFAULT 'oura_gps'
    );
    CREATE INDEX IF NOT EXISTS idx_loc_stays_start ON location_stays(start_ts);
    CREATE INDEX IF NOT EXISTS idx_loc_stays_end   ON location_stays(end_ts);

    PRAGMA journal_mode=WAL;
    """)
    conn.commit()

    # Migrate existing oura_sleep_model tables that predate the extended schema
    _new_sleep_cols = [
        ("sleep_type",            "TEXT"),
        ("period",                "INTEGER"),
        ("time_in_bed",           "INTEGER"),
        ("readiness_json",        "TEXT"),
        ("readiness_score_delta", "REAL"),
        ("sleep_score_delta",     "REAL"),
    ]
    for col, typ in _new_sleep_cols:
        try:
            conn.execute(f"ALTER TABLE oura_sleep_model ADD COLUMN {col} {typ}")
        except Exception:
            pass
    conn.commit()


HOME_RADIUS_M = 3000   # 3 km Homeradius
STAY_RADIUS_M = 200    # innerhalb 200m = gleicher Staysort
MIN_STAY_S    = 1200   # mind. 20 minutes for einen Stay


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(dλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _parse_ts(s: str) -> datetime:
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s).astimezone(timezone.utc)


def detect_stays(points: list[tuple]) -> list[tuple]:
    """
    Zheng-Algorithmus: GPS-Punkte → Aufenthalts-Segmente.
    points: [(ts_str, lat, lon), ...] sortiert nach Zeit
    Returns: [(start_ts, end_ts, lat, lon), ...]
    """
    stays = []
    n = len(points)
    i = 0
    while i < n:
        j = i + 1
        while j < n:
            dist = haversine_m(points[i][1], points[i][2],
                               points[j][1], points[j][2])
            if dist > STAY_RADIUS_M:
                break
            j += 1
        # j = erster Point außerhalb des Radius
        duration = (_parse_ts(points[j-1][0]) - _parse_ts(points[i][0])).total_seconds()
        if duration >= MIN_STAY_S:
            seg = points[i:j]
            lat = sum(p[1] for p in seg) / len(seg)
            lon = sum(p[2] for p in seg) / len(seg)
            stays.append((points[i][0], points[j-1][0], lat, lon))
            i = j
        else:
            i += 1
    return stays


def rebuild(conn: sqlite3.Connection):
    tables = [
        "oura_cycle_insights", "oura_period_starts", "oura_cycle_predictions",
        "oura_tags", "oura_temperature_raw", "oura_daytime_stress",
        "oura_sleep_model", "oura_vo2max", "oura_workouts", "oura_contraception",
        "oura_survey", "oura_blood_glucose", "oura_blood_pressure",
        "oura_medications", "oura_lab_results",
        "oura_guided_sessions", "oura_rest_mode", "oura_sleep_time",
        "oura_bp_signals", "oura_food_items", "oura_meals",
        "oura_glp1_settings", "oura_lab_insights",
    ]
    for tbl in tables:
        conn.execute(f"DELETE FROM {tbl}")
    conn.commit()
    print(t("Tabellen geleert.", "Tables cleared."))


# ── CSV-Helfer ─────────────────────────────────────────────────────────────────

def read_csv(zf: zipfile.ZipFile, name: str) -> list[dict]:
    path = f"{APP_DATA}/{name}.csv"
    if path not in zf.namelist():
        return []
    data = zf.read(path).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(data), delimiter=";"))


def _int(v):
    try:
        return int(v) if v else None
    except (ValueError, TypeError):
        return None

def _float(v):
    try:
        return float(v) if v else None
    except (ValueError, TypeError):
        return None

def _bool(v):
    return 1 if str(v).lower() in ("true", "1", "yes") else 0


# ── Import-Funktionen ─────────────────────────────────────────────────────────

def import_cycle_insights(conn, rows):
    n = 0
    for r in rows:
        conn.execute("""
            INSERT OR IGNORE INTO oura_cycle_insights
            (day, day_of_cycle, cycle_phase, cycle_event, fertile_window,
             risk, reason_for_no_phase)
            VALUES (?,?,?,?,?,?,?)
        """, (
            r["day"], _int(r.get("day_of_cycle")),
            r.get("cycle_phase") or None, r.get("cycle_event") or None,
            r.get("fertile_window") or None, r.get("risk") or None,
            r.get("reason_for_no_cycle_phase") or None,
        ))
        n += 1
    conn.commit()
    return n


def import_period_starts(conn, rows):
    n = 0
    for r in rows:
        stats = {}
        try:
            stats = json.loads(r.get("cycle_statistics") or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        conn.execute("""
            INSERT OR IGNORE INTO oura_period_starts
            (day, is_start, menstrual_flow, timestamp,
             median_cycle_length, number_of_cycles)
            VALUES (?,?,?,?,?,?)
        """, (
            r["day"], _bool(r.get("is_start")),
            r.get("menstrual_flow") or None, r.get("timestamp") or None,
            _int(stats.get("median_cycle_length")),
            _int(stats.get("number_of_cycles")),
        ))
        n += 1
    conn.commit()
    return n


def import_cycle_predictions(conn, rows):
    n = 0
    for r in rows:
        conn.execute("""
            INSERT OR IGNORE INTO oura_cycle_predictions
            (cycle_period_start, day_updated, forecasting_method,
             ovulation, predicted_ovulations, predicted_period_starts)
            VALUES (?,?,?,?,?,?)
        """, (
            r["cycle_period_start"], r.get("day_updated"),
            r.get("forecasting_method"), _int(r.get("ovulation")),
            r.get("predicted_ovulations"), r.get("predicted_period_starts"),
        ))
        n += 1
    conn.commit()
    return n


def import_tags(conn, rows, person: str | None = None):
    person = resolve_person(person)
    n = 0
    for r in rows:
        conn.execute("""
            INSERT OR IGNORE INTO oura_tags
            (id, start_day, start_time, end_day, end_time,
             tag_type_code, custom_tag_name, comment)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            r["id"], r.get("start_day"), r.get("start_time") or None,
            r.get("end_day") or None, r.get("end_time") or None,
            r.get("tag_type_code") or None, r.get("custom_tag_name") or None,
            r.get("comment") or None,
        ))
        tag      = r.get("custom_tag_name") or r.get("tag_type_code") or None
        sd, st   = r.get("start_day"), r.get("start_time") or None
        ed, et   = r.get("end_day") or None, r.get("end_time") or None
        ts_start = f"{sd}T{st}" if sd and st else None
        ts_end   = f"{ed}T{et}" if ed and et else None
        conn.execute("""
            INSERT OR IGNORE INTO user_context
            (id, date, ts_start, ts_end, person, source, source_app, tag, note)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            r["id"], sd, ts_start, ts_end,
            person, "oura_csv", "oura_app", tag, r.get("comment") or None,
        ))
        n += 1
    conn.commit()
    return n


def import_temperature_raw(conn, rows):
    n = 0
    batch = []
    for r in rows:
        batch.append((r["timestamp"], _float(r.get("skin_temp"))))
        if len(batch) >= 5000:
            conn.executemany(
                "INSERT OR IGNORE INTO oura_temperature_raw (timestamp, skin_temp) VALUES (?,?)",
                batch)
            conn.commit()
            n += len(batch)
            batch = []
    if batch:
        conn.executemany(
            "INSERT OR IGNORE INTO oura_temperature_raw (timestamp, skin_temp) VALUES (?,?)",
            batch)
        conn.commit()
        n += len(batch)
    return n


def import_daytime_stress(conn, rows, person: str | None = None):
    person = resolve_person(person)
    batch = []
    for r in rows:
        batch.append((r["timestamp"], person, _float(r.get("stress_value")),
                      _float(r.get("recovery_value"))))
    conn.executemany(
        "INSERT OR IGNORE INTO oura_daytime_stress (timestamp, person, stress_value, recovery_value) VALUES (?,?,?,?)",
        batch)
    conn.commit()
    return len(batch)


def import_sleep_model(conn, rows, person: str | None = None):
    person = resolve_person(person)
    n = 0
    meas_out = []
    for r in rows:
        sleep_type = r.get("type") or None
        conn.execute("""
            INSERT OR IGNORE INTO oura_sleep_model
            (id, day, bedtime_start, bedtime_end,
             sleep_type, period,
             average_heart_rate, average_hrv, average_breath,
             total_sleep_duration, time_in_bed,
             deep_sleep_duration, light_sleep_duration,
             rem_sleep_duration, awake_time, efficiency, latency,
             restless_periods, lowest_heart_rate,
             readiness_json, readiness_score_delta, sleep_score_delta,
             sleep_phase_5_min, sleep_phase_30_sec,
             heart_rate_json, hrv_json, movement_30_sec)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            r["id"], r.get("day"), r.get("bedtime_start"), r.get("bedtime_end"),
            sleep_type, _int(r.get("period")),
            _float(r.get("average_heart_rate")), _float(r.get("average_hrv")),
            _float(r.get("average_breath")),
            _int(r.get("total_sleep_duration")), _int(r.get("time_in_bed")),
            _int(r.get("deep_sleep_duration")), _int(r.get("light_sleep_duration")),
            _int(r.get("rem_sleep_duration")), _int(r.get("awake_time")),
            _int(r.get("efficiency")), _int(r.get("latency")),
            _int(r.get("restless_periods")), _int(r.get("lowest_heart_rate")),
            r.get("readiness") or None,
            _float(r.get("readiness_score_delta")), _float(r.get("sleep_score_delta")),
            r.get("sleep_phase_5_min") or None, r.get("sleep_phase_30_sec") or None,
            r.get("heart_rate") or None, r.get("hrv") or None,
            r.get("movement_30_sec") or None,
        ))

        # Write latency + restless_periods into measurements for main sleep only
        # (these are not written by the API importer and useful for sleep analysis)
        day = r.get("day")
        if day and sleep_type in ("main", None):
            ts_ref = r.get("bedtime_start") or f"{day}T00:00:00+00:00"
            for metric, val, unit in [
                ("sleep_latency_s",        _float(r.get("latency")),          "s"),
                ("sleep_restless_periods", _float(r.get("restless_periods")), None),
                ("sleep_time_in_bed_s",    _float(r.get("time_in_bed")),      "s"),
            ]:
                if val is not None:
                    meas_out.append((ts_ref, day, metric, val, None, unit,
                                     _OURA_DEV, person, _OURA_APP))

        # Expand 5-minute HR and HRV interval series into individual measurements.
        # hrv_rmssd matches the metric name used by import_oura.py (API) → INSERT OR IGNORE deduplicates.
        for json_col, metric, unit in [
            (r.get("heart_rate"), "oura_sleep_hr", "bpm"),
            (r.get("hrv"),        "hrv_rmssd",     "ms"),
        ]:
            if not json_col:
                continue
            try:
                blob = json.loads(json_col)
                items    = blob.get("items", [])
                interval = int(blob.get("interval", 300))
                t0_str   = blob.get("timestamp")
                if not t0_str or not items:
                    continue
                t0  = _parse_ts(t0_str)
                row_day = day or t0.strftime("%Y-%m-%d")
                for i, val in enumerate(items):
                    if val is None:
                        continue
                    ts_dt  = t0 + timedelta(seconds=i * interval)
                    ts_iso = ts_dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                    meas_out.append((ts_iso, row_day, metric, float(val), None, unit,
                                     _OURA_DEV, person, _OURA_APP))
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
        n += 1

    conn.commit()
    _meas_batch(conn, meas_out)
    return n


def import_vo2max(conn, rows):
    n = 0
    for r in rows:
        conn.execute(
            "INSERT OR IGNORE INTO oura_vo2max (day, timestamp, vo2_max) VALUES (?,?,?)",
            (r["day"], r.get("timestamp"), _int(r.get("vo2_max"))))
        n += 1
    conn.commit()
    return n


def import_workouts(conn, rows):
    n = 0
    for r in rows:
        conn.execute("""
            INSERT OR IGNORE INTO oura_workouts
            (id, day, activity, start_datetime, end_datetime,
             calories, distance, intensity, source_app)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            r["id"], r.get("day"), r.get("activity"),
            r.get("start_datetime"), r.get("end_datetime"),
            _float(r.get("calories")), _float(r.get("distance")),
            r.get("intensity") or None, r.get("source") or None,
        ))
        n += 1
    conn.commit()
    return n


# ── oura_workouts → sessions + session_metrics ────────────────────────────────
# Oura hat kein Aequivalent zu Polars 'jemand hat bewusst auf Start gedrueckt'
# (das source_app-Feld — eigentlich Ouras 'source', s. import_workouts oben —
# steht bei ALLEN bisher gesehenen Eintraegen auf 'confirmed', nie 'manual').
# Statt eines Start-Trigger-Flags filtern wir daher nach Aktivitaetstyp:
# 'houseWork' und 'other' sind eindeutig Alltag, keine bewusste Sporteinheit.
OURA_NON_SPORT_ACTIVITIES = {"housework", "other"}

# Grobe Kalibrierung gegen echte Polar-Werte (training_load/calories median
# ~0.111 ueber Krafttraining-Sessions dieser Person) — kein Ersatz fuer eine
# HF-basierte Trainingslast, aber auf derselben Groessenordnung nutzbar als
# Trigger-Signal. intensity-Multiplikator daempft/verstaerkt moderat, da Oura
# nur 'light'/'moderate'/'hard' statt HF-Zonen liefert.
OURA_TRAINING_LOAD_CAL_FACTOR = 0.11
OURA_INTENSITY_MULTIPLIER = {"light": 0.7, "moderate": 1.0, "hard": 1.3}


def _oura_device_for_date(date_str: "str | None") -> "str | None":
    """Oura-Ring-device_id aus device_registry, aktiv an date_str (oder None)."""
    if not date_str:
        return None
    for dev in _cfg.device_registry:
        if str(dev.get("brand", "")).lower() != "oura":
            continue
        date_from = dev.get("date_from")
        date_to = dev.get("date_to")
        if date_from and date_str[:10] >= date_from and (not date_to or date_str[:10] <= date_to):
            return dev.get("device_id")
    return None


def _oura_training_load(calories: "float | None", intensity: "str | None") -> "float | None":
    if not calories:
        return None
    mult = OURA_INTENSITY_MULTIPLIER.get((intensity or "").lower(), 1.0)
    return round(calories * OURA_TRAINING_LOAD_CAL_FACTOR * mult, 1)


def mirror_workouts_to_sessions(conn, person: "str | None" = None) -> int:
    """Spiegelt echte-Sport-Workouts aus oura_workouts in sessions/session_metrics,
    damit sie (wie Polar-Trainings) in tl_d/training_load-basierte Trigger
    einfliessen koennen (s. compute_pem.py). oura_workouts selbst bleibt
    unveraendert die vollstaendige Rohablage aller Eintraege inkl. Alltag.

    Ueberlappungsschutz: liegt fuer denselben Zeitraum bereits eine andere
    Session vor, die entweder training_load>0 traegt ODER selbst als
    auto_detected=1 markiert ist (typischerweise Polar, wenn Ring und
    Brustgurt/Uhr dasselbe Ereignis erfassten — auch wenn Polar es SELBST als
    automatisch erkannt verworfen hat), bekommt die Oura-Session zwar einen
    Eintrag (Audit-Trail), aber KEINEN eigenen training_load. Ohne die zweite
    Bedingung wuerde eine von Polar als Alltagsaktivitaet verworfene Session
    ueber den Oura-Ring doch noch als Sportwert durchrutschen, obwohl Polars
    eigene Erkennung bereits "kein bewusstes Training" befunden hat.
    """
    person = resolve_person(person)
    cur = conn.cursor()
    n = 0
    # Ergebnis vollstaendig materialisieren, BEVOR verschachtelte cur.execute()-
    # Aufrufe im Schleifenkoerper folgen: dieselbe Cursor-Instanz fuer die
    # aeussere SELECT-Iteration und innere INSERT/SELECT-Aufrufe zu benutzen
    # ueberschreibt den Iterationszustand des aeusseren Cursors nach der
    # ersten verschachtelten Query und bricht die Schleife nach der ersten
    # Zeile faktisch ab.
    workouts = cur.execute("""
        SELECT id, day, activity, start_datetime, end_datetime, calories, distance, intensity
        FROM oura_workouts
    """).fetchall()
    for oid, day, activity, start, end, calories, distance, intensity in workouts:
        if (activity or "").lower() in OURA_NON_SPORT_ACTIVITIES:
            continue
        sid = f"oura_workout_{oid}"
        device_id = _oura_device_for_date(day)
        cur.execute("""
            INSERT OR IGNORE INTO sessions
            (id, type, ts_start, ts_end, date, device_id, person, source_app, sport)
            VALUES (?, 'training', ?, ?, ?, ?, ?, 'oura', ?)
        """, (sid, start, end, day, device_id, person, activity))
        if cur.rowcount == 0:
            continue  # bereits gespiegelt
        n += 1

        metrics = [("calories", calories, None, "kcal"), ("distance_m", distance, None, "m")]
        if claim_training_load_slot(conn, person, sid, "oura", day, start, end):
            load = _oura_training_load(calories, intensity)
            if load:
                metrics.append(("training_load", load, None, None))
        for metric, value, value_text, unit in metrics:
            if value is None and value_text is None:
                continue
            cur.execute(
                "INSERT OR IGNORE INTO session_metrics(session_id, metric, value, value_text, unit) "
                "VALUES (?,?,?,?,?)", (sid, metric, value, value_text, unit)
            )
    conn.commit()
    return n


def import_contraception(conn, rows):
    n = 0
    for r in rows:
        method = (r.get("non_hormonal_contraceptive_method")
                  or r.get("hormonal_contraceptive_method") or None)
        conn.execute("""
            INSERT OR IGNORE INTO oura_contraception
            (id, method, method_start_date, method_end_date, timestamp)
            VALUES (?,?,?,?,?)
        """, (
            r["id"], method,
            r.get("method_start_date") or None, r.get("method_end_date") or None,
            r.get("timestamp") or None,
        ))
        n += 1
    conn.commit()
    return n


def import_survey(conn, rows):
    n = 0
    for r in rows:
        conn.execute("""
            INSERT OR IGNORE INTO oura_survey
            (id, survey_id, timestamp, answers_json, version)
            VALUES (?,?,?,?,?)
        """, (
            r["id"], r.get("survey_id"), r.get("timestamp"),
            r.get("answers") or None, _int(r.get("version")),
        ))
        n += 1
    conn.commit()
    return n


def import_blood_glucose(conn, rows):
    n = 0
    for r in rows:
        if r.get("timestamp") and r.get("value"):
            conn.execute(
                "INSERT OR IGNORE INTO oura_blood_glucose (timestamp, value) VALUES (?,?)",
                (r["timestamp"], _float(r["value"])))
            n += 1
    conn.commit()
    return n


def import_blood_pressure(conn, rows):
    n = 0
    for r in rows:
        if r.get("timestamp"):
            conn.execute("""
                INSERT OR IGNORE INTO oura_blood_pressure (timestamp, systolic, diastolic)
                VALUES (?,?,?)
            """, (r["timestamp"], _int(r.get("systolic_blood_pressure")),
                  _int(r.get("diastolic_blood_pressure"))))
            n += 1
    conn.commit()
    return n


def import_medications(conn, rows):
    n = 0
    for r in rows:
        if r.get("id"):
            conn.execute("""
                INSERT OR IGNORE INTO oura_medications
                (id, medication_id, timestamp, dose_value, dose_unit, is_skipped, route)
                VALUES (?,?,?,?,?,?,?)
            """, (
                r["id"], r.get("medication_id"), r.get("timestamp"),
                _float(r.get("administered_dose_value")),
                r.get("administered_dose_unit") or None,
                _bool(r.get("is_skipped")), r.get("route") or None,
            ))
            n += 1
    conn.commit()
    return n


def import_location_stays(conn, rows):
    """
    Subsamplet rawlocation auf 1-Min-Takt, erkennt Aufenthalte per
    Zheng-Algorithmus, speichert in location_stays.
    Bereits importierte Zeiträume werden übersprungen.
    """
    if not rows:
        return 0

    cfg = _Cfg()
    home_lat = cfg.home_lat or 0.0
    home_lon = cfg.home_lon or 0.0

    # Letzten importierten Timestamp holen
    last = conn.execute(
        "SELECT MAX(end_ts) FROM location_stays WHERE source='oura_gps'"
    ).fetchone()[0]

    # Subsample: 1 Point pro Minute (erster Point je Minute)
    seen_min: set[str] = set()
    pts = []
    for r in rows:
        ts = r.get("timestamp", "")
        if not ts or not r.get("latitude") or not r.get("longitude"):
            continue
        if last and ts <= last:
            continue
        minute = ts[:16]   # YYYY-MM-DDTHH:MM
        if minute in seen_min:
            continue
        seen_min.add(minute)
        try:
            pts.append((ts, float(r["latitude"]), float(r["longitude"])))
        except (ValueError, KeyError):
            continue

    if not pts:
        return 0

    stays = detect_stays(pts)

    n = 0
    for start_ts, end_ts, lat, lon in stays:
        is_home = 1 if haversine_m(lat, lon, home_lat, home_lon) <= HOME_RADIUS_M else 0
        rlat, rlon = round_coords(lat, lon)
        conn.execute("""
            INSERT OR IGNORE INTO location_stays
            (start_ts, end_ts, lat, lon, is_home)
            VALUES (?,?,?,?,?)
        """, (start_ts, end_ts, rlat, rlon, is_home))
        n += 1

    conn.commit()
    return n


def import_lab_results(conn, rows):
    n = 0
    for r in rows:
        if r.get("id"):
            conn.execute("""
                INSERT OR IGNORE INTO oura_lab_results
                (id, test_type, timestamp, status, abnormal_result, observations_json)
                VALUES (?,?,?,?,?,?)
            """, (
                r["id"], r.get("test_type"), r.get("timestamp"),
                r.get("status") or None,
                _bool(r.get("abnormal_result")) if r.get("abnormal_result") else None,
                r.get("observations") or None,
            ))
            n += 1
    conn.commit()
    return n


# ── Messungen: Tägliche Zusammenfassungen (historische Gaps füllen) ───────────

_OURA_DEV = _cfg.oura_device_id
_OURA_APP = "oura_app"   # gleiche source_app wie API → INSERT OR IGNORE dedupliziert


def _norm_ts(s: str) -> str:
    return re.sub(r"\.\d+([+-])", r"\1", s.replace("Z", "+00:00"))


def _meas_batch(conn, rows: list) -> None:
    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO measurements"
            "(ts, date, metric, value, value_text, unit, device_id, person, source_app)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()


def _daily_row(day: str, metric: str, value, unit=None, text=None, person=None):
    if value is None and text is None:
        return None
    ts = f"{day}T00:00:00+00:00"
    v  = float(value) if value is not None else None
    return (ts, day, metric, v, text, unit, _OURA_DEV, person, _OURA_APP)


def import_daily_activity_csv(conn, rows, person: str | None = None):
    person = resolve_person(person)
    out = []
    for r in rows:
        day = r.get("day")
        if not day:
            continue
        for metric, field, unit in [
            ("activity_score",   "score",                       None),
            ("steps",            "steps",                       "steps"),
            ("active_calories",  "active_calories",             "kcal"),
            ("total_calories",   "total_calories",              "kcal"),
            ("distance_walking", "equivalent_walking_distance", "m"),
            ("active_time_high", "high_activity_time",          "s"),
            ("active_time_mid",  "medium_activity_time",        "s"),
            ("active_time_low",  "low_activity_time",           "s"),
            ("sedentary_time",   "sedentary_time",              "s"),
            ("resting_time",     "resting_time",                "s"),
            ("met_avg",          "average_met_minutes",         "MET"),
            ("non_wear_time",    "non_wear_time",               "s"),
        ]:
            row = _daily_row(day, metric, _float(r.get(field)), unit, person=person)
            if row:
                out.append(row)
    _meas_batch(conn, out)
    return len(rows)


def import_daily_readiness_csv(conn, rows, person: str | None = None):
    person = resolve_person(person)
    out = []
    for r in rows:
        day = r.get("day")
        if not day:
            continue
        c = {}
        try:
            c = json.loads(r.get("contributors") or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        for metric, val, unit in [
            ("readiness_score",        _float(r.get("score")),                None),
            ("readiness_hrv_balance",  _float(c.get("hrv_balance")),          None),
            ("readiness_hr_resting",   _float(c.get("resting_heart_rate")),   "bpm"),
            ("readiness_recovery_idx", _float(c.get("recovery_index")),       None),
            ("readiness_body_temp",    _float(c.get("body_temperature")),     "°C"),
            ("temp_deviation",         _float(r.get("temperature_deviation")), "°C"),
            ("temp_trend_dev",         _float(r.get("temperature_trend_deviation")), "°C"),
        ]:
            row = _daily_row(day, metric, val, unit, person=person)
            if row:
                out.append(row)
    _meas_batch(conn, out)
    return len(rows)


def import_daily_sleep_csv(conn, rows, person: str | None = None):
    person = resolve_person(person)
    out = []
    for r in rows:
        day = r.get("day")
        if not day:
            continue
        row = _daily_row(day, "sleep_score", _float(r.get("score")), person=person)
        if row:
            out.append(row)
    _meas_batch(conn, out)
    return len(rows)


def import_daily_spo2_csv(conn, rows, person: str | None = None):
    person = resolve_person(person)
    out = []
    for r in rows:
        day = r.get("day")
        if not day:
            continue
        pct = {}
        try:
            pct = json.loads(r.get("spo2_percentage") or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        for metric, val, unit in [
            ("spo2",                         _float(pct.get("average")),                    "%"),
            ("spo2_min",                     _float(pct.get("min")),                        "%"),
            ("spo2_max",                     _float(pct.get("max")),                        "%"),
            ("breathing_disturbance_index",  _float(r.get("breathing_disturbance_index")), None),
        ]:
            row = _daily_row(day, metric, val, unit, person=person)
            if row:
                out.append(row)
    _meas_batch(conn, out)
    return len(rows)


def import_daily_stress_csv(conn, rows, person: str | None = None):
    person = resolve_person(person)
    out = []
    for r in rows:
        day = r.get("day")
        if not day:
            continue
        ts = f"{day}T00:00:00+00:00"
        for metric, val, unit in [
            ("stress_high_min",   _float(r.get("stress_high")),   "min"),
            ("recovery_high_min", _float(r.get("recovery_high")), "min"),
        ]:
            row = _daily_row(day, metric, val, unit, person=person)
            if row:
                out.append(row)
        summary = r.get("day_summary") or None
        if summary:
            out.append((ts, day, "stress_day_summary", None, summary, None,
                        _OURA_DEV, person, _OURA_APP))
    _meas_batch(conn, out)
    return len(rows)


def import_cardiovascular_age_csv(conn, rows, person: str | None = None):
    person = resolve_person(person)
    out = []
    for r in rows:
        day = r.get("day")
        if not day:
            continue
        for metric, field, unit in [
            ("pulse_wave_velocity", "pulse_wave_velocity", "m/s"),
            ("vascular_age",        "vascular_age",        "years"),
        ]:
            row = _daily_row(day, metric, _float(r.get(field)), unit, person=person)
            if row:
                out.append(row)
    _meas_batch(conn, out)
    return len(rows)


def import_heartrate_csv(conn, rows, person: str | None = None):
    person = resolve_person(person)
    out = []
    for r in rows:
        ts_raw = r.get("timestamp", "")
        bpm    = _float(r.get("bpm"))
        if not ts_raw or bpm is None:
            continue
        ts  = _norm_ts(ts_raw)
        day = ts[:10]
        out.append((ts, day, "heart_rate", bpm, None, "bpm",
                    _OURA_DEV, person, _OURA_APP))
        if len(out) >= 5000:
            _meas_batch(conn, out)
            out = []
    _meas_batch(conn, out)
    return len(rows)


def import_daily_resilience(conn, rows, person: str | None = None):
    person = resolve_person(person)
    out = []
    for r in rows:
        day = r.get("day")
        if not day:
            continue
        c = {}
        try:
            c = json.loads(r.get("contributors") or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        level = r.get("level") or None
        ts = f"{day}T00:00:00+00:00"
        if level:
            out.append((ts, day, "resilience_level", None, level, None,
                        _OURA_DEV, person, _OURA_APP))
        for metric, field, unit in [
            ("resilience_daytime_recovery", "daytime_recovery", None),
            ("resilience_sleep_recovery",   "sleep_recovery",   None),
            ("resilience_stress",           "stress",           None),
        ]:
            row = _daily_row(day, metric, _float(c.get(field)), unit, person=person)
            if row:
                out.append(row)
    _meas_batch(conn, out)
    return len(rows)


def import_daily_metabolic_score(conn, rows, person: str | None = None):
    person = resolve_person(person)
    out = []
    for r in rows:
        day = r.get("day")
        if not day:
            continue
        row = _daily_row(day, "metabolic_score", _float(r.get("metabolic_score")), person=person)
        if row:
            out.append(row)
    _meas_batch(conn, out)
    return len(rows)


def import_daily_smoothed_cva(conn, rows, person: str | None = None):
    person = resolve_person(person)
    out = []
    for r in rows:
        day = r.get("day")
        if not day:
            continue
        for metric, field, unit in [
            ("smoothed_pwv",          "pulse_wave_velocity", "m/s"),
            ("smoothed_vascular_age", "cardiovascular_age",  "years"),
        ]:
            row = _daily_row(day, metric, _float(r.get(field)), unit, person=person)
            if row:
                out.append(row)
    _meas_batch(conn, out)
    return len(rows)


def import_bp_signals(conn, rows):
    n = 0
    for r in rows:
        if not r.get("id"):
            continue
        risk = r.get("is_risk_above_threshold")
        conn.execute("""
            INSERT OR IGNORE INTO oura_bp_signals
            (id, day, day_window_start, is_risk_above_threshold)
            VALUES (?,?,?,?)
        """, (r["id"], r.get("day"), r.get("day_window_start") or None,
              _bool(risk) if risk else None))
        n += 1
    conn.commit()
    return n


def import_guided_sessions(conn, rows):
    n = 0
    for r in rows:
        if not r.get("id"):
            continue
        conn.execute("""
            INSERT OR IGNORE INTO oura_guided_sessions
            (id, day, type, start_datetime, end_datetime,
             mood, motion_count, heart_rate_json, hrv_json)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            r["id"], r.get("day"), r.get("type") or None,
            r.get("start_datetime") or None, r.get("end_datetime") or None,
            r.get("mood") or None, _int(r.get("motion_count")),
            r.get("heart_rate") or None, r.get("heart_rate_variability") or None,
        ))
        n += 1
    conn.commit()
    return n


def import_rest_mode(conn, rows):
    n = 0
    for r in rows:
        if not r.get("id"):
            continue
        conn.execute("""
            INSERT OR IGNORE INTO oura_rest_mode
            (id, start_day, start_time, end_day, end_time, episodes)
            VALUES (?,?,?,?,?,?)
        """, (
            r["id"], r.get("start_day"), r.get("start_time") or None,
            r.get("end_day") or None, r.get("end_time") or None,
            r.get("episodes") or None,
        ))
        n += 1
    conn.commit()
    return n


def import_sleep_time(conn, rows):
    n = 0
    for r in rows:
        if not r.get("id"):
            continue
        conn.execute("""
            INSERT OR IGNORE INTO oura_sleep_time
            (id, day, recommendation, status, optimal_bedtime)
            VALUES (?,?,?,?,?)
        """, (
            r["id"], r.get("day"),
            r.get("recommendation") or None, r.get("status") or None,
            r.get("optimal_bedtime") or None,
        ))
        n += 1
    conn.commit()
    return n


def import_food_items(conn, rows):
    n = 0
    for r in rows:
        if not r.get("id"):
            continue
        conn.execute(
            "INSERT OR IGNORE INTO oura_food_items (id, name, weight) VALUES (?,?,?)",
            (r["id"], r.get("name") or None, _float(r.get("weight"))))
        n += 1
    conn.commit()
    return n


def import_meals(conn, rows):
    n = 0
    for r in rows:
        if not r.get("id"):
            continue
        conn.execute("""
            INSERT OR IGNORE INTO oura_meals
            (id, day, name, type, start_time, weight,
             food_item_ids, nutrition_json, meal_scoring_json, favorite)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            r["id"], r.get("day"), r.get("name") or None,
            r.get("type") or None, r.get("start_time") or None,
            _float(r.get("weight")), r.get("food_item_ids") or None,
            r.get("nutrition_details") or None, r.get("meal_scoring_result") or None,
            _bool(r.get("favorite")) if r.get("favorite") else None,
        ))
        n += 1
    conn.commit()
    return n


def import_glp1_settings(conn, rows):
    n = 0
    for r in rows:
        if not r.get("id"):
            continue
        conn.execute("""
            INSERT OR IGNORE INTO oura_glp1_settings
            (id, enabled, start_timestamp, next_dose_timestamp)
            VALUES (?,?,?,?)
        """, (
            r["id"], _bool(r.get("enabled")),
            r.get("start_timestamp") or None,
            r.get("next_dose_timestamp") or None,
        ))
        n += 1
    conn.commit()
    return n


def import_lab_insights(conn, rows):
    n = 0
    for r in rows:
        if not r.get("id"):
            continue
        conn.execute("""
            INSERT OR IGNORE INTO oura_lab_insights
            (id, lab_test_result_id, generated_at, language,
             overview_title, overview_summary, actions, questions)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            r["id"], r.get("lab_test_result_id"), r.get("generated_at"),
            r.get("language") or None, r.get("overview_title") or None,
            r.get("overview_summary") or None, r.get("actions") or None,
            r.get("questions") or None,
        ))
        n += 1
    conn.commit()
    return n


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

IMPORTERS = [
    ("dailycyclemappingdsr",        import_cycle_insights,    "oura_cycle_insights"),
    ("periodstartdsr",              import_period_starts,     "oura_period_starts"),
    ("reproductivecyclepredictiondsr", import_cycle_predictions, "oura_cycle_predictions"),
    ("enhancedtag",                 import_tags,              "oura_tags"),
    ("temperature",                 import_temperature_raw,   "oura_temperature_raw"),
    ("daytimestress",               import_daytime_stress,    "oura_daytime_stress"),
    ("sleepmodel",                  import_sleep_model,       "oura_sleep_model"),
    ("vo2max",                      import_vo2max,            "oura_vo2max"),
    ("workout",                     import_workouts,          "oura_workouts"),
    ("nonhormonalcontraceptionusage", import_contraception,   "oura_contraception"),
    ("hormonalcontraceptionusage",  import_contraception,     "oura_contraception"),
    ("surveyresponse",              import_survey,            "oura_survey"),
    ("bloodglucose",                import_blood_glucose,     "oura_blood_glucose"),
    ("bloodpressure",               import_blood_pressure,    "oura_blood_pressure"),
    ("medicationadministrationlog", import_medications,       "oura_medications"),
    ("labtestresult",               import_lab_results,         "oura_lab_results"),
    ("labtestresultinsights",       import_lab_insights,        "oura_lab_insights"),
    ("rawlocation",                 import_location_stays,      "location_stays"),
    # Tägliche Zusammenfassungen → measurements (füllen historische Lücken ggü. API)
    ("dailyactivity",               import_daily_activity_csv,  "measurements"),
    ("dailyreadiness",              import_daily_readiness_csv, "measurements"),
    ("dailysleep",                  import_daily_sleep_csv,     "measurements"),
    ("dailyspo2",                   import_daily_spo2_csv,      "measurements"),
    ("dailystress",                 import_daily_stress_csv,    "measurements"),
    ("dailycardiovascularage",      import_cardiovascular_age_csv, "measurements"),
    ("heartrate",                   import_heartrate_csv,       "measurements"),
    # Neue Metriken (nicht in API)
    ("dailyresilience",             import_daily_resilience,    "measurements"),
    ("dailymetabolicscore",         import_daily_metabolic_score, "measurements"),
    ("dailysmoothedcardiovascularage", import_daily_smoothed_cva, "measurements"),
    # Neue Tabellen
    ("dailybloodpressuresignals",   import_bp_signals,          "oura_bp_signals"),
    ("session",                     import_guided_sessions,     "oura_guided_sessions"),
    ("restmodeperiod",              import_rest_mode,           "oura_rest_mode"),
    ("sleeptime",                   import_sleep_time,          "oura_sleep_time"),
    ("fooditem",                    import_food_items,          "oura_food_items"),
    ("meal",                        import_meals,               "oura_meals"),
    ("glp1settings",                import_glp1_settings,       "oura_glp1_settings"),
]

# Funktionen, die eine person-Spalte schreiben — Dispatch-Loop reicht --person
# nur an diese durch, s. import_all.py::_PERSON_AWARE für dasselbe Muster.
_PERSON_AWARE = {
    import_tags, import_daytime_stress, import_sleep_model,
    import_daily_activity_csv, import_daily_readiness_csv, import_daily_sleep_csv,
    import_daily_spo2_csv, import_daily_stress_csv, import_cardiovascular_age_csv,
    import_heartrate_csv, import_daily_resilience, import_daily_metabolic_score,
    import_daily_smoothed_cva,
}


def find_zip() -> Path | None:
    candidates = sorted(ZIP_DIR.glob("data*.zip"), reverse=True)
    return candidates[0] if candidates else None


def main():
    """
    Hauptfunktion: Koordiniert den Import der Oura CSV-Export-Daten.

    Command-Line-Argumente:
        --file: Expliziter ZIP-Path
        --rebuild: Tables leeren und neu aufbauen
        --update: Nur neue Daten
        --from/to: Ignoriert (kein Filter auf CSV-Import)
    """
    parser = argparse.ArgumentParser(description="Oura CSV-Export (data.zip) → SQLite")
    parser.add_argument("--file",    metavar="PATH", help="Expliziter ZIP-Path")
    parser.add_argument("--rebuild", action="store_true", help="Tables leeren + neu")
    parser.add_argument("--update",  action="store_true", help="Nur neue Daten (No-op, Duplikate via PRIMARY KEY verhindert)")
    parser.add_argument("--from",    dest="date_from", metavar="DATE", help="Ignoriert (kein Filter auf CSV-Import)")
    parser.add_argument("--to",      dest="date_to",   metavar="DATE", help="Ignoriert (kein Filter auf CSV-Import)")
    parser.add_argument("--person", default=None, help="Ziel-Person (Default: OWN_PERSON_ID)")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = resolve_person(args.person)

    zip_path = Path(args.file) if args.file else find_zip()
    if not zip_path or not zip_path.exists():
        print(t(f"Keine data.zip gefunden in {ZIP_DIR}", f"No data.zip found in {ZIP_DIR}"), file=sys.stderr)
        sys.exit(1)

    conn = open_db()
    setup_db(conn)

    if args.rebuild:
        rebuild(conn)

    print(t(f"Importiere: {zip_path.name}\n", f"Importing: {zip_path.name}\n"))

    total = 0
    with zipfile.ZipFile(zip_path) as zf:
        for csv_name, func, table in IMPORTERS:
            rows = read_csv(zf, csv_name)
            if not rows:
                print(t(f"  {csv_name:45s} — leer / nicht vorhanden",
                        f"  {csv_name:45s} — empty / not present"))
                continue
            n = func(conn, rows, person) if func in _PERSON_AWARE else func(conn, rows)
            total += n
            print(f"  {csv_name:45s} {n:6,}  → {table}")

    n_mirrored = mirror_workouts_to_sessions(conn, person)
    total += n_mirrored
    print(f"  {'workout → sessions (Sport-Filter)':45s} {n_mirrored:6,}  → sessions")

    print(t(f"\n  Gesamt: {total:,} Einträge importiert", f"\n  Total: {total:,} entries imported"))

    # Overview
    print(t("\n── Übersicht ──────────────────────────────────────", "\n── Overview ───────────────────────────────────────"))
    checks = [
        ("oura_cycle_insights",  "SELECT COUNT(*), MIN(day), MAX(day) FROM oura_cycle_insights"),
        ("oura_tags",            "SELECT COUNT(*), MIN(start_day), MAX(start_day) FROM oura_tags"),
        ("oura_temperature_raw", "SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM oura_temperature_raw"),
        ("oura_daytime_stress",  "SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM oura_daytime_stress"),
        ("oura_sleep_model",     "SELECT COUNT(*), MIN(day), MAX(day) FROM oura_sleep_model"),
        ("oura_vo2max",          "SELECT COUNT(*), MIN(day), MAX(day) FROM oura_vo2max"),
        ("location_stays",       "SELECT COUNT(*), MIN(start_ts), MAX(end_ts) FROM location_stays"),
    ]
    for label, sql in checks:
        r = conn.execute(sql).fetchone()
        if r[0]:
            print(f"  {label:30s} {r[0]:6,}  {r[1]} → {r[2]}")

    log_import(conn, "oura_csv", str(zip_path), total, person=person)
    conn.commit()

    print(t(f"\nDatenbank: {DB_PATH}", f"\nDatabase: {DB_PATH}"))
    conn.close()


if __name__ == "__main__":
    main()
