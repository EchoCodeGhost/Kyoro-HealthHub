#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Garmin Connect → health.db

@tier        infrastructure
@purpose.de  Importiert Daten aus Garmin Connect in die health.db.
             Unterstützt Schlaf, Herzfrequenz, HRV, Stress, Body Battery, SpO2,
             Atmung und tägliche Zusammenfassungen.
@purpose.en  Imports data from Garmin Connect into health.db.
             Supports sleep, heart rate, HRV, stress, body battery, SpO2,
             respiration, and daily summaries.
@method.de   Liest Garmin-Daten aus den von garmin_download.py erstellten Dateien.
             Schlaf → sessions + session_metrics, Herzfrequenz/HRV/Stress →
             measurements, tägliche Daten → measurements, Aktivitäten (via
             import_activities) → sessions + session_metrics inkl. training_load
             (aus Garmins eigenem aerobic/anaerobic Training Effect, HF-basiert),
             außer für generische 'other'-Aktivitäten oder wenn eine andere
             Quelle dasselbe Zeitfenster bereits abdeckt/verworfen hat (s.
             claim_training_load_slot, modules/base.py). Konfiguration über
             ~/.config/kyoro/garmin_config.json (geteilt mit garmin_download.py).
@method.en   Reads Garmin data from files created by garmin_download.py.
             Sleep → sessions + session_metrics, heart rate/HRV/stress →
             measurements, daily data → measurements, activities (via
             import_activities) → sessions + session_metrics including
             training_load (from Garmin's own aerobic/anaerobic Training
             Effect, heart-rate-based), except for generic 'other' activities
             or when another source already covers/rejected the same time
             window (see claim_training_load_slot, modules/base.py).
             Configuration via ~/.config/kyoro/garmin_config.json (shared with
             garmin_download.py).
@reads       Garmin-Exportdateien (JSON/CSV)
@writes      health.db (sessions, session_metrics, measurements)
@limits.de   Keine Validierung der Garmin-Datenqualität. Abhängig von der
             Korrektheit des Garmin-Exports. Keine medizinische Interpretation.
             training_load für Aktivitäten ist eine grobe Näherung aus dem
             Trainingseffekt-Wert (s. GARMIN_TRAINING_LOAD_EFFECT_FACTOR),
             nicht direkt mit Polars training_load vergleichbar, nur als
             gleichwertiges Trigger-Signal gedacht.

@relevance.de  Ermöglicht den Import von Gesundheits- und Aktivitätsdaten aus Garmin-Geräten, essentiell für die umfassende Analyse von Wearable-Daten
@relevance.en  Enables import of health and activity data from Garmin devices, essential for comprehensive wearable data analysis
@limits.en   No validation of Garmin data quality. Dependent on the correctness
             of the Garmin export. No medical interpretation.
             training_load for activities is a rough approximation derived
             from the training effect value (see
             GARMIN_TRAINING_LOAD_EFFECT_FACTOR), not directly comparable to
             Polar's training_load, intended only as an equivalent trigger
             signal.
@usage
    python3 import_garmin.py               # from 2024-01-01
    python3 import_garmin.py --update      # only new data
    python3 import_garmin.py --from 2025-01-01 --to 2025-12-31
    python3 import_garmin.py --from 2026-05-01 --only sleep,bb,steps
