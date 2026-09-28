#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Oura Ring API → health.db

@tier        infrastructure
@purpose.de  Importiert Daten vom Oura Ring 4 über die offizielle API in die health.db.
             Unterstützt Schlaf, Schlafbereitschaft, Aktivität, SpO2, HRV, Stress,
             kardiovaskuläre Metriken, kontinuierliche Herzfrequenz, Workouts
             (inkl. automatisch erkannter Alltagsaktivität wie 'houseWork') und
             Nutzer-Tags (Symptome/Kontext).
@purpose.en  Imports data from Oura Ring 4 via the official API into health.db.
             Supports sleep, sleep readiness, activity, SpO2, HRV, stress,
             cardiovascular metrics, continuous heart rate, workouts (incl.
             auto-detected everyday activity like 'houseWork'), and user tags
             (symptoms/context).
@method.de   Ruft Daten von der Oura Cloud API ab. daily_sleep → sessions +
             session_metrics, sleep → sessions (korrigierte Zeistempel) + measurements
             (HRV RMSSD Zeitreihe), andere daily-* Daten → measurements. Workout/
             enhanced_tag → oura_workouts/oura_tags/user_context — gleiche
             Zieltabellen wie import_oura_csv.py (GDPR-Export), INSERT OR IGNORE
             dedupliziert zwischen beiden Importpfaden.
             HRV-Zeitreihen werden als metric='hrv_rmssd' gespeichert.
@method.en   Fetches data from the Oura Cloud API. daily_sleep → sessions +
             session_metrics, sleep → sessions (corrected timestamps) + measurements
             (HRV RMSSD time series), other daily-* data → measurements. Workout/
             enhanced_tag → oura_workouts/oura_tags/user_context — same target
             tables as import_oura_csv.py (GDPR export), INSERT OR IGNORE
             deduplicates between both import paths.
             HRV time series are stored as metric='hrv_rmssd'.
