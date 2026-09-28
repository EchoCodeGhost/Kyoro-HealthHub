#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
create_schema.py — Datenbank-Schema Phase 1 erstellen

@tier        infrastructure
@purpose.de  Erstellt health_v2.db mit vollem v2-Schema und migriert kleine Tabellen.
             Phase 1 der Datenbank-Migration.
@purpose.en  Creates health_v2.db with full v2 schema and migrates small tables.
             Phase 1 of database migration.
@method.de   Schritte: 1) health_v2.db mit v2-Schema erstellen, 2) persons + devices
             befüllen, 3) source_priority (initiale Einträge), 4) Kleine klinische Tabellen
             aus health.db migrieren, 5) Kontext-Tabellen kopieren (home_*, weather_*,
             location_*, polar_sleep_*), 6) schema_version + import_log schreiben.
             Sicher wiederholbar — bricht ab, wenn schema_version 1 bereits vorhanden.
@method.en   Steps: 1) Create health_v2.db with full v2 schema, 2) Populate persons + devices,
             3) source_priority (initial entries), 4) Migrate small clinical tables from
             health.db, 5) Copy context tables (home_*, weather_*, location_*, polar_sleep_*),
             6) Write schema_version + import_log. Safely repeatable.
@reads       data/health.db
@writes      data/health_v2.db (schema_version, import_log, kleine Tabellen)

@limits.de   Migration ist einmalig. Vorherige DB bleibt als health.db erhalten. Setzt Python 3.10+ voraus.

@relevance.de  Ermöglicht die Erstellung von Datenbank-Schemata, essentiell für die Datenorganisation und -struktur
@relevance.en  Enables creation of database schemas, essential for data organization and structure
@limits.en   Migration is one-time. Previous DB is preserved as health.db. Requires Python 3.10+.
@usage
    python create_schema.py
    python create_schema.py --help
    python create_schema.py --from 2024-01-01 --to 2024-12-31
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from modules.i18n import t
from health_config import OWN_PERSON_ID

ROOT   = Path(__file__).resolve().parents[2]
DB_V1  = ROOT / "data" / "health.db"
DB_V2  = ROOT / "data" / "health_v2.db"