"""

import argparse
import json
from datetime import datetime, timedelta, date, timezone
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID, KYORO_CONFIG_DIR
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.base import claim_training_load_slot, log_import
from utils.anonymize import round_coords
_cfg = _Cfg()

CONFIG_PATH = KYORO_CONFIG_DIR / "garmin_config.json"
DB_PATH     = _cfg.db_path
SOURCE      = 'garmin_connect'

# Defaults — überschrieben durch --person / --device in main().
# Modell-spezifische device_id wird bevorzugt aus device_registry (health_config.json)
# gelesen; sonst generischer Fallback 'garmin' (kein hartcodiertes Modell).
def _default_garmin_device_id() -> str:
    for d in _cfg.device_registry:
        brand = (d.get("brand") or "").lower()
        if brand == "garmin" and d.get("device_id"):
            return str(d["device_id"])
    return "garmin"


DEVICE_ID = _default_garmin_device_id()
PERSON    = OWN_PERSON_ID
_DEVICE_OVERRIDE: str | None = None


def _garmin_device_for(date_str: str) -> str:
    """Garmin-Geraet, das an date_str aktiv war (mehrere Personen/Geraete
    in device_registry moeglich, z.B. bei einem Geraetewechsel oder
    mehreren Nutzer:innen). --device-Override gewinnt immer. Fallback:
    DEVICE_ID (erstes Garmin-Geraet), falls date_str leer ist oder kein
    passendes Registry-Fenster existiert."""
    if _DEVICE_OVERRIDE:
        return _DEVICE_OVERRIDE
    from modules.device_registry import device_for_date
    return device_for_date("optical_wrist_gps", date_str, brand="Garmin", person=PERSON) or DEVICE_ID


def _token_store(person: str) -> str:
    return str(Path.home() / ".garmin_tokens")


def get_client(person: str = OWN_PERSON_ID):
    from garminconnect import Garmin
    cfg = json.loads(CONFIG_PATH.read_text())
    if person == OWN_PERSON_ID:
        email = cfg["email"]
    else:
        key = f"{person}_email"
        if key not in cfg:
            raise KeyError(t(
                f"garmin_config.json: Schlüssel '{key}' fehlt für person='{person}'",
                f"garmin_config.json: key '{key}' missing for person='{person}'"
            ))
        email = cfg[key]
    client = Garmin(email)
    client.login(tokenstore=_token_store(person))
    return client


def ms_to_utc(ms: int) -> str:
    """Unix-Millisekanden → UTC ISO timestamp."""
    if ms is None:
        return ""
    dt_utc = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def gmt_to_utc(s: str | None) -> str:
    """Garmin-GMT-String ohne Zonenangabe ('2026-09-09T22:10:00.0') → UTC ISO."""
    if not s:
        return ""
    return s.replace(" ", "T")[:19] + "+00:00"


def _meas(conn, rows: list) -> None:
    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO measurements "
            "(ts, date, metric, value, value_text, unit, device_id, person, source_app) "
            "VALUES (?,?,?,?,?,?,?,?,?)", rows)


def _metrics(cursor, session_id: str, pairs: list) -> None:
    for metric, value, value_text, unit in pairs:
        if value is None and value_text is None:
            continue
        cursor.execute(
            "INSERT OR IGNORE INTO session_metrics(session_id, metric, value, value_text, unit) "
            "VALUES (?,?,?,?,?)",
            (session_id, metric, value, value_text, unit)
        )


def import_heart_rate(conn, client, d: str) -> int:
    try:
        data = client.get_heart_rates(d)
        values = data.get("heartRateValues", [])
        rows = []
        for entry in values:
            if not entry or len(entry) < 2 or entry[1] is None:
                continue
            ts = ms_to_utc(entry[0])
            if not ts:
                continue
            rows.append((ts, ts[:10], 'heart_rate', float(entry[1]), None, 'bpm', _garmin_device_for(ts[:10]), PERSON, SOURCE))
        _meas(conn, rows)
        conn.commit()
        return len(rows)
    except Exception:
        return 0


def import_hrv(conn, client, d: str) -> int:
    try:
        data = client.get_hrv_data(d)
        readings = data.get("hrvReadings", [])
        rows = []
        for r in readings:
            if not r.get("hrvValue"):
                continue
            raw_ts = r.get("readingTimeGMT") or r.get("startTimestampGMT")
            ts = ms_to_utc(raw_ts) if isinstance(raw_ts, int) else (
                raw_ts[:19] + "+00:00" if raw_ts else "")
            if ts:
                rows.append((ts, ts[:10], 'hrv_rmssd', float(r["hrvValue"]), None, 'ms', _garmin_device_for(ts[:10]), PERSON, SOURCE))
        # Fallback / Historie: 5-Min-Readings nur ~jüngste Monate. Nacht-Mittel
        # (hrvSummary.lastNightAvg) reicht Jahre zurück → als Nacht-HRV speichern,
        # wenn keine Detail-Readings da sind. Liefert die HRV-Baseline.
        s = data.get("hrvSummary") or {}
        ts = f"{d}T04:00:00+00:00"
        if not rows:
            v = s.get("lastNightAvg")
            if v:
                rows.append((ts, d, 'hrv_rmssd', float(v), None, 'ms', _garmin_device_for(d), PERSON, SOURCE))
        # Status unabhaengig von den Detail-Readings: frueher nur im Fallback-Zweig
        # geschrieben, weshalb er genau fuer die Naechte mit 5-Min-Readings fehlte.
        stt = s.get("status")
        if stt and s.get("lastNightAvg"):
            rows.append((ts, d, 'hrv_status', None, stt, None, _garmin_device_for(d), PERSON, SOURCE))
        _meas(conn, rows)
        conn.commit()
        return len(rows)
    except Exception as e:
        print(f"[hrv {d}] {type(e).__name__}: {str(e)[:80]}", file=_sys.stderr)
        return 0


def import_sleep(conn, client, d: str) -> int:
    try:
        data = client.get_sleep_data(d)
        dto = data.get("dailySleepDTO", {})
        if not dto:
            return 0
        sid      = f"garmin_sleep_{d}_{PERSON}"
        ts_start = f"{d}T00:00:00+00:00"
        cur = conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO sessions "
            "(id, type, ts_start, ts_end, date, device_id, person, source_app) "
            "VALUES (?, 'sleep', ?, NULL, ?, ?, ?, ?)",
            (sid, ts_start, d, _garmin_device_for(d), PERSON, SOURCE)
        )
        sev = dto.get("breathingDisruptionSeverity")        # NONE/MILD/MODERATE/SEVERE — Garmin-Apnoe-Screening
        _SEV = {"NONE": 0, "LOW": 1, "MILD": 1, "MODERATE": 2, "HIGH": 3, "SEVERE": 3}
        _metrics(cur, sid, [
            ("sleep_score",     dto.get("sleepScores", {}).get("overall", {}).get("value"), None, None),
            ("duration_s",      dto.get("sleepTimeSeconds"),        None, "s"),
            ("deep_s",          dto.get("deepSleepSeconds"),        None, "s"),
            ("light_s",         dto.get("lightSleepSeconds"),       None, "s"),
            ("rem_s",           dto.get("remSleepSeconds"),         None, "s"),
            ("awake_s",         dto.get("awakeSleepSeconds"),       None, "s"),
            ("awake_count",     dto.get("awakeCount"),              None, None),
            ("spo2_avg",        dto.get("averageSpO2Value"),        None, "%"),
            ("spo2_min",        dto.get("lowestSpO2Value"),         None, "%"),
            ("spo2_sleep_hr",   dto.get("averageSpO2HRSleep"),      None, None),
            ("respiration_avg", dto.get("averageRespirationValue"), None, "rpm"),
            ("respiration_min", dto.get("lowestRespirationValue"),  None, "rpm"),
            ("respiration_max", dto.get("highestRespirationValue"), None, "rpm"),
            ("sleep_hr_avg",    dto.get("avgHeartRate"),            None, "bpm"),
            ("avg_stress",      dto.get("avgSleepStress"),          None, None),
            ("overnight_hrv",   data.get("avgOvernightHrv"),        None, "ms"),
            ("breathing_severity", _SEV.get(sev), sev,              None),
            ("restless_moments", data.get("restlessMomentsCount"),  None, None),
            # Hauttemperatur-Abweichung: neuere Garmin-Uhren messen sie am Handgelenk und
            # liefern sie im ohnehin abgerufenen Schlafdatensatz mit. Sie wurde bisher
            # nicht ausgelesen, weshalb der Temperaturkanal in Auswertungen als
            # "geraeteseitig nicht verfuegbar" galt, obwohl die Daten vorlagen.
            # Es ist eine ABWEICHUNG von der geraeteeigenen Baseline (Kelvin-Delta),
            # kein Absolutwert — Vorzeichen und Nullpunkt haengen an der Kalibrierung.
            # Nur mit skinTempDataExists — sonst landet eine 0.0 ohne Messung hier.
            ("skin_temp_deviation_c",
             data.get("avgSkinTempDeviationC") if data.get("skinTempDataExists") else None,
             None, "°C"),
            ("skin_temp_calib_days",  data.get("skinTempCalibrationDays"), None, "d"),
        ])
        # Apnoe-Screening als Tages-Zeitreihe: Atemstörungs-Schweregrad + Nacht-SpO2-Tief
        day_rows = []
        if sev is not None:
            day_rows.append((f"{d}T04:00:00+00:00", d, 'sleep_breathing_severity',
                             float(_SEV.get(sev, 0)), sev, None, _garmin_device_for(d), PERSON, SOURCE))
        if dto.get("lowestSpO2Value") is not None:
            day_rows.append((f"{d}T04:00:00+00:00", d, 'sleep_spo2_min',
                             float(dto["lowestSpO2Value"]), None, "%", _garmin_device_for(d), PERSON, SOURCE))
        # Nur schreiben, wenn das Geraet die Messung als vorhanden meldet — sonst
        # landet eine 0.0-Abweichung als echter Messwert in der Zeitreihe.
        if data.get("skinTempDataExists") and data.get("avgSkinTempDeviationC") is not None:
            day_rows.append((f"{d}T04:00:00+00:00", d, 'skin_temp_deviation_c',
                             float(data["avgSkinTempDeviationC"]), None, "°C",
                             _garmin_device_for(d), PERSON, SOURCE))
        # Schlafphasen-Segmente (sleepLevels) — die API liefert sie nur fuer die
        # juengsten Monate, danach nur noch die Summen im DTO. value = Garmins
        # activityLevel (0=DEEP, 1=LIGHT, 2=REM, 3=WAKE; gegen deep/light/rem/
        # awakeSleepSeconds verifiziert), value_text = Segment-Ende (UTC), damit
        # compute_sleep_hypnogram die Dauer exakt statt aus dem Folgesegment bildet.
        # date = Schlaf-Kalendertag d, wie die Session — nicht der Tag des Segments.
        for lv in data.get("sleepLevels") or []:
            ts_a, ts_b = gmt_to_utc(lv.get("startGMT")), gmt_to_utc(lv.get("endGMT"))
            if ts_a and lv.get("activityLevel") is not None:
                day_rows.append((ts_a, d, 'garmin_sleep_level', float(lv["activityLevel"]),
                                 ts_b or None, None, _garmin_device_for(d), PERSON, SOURCE))
        # Minuetliche Bewegungsintensitaet waehrend der Schlafphase (0..~4).
        for mv in data.get("sleepMovement") or []:
            ts_a = gmt_to_utc(mv.get("startGMT"))
            if ts_a and mv.get("activityLevel") is not None:
                day_rows.append((ts_a, d, 'sleep_movement', float(mv["activityLevel"]),
                                 None, None, _garmin_device_for(d), PERSON, SOURCE))
        if day_rows:
            _meas(conn, day_rows)
        conn.commit()
        return 1
    except Exception as e:
        print(f"[sleep {d}] {type(e).__name__}: {str(e)[:80]}", file=_sys.stderr)
        return 0


def import_stress(conn, client, d: str) -> int:
    try:
        data = client.get_stress_data(d)
        values = data.get("stressValuesArray", [])
        rows = []
        for entry in values:
            if not entry or len(entry) < 2 or entry[1] is None or entry[1] < 0:
                continue
            ts = ms_to_utc(entry[0])
            if ts:
                rows.append((ts, ts[:10], 'stress', float(entry[1]), None, None, _garmin_device_for(ts[:10]), PERSON, SOURCE))
        _meas(conn, rows)
        conn.commit()
        return len(rows)
    except Exception:
        return 0


def _bb_level_index(descriptors: list | None, default: int) -> int:
    """Spaltenindex des Body-Battery-Werts laut Descriptor-Liste der Antwort."""
    for dsc in descriptors or []:
        key = dsc.get("bodyBatteryValueDescriptorKey") or dsc.get("bodyBatteryValueDescriptorsKey")
        if key == "bodyBatteryLevel":
            return int(dsc.get("bodyBatteryValueDescriptorIndex", default))
    return default


def import_body_battery(conn, client, d: str) -> int:
    """Body Battery: Tagesverlauf, Tagesbilanz und Ereignisse.

    get_body_battery() liefert nur ~6 Stuetzpunkte pro Tag. Der eigentliche
    Verlauf (3-Minuten-Raster) steckt in der Antwort von get_stress_data() —
    dort mit anderem Spaltenlayout [ts, status, level, version], deshalb wird
    der Wert-Index aus den Descriptoren gelesen statt fest angenommen.
    """
    rows = []
    try:
        st = client.get_stress_data(d) or {}
        idx = _bb_level_index(st.get("bodyBatteryValueDescriptorsDTOList"), 2)
        for item in st.get("bodyBatteryValuesArray") or []:
            if not item or len(item) <= idx or item[idx] is None:
                continue
            ts = ms_to_utc(item[0])
            if ts:
                rows.append((ts, ts[:10], 'body_battery', float(item[idx]), None, None, _garmin_device_for(ts[:10]), PERSON, SOURCE))
    except Exception as e:
        print(f"[body_battery/stress {d}] {type(e).__name__}: {str(e)[:80]}", file=_sys.stderr)
    try:
        for entry in client.get_body_battery(d, d) or []:
            idx = _bb_level_index(entry.get("bodyBatteryValueDescriptorDTOList"), 1)
            for item in entry.get("bodyBatteryValuesArray", []) or []:
                if not item or len(item) <= idx or item[idx] is None:
                    continue
                ts = ms_to_utc(item[0])
                if ts:
                    rows.append((ts, ts[:10], 'body_battery', float(item[idx]), None, None, _garmin_device_for(ts[:10]), PERSON, SOURCE))
            for metric, key in [("body_battery_charged", "charged"), ("body_battery_drained", "drained")]:
                v = entry.get(key)
                if v is not None:
                    rows.append((f"{d}T00:00:00+00:00", d, metric, float(v), None, None, _garmin_device_for(d), PERSON, SOURCE))
    except Exception as e:
        print(f"[body_battery {d}] {type(e).__name__}: {str(e)[:80]}", file=_sys.stderr)
    try:
        # Ereignisse mit Body-Battery-Wirkung (Schlaf, Aktivitaet, Stress, Erholung):
        # value = Wirkung in Punkten, value_text = Ereignistyp.
        for ev in client.get_body_battery_events(d) or []:
            e = ev.get("event") or {}
            ts = gmt_to_utc(e.get("eventStartTimeGmt"))
            if ts and e.get("bodyBatteryImpact") is not None:
                rows.append((ts, d, 'body_battery_event', float(e["bodyBatteryImpact"]),
                             e.get("eventType"), None, _garmin_device_for(d), PERSON, SOURCE))
    except Exception as e:
        print(f"[body_battery_events {d}] {type(e).__name__}: {str(e)[:80]}", file=_sys.stderr)
    _meas(conn, rows)
    conn.commit()
    return len(rows)


def import_steps_intraday(conn, client, d: str) -> int:
    """15-Minuten-Schritte. Eigene Metrik 'steps_interval', NICHT 'steps' —
    'steps' ist bei Garmin die Tagessumme; Leser, die je Tag summieren, wuerden
    sonst doppelt zaehlen. value_text = Garmins Aktivitaetsstufe des Intervalls
    (sedentary/active/highlyActive/sleeping). Intervalle ohne Tragen ('none'
    und 0 Schritte) werden ausgelassen."""
    try:
        rows = []
        for x in client.get_steps_data(d) or []:
            steps, lvl = x.get("steps"), x.get("primaryActivityLevel")
            if steps is None or (not steps and lvl in (None, "none")):
                continue
            ts = gmt_to_utc(x.get("startGMT"))
            if ts:
                rows.append((ts, d, 'steps_interval', float(steps), lvl, 'steps', _garmin_device_for(d), PERSON, SOURCE))
        _meas(conn, rows)
        conn.commit()
        return len(rows)
    except Exception as e:
        print(f"[steps {d}] {type(e).__name__}: {str(e)[:80]}", file=_sys.stderr)
        return 0


def import_spo2(conn, client, d: str) -> int:
    try:
        data = client.get_spo2_data(d)
        rows = []
        # spO2HourlyAverages: Liste von [ms, wert]-Paaren
        for pair in data.get("spO2HourlyAverages", []) or []:
            if not pair or len(pair) < 2 or pair[1] is None:
                continue
            ts = ms_to_utc(pair[0])
            if ts:
                rows.append((ts, ts[:10], 'spo2', float(pair[1]), None, '%', _garmin_device_for(ts[:10]), PERSON, SOURCE))
        # Fallback: Tages-/Schlaf-Aggregat, falls keine Stundenreihe
        if not rows:
            avg = data.get("avgSleepSpO2") or data.get("averageSpO2")
            if avg:
                ts = f"{d}T12:00:00+00:00"
                rows.append((ts, d, 'spo2', float(avg), None, '%', _garmin_device_for(d), PERSON, SOURCE))
        _meas(conn, rows)
        conn.commit()
        return len(rows)
    except Exception as e:
        print(f"[spo2 {d}] {type(e).__name__}: {str(e)[:80]}", file=_sys.stderr)
        return 0


def import_respiration(conn, client, d: str) -> int:
    try:
        data = client.get_respiration_data(d)
        values = data.get("respirationValuesArray", [])
        rows = []
        for entry in values:
            if not entry or len(entry) < 2 or entry[1] is None or entry[1] <= 0:
                continue
            ts = ms_to_utc(entry[0])
            if ts:
                rows.append((ts, ts[:10], 'respiration_rate', float(entry[1]), None, 'rpm', _garmin_device_for(ts[:10]), PERSON, SOURCE))
        _meas(conn, rows)
        conn.commit()
        return len(rows)
    except Exception:
        return 0


def import_daily(conn, client, d: str) -> int:
    try:
        stats = client.get_stats(d)
        ts    = f"{d}T00:00:00+00:00"
        rows  = []
        for metric, val, unit in [
            ('steps',            stats.get('totalSteps'),          'steps'),
            ('active_kcal',      stats.get('activeKilocalories'),  'kcal'),
            ('total_kcal',       stats.get('totalKilocalories'),   'kcal'),
            ('distance_m',       stats.get('totalDistanceMeters'), 'm'),
            ('avg_stress',       stats.get('averageStressLevel'),  None),
            ('max_stress',       stats.get('maxStressLevel'),      None),
            ('body_battery_min', stats.get('minBodyBattery'),      None),
            ('body_battery_max', stats.get('maxBodyBattery'),      None),
            ('avg_hr',           stats.get('averageHeartRate'),    'bpm'),
            ('resting_hr',       stats.get('restingHeartRate'),    'bpm'),
        ]:
            if val is not None:
                rows.append((ts, d, metric, float(val), None, unit, _garmin_device_for(d), PERSON, SOURCE))
        _meas(conn, rows)
        conn.commit()
        return 1 if rows else 0
    except Exception:
        return 0


def get_last_import(conn) -> str | None:
    r = conn.execute(
        "SELECT MAX(date) FROM sessions WHERE type='sleep' AND source_app=? AND person=?",
        (SOURCE, PERSON)
    ).fetchone()
    return r[0] if r and r[0] else None


def date_range(start: str, end: str):
    cur = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    while cur <= end_dt:
        yield cur.strftime("%Y-%m-%d")
        cur += timedelta(days=1)


# ── Tier 1: tagesbezogene Fitness-Metriken → measurements ─────────────────────

def import_training_daily(conn, client, d: str) -> int:
    """VO2max, Training Readiness, Intensity Minutes, Floors (tagesbezogen)."""
    ts = f"{d}T12:00:00+00:00"
    rows = []

    try:
        ts_stat = client.get_training_status(d) or {}
        vo2 = (ts_stat.get("mostRecentVO2Max") or {})
        for sub in ("generic", "cycling"):
            entry = vo2.get(sub) or {}
            v = entry.get("vo2MaxValue")
            # "mostRecent" ist der zuletzt ermittelte Wert, nicht der Wert des
            # Abruftags. Frueher wurde er mit dem Abrufdatum geschrieben — jeder
            # Tag ohne neue Schaetzung erschien als eigene Messung, und ein
            # monatelang unveraenderter Wert wirkte wie eine dichte Messreihe.
            # Datum daher aus calendarDate; ohne calendarDate kein Eintrag.
            vd = str(entry.get("calendarDate") or "")[:10]
            if v and vd:
                rows.append((f"{vd}T12:00:00+00:00", vd, "vo2max", float(v), None, "ml/kg/min",
                             _garmin_device_for(vd), PERSON, SOURCE))
                break
    except Exception as e:
        print(f"[train_status {d}] {type(e).__name__}: {str(e)[:60]}", file=_sys.stderr)

    try:
        tr = client.get_training_readiness(d) or []
        if tr:
            r0 = tr[0]
            for metric, key, unit in [("training_readiness", "score", None),
                                      ("recovery_time", "recoveryTime", "h"),
                                      ("sleep_score", "sleepScore", None)]:
                v = r0.get(key)
                if v is not None:
                    rows.append((ts, d, metric, float(v), None, unit, _garmin_device_for(d), PERSON, SOURCE))
    except Exception as e:
        print(f"[readiness {d}] {type(e).__name__}: {str(e)[:60]}", file=_sys.stderr)

    try:
        im = client.get_intensity_minutes_data(d) or {}
        for metric, key in [("intensity_moderate", "moderateMinutes"),
                            ("intensity_vigorous", "vigorousMinutes")]:
            v = im.get(key)
            if v is not None:
                rows.append((ts, d, metric, float(v), None, "min", _garmin_device_for(d), PERSON, SOURCE))
    except Exception as e:
        print(f"[intensity {d}] {type(e).__name__}: {str(e)[:60]}", file=_sys.stderr)

    try:
        fl = client.get_floors(d) or {}
        arr = fl.get("floorValuesArray") or []
        up = sum(x[2] for x in arr if len(x) > 3 and x[2])
        down = sum(x[3] for x in arr if len(x) > 3 and x[3])
        if up:
            rows.append((ts, d, "floors_up", float(up), None, None, _garmin_device_for(d), PERSON, SOURCE))
        if down:
            rows.append((ts, d, "floors_down", float(down), None, None, _garmin_device_for(d), PERSON, SOURCE))
    except Exception as e:
        print(f"[floors {d}] {type(e).__name__}: {str(e)[:60]}", file=_sys.stderr)

    _meas(conn, rows)
    conn.commit()
    return len(rows)


# ── Tier 2: Snapshots (langsam veränderlich, 1× pro Lauf) → measurements ──────

def import_garmin_snapshots(conn, client, d: str, start_d: str | None = None) -> int:
    """Race Predictions, Endurance/Hill Score, Fitness Age, Body-Comp, FTP/Laktatschwelle."""
    ts = f"{d}T12:00:00+00:00"
    rows = []

    try:
        rp = client.get_race_predictions() or {}
        for metric, key in [("race_time_5k", "time5K"), ("race_time_10k", "time10K"),
                            ("race_time_half", "timeHalfMarathon"), ("race_time_marathon", "timeMarathon")]:
            v = rp.get(key)
            if v:
                rows.append((ts, d, metric, float(v), None, "s", _garmin_device_for(d), PERSON, SOURCE))
    except Exception as e:
        print(f"[race_pred] {type(e).__name__}: {str(e)[:60]}", file=_sys.stderr)

    for fn_name, metric in [("get_endurance_score", "endurance_score"), ("get_hill_score", "hill_score")]:
        try:
            r = getattr(client, fn_name)(d) or {}
            v = r.get("overallScore")
            if v:
                rows.append((ts, d, metric, float(v), None, None, _garmin_device_for(d), PERSON, SOURCE))
        except Exception as e:
            print(f"[{metric}] {type(e).__name__}: {str(e)[:60]}", file=_sys.stderr)

    try:
        fa = client.get_fitnessage_data(d) or {}
        v = fa.get("fitnessAge")
        if v:
            rows.append((ts, d, "fitness_age", float(v), None, "years", _garmin_device_for(d), PERSON, SOURCE))
    except Exception as e:
        print(f"[fitnessage] {type(e).__name__}: {str(e)[:60]}", file=_sys.stderr)

    # Body Composition (Garmin-Waage) → body_mass/body_fat/muscle
    try:
        # Waagen-Eintraege sind selten und koennen Jahre alt sein: das Fenster reicht
        # bis zum Laufbeginn zurueck, mindestens aber 365 Tage.
        bc_start = min(start_d or d, (date.fromisoformat(d) - timedelta(days=365)).isoformat())
        bc = client.get_body_composition(bc_start, d) or {}
        for w in (bc.get("dateWeightList") or []):
            wts = ms_to_utc(w.get("date")) if isinstance(w.get("date"), int) else (w.get("calendarDate", d) + "T12:00:00+00:00")
            wd = wts[:10]
            for metric, key, unit in [("body_mass", "weight", "g"), ("body_fat", "bodyFat", "%"),
                                      ("muscle_mass", "muscleMass", "g"), ("bmi", "bmi", None)]:
                v = w.get(key)
                if v is not None:
                    val = float(v) / 1000.0 if unit == "g" else float(v)
                    rows.append((wts, wd, metric, val, None, "kg" if unit == "g" else unit, _garmin_device_for(wd), PERSON, SOURCE))
    except Exception as e:
        print(f"[body_comp] {type(e).__name__}: {str(e)[:60]}", file=_sys.stderr)

    # Leistungsschwelle Rad (FTP) und Laktatschwelle Lauf — jeweils mit dem Datum,
    # an dem Garmin den Wert ermittelt hat, nicht dem Abrufdatum.
    try:
        lt = client.get_lactate_threshold() or {}
        pw = lt.get("power") or {}
        if pw.get("functionalThresholdPower") and pw.get("calendarDate"):
            pd = str(pw["calendarDate"])[:10]
            rows.append((f"{pd}T12:00:00+00:00", pd, "cycling_ftp", float(pw["functionalThresholdPower"]),
                         pw.get("sport"), "W", _garmin_device_for(pd), PERSON, SOURCE))
        sh = lt.get("speed_and_heart_rate") or {}
        if sh.get("calendarDate"):
            sd = str(sh["calendarDate"])[:10]
            for metric, key, unit in [("lactate_threshold_hr", "heartRate", "bpm"),
                                      ("lactate_threshold_speed", "speed", "m/s")]:
                if sh.get(key):
                    rows.append((f"{sd}T12:00:00+00:00", sd, metric, float(sh[key]), None, unit,
                                 _garmin_device_for(sd), PERSON, SOURCE))
    except Exception as e:
        print(f"[lactate_threshold] {type(e).__name__}: {str(e)[:60]}", file=_sys.stderr)

    _meas(conn, rows)
    conn.commit()
    return len(rows)


# ── Tier 3: Aktivitäten (Workouts) → sessions + session_metrics + GPS-Tracks ──

def _import_activity_gps(cur, client, activity_id, sid: str) -> int:
    """GPS-/HR-Punkte einer Aktivität → session_tracks."""
    try:
        det = client.get_activity_details(activity_id, maxchart=2000, maxpoly=2000) or {}
        idx = {m.get("key"): m.get("metricsIndex") for m in det.get("metricDescriptors", [])}
        i_lat, i_lon = idx.get("directLatitude"), idx.get("directLongitude")
        i_ele, i_spd, i_ts = idx.get("directElevation"), idx.get("directSpeed"), idx.get("directTimestamp")
        if i_lat is None or i_lon is None:
            return 0
        n = 0
        for row in det.get("activityDetailMetrics", []) or []:
            m = row.get("metrics") or []
            if max(filter(None, [i_lat, i_lon])) >= len(m):
                continue
            lat, lon = m[i_lat], m[i_lon]
            if lat is None or lon is None:
                continue
            # Reduziere GPS-Präzision auf 5 Dezimalstellen (~1m) für Datenschutz
            lat, lon = round_coords(float(lat), float(lon), precision=5) if lat is not None and lon is not None else (None, None)
            ts = ms_to_utc(int(m[i_ts])) if (i_ts is not None and m[i_ts]) else None
            ele = m[i_ele] if (i_ele is not None and i_ele < len(m)) else None
            spd = m[i_spd] if (i_spd is not None and i_spd < len(m)) else None
            cur.execute(
                "INSERT OR IGNORE INTO session_tracks(session_id, ts, lat, lon, elevation_m, speed_ms) "
                "VALUES (?,?,?,?,?,?)", (sid, ts, lat, lon, ele, spd))
            n += 1
        return n
    except Exception as e:
        print(f"[gps {activity_id}] {type(e).__name__}: {str(e)[:60]}", file=_sys.stderr)
        return 0


# 'other' ist Garmins generischer Fallback-Typ fuer Aktivitaeten, die es nicht
# eindeutig klassifizieren konnte (analog zu Oura, s. import_oura_csv.py::
# OURA_NON_SPORT_ACTIVITIES) — kein bewusst gestartetes, benanntes Training.
# Garmin liefert kein separates Auto-Erkennungs-Flag wie Polars startTrigger.
GARMIN_NON_SPORT_ACTIVITIES = {"other"}

# aerobicTrainingEffect/anaerobicTrainingEffect sind Garmins eigene (Firstbeat-
# basierte) 0-5-Trainingseffekt-Skala, HF-abgeleitet wie Polars training_load —
# deutlich belastbarer als eine reine Kalorien-Naeherung (vgl. Oura). Faktor
# grob kalibriert, damit typische Werte (~3.5-5.0 Summe) in dieselbe
# Groessenordnung wie reale Polar-training_load-Werte (~50-140) fallen.
GARMIN_TRAINING_LOAD_EFFECT_FACTOR = 15.0


def _garmin_training_load(aerobic: "float | None", anaerobic: "float | None") -> "float | None":
    total = (aerobic or 0) + (anaerobic or 0)
    if not total:
        return None
    return round(total * GARMIN_TRAINING_LOAD_EFFECT_FACTOR, 1)


def import_activities(conn, client, start_d: str, end_d: str, with_gps: bool = True) -> tuple[int, int]:
    """Aktivitäten (neueste zuerst) im Zeitfenster → sessions + session_metrics."""
    cur = conn.cursor()
    n_act = n_trk = 0
    offset = 0
    import time
    while True:
        batch = client.get_activities(offset, 50) or []
        if not batch:
            break
        stop = False
        for a in batch:
            stl = (a.get("startTimeLocal") or "")[:10]
            if not stl:
                continue
            if stl > end_d:
                continue
            if stl < start_d:
                stop = True
                break
            aid = a.get("activityId")
            sid = f"garmin_act_{aid}"
            sport = (a.get("activityType") or {}).get("typeKey")
            gmt = a.get("startTimeGMT")
            ts_start = gmt.replace(" ", "T") + "+00:00" if gmt else None
            cur.execute(
                "INSERT OR IGNORE INTO sessions "
                "(id, type, ts_start, ts_end, date, device_id, person, source_app, sport) "
                "VALUES (?, 'training', ?, NULL, ?, ?, ?, ?, ?)",
                (sid, ts_start, stl, _garmin_device_for(stl), PERSON, SOURCE, sport))
            for metric, key, unit in [
                ("duration_s", "duration", "s"), ("distance_m", "distance", "m"),
                ("calories", "calories", "kcal"), ("hr_avg", "averageHR", "bpm"),
                ("hr_max", "maxHR", "bpm"), ("elevation_gain", "elevationGain", "m"),
                ("elevation_loss", "elevationLoss", "m"), ("avg_speed", "averageSpeed", "m/s"),
                ("max_speed", "maxSpeed", "m/s"), ("aerobic_training_effect", "aerobicTrainingEffect", None),
                ("anaerobic_training_effect", "anaerobicTrainingEffect", None),
                ("cadence_avg", "averageRunningCadenceInStepsPerMin", "spm"),
                ("power_avg", "avgPower", "W"), ("power_max", "maxPower", "W"),
            ]:
                v = a.get(key)
                if v is not None:
                    cur.execute(
                        "INSERT OR IGNORE INTO session_metrics(session_id, metric, value, value_text, unit) "
                        "VALUES (?,?,?,?,?)", (sid, metric, float(v), None, unit))
            if sport:
                cur.execute(
                    "INSERT OR IGNORE INTO session_metrics(session_id, metric, value, value_text, unit) "
                    "VALUES (?, 'workout_type', NULL, ?, NULL)", (sid, sport))

            # training_load nur fuer echte, klar benannte Sportarten (nicht
            # Garmins generisches 'other'). claim_training_load_slot prueft
            # zusaetzlich gegen zeitgleiche Polar-/Oura-Sessions: Garmin hat
            # dort die hoechste Prioritaet (s. TRAINING_LOAD_SOURCE_PRIORITY,
            # modules/base.py) und verdraengt bei Ueberlappung deren
            # training_load — unabhaengig davon, welche Quelle zuerst
            # importiert wurde.
            if (sport or "").lower() not in GARMIN_NON_SPORT_ACTIVITIES and ts_start:
                dur = a.get("duration")
                ts_end_est = (ms_to_utc(int((datetime.fromisoformat(ts_start).timestamp()
                                              + float(dur)) * 1000))
                              if dur else None)
                if claim_training_load_slot(conn, PERSON, sid, SOURCE, stl, ts_start, ts_end_est):
                    load = _garmin_training_load(a.get("aerobicTrainingEffect"),
                                                  a.get("anaerobicTrainingEffect"))
                    if load:
                        cur.execute(
                            "INSERT OR IGNORE INTO session_metrics"
                            "(session_id, metric, value, value_text, unit) VALUES (?,?,?,?,?)",
                            (sid, "training_load", load, None, None))
            n_act += 1
            if with_gps and a.get("hasPolyline"):
                n_trk += _import_activity_gps(cur, client, aid, sid)
                time.sleep(0.3)
        conn.commit()
        offset += len(batch)
        if stop or len(batch) < 50:
            break
    return n_act, n_trk


# Abrufbare Teile fuer --only. Tagesverlaeufe haelt die API nur einige Monate
# vor; ein Backfill ueber Jahre lohnt nur fuer tagesbezogene Teile.
PARTS = ["hr", "hrv", "sleep", "stress", "bb", "spo2", "resp", "daily", "train",
         "steps", "snapshots", "activities"]


def main():
    """
    Hauptfunktion: Koordiniert den Import der Garmin Connect-Daten.

    Command-Line-Argumente:
        --update: Nur neue Daten ergänzen
        --from: Startdatum (YYYY-MM-DD)
        --to: Enddatum (YYYY-MM-DD)
        --person: Personen-ID
    """
    global DEVICE_ID, PERSON, _DEVICE_OVERRIDE

    parser = argparse.ArgumentParser(description=t(
        "Garmin Connect passive Daten → health.db",
        "Garmin Connect passive data → health.db"))
    parser.add_argument("--update", action="store_true",
                        help=t("Nur neue Daten ergänzen",
                               "Only fetch new data"))
    parser.add_argument("--from",   dest="date_from", default=None,
                        help=t("Startdatum YYYY-MM-DD",
                               "Start date YYYY-MM-DD"))
    parser.add_argument("--to",     dest="date_to",   default=None,
                        help=t("Enddatum YYYY-MM-DD",
                               "End date YYYY-MM-DD"))
    parser.add_argument("--only", default=None, metavar="LISTE",
                        help=t("Nur diese Teile, kommagetrennt: " + ",".join(PARTS),
                               "Only these parts, comma-separated: " + ",".join(PARTS)))
    parser.add_argument("--person", default=None,
                        help=t("Person-ID (Standard: OWN_PERSON_ID)",
                               "Person ID (default: OWN_PERSON_ID)"))
    parser.add_argument("--device", default=None,
                        help=t("device_id für measurements/sessions (Standard: erstes Garmin-Gerät aus device_registry oder 'garmin')",
                               "device_id for measurements/sessions (default: first Garmin device from device_registry or 'garmin')"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    only = set(PARTS) if not args.only else {p.strip() for p in args.only.split(",") if p.strip()}
    unknown = only - set(PARTS)
    if unknown:
        parser.error(t(f"Unbekannte Teile: {', '.join(sorted(unknown))}",
                       f"Unknown parts: {', '.join(sorted(unknown))}"))

    if args.person:
        PERSON = args.person
    if args.device:
        _DEVICE_OVERRIDE = args.device

    conn = open_db()
    conn.execute("PRAGMA journal_mode=WAL")

    end_date   = args.date_to   or date.today().isoformat()
    if args.date_from:
        start_date = args.date_from
    else:
        row = conn.execute(
            "SELECT date_from FROM devices WHERE device_id=?", (_DEVICE_OVERRIDE or DEVICE_ID,)
        ).fetchone()
        start_date = row[0] if row and row[0] else (_cfg.data_start or "2000-01-01")

    if args.update:
        last = get_last_import(conn)
        if last:
            start_date = (datetime.strptime(last, "%Y-%m-%d") +
                          timedelta(days=1)).strftime("%Y-%m-%d")
            print(t(f"Update-Modus: ab {start_date}",
                    f"Update mode: from {start_date}"))

    if start_date > end_date:
        print(t("Daten bereits aktuell.",
                "Data already up to date."))
        conn.close()
        return

    print(t(f"Verbinde mit Garmin Connect (person={PERSON}, device={_DEVICE_OVERRIDE or DEVICE_ID}) ...",
            f"Connecting to Garmin Connect (person={PERSON}, device={_DEVICE_OVERRIDE or DEVICE_ID}) ..."))
    client = get_client(PERSON)
    print(t(f"Zeitraum: {start_date} → {end_date}\n",
            f"Date range: {start_date} → {end_date}\n"))

    # Nur Snapshots/Aktivitaeten angefordert → keine Tagesschleife ohne Abrufe.
    day_parts = only - {"snapshots", "activities"}
    dates  = list(date_range(start_date, end_date)) if day_parts else []
    totals = {k: 0 for k in ["hr", "hrv", "sleep", "stress", "bb", "spo2", "resp", "daily", "train", "steps"]}

    sleep_mark = t("Schlaf✓", "Sleep✓")
    for i, d in enumerate(dates, 1):
        print(t(f"  {d} ({i}/{len(dates)}) ...",
                f"  {d} ({i}/{len(dates)}) ..."), end=" ", flush=True)

        n_hr    = import_heart_rate(conn, client, d)      if "hr"     in only else 0
        n_hrv   = import_hrv(conn, client, d)             if "hrv"    in only else 0
        n_sleep = import_sleep(conn, client, d)           if "sleep"  in only else 0
        n_st    = import_stress(conn, client, d)          if "stress" in only else 0
        n_bb    = import_body_battery(conn, client, d)    if "bb"     in only else 0
        n_spo2  = import_spo2(conn, client, d)            if "spo2"   in only else 0
        n_resp  = import_respiration(conn, client, d)     if "resp"   in only else 0
        n_day   = import_daily(conn, client, d)           if "daily"  in only else 0
        n_train = import_training_daily(conn, client, d)  if "train"  in only else 0
        n_steps = import_steps_intraday(conn, client, d)  if "steps"  in only else 0
        totals["steps"] += n_steps

        totals["train"] += n_train
        totals["hr"]    += n_hr
        totals["hrv"]   += n_hrv
        totals["sleep"] += n_sleep
        totals["stress"]+= n_st
        totals["bb"]    += n_bb
        totals["spo2"]  += n_spo2
        totals["resp"]  += n_resp
        totals["daily"] += n_day

        parts = []
        if n_hr:    parts.append(f"HR:{n_hr}")
        if n_hrv:   parts.append(f"HRV:{n_hrv}")
        if n_sleep: parts.append(sleep_mark)
        if n_st:    parts.append(f"Stress:{n_st}")
        if n_spo2:  parts.append(f"SpO2:{n_spo2}")
        if n_bb:    parts.append(f"BB:{n_bb}")
        if n_steps: parts.append(t(f"Schritte:{n_steps}", f"Steps:{n_steps}"))
        print(" | ".join(parts) if parts else "—")

        import time; time.sleep(0.3)

    # Snapshots (1× pro Lauf) + Aktivitäten
    print(t("\n  Snapshots (VO2max-Trend, Race, Endurance, Fitness Age, Body-Comp) ...",
            "\n  Snapshots ...") , flush=True)
    n_snap = import_garmin_snapshots(conn, client, end_date, start_date) if "snapshots" in only else 0
    print(t(f"  Aktivitäten (Workouts + GPS) {start_date}→{end_date} ...",
            f"  Activities {start_date}→{end_date} ..."), flush=True)
    n_act, n_trk = (import_activities(conn, client, start_date, end_date)
                    if "activities" in only else (0, 0))

    header = t("── Garmin-Daten importiert ──────────────────────────────────",
               "── Garmin data imported ──────────────────────────────────────")
    print(f"\n{header}")
    samples = t("Messpunkte", "samples")
    windows = t("Fenster",    "windows")
    nights  = t("Nächte",     "nights")
    print(t(f"  HR:           {totals['hr']:>7,} {samples}",
            f"  HR:           {totals['hr']:>7,} {samples}"))
    print(f"  HRV:          {totals['hrv']:>7,} {windows}")
    print(t(f"  Schlaf:       {totals['sleep']:>7} {nights}",
            f"  Sleep:        {totals['sleep']:>7} {nights}"))
    print(f"  Stress:       {totals['stress']:>7,} {samples}")
    print(f"  Body Battery: {totals['bb']:>7,} {samples}")
    print(f"  SpO2:         {totals['spo2']:>7,} {samples}")
    print(t(f"  Schritte/15m: {totals['steps']:>7,} {samples}",
            f"  Steps/15m:    {totals['steps']:>7,} {samples}"))
    print(t(f"  Atemfrequenz: {totals['resp']:>7,} {samples}",
            f"  Respiration:  {totals['resp']:>7,} {samples}"))
    print(t(f"  Fitness/Tag:  {totals['train']:>7,} {samples}",
            f"  Fitness/day:  {totals['train']:>7,} {samples}"))
    print(t(f"  Snapshots:    {n_snap:>7,} {samples}", f"  Snapshots:    {n_snap:>7,} {samples}"))
    print(t(f"  Aktivitäten:  {n_act:>7} ({n_trk:,} GPS-Punkte)",
            f"  Activities:   {n_act:>7} ({n_trk:,} GPS points)"))

    r = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM sessions WHERE type='sleep' AND source_app=?",
        (SOURCE,)
    ).fetchone()
    print(t(f"  Schlaf gesamt: {r[0]} | {r[1]}→{r[2]}",
            f"  Sleep total:  {r[0]} | {r[1]}→{r[2]}"))
    r = conn.execute(
        "SELECT COUNT(*), MIN(date), MAX(date) FROM measurements WHERE source_app=?", (SOURCE,)
    ).fetchone()
    print(t(f"  Messungen:     {r[0]:,} | {r[1]}→{r[2]}",
            f"  Measurements: {r[0]:,} | {r[1]}→{r[2]}"))

    log_import(conn, 'garmin', '', sum(totals.values()) + n_snap + n_act)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