@reads       Oura Cloud API (https://cloud.ouraring.com)
@writes      health.db (sessions, session_metrics, measurements, oura_workouts,
             oura_tags, user_context)
@limits.de   Abhängig von der Verfügbarkeit der Oura API und der Qualität der
             zurückgegebenen Daten. Keine medizinische Interpretation.

@relevance.de  Ermöglicht den Import von Schlaf- und Erholungsdaten aus Oura-Ringen, essentiell für die Schlafanalyse
@relevance.en  Enables import of sleep and recovery data from Oura rings, essential for sleep analysis
@limits.en   Dependent on the availability of the Oura API and the quality of
             returned data. No medical interpretation.
@usage
    python import_oura.py --setup
    python import_oura.py             # Vollimport (ab 2024-01-01)
    python import_oura.py --update    # Nur neue Daten
    python import_oura.py --from 2024-06-01 --to 2024-12-31
    python import_oura.py --no-hr     # Ohne kontinuierliche HR
"""

import json
import re
from datetime import datetime, timedelta, date
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID, KYORO_CONFIG_DIR
from modules.db import open_db
_cfg = _Cfg()

import argparse
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import log_import

try:
    import requests
except ImportError:
    print(t("requests fehlen: pip3 install requests", "requests missing: pip3 install requests"))
    _sys.exit(1)

DB_PATH     = _cfg.db_path
CONFIG_PATH = KYORO_CONFIG_DIR / "oura_config.json"
API_BASE    = "https://api.ouraring.com/v2/usercollection"
_OURA_DEV   = _cfg.oura_device_id


def _norm_ts(ts: str) -> str:
    """Normalisiert Oura-API-Timestamps: Z→+00:00, sub-Sekunden entfernen.
    '2026-05-26T00:01:35.000+00:00' → '2026-05-26T00:01:35+00:00'
    '2026-05-26T00:01:35Z'          → '2026-05-26T00:01:35+00:00'
    """
    ts = ts.replace("Z", "+00:00")
    return re.sub(r"\.\d+([+-])", r"\1", ts)


def _dedup_oura_hr(conn) -> int:
    """Bereinigt bestehende Duplikate in measurements (Oura heart_rate).
    Ursache: API lieferte teils '...T00:00:35.000+00:00', teils '...T00:00:35+00:00' —
    beides gilt als unterschiedlicher PRIMARY KEY und wurde separat gespeichert.
    Strategie: .000-Version löschen wenn normalisierte Version existiert,
    sonst .000-Version auf normalisierten Timestamp aktualisieren.
    Gibt Anzahl bereinigter Zeilen zurück.
    """
    cur = conn.cursor()

    # Alle .000-Timestamps für Oura HR laden
    dot_rows = cur.execute("""
        SELECT ts, value, person FROM measurements
        WHERE metric='heart_rate' AND device_id=?
          AND ts LIKE '%.000+%'
    """, (_OURA_DEV,)).fetchall()

    deleted = 0
    updated = 0
    for ts_dot, value, person in dot_rows:
        ts_norm = re.sub(r"\.\d+([+-])", r"\1", ts_dot)
        exists = cur.execute("""
            SELECT 1 FROM measurements
            WHERE ts=? AND metric='heart_rate' AND device_id=? AND person=?
        """, (ts_norm, _OURA_DEV, person)).fetchone()
        if exists:
            cur.execute("""
                DELETE FROM measurements
                WHERE ts=? AND metric='heart_rate' AND device_id=? AND person=?
            """, (ts_dot, _OURA_DEV, person))
            deleted += 1
        else:
            cur.execute("""
                UPDATE measurements SET ts=?
                WHERE ts=? AND metric='heart_rate' AND device_id=? AND person=?
            """, (ts_norm, ts_dot, _OURA_DEV, person))
            updated += 1

    conn.commit()
    return deleted + updated


def setup_config():
    print(t("=== Oura Ring Konfiguration ===\n", "=== Oura Ring Configuration ===\n"))
    print("Token: https://cloud.ouraring.com/personal-access-tokens\n")
    token = input(t("Personal Access Token: ", "Personal Access Token: ")).strip()
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"token": token}, indent=2))
    CONFIG_PATH.chmod(0o600)
    print(t(f"\nGespeichert: {CONFIG_PATH}", f"\nSaved: {CONFIG_PATH}"))


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(t(f"Keine Konfiguration: {CONFIG_PATH}\nBitte --setup ausführen.", f"No configuration: {CONFIG_PATH}\nPlease run --setup."))
        _sys.exit(1)
    return json.loads(CONFIG_PATH.read_text())


def oura_get(token: str, endpoint: str, params: dict) -> list:
    headers  = {"Authorization": f"Bearer {token}"}
    all_data = []
    url      = f"{API_BASE}/{endpoint}"
    while True:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        body = r.json()
        all_data.extend(body.get("data", []))
        # next_token ist ein opaker Cursor-String, kein URL
        next_token = body.get("next_token")
        if not next_token:
            break
        params = {"next_token": next_token}
    return all_data


def _metrics(cursor, session_id: str, pairs: list) -> None:
    for metric, value, value_text, unit in pairs:
        if value is None and value_text is None:
            continue
        cursor.execute(
            "INSERT OR IGNORE INTO session_metrics(session_id, metric, value, value_text, unit) "
            "VALUES (?,?,?,?,?)",
            (session_id, metric, value, value_text, unit)
        )


def import_sleep(conn, token, start, end) -> int:
    data = oura_get(token, "daily_sleep", {"start_date": start, "end_date": end})
    cur = conn.cursor()
    n = 0
    for d in data:
        c   = d.get("contributors", {})
        day = d.get("day")
        if not day:
            continue
        sid      = f"oura_sleep_{day}"
        ts_start = f"{day}T00:00:00+00:00"

        cur.execute(
            "INSERT OR IGNORE INTO sessions"
            "(id, type, ts_start, ts_end, date, device_id, person, source_app) "
            "VALUES (?, 'sleep', ?, NULL, ?, ?, ?, 'oura_app')",
            (sid, ts_start, day, _OURA_DEV, OWN_PERSON_ID)
        )
        _metrics(cur, sid, [
            ("sleep_score",         d.get("score"),                    None, None),
            ("total_sleep_s",       d.get("total_sleep_duration"),     None, "s"),
            ("rem_s",               d.get("rem_sleep_duration"),       None, "s"),
            ("deep_s",              d.get("deep_sleep_duration"),      None, "s"),
            ("light_s",             d.get("light_sleep_duration"),     None, "s"),
            ("awake_s",             d.get("awake_time"),               None, "s"),
            ("sleep_efficiency_pct", d.get("sleep_efficiency"),        None, "%"),
            ("latency_s",           d.get("sleep_latency"),            None, "s"),
            ("restfulness",         c.get("restfulness"),              None, None),
            ("hr_lowest",           d.get("lowest_heart_rate"),        None, "bpm"),
            ("hr_avg",              d.get("average_heart_rate"),       None, "bpm"),
            ("hrv_avg_ms",          d.get("average_hrv"),              None, "ms"),
            ("hrv_rmssd_ms",        d.get("average_hrv"),              None, "ms"),
            ("respiration_avg",     d.get("average_breath"),           None, "rpm"),
            ("temp_deviation",      d.get("temperature_deviation"),    None, "°C"),
            ("temp_trend_dev",      d.get("temperature_trend_deviation"), None, "°C"),
        ])
        n += 1
    conn.commit()
    return n


def _meas_rows(date: str, metric: str, value, unit: str | None) -> tuple | None:
    if value is None:
        return None
    ts = f"{date}T00:00:00+00:00"
    return (ts, date, metric, float(value), None, unit, _OURA_DEV, OWN_PERSON_ID, 'oura_app')


def import_readiness(conn, token, start, end) -> int:
    data = oura_get(token, "daily_readiness", {"start_date": start, "end_date": end})
    rows = []
    for d in data:
        c = d.get("contributors", {})
        day = d.get("day")
        if not day:
            continue
        for metric, val, unit in [
            ('readiness_score',        d.get('score'),                None),
            ('readiness_hrv_balance',  c.get('hrv_balance'),         None),
            # contributors.* sind 0-100-Skalen-Scores ("wie gut relativ zur
            # eigenen Baseline"), keine Rohwerte -- war zuvor faelschlich mit
            # Einheit 'bpm' als readiness_hr_resting importiert. Die echte
            # naechtliche Ruhe-HF liegt bereits korrekt unter hr_lowest
            # (s. import_sleep(), lowest_heart_rate).
            ('readiness_contrib_resting_hr', c.get('resting_heart_rate'), None),
            ('readiness_recovery_idx', c.get('recovery_index'),      None),
            ('readiness_body_temp',    c.get('body_temperature'),    '°C'),
        ]:
            r = _meas_rows(day, metric, val, unit)
            if r: rows.append(r)
    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO measurements"
            "(ts, date, metric, value, value_text, unit, device_id, person, source_app) "
            "VALUES (?,?,?,?,?,?,?,?,?)", rows)
        conn.commit()
    return len(data)


def import_activity(conn, token, start, end) -> int:
    data = oura_get(token, "daily_activity", {"start_date": start, "end_date": end})
    rows = []
    for d in data:
        day = d.get("day")
        if not day:
            continue
        for metric, val, unit in [
            ('activity_score',   d.get('score'),                        None),
            ('steps',            d.get('steps'),                        'steps'),
            ('active_calories',  d.get('active_calories'),              'kcal'),
            ('total_calories',   d.get('total_calories'),               'kcal'),
            ('distance_walking', d.get('equivalent_walking_distance'),  'm'),
            ('active_time_high', d.get('high_activity_time'),           's'),
            ('active_time_mid',  d.get('medium_activity_time'),         's'),
            ('active_time_low',  d.get('low_activity_time'),            's'),
            ('sedentary_time',   d.get('sedentary_time'),               's'),
            ('resting_time',     d.get('resting_time'),                 's'),
            ('met_avg',          d.get('average_met'),                  'MET'),
        ]:
            r = _meas_rows(day, metric, val, unit)
            if r: rows.append(r)
    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO measurements"
            "(ts, date, metric, value, value_text, unit, device_id, person, source_app) "
            "VALUES (?,?,?,?,?,?,?,?,?)", rows)
        conn.commit()
    return len(data)


def import_spo2(conn, token, start, end) -> int:
    data = oura_get(token, "daily_spo2", {"start_date": start, "end_date": end})
    rows = []
    for d in data:
        day = d.get("day")
        pct = d.get("spo2_percentage", {})
        if not day:
            continue
        for metric, val, unit in [
            ('spo2',     pct.get('average'), '%'),
            ('spo2_min', pct.get('min'),     '%'),
            ('spo2_max', pct.get('max'),     '%'),
        ]:
            r = _meas_rows(day, metric, val, unit)
            if r: rows.append(r)
    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO measurements"
            "(ts, date, metric, value, value_text, unit, device_id, person, source_app) "
            "VALUES (?,?,?,?,?,?,?,?,?)", rows)
        conn.commit()
    return len(data)


def import_sleep_sessions(conn, token, start, end) -> tuple[int, int]:
    """Granulare Schlaf-Sessions: korrigiert ts_start/ts_end + extrahiert HRV-Zeitreihe.

    Schreibt 5-min-RMSSD-Werte als metric='hrv_rmssd' in measurements — analog
    zu Polar-HRV, damit compute_af_evidence.py einheitlich darauf zugreifen kann.
    Gibt (n_sessions, n_hrv_rows) zurück.
    """
    data = oura_get(token, "sleep", {"start_date": start, "end_date": end})
    hrv_rows: list[tuple] = []
    cur = conn.cursor()

    for s in data:
        day           = s.get("day")
        bedtime_start = s.get("bedtime_start")
        bedtime_end   = s.get("bedtime_end")
        if not day or not bedtime_start:
            continue

        sid = f"oura_sleep_{day}"

        # Echtere Schlaf-Timestamps in bestehende Session schreiben
        cur.execute(
            "UPDATE sessions SET ts_start = ?, ts_end = ? WHERE id = ?",
            (bedtime_start, bedtime_end, sid),
        )

        # Schlafphasen aus granularer Sleep-Session (INSERT OR IGNORE: daily_sleep hat Vorrang)
        # /sleep-Endpoint liefert efficiency + onset_latency statt sleep_efficiency/sleep_latency
        # hr_lowest/hr_avg/respiration_avg hier ergaenzt: daily_sleep liefert diese
        # Rohwerte seit der Oura-Schema-Aenderung nicht mehr, /sleep aber weiterhin.
        _metrics(cur, sid, [
            ("rem_s",                s.get("rem_sleep_duration"),   None, "s"),
            ("deep_s",               s.get("deep_sleep_duration"),  None, "s"),
            ("light_s",              s.get("light_sleep_duration"), None, "s"),
            ("awake_s",              s.get("awake_time"),           None, "s"),
            ("sleep_efficiency_pct", s.get("efficiency"),           None, "%"),
            ("latency_s",            s.get("onset_latency"),        None, "s"),
            ("total_sleep_s",        s.get("total_sleep_duration"), None, "s"),
            ("hr_lowest",            s.get("lowest_heart_rate"),    None, "bpm"),
            ("hr_avg",               s.get("average_heart_rate"),   None, "bpm"),
            ("hrv_avg_ms",           s.get("average_hrv"),          None, "ms"),
            ("respiration_avg",      s.get("average_breath"),       None, "rpm"),
        ])

        try:
            t0 = datetime.fromisoformat(bedtime_start.replace("Z", "+00:00"))
        except ValueError:
            continue

        # HRV-Zeitreihe (5-min RMSSD-Intervalle während Schlaf)
        hrv_data  = s.get("hrv") or {}
        for i, val in enumerate(hrv_data.get("items") or []):
            if val is None:
                continue
            ts_dt = t0 + timedelta(seconds=i * int(hrv_data.get("interval", 300)))
            ts_str = ts_dt.isoformat()
            hrv_rows.append((
                ts_str, ts_str[:10],
                "hrv_rmssd", float(val), None, "ms",
                _OURA_DEV, OWN_PERSON_ID, "oura_app",
            ))

        # HR-Zeitreihe (5-min Herzrate-Intervalle während Schlaf)
        hr_data = s.get("heart_rate") or {}
        for i, val in enumerate(hr_data.get("items") or []):
            if val is None:
                continue
            ts_dt = t0 + timedelta(seconds=i * int(hr_data.get("interval", 300)))
            ts_str = ts_dt.isoformat()
            hrv_rows.append((
                ts_str, ts_str[:10],
                "oura_sleep_hr", float(val), None, "bpm",
                _OURA_DEV, OWN_PERSON_ID, "oura_app",
            ))

    if hrv_rows:
        conn.executemany(
            "INSERT OR IGNORE INTO measurements"
            "(ts, date, metric, value, value_text, unit, device_id, person, source_app) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            hrv_rows,
        )
    conn.commit()
    return len(data), len(hrv_rows)



def import_daily_stress(conn, token, start, end) -> int:
    """Tägliche Stress/Recovery-Daten von /v2/usercollection/daily_stress → measurements."""
    data = oura_get(token, "daily_stress", {"start_date": start, "end_date": end})
    rows = []
    for d in data:
        day = d.get("day")
        if not day:
            continue
        ts = f"{day}T00:00:00+00:00"
        for metric, val, unit in [
            ("stress_high_min",    d.get("stress_high"),    "min"),
            ("recovery_high_min",  d.get("recovery_high"),  "min"),
            ("day_summary",        None,                    None),
        ]:
            if metric == "day_summary":
                summary = d.get("day_summary")
                if summary:
                    rows.append((ts, day, "stress_day_summary", None, summary, None,
                                 _OURA_DEV, OWN_PERSON_ID, "oura_app"))
            elif val is not None:
                rows.append((ts, day, metric, float(val), None, unit, _OURA_DEV, OWN_PERSON_ID, "oura_app"))
    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO measurements"
            "(ts, date, metric, value, value_text, unit, device_id, person, source_app) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
    return len(data)


def import_heartrate(conn, token, start_dt: str, end_dt: str) -> int:
    total = 0
    cur   = datetime.strptime(start_dt, "%Y-%m-%d")
    end   = datetime.strptime(end_dt,   "%Y-%m-%d")
    while cur <= end:
        block_end = min(cur + timedelta(days=29), end)
        try:
            data = oura_get(token, "heartrate", {
                "start_datetime": f"{cur.strftime('%Y-%m-%d')}T00:00:00+00:00",
                "end_datetime":   f"{block_end.strftime('%Y-%m-%d')}T23:59:59+00:00",
            })
            rows = []
            for d in data:
                bpm = d.get("bpm")
                ts  = d.get("timestamp", "")
                if not bpm or not ts:
                    continue
                ts_utc = _norm_ts(ts)
                date_s = ts_utc[:10]
                rows.append((ts_utc, date_s, 'heart_rate', float(bpm), None, 'bpm', _OURA_DEV, OWN_PERSON_ID, 'oura_app'))
            if rows:
                conn.executemany(
                    "INSERT OR IGNORE INTO measurements"
                    "(ts, date, metric, value, value_text, unit, device_id, person, source_app) "
                    "VALUES (?,?,?,?,?,?,?,?,?)", rows)
                conn.commit()
                total += len(rows)
        except Exception as e:
            print(t(f"\n    Block {cur.date()}–{block_end.date()}: {e}",
                    f"\n    Block {cur.date()}–{block_end.date()}: {e}"), end="")
        cur = block_end + timedelta(days=1)
    return total


def import_cardiovascular_age(conn, token, start, end) -> int:
    """Pulse Wave Velocity + vaskuläres Alter aus /v2/usercollection/daily_cardiovascular_age.

    PWV (m/s): Maß für arterielle Gefäßsteifigkeit — erhöhte Werte deuten auf
    Arteriosklerose hin. Klinischer Referenzwert für 40-Jährige: ~7–8 m/s.
    Vaskuläres Alter: vom Oura-Algorithmus geschätztes "Gefäßalter" in Jahren.

    Ref: Laurent et al. 2006, doi:10.1093/eurheartj/ehl088
    """
    data = oura_get(token, "daily_cardiovascular_age",
                    {"start_date": start, "end_date": end})
    rows = []
    for d in data:
        day = d.get("day")
        if not day:
            continue
        ts = f"{day}T00:00:00+00:00"
        pwv = d.get("pulse_wave_velocity")
        vage = d.get("vascular_age")
        if pwv is not None:
            rows.append((ts, day, "pulse_wave_velocity", float(pwv), None, "m/s",
                         _OURA_DEV, OWN_PERSON_ID, "oura_app"))
        if vage is not None:
            rows.append((ts, day, "vascular_age", float(vage), None, "years",
                         _OURA_DEV, OWN_PERSON_ID, "oura_app"))
    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO measurements"
            "(ts, date, metric, value, value_text, unit, device_id, person, source_app) "
            "VALUES (?,?,?,?,?,?,?,?,?)", rows)
        conn.commit()
    return len(data)


def _setup_workout_tag_tables(conn) -> None:
    """Legt oura_workouts/oura_tags an, falls die API läuft ohne dass zuvor
    der GDPR-CSV-Importer (import_oura_csv.py) lief — user_context existiert
    bereits über utils/create_schema.py, hier nur die Oura-spezifischen
    Zusatztabellen.

    Ein Stub-View gleichen Namens (utils/compat_views.py) wird vorher entfernt:
    Tabellen und Views teilen sich in SQLite einen Namensraum, CREATE TABLE IF
    NOT EXISTS bliebe sonst still wirkungslos und jeder INSERT liefe gegen den
    View. Gleiches Vorgehen wie import_oura_csv.setup_db()."""
    for tbl in ("oura_workouts", "oura_tags"):
        row = conn.execute("SELECT type FROM sqlite_master WHERE name=?", (tbl,)).fetchone()
        if row and row[0] == "view":
            conn.execute(f"DROP VIEW {tbl}")
    conn.executescript("""
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
        source                  TEXT DEFAULT 'oura_api'
    );
    CREATE TABLE IF NOT EXISTS oura_tags (
        id                      TEXT PRIMARY KEY,
        start_day               TEXT,
        start_time              TEXT,
        end_day                 TEXT,
        end_time                TEXT,
        tag_type_code           TEXT,
        custom_tag_name         TEXT,
        comment                 TEXT,
        source                  TEXT DEFAULT 'oura_api'
    );
    CREATE INDEX IF NOT EXISTS idx_oura_tags_day ON oura_tags(start_day);
    """)
    conn.commit()


def import_workouts_api(conn, token, start, end) -> int:
    """Automatisch erkannte + manuell geloggte Workouts (u.a. 'houseWork',
    'walking') über /v2/usercollection/workout. Gleiche Zieltabelle wie
    import_oura_csv.py::import_workouts() — INSERT OR IGNORE dedupliziert
    zwischen API- und GDPR-Export-Pfad."""
    data = oura_get(token, "workout", {"start_date": start, "end_date": end})
    n = 0
    for r in data:
        conn.execute("""
            INSERT OR IGNORE INTO oura_workouts
            (id, day, activity, start_datetime, end_datetime,
             calories, distance, intensity, source_app)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            r.get("id"), r.get("day"), r.get("activity"),
            r.get("start_datetime"), r.get("end_datetime"),
            r.get("calories"), r.get("distance"),
            r.get("intensity") or None, r.get("source") or None,
        ))
        n += 1
    conn.commit()
    return n