PHASE = 1
PHASE_DESC = "Schema + kleine Tabellen (Phase 1)"
NOW   = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """

-- Versionierung
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL,
    description TEXT NOT NULL
);

-- Personen
CREATE TABLE IF NOT EXISTS persons (
    person_id      TEXT PRIMARY KEY,
    display_name   TEXT,
    device_user_id TEXT,
    timezone       TEXT NOT NULL DEFAULT 'Europe/Berlin',
    active         INTEGER DEFAULT 1,
    notes          TEXT
);

-- Geräte
-- brand/model bewusst NICHT hier: ein Klartext-Gerätemodell (z.B. "Polar
-- Vantage V3") in derselben Zeile wie das device_id-Pseudonym würde die
-- Pseudonymisierung sofort aushebeln (siehe docs/PRIVACY_ARCHITECTURE.md).
-- brand/model bleiben ausschließlich lokal in registry.json, aufgelöst über
-- identity_resolver.resolve_display_name() für lokale Reports/Exporte.
CREATE TABLE IF NOT EXISTS devices (
    device_id        TEXT PRIMARY KEY,
    serial           TEXT,
    sensor_type      TEXT,
    person           TEXT REFERENCES persons(person_id),
    timezone         TEXT,
    date_from        TEXT NOT NULL,
    date_to          TEXT,
    notes            TEXT,
    regulatory_json  TEXT   -- JSON: {medical_device, grade, mdr_class, fda_510k, ...}
);

-- device_serial_map und account_pseudo_map leben in ~/.config/kyoro/identity.db (nicht hier)

CREATE TABLE IF NOT EXISTS device_firmware_history (
    device_id   TEXT NOT NULL REFERENCES devices(device_id),
    firmware    TEXT NOT NULL,
    valid_from  TEXT NOT NULL,
    detected_by TEXT NOT NULL,
    notes       TEXT,
    PRIMARY KEY (device_id, valid_from)
);

-- Import-Protokoll
CREATE TABLE IF NOT EXISTS import_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_run        TEXT NOT NULL,
    source        TEXT NOT NULL,
    data_path     TEXT,
    person        TEXT REFERENCES persons(person_id),
    rows_inserted INTEGER DEFAULT 0,
    rows_skipped  INTEGER DEFAULT 0,
    errors        INTEGER DEFAULT 0,
    error_detail  TEXT,
    duration_s    REAL
);
CREATE INDEX IF NOT EXISTS idx_importlog_source ON import_log(source, ts_run);

-- Datei-Hashes für Chain-of-Custody (forensische Integrität)
CREATE TABLE IF NOT EXISTS import_file_hashes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    import_log_id INTEGER NOT NULL REFERENCES import_log(id),
    file_path     TEXT NOT NULL,
    sha256        TEXT NOT NULL,
    file_size     INTEGER,
    file_mtime    TEXT
);
CREATE INDEX IF NOT EXISTS idx_importfilehashes_log ON import_file_hashes(import_log_id);

-- Compute-Protokoll (Pendant zu import_log für scripts/compute/*)
CREATE TABLE IF NOT EXISTS compute_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_run        TEXT NOT NULL,
    script        TEXT NOT NULL,
    git_commit    TEXT,
    returncode    INTEGER NOT NULL DEFAULT 0,
    duration_s    REAL
);
CREATE INDEX IF NOT EXISTS idx_computelog_script ON compute_log(script, ts_run);

-- Quell-Priorität (Duplikat-Auflösung)
CREATE TABLE IF NOT EXISTS source_priority (
    metric     TEXT NOT NULL,
    device_id  TEXT NOT NULL,
    source_app TEXT NOT NULL,
    priority   INTEGER NOT NULL,
    person     TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (metric, device_id, source_app, person)
);

-- Datenqualität
CREATE TABLE IF NOT EXISTS data_quality_flags (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT,
    date       TEXT,
    table_name TEXT NOT NULL,
    metric     TEXT,
    device_id  TEXT,
    person     TEXT NOT NULL DEFAULT 'unknown',
    flag_type  TEXT NOT NULL,
    detail     TEXT
);

-- -----------------------------------------------------------------------
-- Zeitreihen (Phase 4)
-- -----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS measurements (
    ts         TEXT NOT NULL,
    date       TEXT NOT NULL,
    metric     TEXT NOT NULL,
    value      REAL,
    value_text TEXT,
    unit       TEXT,
    device_id  TEXT REFERENCES devices(device_id),
    person     TEXT NOT NULL DEFAULT 'unknown',
    source_app TEXT,
    PRIMARY KEY (ts, metric, device_id, person)
);
CREATE INDEX IF NOT EXISTS idx_meas_date   ON measurements(date);
CREATE INDEX IF NOT EXISTS idx_meas_metric ON measurements(metric, date);
CREATE INDEX IF NOT EXISTS idx_meas_person ON measurements(person, date);
CREATE INDEX IF NOT EXISTS idx_meas_metric_ts ON measurements(metric, ts);

CREATE TABLE IF NOT EXISTS ppi_raw (
    datetime  TEXT NOT NULL,
    pulse_ms  INTEGER NOT NULL,
    device    TEXT,
    source    TEXT DEFAULT NULL,
    person    TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (datetime, pulse_ms, device, person)
);
CREATE INDEX IF NOT EXISTS idx_ppi_date   ON ppi_raw(substr(datetime,1,10));
CREATE INDEX IF NOT EXISTS idx_ppi_person ON ppi_raw(person, substr(datetime,1,10));

CREATE TABLE IF NOT EXISTS cgm_readings (
    ts           TEXT NOT NULL,
    date         TEXT NOT NULL,
    glucose_mmol REAL,
    glucose_mgdl REAL,
    trend        TEXT,
    device_id    TEXT REFERENCES devices(device_id),
    person       TEXT NOT NULL DEFAULT 'unknown',
    source       TEXT,
    PRIMARY KEY (ts, person)
);
CREATE INDEX IF NOT EXISTS idx_cgm_date   ON cgm_readings(date);
CREATE INDEX IF NOT EXISTS idx_cgm_person ON cgm_readings(person, date);

-- -----------------------------------------------------------------------
-- Sessions (Phase 2)
-- -----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    type          TEXT NOT NULL,
    ts_start      TEXT NOT NULL,
    ts_end        TEXT,
    date          TEXT NOT NULL,
    device_id     TEXT REFERENCES devices(device_id),
    person        TEXT NOT NULL DEFAULT 'unknown',
    source_app    TEXT,
    sport         TEXT,
    wear_location TEXT,  -- Tragort, falls das Geraet je Nutzung variiert (z.B. Verity Sense: Arm/Bein/Schlaefe); NULL = fixer/unbekannter Tragort
    mode          TEXT   -- Aufzeichnungsmodus, falls relevant (z.B. 'schwimmen'); NULL = Standardmodus
);
CREATE INDEX IF NOT EXISTS idx_sess_date   ON sessions(date);
CREATE INDEX IF NOT EXISTS idx_sess_type   ON sessions(type, date);
CREATE INDEX IF NOT EXISTS idx_sess_device ON sessions(device_id);

CREATE TABLE IF NOT EXISTS session_metrics (
    session_id TEXT NOT NULL REFERENCES sessions(id),
    metric     TEXT NOT NULL,
    value      REAL,
    value_text TEXT,
    unit       TEXT,
    PRIMARY KEY (session_id, metric)
);
CREATE INDEX IF NOT EXISTS idx_sm_metric ON session_metrics(metric);

CREATE TABLE IF NOT EXISTS session_tracks (
    session_id  TEXT REFERENCES sessions(id),
    ts          TEXT NOT NULL,
    lat         REAL,
    lon         REAL,
    elevation_m REAL,
    speed_ms    REAL,
    PRIMARY KEY (session_id, ts)
);

-- -----------------------------------------------------------------------
-- Stryd (Laufleistungsmesser, sekundengenaue Laufdynamik)
-- -----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS stryd_sessions (
    session_id   TEXT NOT NULL,  -- ISO-Timestamp der ersten Zeile
    person       TEXT NOT NULL DEFAULT 'unknown',
    ts_start     TEXT NOT NULL,
    ts_end       TEXT,
    date         TEXT NOT NULL,
    duration_s   INTEGER,
    device_id    TEXT REFERENCES devices(device_id),
    source_file  TEXT,
    PRIMARY KEY (session_id, person)
);
CREATE INDEX IF NOT EXISTS idx_stryd_sessions_date ON stryd_sessions(person, date);

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
CREATE INDEX IF NOT EXISTS idx_stryd_samples_session ON stryd_samples(session_id, session_person);

-- -----------------------------------------------------------------------
-- ECG (Phase 3)
-- -----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ecg_sessions (
    datetime        TEXT NOT NULL,
    classification  TEXT,
    symptoms        TEXT,
    sample_rate_hz  INTEGER,
    lead            TEXT DEFAULT 'lead_1',
    duration_s      REAL,
    device_id       TEXT REFERENCES devices(device_id),
    person          TEXT NOT NULL DEFAULT 'unknown',
    source          TEXT,
    PRIMARY KEY (datetime, person)
);
CREATE INDEX IF NOT EXISTS idx_ecg_person ON ecg_sessions(person, datetime);

CREATE TABLE IF NOT EXISTS ecg_samples (
    session_dt     TEXT NOT NULL,
    session_person TEXT NOT NULL DEFAULT 'unknown',
    sample_index   INTEGER,
    uv             REAL,
    PRIMARY KEY (session_dt, session_person, sample_index),
    FOREIGN KEY (session_dt, session_person) REFERENCES ecg_sessions(datetime, person)
);

CREATE TABLE IF NOT EXISTS fibricheck_sessions (
    ts                 TEXT NOT NULL,   -- Messbeginn
    ts_reviewed        TEXT,            -- Zeitpunkt Expertengremium-Pruefung, NULL wenn (noch) ungeprueft
    date               TEXT NOT NULL,
    result_code        TEXT,            -- normalisiert, z.B. 'extrasystoles_bigeminy', 'normal', 'afib_suspected'
    result_text        TEXT,            -- Original-Ergebnistext aus dem PDF
    hr_avg_bpm         REAL,
    activity_context   TEXT,            -- z.B. 'sleeping', vom Nutzer vor der Messung angegeben
    symptoms_reported  INTEGER DEFAULT 0,
    recording_device   TEXT,            -- Aufnahmegeraet lt. Bericht (z.B. "Apple iPhone 16 Pro") - Freitext, kein devices.device_id
    algorithm_version   TEXT,
    panel_reviewed      INTEGER DEFAULT 0,
    person              TEXT NOT NULL DEFAULT 'unknown',
    source_file         TEXT,
    PRIMARY KEY (ts, person)
);
CREATE INDEX IF NOT EXISTS idx_fibricheck_person ON fibricheck_sessions(person, date);

CREATE TABLE IF NOT EXISTS ecg_rpeaks (
    session_dt     TEXT NOT NULL,
    session_person TEXT NOT NULL,
    sample_index   INTEGER NOT NULL,
    peak_ms        REAL,
    method         TEXT DEFAULT 'pan_tompkins',
    PRIMARY KEY (session_dt, session_person, sample_index),
    FOREIGN KEY (session_dt, session_person) REFERENCES ecg_sessions(datetime, person)
);
CREATE INDEX IF NOT EXISTS idx_ecg_rpeaks_session ON ecg_rpeaks(session_dt, session_person);

-- -----------------------------------------------------------------------
-- Klinische Tabellen (Phase 1 — Daten aus health.db)
-- -----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS blood_pressure (
    ts            TEXT NOT NULL,
    date          TEXT NOT NULL,
    systolic      INTEGER,
    diastolic     INTEGER,
    pulse         INTEGER,
    ihb_flag      INTEGER,
    afib_possible INTEGER,
    truread       TEXT,
    symptoms      TEXT,
    movement      TEXT,
    cuff_ok       TEXT,
    device_id     TEXT REFERENCES devices(device_id),
    notes         TEXT,
    person        TEXT NOT NULL DEFAULT 'unknown',
    source        TEXT,
    PRIMARY KEY (ts, person)
);

CREATE TABLE IF NOT EXISTS blood_glucose (
    ts           TEXT NOT NULL,
    date         TEXT NOT NULL,
    glucose_mmol REAL,
    glucose_mgdl REAL,
    meal_context TEXT,
    hba1c        REAL,
    comment      TEXT,
    device_id    TEXT REFERENCES devices(device_id),
    person       TEXT NOT NULL DEFAULT 'unknown',
    source       TEXT,
    PRIMARY KEY (ts, person)
);

CREATE TABLE IF NOT EXISTS body_composition (
    ts                TEXT NOT NULL,
    date              TEXT NOT NULL,
    weight_kg         REAL,
    bmi               REAL,
    body_fat_pct      REAL,
    water_pct         REAL,
    muscle_pct        REAL,
    bone_kg           REAL,
    fat_arm_left      REAL,
    fat_arm_right     REAL,
    fat_leg_left      REAL,
    fat_leg_right     REAL,
    fat_trunk         REAL,
    fat_visceral_pct  REAL,
    muscle_arm_left   REAL,
    muscle_arm_right  REAL,
    muscle_leg_left   REAL,
    muscle_leg_right  REAL,
    muscle_trunk      REAL,
    metabolic_age     INTEGER,
    visceral_fat      INTEGER,
    pulse_bpm         INTEGER,
    waist_cm          REAL,
    hip_cm            REAL,
    soft_lean_mass_kg REAL,
    lean_body_mass_kg REAL,
    protein_pct       REAL,
    muscle_mass_organ_kg REAL,
    comment           TEXT,
    device_id         TEXT REFERENCES devices(device_id),
    person            TEXT NOT NULL DEFAULT 'unknown',
    source            TEXT,
    PRIMARY KEY (ts, person)
);

CREATE TABLE IF NOT EXISTS symptoms (
    date       TEXT NOT NULL,
    symptom    TEXT NOT NULL,
    value_num  REAL,
    value_text TEXT,
    category   TEXT,
    person     TEXT NOT NULL DEFAULT 'unknown',
    source     TEXT,
    PRIMARY KEY (date, symptom, person, source)
);

CREATE TABLE IF NOT EXISTS reproductive_health (
    date       TEXT NOT NULL,
    event_type TEXT NOT NULL,
    value_num  REAL,
    value_text TEXT,
    person     TEXT NOT NULL DEFAULT 'unknown',
    source     TEXT,
    PRIMARY KEY (date, event_type, person, source)
);

CREATE TABLE IF NOT EXISTS user_context (
    id          TEXT NOT NULL,
    date        TEXT NOT NULL,
    ts_start    TEXT,
    ts_end      TEXT,
    person      TEXT NOT NULL,
    source      TEXT NOT NULL,
    source_app  TEXT,
    tag         TEXT,
    note        TEXT,
    PRIMARY KEY (id, person)
);
CREATE INDEX IF NOT EXISTS idx_user_context_date ON user_context(date);

CREATE TABLE IF NOT EXISTS medications (
    ts             TEXT NOT NULL,
    date           TEXT NOT NULL,
    medication_id  TEXT,
    drug_name      TEXT NOT NULL,
    dose_value     REAL,
    dose_unit      TEXT,
    route          TEXT,
    injection_site TEXT,
    is_skipped     INTEGER DEFAULT 0,
    is_chronic     INTEGER DEFAULT 1,
    notes          TEXT,
    person         TEXT NOT NULL DEFAULT 'unknown',
    source         TEXT,
    PRIMARY KEY (ts, person, source, drug_name)
);

CREATE TABLE IF NOT EXISTS self_care (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT    NOT NULL,
    date         TEXT    NOT NULL,
    person       TEXT    NOT NULL,
    category     TEXT    NOT NULL,
    name         TEXT    NOT NULL,
    dose_value   REAL,
    dose_unit    TEXT,
    route        TEXT,
    duration_min INTEGER,
    effect       INTEGER,
    notes        TEXT,
    source       TEXT    DEFAULT 'manual',
    UNIQUE (ts, person, name)
);

CREATE TABLE IF NOT EXISTS lab_results (
    id              TEXT NOT NULL,
    test_type       TEXT NOT NULL,
    ts              TEXT NOT NULL,
    date            TEXT NOT NULL,
    status          TEXT,
    abnormal_result INTEGER,
    observations    TEXT,
    person          TEXT NOT NULL DEFAULT 'unknown',
    source          TEXT DEFAULT 'oura',
    PRIMARY KEY (id, person)
);

CREATE TABLE IF NOT EXISTS lab_manual (
    date       TEXT NOT NULL,
    parameter  TEXT NOT NULL,
    kategorie  TEXT,
    wert       TEXT,
    wert_num   REAL,
    einheit    TEXT,
    ref_min    REAL,
    ref_max    REAL,
    labor      TEXT NOT NULL DEFAULT '',
    status     TEXT,
    kommentar  TEXT,
    person     TEXT NOT NULL,
    source     TEXT DEFAULT 'manual',
    PRIMARY KEY (date, parameter, labor, person)
);

CREATE TABLE IF NOT EXISTS assessments (
    ts         TEXT NOT NULL,
    date       TEXT NOT NULL,
    instrument TEXT NOT NULL,
    score      REAL,
    details    TEXT,
    person     TEXT NOT NULL DEFAULT 'unknown',
    source     TEXT,
    PRIMARY KEY (ts, instrument, person)
);

CREATE TABLE IF NOT EXISTS nutrition_daily (
    date       TEXT NOT NULL,
    kcal       REAL,
    fat_g      REAL,
    carbs_g    REAL,
    protein_g  REAL,
    fiber_g    REAL,
    sugar_g    REAL,
    salt_g     REAL,
    meal_count INTEGER,
    last_meal  TEXT,
    person     TEXT NOT NULL DEFAULT 'unknown',
    source     TEXT,
    PRIMARY KEY (date, person)
);

CREATE TABLE IF NOT EXISTS nutrition_entries (
    ts         TEXT NOT NULL,
    date       TEXT NOT NULL,
    time_str   TEXT,
    meal_type  TEXT,
    name       TEXT,
    product_id TEXT,
    energy_kj  REAL,
    fat_g      REAL,
    carbs_g    REAL,
    protein_g  REAL,
    fiber_g    REAL,
    sugar_g    REAL,
    salt_g     REAL,
    portion_g  REAL,
    person     TEXT NOT NULL DEFAULT 'unknown',
    source     TEXT,
    PRIMARY KEY (ts, name, person, source)
);

CREATE TABLE IF NOT EXISTS nutrition_allergens (
    ts           TEXT NOT NULL,
    date         TEXT NOT NULL,
    name         TEXT NOT NULL,
    gluten       INTEGER DEFAULT 0,
    oats         INTEGER DEFAULT 0,
    milk         INTEGER DEFAULT 0,
    eggs         INTEGER DEFAULT 0,
    fish         INTEGER DEFAULT 0,
    shellfish    INTEGER DEFAULT 0,
    peanuts      INTEGER DEFAULT 0,
    tree_nuts    INTEGER DEFAULT 0,
    soy          INTEGER DEFAULT 0,
    celery       INTEGER DEFAULT 0,
    mustard      INTEGER DEFAULT 0,
    sesame       INTEGER DEFAULT 0,
    sulphites    INTEGER DEFAULT 0,
    lupin        INTEGER DEFAULT 0,
    person       TEXT NOT NULL DEFAULT 'unknown',
    source       TEXT DEFAULT 'keyword_match',
    PRIMARY KEY (ts, person)
);
CREATE INDEX IF NOT EXISTS idx_nutr_all_date   ON nutrition_allergens(date);
CREATE INDEX IF NOT EXISTS idx_nutr_all_person ON nutrition_allergens(person);

-- -----------------------------------------------------------------------
-- Kontext-Tabellen (bleiben, person-Spalte ergänzt)
-- -----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS polar_sleep_hypnogram (
    date        TEXT NOT NULL,
    offset_s    INTEGER,
    state       TEXT,
    sleep_start TEXT,
    person      TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (date, offset_s, person)
);

CREATE TABLE IF NOT EXISTS polar_sleep_wake (
    date          TEXT NOT NULL,
    device        TEXT,
    millis_in_day INTEGER,
    state         TEXT,
    person        TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (date, millis_in_day, person)
);

CREATE TABLE IF NOT EXISTS kubios_hrv_resting (
    datetime         TEXT NOT NULL,
    hr_bpm           REAL,
    rmssd_ms         REAL,
    mean_rr_ms       REAL,
    sdnn_ms          REAL,
    sd1_ms           REAL,
    sd2_ms           REAL,
    stress_index     REAL,
    resp_rate        REAL,
    lf_power_ms2     REAL,
    hf_power_ms2     REAL,
    lf_nu            REAL,
    hf_nu            REAL,
    lf_hf_ratio      REAL,
    pns_index        REAL,
    sns_index        REAL,
    physiological_age INTEGER,
    readiness_pct    INTEGER,
    person           TEXT NOT NULL DEFAULT 'unknown',
    source           TEXT,
    PRIMARY KEY (datetime, person)
);

CREATE TABLE IF NOT EXISTS camera_hrv_resting (
    datetime         TEXT NOT NULL,        -- ISO 8601 UTC
    hr_bpm           REAL,
    rmssd_ms         REAL,
    mean_rr_ms       REAL,
    sdnn_ms          REAL,
    pnn50_pct        REAL,
    lf_power         REAL,                 -- unit is app-export-dependent, not
    hf_power         REAL,                 -- guaranteed ms² -- see import_camerahRV.py @limits
    lf_hf_ratio      REAL,
    stress_index     REAL,
    readiness_pct    INTEGER,
    measurement_s    INTEGER,              -- Messdauer in Sekunden
    person           TEXT NOT NULL DEFAULT 'unknown',
    source_app       TEXT DEFAULT 'camerahRV',
    PRIMARY KEY (datetime, person)
);

CREATE TABLE IF NOT EXISTS oura_sleep_model (
    id                     TEXT NOT NULL,
    day                    TEXT,
    bedtime_start          TEXT,
    bedtime_end            TEXT,
    average_heart_rate     REAL,
    average_hrv            REAL,
    average_breath         REAL,
    total_sleep_duration   INTEGER,
    deep_sleep_duration    INTEGER,
    light_sleep_duration   INTEGER,
    rem_sleep_duration     INTEGER,
    awake_time             INTEGER,
    efficiency             INTEGER,
    latency                INTEGER,
    restless_periods       INTEGER,
    lowest_heart_rate      INTEGER,
    sleep_phase_5_min      TEXT,
    sleep_phase_30_sec     TEXT,
    heart_rate_json        TEXT,
    hrv_json               TEXT,
    movement_30_sec        TEXT,
    person                 TEXT NOT NULL DEFAULT 'unknown',
    source                 TEXT,
    PRIMARY KEY (id, person)
);

CREATE TABLE IF NOT EXISTS sleep_hypnogram (
    session_id  TEXT,
    ts          TEXT NOT NULL,
    date        TEXT NOT NULL,
    stage       TEXT NOT NULL CHECK(stage IN ('WAKE','LIGHT','DEEP','REM')),
    duration_s  INTEGER,
    source      TEXT NOT NULL,
    device_id   TEXT,
    person      TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (ts, source, person)
);

CREATE TABLE IF NOT EXISTS home_environment (
    date        TEXT NOT NULL,
    entity_id   TEXT,
    sensor_type TEXT,
    mean_value  REAL,
    min_value   REAL,
    max_value   REAL,
    unit        TEXT,
    source      TEXT,
    PRIMARY KEY (date, entity_id)
);

CREATE TABLE IF NOT EXISTS home_environment_ts (
    datetime    TEXT NOT NULL,
    sensor_type TEXT,
    value       REAL,
    entity_id   TEXT,
    source      TEXT,
    PRIMARY KEY (datetime, entity_id)
);

CREATE TABLE IF NOT EXISTS home_presence (
    date        TEXT NOT NULL PRIMARY KEY,
    at_home     INTEGER,
    iphone_home INTEGER,
    car_home    INTEGER,
    away_hours  REAL,
    source      TEXT
);

CREATE TABLE IF NOT EXISTS weather_station (
    date           TEXT NOT NULL PRIMARY KEY,
    temp_out_c     REAL,
    temp_out_min   REAL,
    temp_out_max   REAL,
    humidity_out   REAL,
    temp_in_c      REAL,
    humidity_in    REAL,
    pressure_hpa   REAL,
    pressure_min   REAL,
    pressure_max   REAL,
    wind_speed_kmh REAL,
    wind_gust_max  REAL,
    wind_dir_deg   REAL,
    rain_mm        REAL,
    rain_rate_max  REAL,
    uv_index_max   REAL,
    solar_wm2_max  REAL,
    dewpoint_c     REAL,
    feels_like_c   REAL,
    source         TEXT,
    location       TEXT,
    lat            REAL,
    lon            REAL,
    person         TEXT NOT NULL DEFAULT 'unknown'
);

CREATE TABLE IF NOT EXISTS weather_remote (
    ts           TEXT NOT NULL PRIMARY KEY,
    lat          REAL,
    lon          REAL,
    temp_c       REAL,
    precip_mm    REAL,
    windspeed_kmh REAL,
    pressure_hpa REAL,
    weathercode  INTEGER,
    source       TEXT,
    person       TEXT NOT NULL DEFAULT 'unknown'
);

CREATE TABLE IF NOT EXISTS air_quality (
    date         TEXT NOT NULL,
    lat          REAL NOT NULL,
    lon          REAL NOT NULL,
    pm25_mean    REAL,
    pm25_max     REAL,
    pm10_mean    REAL,
    pm10_max     REAL,
    no2_mean     REAL,
    no2_max      REAL,
    o3_mean      REAL,
    o3_max       REAL,
    co_mean      REAL,
    co_max       REAL,
    aqi_eu_mean  REAL,
    aqi_eu_max   INTEGER,
    dust_mean    REAL,
    dust_max     REAL,
    source       TEXT DEFAULT 'open-meteo',
    person       TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (date, lat, lon)
);

CREATE TABLE IF NOT EXISTS pollen_dwd (
    date        TEXT NOT NULL,
    region_id   INTEGER NOT NULL,
    region_name TEXT,
    hazel       REAL,
    alder       REAL,
    ash         REAL,
    birch       REAL,
    grass       REAL,
    rye         REAL,
    mugwort     REAL,
    ragweed     REAL,
    source      TEXT DEFAULT 'dwd',
    person      TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (date, region_id)
);

CREATE TABLE IF NOT EXISTS pollen_google (
    date        TEXT NOT NULL,
    plant_code  TEXT NOT NULL,
    upi         REAL,
    category    TEXT,
    source      TEXT DEFAULT 'google',
    person      TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (date, plant_code)
);

CREATE TABLE IF NOT EXISTS biometeo (
    date                 TEXT NOT NULL,
    lat                  REAL NOT NULL,
    lon                  REAL NOT NULL,
    sunshine_h           REAL,
    solar_mj_m2          REAL,
    uv_index_max         REAL,
    apparent_temp_mean   REAL,
    apparent_temp_max    REAL,
    apparent_temp_min    REAL,
    dewpoint_mean        REAL,
    humidity_mean        REAL,
    source               TEXT DEFAULT 'open-meteo',
    person               TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (date, lat, lon)
);

CREATE TABLE IF NOT EXISTS photo_locations (
    date                 TEXT NOT NULL,
    lat                  REAL NOT NULL,
    lon                  REAL NOT NULL,
    source               TEXT NOT NULL,
    person               TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (date, lat, lon, source)
);

CREATE TABLE IF NOT EXISTS indoor_air_quality (
    date        TEXT NOT NULL,
    entity_id   TEXT NOT NULL,
    device      TEXT,           -- 'dyson' / 'vesync' / 'other'
    sensor_type TEXT,           -- 'pm25','pm10','voc','no2','aqi','co2','filter_life','temperature','humidity'
    mean_value  REAL,
    min_value   REAL,
    max_value   REAL,
    unit        TEXT,
    source      TEXT DEFAULT 'homeassistant',
    person      TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (date, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_iaq_date ON indoor_air_quality(date);
CREATE INDEX IF NOT EXISTS idx_iaq_type ON indoor_air_quality(sensor_type);
CREATE INDEX IF NOT EXISTS idx_iaq_device ON indoor_air_quality(device);

CREATE TABLE IF NOT EXISTS pollen (
    date         TEXT NOT NULL,
    lat          REAL NOT NULL,
    lon          REAL NOT NULL,
    birch        REAL,
    alder        REAL,
    grass        REAL,
    mugwort      REAL,
    ragweed      REAL,
    olive        REAL,
    source       TEXT DEFAULT 'open-meteo',
    person       TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (date, lat, lon)
);

CREATE TABLE IF NOT EXISTS location_history (
    datetime     TEXT NOT NULL,
    date         TEXT,
    hour         INTEGER,
    state        TEXT,
    lat          REAL,
    lon          REAL,
    gps_accuracy REAL,
    zone         TEXT,
    city         TEXT,
    person       TEXT NOT NULL DEFAULT 'unknown',
    source       TEXT,
    PRIMARY KEY (datetime, person)
);

CREATE TABLE IF NOT EXISTS location_stays (
    id       INTEGER PRIMARY KEY,
    start_ts TEXT,
    end_ts   TEXT,
    lat      REAL,
    lon      REAL,
    is_home  INTEGER,
    timezone TEXT,
    person   TEXT NOT NULL DEFAULT 'unknown',
    source   TEXT
);

-- Outbreak-Surveillance: Ausbruchsmeldungen aus WHO, ECDC, ProMED, HealthMap
-- und statische Endemie-Referenzdaten
CREATE TABLE IF NOT EXISTS outbreak_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,       -- who_don | ecdc | promedmail | healthmap | endemic_ref
    disease       TEXT NOT NULL,       -- originaler Krankheitsname
    syndrome_slug TEXT,                -- maps to SYNDROME_CONFIG keys
    country       TEXT,
    country_iso   TEXT,
    region        TEXT,
    lat           REAL,
    lon           REAL,
    date_reported TEXT NOT NULL,       -- Meldedatum (ISO)
    date_start    TEXT,                -- Ausbruchsbeginn (falls bekannt)
    date_end      TEXT,                -- Ausbruchsende (NULL = laufend/unbekannt)
    severity      TEXT,                -- low | medium | high
    url           TEXT,
    title         TEXT,
    fetched_at    TEXT NOT NULL,
    person        TEXT NOT NULL DEFAULT 'unknown',
    radius_km     REAL,                -- Geo-Match-Radius-Override in km (NULL = Skript-Standard
                                        -- je nach source); klein (~20 km) fuer landkreisgenaue
                                        -- Referenzpunkte, damit Nachbar-Landkreise nicht ueber
                                        -- einen fuer Laender-Zentroide gedachten Radius verschmelzen
    note          TEXT,                -- Freitext-Quellenkontext (z.B. "etablierte Population,
                                        -- LGL Bayern, Stand ..."); nur bei source='endemic_ref'
                                        -- befuellt, dient der Nachvollziehbarkeit im Report
    since_date    TEXT                 -- Frueheste dokumentierte Existenz dieses Risikos (YYYY-MM-DD);
                                        -- NULL = seit jeher/unbekannt endemisch (Standardverhalten,
                                        -- z.B. FSME/Malariazonen). Gesetzt nur bei juengeren, aktiv
                                        -- expandierenden Risiken (z.B. Tigermuecken-Landkreise) —
                                        -- verhindert, dass ein 2025er Verbreitungsstand faelschlich
                                        -- auf Reisen von vor Existenz des Risikos angewandt wird
                                        -- (anders als date_start, das nur eine saisonale
                                        -- Anzeige-Hilfsgroesse ist und nicht zur Filterung dient)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_outbreak_url
    ON outbreak_events(source, COALESCE(url, title || date_reported));

-- Inhaltsbasierter Deduplizierungs-Index (fängt URL-Änderungen ab)
CREATE UNIQUE INDEX IF NOT EXISTS idx_outbreak_content
    ON outbreak_events(source, disease, country, region, COALESCE(date_start, date_reported));

-- AMELAG-Abwassersurveillance (RKI/Umweltbundesamt): Viruslast im Abwasser
-- für SARS-CoV-2/Influenza/RSV. Eigene Tabelle statt outbreak_events, da die
-- Werte (Viruslast, Vorhersage, Konfidenzgrenzen, Bevölkerungsanteil) deutlich
-- reicher sind als ein einfaches Fall-/Inzidenz-Ereignis.
CREATE TABLE IF NOT EXISTS wastewater_amelag (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    date                  TEXT NOT NULL,
    level                 TEXT NOT NULL,       -- national | site
    site                  TEXT,                -- NULL bei level='national'
    bundesland            TEXT,                -- NULL bei level='national'
    virus                 TEXT NOT NULL,       -- SARS-CoV-2 | Influenza A | Influenza B | RSV A | RSV B | ...
    viral_load            REAL,
    viral_load_normalized REAL,
    forecast              REAL,
    upper_bound           REAL,
    lower_bound           REAL,
    population_share      REAL,                -- national: Anteil der Bevölkerung mit Abwasserdaten
    population_covered    INTEGER,             -- site: Einwohnerzahl im Einzugsgebiet
    below_detection_limit INTEGER,             -- site: 0/1, NULL wenn unbekannt
    source                TEXT DEFAULT 'rki_amelag',
    person                TEXT NOT NULL DEFAULT 'unknown'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_wastewater_amelag_key
    ON wastewater_amelag(date, level, COALESCE(site, ''), virus);

-- RKI-Notaufnahmesurveillance (AKTIN-Infrastruktur/Notaufnahmeregister):
-- tagesaktuelle Syndrom-Anteile an allen Notaufnahme-Vorstellungen (ARI, ILI,
-- COVID, SARI, GI, HEAT) inkl. Erwartungswert/Prädiktionsintervall aus der
-- Quelle selbst. Eigene Tabelle statt outbreak_events aus demselben Grund wie
-- wastewater_amelag — Erwartungswert/Grenzen passen nicht in ein einfaches
-- Fall-Event, und die Tages-Granularität würde outbreak_events fluten.
CREATE TABLE IF NOT EXISTS ed_syndromic_surveillance (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    date                   TEXT NOT NULL,
    ed_type                TEXT NOT NULL,      -- all | central | pediatric
    age_group              TEXT NOT NULL,      -- 00+ | 0-4 | 5-9 | ...
    syndrome               TEXT NOT NULL,      -- ARI | ILI | COVID | SARI | GI | HEAT
    relative_cases         REAL,               -- Anteil an allen ED-Vorstellungen (%)
    relative_cases_7day_ma REAL,
    expected_value         REAL,
    expected_lowerbound    REAL,
    expected_upperbound    REAL,
    ed_count               INTEGER,            -- Anzahl beitragender Notaufnahmen
    source                 TEXT DEFAULT 'rki_notaufnahme',
    person                 TEXT NOT NULL DEFAULT 'unknown'
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ed_syndromic_key
    ON ed_syndromic_surveillance(date, ed_type, age_group, syndrome);

-- Expositionsanalyse: Reise × Ausbruch
CREATE TABLE IF NOT EXISTS outbreak_exposure (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_name       TEXT,
    trip_country    TEXT,
    trip_region     TEXT,
    trip_date_from  TEXT,
    trip_date_to    TEXT,
    outbreak_id     INTEGER REFERENCES outbreak_events(id),
    overlap_days    INTEGER,
    exposure_score  REAL,       -- 0.0–1.0
    source          TEXT,       -- travel_history | location_stays | gps | home_residence
    computed_at     TEXT NOT NULL
);

-- GPS-Aufenthalte mit Reverse-Geocoding-Ergebnis
CREATE TABLE IF NOT EXISTS location_stays_geocoded (
    stay_id         INTEGER PRIMARY KEY REFERENCES location_stays(id),
    country         TEXT,
    country_iso     TEXT,
    state           TEXT,
    county          TEXT,
    city            TEXT,
    subregion       TEXT,       -- Zusammenfassung für Expositionsmatching
    climate_zone    TEXT,
    geocoded_at     TEXT NOT NULL
);

-- Kognitive Kurztests (täglich ~2 min)
CREATE TABLE IF NOT EXISTS cognitive_tests (
    ts           TEXT NOT NULL,
    date         TEXT NOT NULL,
    test_name    TEXT NOT NULL,  -- 'reaction_time','sdmt','spatial_memory','stroop','digit_span'
    score        REAL,
    reaction_ms  REAL,           -- Median-Reaktionszeit in ms
    errors       INTEGER,
    duration_s   INTEGER,
    percentile   REAL,           -- normative Percentile falls verfügbar
    session_type TEXT,           -- 'morning','afternoon','evening'
    device       TEXT,
    notes        TEXT,
    person       TEXT NOT NULL DEFAULT 'unknown',
    source       TEXT,
    PRIMARY KEY (ts, test_name, person)
);

-- Funktionale Kapazitätstests (6MWT, Sit-to-Stand, TUG)
CREATE TABLE IF NOT EXISTS functional_tests (
    ts          TEXT NOT NULL,
    date        TEXT NOT NULL,
    test_type   TEXT NOT NULL,  -- '6mwt','sst','tug','1mwt','2mwt'
    distance_m  REAL,           -- 6MWT: Gehstrecke in Meter
    hr_rest     REAL,           -- Ruhe-HR vor Test (bpm)
    hr_peak     REAL,           -- Peak-HR während Test (bpm)
    hr_recovery REAL,           -- HR nach 1 min Pause (bpm)
    spo2_pre    REAL,           -- SpO2 vor Test (%)
    spo2_post   REAL,           -- SpO2 nach Test (%)
    borg_pre    INTEGER,        -- Borg-RPE vor Test (6–20)
    borg_post   INTEGER,        -- Borg-RPE nach Test (6–20)
    duration_s  INTEGER,        -- Testdauer (6MWT = 360 s)
    stops       INTEGER,        -- Anzahl Pausen
    session_id  INTEGER,        -- optionaler Link zu sessions
    notes       TEXT,
    person      TEXT NOT NULL DEFAULT 'unknown',
    source      TEXT,
    PRIMARY KEY (ts, test_type, person)
);

-- MCAS / Histamin-Trigger-Tagebuch
CREATE TABLE IF NOT EXISTS food_triggers (
    ts            TEXT NOT NULL,
    date          TEXT NOT NULL,
    time_str      TEXT,
    food_name     TEXT NOT NULL,
    portion_g     REAL,
    histamine_cat TEXT,          -- 'high','medium','low','liberator','blocker'
    reaction_h    REAL,          -- Stunden bis Reaktion (NULL = keine)
    symptoms      TEXT,          -- kommaseparierte Symptome
    severity      INTEGER CHECK (severity BETWEEN 0 AND 4),
    meal_type     TEXT,          -- 'breakfast','lunch','dinner','snack'
    notes         TEXT,
    person        TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (ts, food_name, person)
);

-- Histamin-Lebensmitteldatenbank (Referenz)
CREATE TABLE IF NOT EXISTS histamine_food_db (
    name              TEXT PRIMARY KEY,
    histamine_cat     TEXT NOT NULL,  -- 'high','medium','low','liberator','blocker'
    histamine_mg_100g REAL,
    food_category     TEXT,           -- 'dairy','fish','meat','fermented','fruit','vegetable','other'
    notes             TEXT
);

-- Flüssigkeitsaufnahme (OI/POTS-Management)
CREATE TABLE IF NOT EXISTS fluid_intake (
    ts          TEXT NOT NULL,
    date        TEXT NOT NULL,
    time_str    TEXT,
    beverage    TEXT NOT NULL,   -- 'water','tea','coffee','juice','broth',etc.
    volume_ml   REAL NOT NULL,
    caffeine_mg REAL DEFAULT 0,
    alcohol_g   REAL DEFAULT 0,
    sodium_mg   REAL DEFAULT 0,
    notes       TEXT,
    person      TEXT NOT NULL DEFAULT 'unknown',
    source      TEXT,
    PRIMARY KEY (ts, beverage, person)
);

CREATE TABLE IF NOT EXISTS orthostatic_tests (
    datetime      TEXT NOT NULL,
    date          TEXT,
    hr_supine     REAL,
    hr_stand_peak REAL,
    hr_stand      REAL,
    hr_delta      REAL,
    rmssd_supine  REAL,
    rmssd_stand   REAL,
    rmssd_delta   REAL,
    n_supine      INTEGER,
    n_standing    INTEGER,
    data_source   TEXT,    -- 'ppi_raw' (RMSSD exakt) oder 'measurements' (RMSSD Näherung)
    device        TEXT,    -- HR-Sensor: H10, H7, apple_watch, ...
    source_app    TEXT,    -- Methode: guided_test, polar_flow, manual
    notes         TEXT,
    person        TEXT NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (datetime, person)
);
CREATE INDEX IF NOT EXISTS idx_orthostatic_tests_date ON orthostatic_tests(date, person);

CREATE TABLE IF NOT EXISTS personal_baseline (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    person       TEXT    NOT NULL,
    metric       TEXT    NOT NULL,
    value        REAL    NOT NULL,
    stddev       REAL,
    pct25        REAL,
    pct75        REAL,
    n_days       INTEGER NOT NULL,
    period_start TEXT    NOT NULL,
    period_end   TEXT    NOT NULL,
    method       TEXT    NOT NULL DEFAULT 'iqr_median',
    computed_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_personal_baseline_lookup
    ON personal_baseline(person, metric, computed_at);

-- -----------------------------------------------------------------------
-- Akute-Episoden-Score (compute_acute_events)
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS acute_events (
    date              TEXT NOT NULL,
    person            TEXT NOT NULL,
    score_total       INTEGER NOT NULL DEFAULT 0,
    severity          TEXT    NOT NULL DEFAULT 'none',
    score_hr          INTEGER DEFAULT 0,
    score_spo2        INTEGER DEFAULT 0,
    score_rr          INTEGER DEFAULT 0,
    score_temp        INTEGER DEFAULT 0,
    score_hrv         INTEGER DEFAULT 0,
    score_symptoms    INTEGER DEFAULT 0,
    hr_bpm            REAL,
    hrv_rmssd_ms      REAL,
    hrv_baseline_ms   REAL,
    spo2_pct          REAL,
    rr_rpm            REAL,
    temp_deviation_c  REAL,
    temp_abs_c        REAL,
    temp_method       TEXT,
    symptom_count     INTEGER DEFAULT 0,
    sources_used      TEXT,
    missing_domains   TEXT,
    notes             TEXT,
    computed_at       TEXT    NOT NULL,
    PRIMARY KEY (date, person)
);
CREATE INDEX IF NOT EXISTS idx_acute_events_date ON acute_events(date, person);
CREATE INDEX IF NOT EXISTS idx_acute_events_score ON acute_events(score_total, date, person);

-- -----------------------------------------------------------------------
-- Anamnese-Interviews
-- -----------------------------------------------------------------------
-- Sitzungs-Transkripte und Metadaten
CREATE TABLE IF NOT EXISTS anamnese_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    track           TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    last_updated_at TEXT NOT NULL,
    transcript_json TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'in_progress'
);
CREATE INDEX IF NOT EXISTS idx_anamnese_sessions_track ON anamnese_sessions(track);
CREATE INDEX IF NOT EXISTS idx_anamnese_sessions_status ON anamnese_sessions(status);

-- Strukturierte Befunde aus den Interviews
-- event_text ist die sensibelste Freitext-Spalte im gesamten Projekt
-- (unstrukturierte Familien-/Expositionsgeschichte, schwer zu pseudonymisieren
-- ohne den assoziativen Wert zu zerstören)
CREATE TABLE IF NOT EXISTS anamnese_findings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL,
    track           TEXT NOT NULL,
    date_or_period  TEXT,
    place_or_subject TEXT,
    event_text      TEXT NOT NULL,
    relevance_note  TEXT,
    person          TEXT NOT NULL,
    slug            TEXT,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES anamnese_sessions(id),
    FOREIGN KEY (person) REFERENCES persons(person_id)
);
CREATE INDEX IF NOT EXISTS idx_anamnese_findings_session ON anamnese_findings(session_id);
CREATE INDEX IF NOT EXISTS idx_anamnese_findings_track ON anamnese_findings(track);
CREATE INDEX IF NOT EXISTS idx_anamnese_findings_person ON anamnese_findings(person);

-- Promotion-Tracking: welche Befund/Ziel-Paare wurden bereits in die
-- bestehenden strukturierten JSON-Speicher promotet (Idempotenz, s.
-- add-anamnese-findings-promotion design.md Decision 5)
CREATE TABLE IF NOT EXISTS anamnese_promotions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id    INTEGER NOT NULL,
    target_type   TEXT NOT NULL,
    promoted_at   TEXT NOT NULL,
    FOREIGN KEY (finding_id) REFERENCES anamnese_findings(id),
    UNIQUE (finding_id, target_type)
);
CREATE INDEX IF NOT EXISTS idx_anamnese_promotions_finding ON anamnese_promotions(finding_id);

-- -----------------------------------------------------------------------
-- Genetik
-- -----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS genetic_variants (
    person       TEXT NOT NULL,
    rsid         TEXT NOT NULL,
    chrom        TEXT,
    pos          INTEGER,
    ref          TEXT,
    alt          TEXT,
    genotype     TEXT,
    zygosity     TEXT,
    source       TEXT NOT NULL,
    genome_build TEXT DEFAULT 'GRCh38',
    imported_at  TEXT NOT NULL,
    PRIMARY KEY (person, rsid, source)
);
CREATE INDEX IF NOT EXISTS idx_gv_rsid   ON genetic_variants(rsid);
CREATE INDEX IF NOT EXISTS idx_gv_person ON genetic_variants(person, source);
CREATE INDEX IF NOT EXISTS idx_gv_chrom  ON genetic_variants(chrom, pos);

CREATE TABLE IF NOT EXISTS genetic_risk_markers (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    person                TEXT NOT NULL,
    rsid                  TEXT,
    gene                  TEXT,
    variant_name          TEXT,
    category              TEXT,
    genotype              TEXT,
    risk_allele           TEXT,
    effect_size           TEXT,
    clinical_significance TEXT,
    phenotype             TEXT,
    pmid                  TEXT,
    clinvar_id            TEXT,
    source                TEXT NOT NULL,
    imported_at           TEXT NOT NULL,
    notes                 TEXT,
    UNIQUE (person, rsid, category)
);
CREATE INDEX IF NOT EXISTS idx_grm_person ON genetic_risk_markers(person);
CREATE INDEX IF NOT EXISTS idx_grm_gene   ON genetic_risk_markers(gene);
CREATE INDEX IF NOT EXISTS idx_grm_rsid   ON genetic_risk_markers(rsid);

-- Compat-Views für ältere Abfragen
CREATE VIEW IF NOT EXISTS polar_orthostatic AS
    SELECT datetime, hr_supine, hr_stand_peak AS hr_standup_min, hr_stand,
           rmssd_supine, rmssd_stand, hr_delta, rmssd_delta,
           data_source AS source, person, source_app
    FROM orthostatic_tests;

CREATE VIEW IF NOT EXISTS orthostatic_test AS
    SELECT date, hr_supine, hr_stand_peak, hr_stand, hr_delta,
           rmssd_supine, rmssd_stand, rmssd_delta,
           data_source AS source, person, source_app
    FROM orthostatic_tests;

-- ── Analyse-Views ──────────────────────────────────────────────────────────

CREATE VIEW IF NOT EXISTS context_with_symptoms AS
SELECT
    uc.date,
    uc.person,
    uc.source,
    uc.source_app,
    uc.tag,
    uc.note,
    uc.ts_start,
    uc.ts_end,
    GROUP_CONCAT(
        sc.symptom_de || CASE WHEN sc.value_num IS NOT NULL
            THEN ' (' || CAST(CAST(sc.value_num AS INTEGER) AS TEXT) || ')'
            ELSE '' END,
        ', '
    ) AS symptoms_same_day,
    GROUP_CONCAT(DISTINCT sc.category) AS symptom_categories
FROM user_context uc
LEFT JOIN symptoms_canonical sc
    ON sc.date = uc.date AND sc.person = uc.person
GROUP BY uc.id, uc.person;

CREATE VIEW IF NOT EXISTS symptoms_with_context AS
SELECT
    sc.date,
    sc.person,
    sc.symptom_de,
    sc.symptom_en,
    sc.category,
    sc.value_num,
    sc.source       AS symptom_source,
    GROUP_CONCAT(
        CASE
            WHEN uc.note IS NOT NULL AND uc.tag IS NOT NULL
                THEN '[' || uc.source || '/' || uc.tag || '] ' || uc.note
            WHEN uc.note IS NOT NULL
                THEN '[' || uc.source || '] ' || uc.note
            WHEN uc.tag IS NOT NULL
                THEN '[' || uc.source || '] ' || uc.tag
        END,
        ' | '
    ) AS context_notes
FROM symptoms_canonical sc
LEFT JOIN user_context uc
    ON uc.date = sc.date AND uc.person = sc.person
    AND (uc.note IS NOT NULL OR uc.tag IS NOT NULL)
GROUP BY sc.date, sc.symptom_de, sc.person, sc.source;

"""

# ---------------------------------------------------------------------------
# Seed-Daten — werden aus ~/.config/kyoro/health_config.json gelesen (device_registry,
# persons, source_priority). Diese Listen sind nur noch leere Fallbacks damit
# alter Code der sie importiert nicht bricht.
# ---------------------------------------------------------------------------

PERSONS = []
DEVICES = []
SOURCE_PRIORITY = []

# ---------------------------------------------------------------------------
# Oura-day → Kategorie
# ---------------------------------------------------------------------------

TAG_CATEGORY = {
    "tag_generic_period":              "reproductive",
    "tag_generic_emotionally_exhausted": "mental",
    "tag_generic_physically_exhausted":  "health",
    "tag_generic_overwhelmed":          "mental",
    "tag_generic_tired":                "health",
    "tag_generic_low_motivation":       "mental",
    "tag_generic_nausea":               "health",
    "tag_generic_diarrhea":             "health",
    "tag_generic_night_sweats":         "health",
    "tag_generic_train":                "activity",
    "tag_generic_car":                  "activity",
    "tag_generic_work":                 "activity",
    "tag_generic_sun":                  "environment",
    "tag_sleep_stress":                 "mental",
    "tag_sleep_late_coffee":            "lifestyle",
    "tag_sleep_latemeal":               "lifestyle",
    "tag_sleep_temp_high":              "environment",
    "custom":                           "oura_tag",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ts_to_date(ts: str) -> str:
    return ts[:10] if ts else None


def log(msg: str):
    print(f"  {msg}")


def _migrate_anamnese_findings_slug(conn: sqlite3.Connection) -> None:
    """Add slug to anamnese_findings on DBs created before this column existed."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='anamnese_findings'"
    ).fetchone()
    if not exists:
        return
    cols = {row[1] for row in conn.execute("PRAGMA table_info(anamnese_findings)")}
    if "slug" not in cols:
        conn.execute("ALTER TABLE anamnese_findings ADD COLUMN slug TEXT")
        conn.commit()


def _migrate_outbreak_events_columns(conn: sqlite3.Connection) -> None:
    """Add radius_km/note to outbreak_events on DBs created before these columns existed."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='outbreak_events'"
    ).fetchone()
    if not exists:
        return
    cols = {row[1] for row in conn.execute("PRAGMA table_info(outbreak_events)")}
    if "radius_km" not in cols:
        conn.execute("ALTER TABLE outbreak_events ADD COLUMN radius_km REAL")
        conn.commit()
    if "note" not in cols:
        conn.execute("ALTER TABLE outbreak_events ADD COLUMN note TEXT")
        conn.commit()
    if "since_date" not in cols:
        conn.execute("ALTER TABLE outbreak_events ADD COLUMN since_date TEXT")
        conn.commit()