def import_enhanced_tags(conn, token, start, end) -> int:
    """Nutzer-Tags (Symptome, Kontext, Freitext) über
    /v2/usercollection/enhanced_tag. Schreibt in oura_tags (gleiche
    Zieltabelle wie CSV-Pfad) UND in user_context (generisches
    Kontext-Log, s. utils/create_schema.py) für skriptübergreifende Nutzung."""
    data = oura_get(token, "enhanced_tag", {"start_date": start, "end_date": end})
    n = 0
    for r in data:
        tag_id = r.get("id")
        if not tag_id:
            continue
        conn.execute("""
            INSERT OR IGNORE INTO oura_tags
            (id, start_day, start_time, end_day, end_time,
             tag_type_code, custom_tag_name, comment)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            tag_id, r.get("start_day"), r.get("start_time") or None,
            r.get("end_day") or None, r.get("end_time") or None,
            r.get("tag_type_code") or None, r.get("custom_name") or None,
            r.get("comment") or None,
        ))
        tag    = r.get("custom_name") or r.get("tag_type_code") or None
        sd, st = r.get("start_day"), r.get("start_time") or None
        ed, et = r.get("end_day") or None, r.get("end_time") or None
        ts_start = f"{sd}T{st}" if sd and st else None
        ts_end   = f"{ed}T{et}" if ed and et else None
        conn.execute("""
            INSERT OR IGNORE INTO user_context
            (id, date, ts_start, ts_end, person, source, source_app, tag, note)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (
            tag_id, sd, ts_start, ts_end,
            OWN_PERSON_ID, "oura_api", "oura_app", tag, r.get("comment") or None,
        ))
        n += 1
    conn.commit()
    return n