def migrate_table(v1: sqlite3.Connection, v2: sqlite3.Connection,
                  src: str, dst: str, transform, desc: str):
    rows = v1.execute(f"SELECT * FROM {src}").fetchall()
    inserted = skipped = 0
    errors = []
    for row in rows:
        try:
            out = transform(row)
            if out is None:
                skipped += 1
                continue
            if isinstance(out, list):
                for r in out:
                    v2.execute(f"INSERT OR IGNORE INTO {dst} VALUES ({','.join('?'*len(r))})", r)
                    inserted += 1
            else:
                v2.execute(f"INSERT OR IGNORE INTO {dst} VALUES ({','.join('?'*len(out))})", out)
                inserted += 1
        except Exception as e:
            skipped += 1
            errors.append(str(e))
    log(f"{desc}: {inserted} migriert, {skipped} übersprungen")
    if errors:
        log(f"  FEHLER ({len(errors)}): {errors[:3]}")
    return inserted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if DB_V2.exists():
        try:
            conn_check = sqlite3.connect(DB_V2)
            ver = conn_check.execute(
                "SELECT version FROM schema_version WHERE version=?", (PHASE,)
            ).fetchone()
            if ver:
                _migrate_anamnese_findings_slug(conn_check)
                _migrate_outbreak_events_columns(conn_check)
                conn_check.close()
                print(t(f"Phase {PHASE} already abgeschlossen — nichts zu tun.", f"Phase {PHASE} already completed — nothing to do."))
                sys.exit(0)
            conn_check.close()
        except Exception:
            pass

    print(t(f"Erstelle {DB_V2} ...", f"Creating {DB_V2} ..."))
    v2 = sqlite3.connect(DB_V2)
    v2.execute("PRAGMA journal_mode=WAL")
    v2.execute("PRAGMA foreign_keys=ON")
    v2.executescript(SCHEMA)
    v2.commit()
    print(t("Schema created.", "Schema created."))

    _create_data_dirs()

    if not DB_V1.exists():
        print(t(f"WARNUNG: {DB_V1} nicht found — überspringe Datenmigration.", f"WARNING: {DB_V1} not found — skipping data migration."))
        _write_schema_version(v2)
        v2.close()
        return

    v1 = sqlite3.connect(DB_V1)
    print(f"\nVerbanden with {DB_V1}")

    # -------------------------------------------------------------------
    print("\n── Persons & Devices ──────────────────────────────────────────")
    # -------------------------------------------------------------------

    for p in PERSONS:
        v2.execute("INSERT OR IGNORE INTO persons VALUES (?,?,?,?,?,?)", p)
    log(f"persons: {len(PERSONS)} entries")

    for d in DEVICES:
        v2.execute("INSERT OR IGNORE INTO devices VALUES (?,?,?,?,?,?,?,?,?,?)", d)
    log(f"devices: {len(DEVICES)} Devicee")

    for sp in SOURCE_PRIORITY:
        v2.execute("INSERT OR IGNORE INTO source_priority VALUES (?,?,?,?,?)", sp)
    log(f"source_priority: {len(SOURCE_PRIORITY)} entries")

    v2.commit()

    # -------------------------------------------------------------------
    print("\n── Clinical Tables ─────────────────────────────────────────")
    # -------------------------------------------------------------------

    # blood_pressure (omron + oura)
    def bp_omron(r):
        # datetime, date, systolic, diastolic, pulse, ihb_flag, afib_possible,
        # truread, symptoms, movement, cuff_ok, device, notes, source
        return (r[0], r[1], r[2], r[3], r[4], r[5], r[6],
                r[7], r[8], r[9], r[10], "omron_bp", r[12], OWN_PERSON_ID, r[13])

    def bp_oura(r):
        # timestamp, systolic, diastolic, source
        return (r[0], ts_to_date(r[0]), r[1], r[2], None,
                None, None, None, None, None, None, None, None, OWN_PERSON_ID, r[3])

    migrate_table(v1, v2, "omron_blood_pressure", "blood_pressure", bp_omron,
                  "blood_pressure ← omron_blood_pressure")
    migrate_table(v1, v2, "oura_blood_pressure", "blood_pressure", bp_oura,
                  "blood_pressure ← oura_blood_pressure")

    # blood_glucose (beurer + oura)
    def bg_beurer(r):
        # datetime, date, glucose_mgdl, glucose_mmol, in_range, marker, hba1c, comment, source
        return (r[0], r[1], r[3], r[2], None, r[6], r[7], "beurer_gl60", OWN_PERSON_ID, r[8])

    def bg_oura(r):
        # timestamp, value (mmol), source
        return (r[0], ts_to_date(r[0]), r[1], None, None, None, None, None, OWN_PERSON_ID, r[2])

    migrate_table(v1, v2, "beurer_glucose", "blood_glucose", bg_beurer,
                  "blood_glucose ← beurer_glucose")
    migrate_table(v1, v2, "oura_blood_glucose", "blood_glucose", bg_oura,
                  "blood_glucose ← oura_blood_glucose")

    # body_composition (beurer_weight + fddb_weight)
    def bc_beurer(r):
        # datetime, date, weight_kg, bmi, body_fat_pct, water_pct, muscle_pct, bone_kg,
        # fat_arm_left, fat_arm_right, fat_leg_left, fat_leg_right, fat_trunk,
        # fat_visceral_pct, muscle_arm_left, muscle_arm_right, muscle_leg_left,
        # muscle_leg_right, muscle_trunk, metabolic_age, visceral_fat, pulse_bpm,
        # comment, source
        return (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7],
                r[8], r[9], r[10], r[11], r[12], r[13],
                r[14], r[15], r[16], r[17], r[18],
                r[19], r[20], r[21], r[22], "beurer_bf990", OWN_PERSON_ID, r[23])

    def bc_fddb(r):
        # date, gewicht_kg, koerperfett_pct, wasser_pct, taille_cm, huefte_cm, source
        ts = r[0] + "T12:00:00+00:00"
        return (ts, r[0], r[1], None, r[2], r[3], None, None,
                None, None, None, None, None, None,
                None, None, None, None, None,
                None, None, None, None, None, OWN_PERSON_ID, r[6])

    migrate_table(v1, v2, "beurer_weight", "body_composition", bc_beurer,
                  "body_composition ← beurer_weight")
    migrate_table(v1, v2, "fddb_weight", "body_composition", bc_fddb,
                  "body_composition ← fddb_weight")

    # body_temperature → measurements
    def bt_meas(r):
        # datetime, date, temp_celsius, comment, source
        return (r[0], r[1], "body_temperature", r[2], None, "°C",
                "beurer_ft95", OWN_PERSON_ID, r[4])

    migrate_table(v1, v2, "beurer_temperature", "measurements", bt_meas,
                  "measurements ← beurer_temperature (body_temperature)")

    # symptoms (symptomtagebuch)
    def symp_stb(r):
        # date, symptom, wert_num, wert_text, kategorie, source
        return (r[0], r[1], r[2], r[3], r[4], OWN_PERSON_ID, r[5])

    migrate_table(v1, v2, "symptomtagebuch", "symptoms", symp_stb,
                  "symptoms ← symptomtagebuch")

    # symptoms (womanlog_symptoms)
    def symp_wl(r):
        # date, symptom, source
        return (r[0], r[1], None, None, "womanlog", OWN_PERSON_ID, r[2])

    migrate_table(v1, v2, "womanlog_symptoms", "symptoms", symp_wl,
                  "symptoms ← womanlog_symptoms")

    # symptoms + reproductive_health (oura_tags)
    def oura_tag_symp(r):
        # id, start_day, start_time, end_day, end_time, tag_type_code, custom_tag_name, comment, source
        tag_type  = r[5] or ""
        tag_label = r[6] if r[6] else tag_type
        category  = TAG_CATEGORY.get(tag_type, "oura_tag")
        date      = r[1]
        comment   = r[7]
        rows = [(date, tag_label, None, comment, category, OWN_PERSON_ID, r[8])]
        if tag_type == "tag_generic_period":
            rows.append((date, "period_start", None, None, "reproductive", OWN_PERSON_ID, "oura"))
        return rows

    migrate_table(v1, v2, "oura_tags", "symptoms", oura_tag_symp,
                  "symptoms ← oura_tags")

    # reproductive_health
    def rh_wl_cycles(r):
        # date, duration_days, source
        rows = []
        rows.append((r[0], "period_start",  None,  None, OWN_PERSON_ID, r[2]))
        if r[1]:
            rows.append((r[0], "cycle_length", float(r[1]), None, OWN_PERSON_ID, r[2]))
        return rows

    def rh_wl_ovulation(r):
        # date, source
        return (r[0], "ovulation", None, None, OWN_PERSON_ID, r[1])

    def rh_oura_cycle(r):
        # day, day_of_cycle, cycle_phase, cycle_event, fertile_window, risk, reason, source
        rows = []
        if r[2]:
            rows.append((r[0], "cycle_phase",     None, r[2], OWN_PERSON_ID, r[7]))
        if r[4]:
            rows.append((r[0], "fertile_window",  None, r[4], OWN_PERSON_ID, r[7]))
        if r[3]:
            rows.append((r[0], "cycle_event",     None, r[3], OWN_PERSON_ID, r[7]))
        return rows if rows else None

    def rh_oura_period(r):
        # day, is_start, menstrual_flow, timestamp, median_cycle_length, number_of_cycles, source
        rows = []
        if r[1]:
            rows.append((r[0], "period_start", None, r[2], OWN_PERSON_ID, r[6]))
        if r[4]:
            rows.append((r[0], "cycle_length", float(r[4]), None, OWN_PERSON_ID, r[6]))
        return rows if rows else None

    def rh_oura_contraception(r):
        # id, method, method_start_date, method_end_date, timestamp, source
        return (r[2] or ts_to_date(r[4]), "contraception", None, r[1], OWN_PERSON_ID, r[5])

    def rh_oura_predictions(r):
        # cycle_period_start, day_updated, forecasting_method,
        # ovulation, predicted_ovulations, predicted_period_starts, source
        rows = []
        try:
            starts = json.loads(r[5]) if r[5] else []
            for d in starts:
                rows.append((d, "predicted_period_start", None, r[2], OWN_PERSON_ID, r[6]))
        except Exception:
            pass
        try:
            ovs = json.loads(r[4]) if r[4] else []
            for d in ovs:
                rows.append((d, "predicted_ovulation", None, r[2], OWN_PERSON_ID, r[6]))
        except Exception:
            pass
        return rows if rows else None

    migrate_table(v1, v2, "womanlog_cycles",      "reproductive_health", rh_wl_cycles,      "reproductive_health ← womanlog_cycles")
    migrate_table(v1, v2, "womanlog_ovulation",   "reproductive_health", rh_wl_ovulation,   "reproductive_health ← womanlog_ovulation")
    migrate_table(v1, v2, "oura_cycle_insights",  "reproductive_health", rh_oura_cycle,     "reproductive_health ← oura_cycle_insights")
    migrate_table(v1, v2, "oura_period_starts",   "reproductive_health", rh_oura_period,    "reproductive_health ← oura_period_starts")
    migrate_table(v1, v2, "oura_contraception",   "reproductive_health", rh_oura_contraception, "reproductive_health ← oura_contraception")
    migrate_table(v1, v2, "oura_cycle_predictions","reproductive_health",rh_oura_predictions,"reproductive_health ← oura_cycle_predictions")

    # oura_tags → reproductive_health (period tags)
    oura_tags = v1.execute("SELECT start_day, source FROM oura_tags WHERE tag_type_code='tag_generic_period'").fetchall()
    for row in oura_tags:
        v2.execute("INSERT OR IGNORE INTO reproductive_health VALUES (?,?,?,?,?,?)",
                   (row[0], "period_start", None, None, OWN_PERSON_ID, row[1]))
    log(f"reproductive_health ← oura_tags (period): {len(oura_tags)} entries")

    # medications
    def med_oura(r):
        # id, medication_id, timestamp, dose_value, dose_unit, is_skipped, route, source
        return (r[2], ts_to_date(r[2]), r[1], None, r[3], r[4], r[6], None, r[5], None, OWN_PERSON_ID, r[7])

    migrate_table(v1, v2, "oura_medications", "medications", med_oura,
                  "medications ← oura_medications")

    # lab_results
    def lab_oura(r):
        # id, test_type, timestamp, status, abnormal_result, observations_json, source
        return (r[0], r[1], r[2], ts_to_date(r[2]), r[3], r[4], r[5], OWN_PERSON_ID, r[6])

    migrate_table(v1, v2, "oura_lab_results", "lab_results", lab_oura,
                  "lab_results ← oura_lab_results")

    # assessments (migraene_hit6, migraene_midas, oura_survey)
    def assess_hit6(r):
        # datetime, date, score, source
        return (r[0], r[1], "HIT-6", float(r[2]) if r[2] else None, None, OWN_PERSON_ID, r[3])

    def assess_midas(r):
        return (r[0], r[1], "MIDAS", float(r[2]) if r[2] else None, None, OWN_PERSON_ID, r[3])

    def assess_oura_survey(r):
        # id, survey_id, timestamp, answers_json, version, source
        return (r[2], ts_to_date(r[2]), "oura_survey", None, r[3], OWN_PERSON_ID, r[5])

    migrate_table(v1, v2, "migraene_hit6",  "assessments", assess_hit6,       "assessments ← migraene_hit6")
    migrate_table(v1, v2, "migraene_midas", "assessments", assess_midas,      "assessments ← migraene_midas")
    migrate_table(v1, v2, "oura_survey",    "assessments", assess_oura_survey,"assessments ← oura_survey")

    # nutrition
    def nutr_daily(r):
        # date, kcal, fett_g, kh_g, protein_g, mahlzeiten, letzte_mahlzeit, source
        return (r[0], r[1], r[2], r[3], r[4], None, None, None, r[5], r[6], OWN_PERSON_ID, r[7])

    def nutr_entry(r):
        # datetime, date, time_str, bezeichnung, produkt_id, energie_kj,
        # fett_g, kh_g, protein_g, source
        return (r[0], r[1], r[2], None, r[3], r[4],
                r[5], r[6], r[7], r[8], None, None, None, None, OWN_PERSON_ID, r[9])

    migrate_table(v1, v2, "fddb_daily", "nutrition_daily",   nutr_daily, "nutrition_daily ← fddb_daily")
    migrate_table(v1, v2, "fddb_diary", "nutrition_entries", nutr_entry, "nutrition_entries ← fddb_diary")

    v2.commit()

    # -------------------------------------------------------------------
    print("\n── Kontext-Tables kopieren ───────────────────────────────────")
    # -------------------------------------------------------------------

    def copy_with_person(src_table, dst_table, extra_cols=""):
        rows = v1.execute(f"SELECT * FROM {src_table}").fetchall()
        if not rows:
            log(f"{dst_table}: leer")
            return
        placeholders = ",".join("?" * (len(rows[0]) + 1))
        for row in rows:
            v2.execute(f"INSERT OR IGNORE INTO {dst_table} VALUES ({placeholders})",
                       (*row, OWN_PERSON_ID))
        log(f"{dst_table}: {len(rows)} rows kopiert (+person=OWN_PERSON_ID)")

    copy_with_person("polar_sleep_hypnogram", "polar_sleep_hypnogram")
    copy_with_person("polar_sleep_wake",      "polar_sleep_wake")

    # kubios_hrv_resting: screenshot_path weglassen
    kub_rows = v1.execute(
        "SELECT datetime, hr_bpm, rmssd_ms, mean_rr_ms, sdnn_ms, sd1_ms, sd2_ms, "
        "stress_index, resp_rate, lf_power_ms2, hf_power_ms2, lf_nu, hf_nu, lf_hf_ratio, "
        "pns_index, sns_index, physiological_age, readiness_pct, source "
        "FROM kubios_hrv_resting"
    ).fetchall()
    for row in kub_rows:
        v2.execute("INSERT OR IGNORE INTO kubios_hrv_resting VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (*row, OWN_PERSON_ID))
    log(f"kubios_hrv_resting: {len(kub_rows)} rows (screenshot_path entfernt)")

    # oura_sleep_model
    osm_rows = v1.execute("SELECT * FROM oura_sleep_model").fetchall()
    for row in osm_rows:
        v2.execute("INSERT OR IGNORE INTO oura_sleep_model VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (*row, OWN_PERSON_ID))
    log(f"oura_sleep_model: {len(osm_rows)} rows kopiert")

    # Kontext-Tables 1:1
    for src in ("home_environment", "home_environment_ts", "home_presence",
                "weather_station", "weather_remote"):
        rows = v1.execute(f"SELECT * FROM {src}").fetchall()
        if rows:
            ph = ",".join("?" * len(rows[0]))
            for row in rows:
                v2.execute(f"INSERT OR IGNORE INTO {src} VALUES ({ph})", row)
        log(f"{src}: {len(rows)} rows kopiert")

    # location_history + location_stays (+ person)
    copy_with_person("location_history", "location_history")

    stays = v1.execute("SELECT * FROM location_stays").fetchall()
    for row in stays:
        # id, start_ts, end_ts, lat, lon, is_home, source → + timezone=NULL, person=OWN_PERSON_ID
        v2.execute("INSERT OR IGNORE INTO location_stays VALUES (?,?,?,?,?,?,?,?,?)",
                   (*row, None, OWN_PERSON_ID))
    log(f"location_stays: {len(stays)} rows kopiert (+timezone=NULL, person={OWN_PERSON_ID})")

    v2.commit()

    # -------------------------------------------------------------------
    _write_schema_version(v2)
    v1.close()
    v2.close()

    print(f"\n✓ Phase 1 abgeschlossen — {DB_V2}")


def _create_data_dirs():
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from health_config import Config
        cfg = Config()
    except Exception:
        return

    dirs = [
        cfg.data_root,
        cfg.manual_dir,
        cfg.polar_dir,
        cfg.apple_xml.parent,
        cfg.beurer_dir,
        cfg.omron_dir,
        cfg.migraine_dir,
        cfg.symptom_diary_dir,
        cfg.garmin_dir,
        cfg.data_root / "oura",
        cfg.data_root / "womanlog",
        cfg.data_root / "sleep_cycle",
        cfg.data_root / "fddb",
        cfg.analyses_dir,
        cfg.db_path.parent,
        Path(__file__).parents[2] / "medicine",
        Path(__file__).parents[2] / "medicine" / "krankenakte",
        Path(__file__).parents[2] / "medicine" / "laborbefunde",
        Path(__file__).parents[2] / "medicine" / "arztbriefe",
    ]
    print("\n── Verzeichnisse anlegen ────────────────────────────────────────")
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  {d}")
    print(t("Verzeichnisse bereit.", "Directories ready."))


def _write_schema_version(v2: sqlite3.Connection):
    print("\n── Abschluss ───────────────────────────────────────────────────")
    v2.execute("INSERT OR IGNORE INTO schema_version VALUES (?,?,?)",
               (PHASE, NOW, PHASE_DESC))
    v2.execute("INSERT INTO import_log (ts_run, source, rows_inserted) VALUES (?,?,?)",
               (NOW, "create_schema", 1))
    v2.commit()
    log(f"schema_version {PHASE} geschrieben")


if __name__ == "__main__":
    main()