def get_last_import(conn) -> str | None:
    # Nicht auf sessions.date verlassen: import_sleep() legt fuer JEDEN Tag
    # eine Session-Zeile an, auch wenn Oura's daily_sleep-Endpoint (seit der
    # Schema-Aenderung ~Sept 2026, nur noch Scores statt Rohwerte) keine
    # echten HRV-/Schlafdaten mehr liefert -- der Tag wuerde dann faelschlich
    # als "erledigt" gelten, bevor import_sleep_sessions() (die den
    # tatsaechlichen HRV-Nachschub vom sleep-Endpoint holt) ihn je verarbeitet
    # hat, weil beide Funktionen dasselbe start/end-Fenster teilen. Stattdessen
    # den tatsaechlichen HRV-Datenstand selbst pruefen.
    r = conn.execute(
        "SELECT MAX(date) FROM measurements WHERE metric='hrv_rmssd' AND source_app='oura_app'"
    ).fetchone()
    return r[0] if r and r[0] else None


def main():
    """
    Hauptfunktion: Koordiniert den Import der Oura Ring API-Daten.

    Command-Line-Argumente:
        --setup: Token einrichten
        --update: Nur neue Daten
        --from: Startdatum (YYYY-MM-DD)
        --to: Enddatum (YYYY-MM-DD)
        --no-hr: Kontinuierliche HR-Daten nicht importieren
    """
    parser = argparse.ArgumentParser(description=t("Oura Ring 4 → health.db", "Oura Ring 4 → health.db"))
    parser.add_argument("--setup",  action="store_true", help="Token einrichten")
    parser.add_argument("--update", action="store_true", help="Nur neue Daten")
    parser.add_argument("--from",   dest="date_from", default=None)
    parser.add_argument("--to",     dest="date_to",   default=None)
    parser.add_argument("--no-hr",  action="store_true",
                        help="Kontinuierliche HR-Daten NICHT importieren")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    if args.setup:
        setup_config(); return

    config = load_config()
    token  = config["token"]

    print(t("Verbinde mit Oura API ...", "Connecting to Oura API ..."))
    try:
        r = requests.get("https://api.ouraring.com/v2/usercollection/personal_info",
                        headers={"Authorization": f"Bearer {token}"}, timeout=10)
        r.raise_for_status()
        print(t("  Verbunden: Oura-Konto", "  Connected: Oura account"))
    except Exception as e:
        print(t(f"Verbindungsfehler: {e}", f"Connection error: {e}")); return

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _setup_workout_tag_tables(conn)

    n_dedup = _dedup_oura_hr(conn)
    if n_dedup:
        print(t(f"  Duplikate bereinigt: {n_dedup} Oura-HR-Einträge normalisiert",
                f"  Duplicates cleaned: {n_dedup} Oura HR entries normalised"))

    if args.update:
        last  = get_last_import(conn)
        start = (datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)
                ).strftime("%Y-%m-%d") if last else (_cfg.data_start or "2000-01-01")
        print(t(f"Update-Modus: ab {start}", f"Update mode: from {start}"))
    else:
        start = args.date_from or _cfg.data_start or "2000-01-01"

    end = args.date_to or date.today().strftime("%Y-%m-%d")

    if start > end:
        print(t("Daten bereits aktuell — nichts zu importieren.", "Data already up to date — nothing to import."))
        conn.close()
        return

    print(t(f"Zeitraum: {start} → {end}\n", f"Period: {start} → {end}\n"))

    failed_steps: list[str] = []

    for label, fn in [
        (t("Schlaf täglich (HRV, Phasen, Temperatur)", "Sleep daily (HRV, phases, temperature)"), import_sleep),
        (t("Readiness Score",                          "Readiness Score"),                         import_readiness),
        (t("Aktivität (Schritte, MET)",                "Activity (steps, MET)"),                   import_activity),
        ("SpO2",                                                                                    import_spo2),
        (t("Stress/Recovery täglich",                  "Stress/Recovery daily"),                   import_daily_stress),
        (t("Pulse Wave Velocity / Vaskuläres Alter",   "Pulse Wave Velocity / Vascular Age"),      import_cardiovascular_age),
        (t("Workouts (u.a. houseWork, walking)",       "Workouts (incl. houseWork, walking)"),     import_workouts_api),
        (t("Nutzer-Tags (Symptome, Kontext)",          "User tags (symptoms, context)"),           import_enhanced_tags),
    ]:
        print(f"  {label} ...", end=" ", flush=True)
        try:
            n = fn(conn, token, start, end)
            print(t(f"{n} Tage", f"{n} days"))
        except Exception as e:
            print(t(f"Fehler: {e}", f"Error: {e}"))
            failed_steps.append(label)

    print(t("  Schlaf-Sessions (HRV-Zeitreihe) ...", "  Sleep sessions (HRV time series) ..."), end=" ", flush=True)
    try:
        n_sess, n_hrv = import_sleep_sessions(conn, token, start, end)
        print(t(f"{n_sess} Sessions, {n_hrv:,} HRV-Punkte", f"{n_sess} sessions, {n_hrv:,} HRV points"))
    except Exception as e:
        print(t(f"Fehler: {e}", f"Error: {e}"))
        failed_steps.append(t("Schlaf-Sessions (HRV-Zeitreihe)", "Sleep sessions (HRV time series)"))

    if not args.no_hr:
        print(t("  Kontinuierliche HR ...", "  Continuous HR ..."), end=" ", flush=True)
        try:
            n = import_heartrate(conn, token, start, end)
            print(t(f"{n:,} Messwerte", f"{n:,} measurements"))
        except Exception as e:
            print(t(f"Fehler: {e}", f"Error: {e}"))
            failed_steps.append(t("Kontinuierliche HR", "Continuous HR"))

    print(t("\n── Oura in health.db ───────────────────────────────────",
            "\n── Oura in health.db ───────────────────────────────────"))
    r = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM sessions WHERE type='sleep' AND source_app='oura_app'"
    ).fetchone()
    print(t(f"  sleep sessions:  {r[0]:>5} | {r[1]}→{r[2]}",
            f"  sleep sessions:  {r[0]:>5} | {r[1]}→{r[2]}"))
    r = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM measurements WHERE source_app='oura_app'"
    ).fetchone()
    print(t(f"  measurements:    {r[0]:>5} | {r[1]}→{r[2]}",
            f"  measurements:    {r[0]:>5} | {r[1]}→{r[2]}"))
    r = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM measurements "
        "WHERE source_app='oura_app' AND metric='hrv_rmssd'"
    ).fetchone()
    print(t(f"  hrv_rmssd:       {r[0]:>5} | {r[1]}→{r[2]}",
            f"  hrv_rmssd:       {r[0]:>5} | {r[1]}→{r[2]}"))

    log_import(conn, 'oura_api', '', 0)
    conn.commit()
    conn.close()

    if failed_steps:
        # Wichtig für fetch_daily.py: die dortige Subprozess-Wrapper-Funktion
        # (fetch_devices()) prüft NUR den Exit-Code und meldet bei 0 pauschal
        # "✓ synchronisiert", ohne die eigentliche Ausgabe zu betrachten. Ohne
        # diesen sys.exit(1) bleiben Fehler in einzelnen Schritten (z.B. der
        # HRV-Zeitreihe) für den Aufrufer unsichtbar, obwohl sie hier oben
        # bereits gedruckt wurden — genau das führte zu einer über einen Monat
        # unbemerkten HRV-Datenlücke.
        print(t(f"\n⚠ {len(failed_steps)} Schritt(e) fehlgeschlagen: {', '.join(failed_steps)}",
                f"\n⚠ {len(failed_steps)} step(s) failed: {', '.join(failed_steps)}"), file=_sys.stderr)
        _sys.exit(1)


if __name__ == "__main__":
    main()
