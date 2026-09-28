#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
AFib-Burden-Analyse — Häufigkeit, Dauer und Trends von Arrhythmie-Episoden

Datenquellen:
  - arrhythmie_episoden: Polar PPI-basierte Erkennungen
  - ecg_sessions: Apple Watch EKG-Klassifikationen
  - measurements (hrv_rmssd/rmssd_ms) über modules/metric_loader: Schlaf-HRV als
    Kontextindikator, geräteunabhängig (nicht mehr polar_nightly_hrv-exklusiv)
  - biometeo / weather_station: Luftdruck

@tier        calibrated
@purpose.de  Analysiert Häufigkeit, Dauer und zeitliche Verteilung von Arrhythmie-Episoden
             aus Polar-PPI-Daten und Apple Watch EKG sowie Zusammenhänge mit Luftdruck,
             Blutdruck, HRV, Schlaf und Stress.
@purpose.en  Analyses frequency, duration and temporal distribution of arrhythmia episodes
             from Polar PPI data and Apple Watch ECG, plus correlations with barometric
             pressure, blood pressure, HRV, sleep and stress.
@method.de   Liest direkt aus compute-generierten arrhythmie_episoden und ecg_sessions;
             verwendet CV-Klassifikation (CV ≥ 10 % = AFib-verdächtig, < 10 % = Ektopie)
             aus arrhythmia_utils. Keine eigene Episodendetektion im Script.
@method.en   Reads directly from compute-generated arrhythmie_episoden and ecg_sessions;
             applies CV classification (CV ≥ 10 % = AFib-suspicious, < 10 % = ectopy)
             from arrhythmia_utils. No independent episode detection in this script.
@limits.de   Polar-CV-Erkennung ist kein klinisches EKG. Die CV-Schwellen sind
             empirisch, nicht formal validiert. n=1, keine Kontrollgruppe, Consumer-Sensorik.
@limits.en   Polar CV detection is not a clinical ECG. CV thresholds are empirical,
             not formally validated. n=1, no control group, consumer-grade sensors.
@reads       arrhythmie_episoden, ecg_sessions, biometeo,
             weather_station, blood_pressure, measurements, sessions, session_metrics,
             symptoms
@writes      analyses/cardiovascular/*.{md,png} (kein DB-Write)
@refs        Perez MV, Mahaffey KW, Hedlin H et al. (2019). Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation. New England Journal of Medicine, 381(20):1909-1917. doi:10.1056/NEJMoa1901183
             Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439

Usage:
  python analyse_afib_burden.py --plot
  python analyse_afib_burden.py --from 2025-01-01 --to 2026-05-31
  python analyse_afib_burden.py --all   # alle verfügbaren Daten

Hinweis: Standard-Zeitfenster sind die letzten 365 Tage. Bei analyse_all.py
wird dieses Default ebenfalls verwendet — für die vollständige Historie
immer --all übergeben oder direkt mit --from aufrufen.


@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@usage
    python analyse_afib_burden.py
    python analyse_afib_burden.py --help
    python analyse_afib_burden.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.device_registry import is_device_active
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_AFIB_BURDEN_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_AFIB_BURDEN_EN as SYSTEM_PROMPT_EN,
)
from modules.arrhythmia_utils import (
    CV_AFIB_LOW, CV_AFIB_MID, CV_AFIB_HIGH,
    load_trainings, sport_mapping,
    cv_klassifikation, load_pre_episode_context,
    load_druck, load_blutdruck, load_ecg_logger,
    load_pollen, load_air_quality, load_indoor_air,
)
from modules.metric_loader import load_metric_daily, source_summary, weakest_confidence
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "cardiovascular"


# ── Data loading ──────────────────────────────────────────────────────────────

def _table_exists(conn, name):
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row[0] > 0


def load_episoden(conn, d_from, d_to, person: str = OWN_PERSON_ID):
    """Load arrhythmie_episoden rows within the date range."""
    if not _table_exists(conn, "arrhythmie_episoden"):
        return []
    try:
        return conn.execute("""
            SELECT episode_start, episode_end, dauer_min, n_fenster,
                   cv_max, cv_mean, hr_mean, time_of_day, source
            FROM arrhythmie_episoden
            WHERE DATE(episode_start) >= ? AND DATE(episode_start) <= ?
              AND person = ?
            ORDER BY episode_start
        """, (d_from, d_to, person)).fetchall()
    except Exception:
        return []


def load_ecg(conn, d_from, d_to, person: str = OWN_PERSON_ID):
    """Load ecg_sessions within the date range. Sessions whose device was not
    active (per device_registry date_from/date_to) at the session's own
    timestamp are dropped — a device can't have produced a real reading
    before it was owned/after it was retired."""
    if not _table_exists(conn, "ecg_sessions"):
        return []
    try:
        rows = conn.execute("""
            SELECT datetime, classification, symptoms, duration_s, device_id
            FROM ecg_sessions
            WHERE DATE(datetime) >= ? AND DATE(datetime) <= ?
              AND person = ?
            ORDER BY datetime
        """, (d_from, d_to, person)).fetchall()
    except Exception:
        return []
    kept, dropped = [], 0
    for r in rows:
        if r[4] and not is_device_active(r[4], r[0]):
            dropped += 1
            continue
        kept.append(r)
    if dropped:
        print(t(f"  ⚠ {dropped} ECG-Session(s) außerhalb der Geräte-Trageperiode laut registry.json übersprungen",
                f"  ⚠ {dropped} ECG session(s) outside the device's registry.json wear period skipped"))
    return kept


def load_hrv(conn, d_from, d_to, person: str = OWN_PERSON_ID):
    """Load nightly HRV (RMSSD) as one value per day, device-agnostic.

    Was polar_nightly_hrv-only, which is empty on every installation without
    a Polar device (this DB included — 0 rows there vs. ~17k rows of
    hrv_rmssd in measurements from other devices). load_metric_daily() picks
    one source per calendar day (registry-configured device > source_priority
    > most readings that day) and merges export paths of the same hardware,
    so the same night isn't counted twice.

    Returns (hrv_dict, source_summary, weakest_confidence):
      hrv_dict: {date: rmssd_ms} — unchanged shape for existing callers.
      source_summary: {source_app: n_days} for reporting.
      weakest_confidence: the most cautious confidence level among used days.
    """
    days = load_metric_daily(conn, ("hrv_rmssd", "rmssd_ms"), d_from, d_to,
                              person=person, agg="avg")
    hrv_dict = {d: day.value for d, day in days.items()}
    return hrv_dict, source_summary(days), weakest_confidence(days)




# ── Statistics helpers ────────────────────────────────────────────────────────

def _avg(lst):
    valid = [x for x in lst if x is not None]
    return round(sum(valid) / len(valid), 2) if valid else None


def _median(lst):
    valid = sorted(x for x in lst if x is not None)
    n = len(valid)
    if n == 0:
        return None
    mid = n // 2
    return valid[mid] if n % 2 else round((valid[mid - 1] + valid[mid]) / 2, 2)


def _moving_avg(values, window=4):
    """Simple unweighted moving average; returns list of same length (None-padded)."""
    result = []
    for i in range(len(values)):
        if i < window - 1:
            result.append(None)
        else:
            chunk = values[i - window + 1 : i + 1]
            valid = [v for v in chunk if v is not None]
            result.append(round(sum(valid) / len(valid), 2) if valid else None)
    return result


def _iso_week(date_str):
    """Return 'YYYY-Www' week key from YYYY-MM-DD string."""
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.strftime("%G-W%V")
    except Exception:
        return "unknown"


def _week_monday(week_str):
    """Parse 'YYYY-Www' back to datetime of Monday."""
    try:
        return datetime.strptime(week_str + "-1", "%G-W%V-%u")
    except Exception:
        return None


def _total_monitored_minutes(d_from, d_to):
    """Estimate total monitored minutes in the date range (24 h per day)."""
    try:
        dt_from = datetime.strptime(d_from, "%Y-%m-%d")
        dt_to   = datetime.strptime(d_to,   "%Y-%m-%d")
        days    = max((dt_to - dt_from).days + 1, 1)
        return days * 24 * 60
    except Exception:
        return None


# ── Analysis functions ────────────────────────────────────────────────────────





def load_atemfrequenz(conn, d_from, d_to, person: str = OWN_PERSON_ID):
    """Load daily mean respiratory rate from measurements. Returns dict {date: avg_rr}."""
    try:
        rows = conn.execute("""
            SELECT DATE(ts) AS d, AVG(value) AS avg_rr
            FROM measurements
            WHERE metric = 'respiratory_rate'
              AND DATE(ts) >= ? AND DATE(ts) <= ?
              AND person = ?
            GROUP BY d
            ORDER BY d
        """, (d_from, d_to, person)).fetchall()
        return {r[0]: round(r[1], 1) for r in rows}
    except Exception:
        return {}


def load_spo2_nacht(conn, d_from, d_to, person: str = OWN_PERSON_ID):
    """Load nocturnal SpO2 minimum from measurements. Returns dict {date: spo2_min}."""
    try:
        rows = conn.execute("""
            SELECT DATE(ts) AS d, MIN(value) AS spo2_min
            FROM measurements
            WHERE metric IN ('spo2', 'spo2_avg')
              AND DATE(ts) >= ? AND DATE(ts) <= ?
              AND person = ?
              AND value > 50
            GROUP BY d
            ORDER BY d
        """, (d_from, d_to, person)).fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def load_afes_spo2(conn, d_from, d_to, person: str = OWN_PERSON_ID):
    """SpO2-Vornacht-Korrelation mit AFES-Level.

    Für jeden AFES-Tag: minimales SpO2 der Vornacht (alle Quellen, normalisiert).
    Gibt (level_stats, detail_rows) zurück:
      level_stats: {level: {n_total, n_spo2, n_under90, n_under94}}
      detail_rows: [(date, score, level, spo2_min)] für high/critical, sortiert
    """
    try:
        afes = conn.execute("""
            SELECT date, score, level FROM af_evidence_scores
            WHERE date >= ? AND date <= ? AND person = ?
            ORDER BY date
        """, (d_from, d_to, person)).fetchall()
    except Exception:
        return {}, []

    level_stats = {}
    detail_rows = []

    for date, score, level in afes:
        from datetime import datetime as _dt, timedelta as _td
        prev = (_dt.strptime(date, "%Y-%m-%d") - _td(days=1)).strftime("%Y-%m-%d")
        row = conn.execute("""
            SELECT MIN(CASE WHEN value <= 1.5 THEN value * 100.0 ELSE value END)
            FROM measurements
            WHERE metric IN ('spo2', 'oxygen_saturation')
              AND date = ? AND person = ? AND value > 0
        """, (prev, person)).fetchone()
        spo2_min = row[0] if row and row[0] else None

        s = level_stats.setdefault(level, {"n_total": 0, "n_spo2": 0,
                                            "n_under90": 0, "n_under94": 0})
        s["n_total"] += 1
        if spo2_min is not None:
            s["n_spo2"] += 1
            if spo2_min < 90:
                s["n_under90"] += 1
            if spo2_min < 94:
                s["n_under94"] += 1
        if level in ("high", "critical"):
            detail_rows.append((date, score, level, spo2_min))

    return level_stats, detail_rows


def load_sleep(conn, d_from, d_to, person: str = OWN_PERSON_ID):
    """Load sleep quality metrics from sessions + session_metrics.

    Returns dict {date: {efficiency, rem_pct, awake_s}}.
    """
    if not _table_exists(conn, "sessions"):
        return {}
    try:
        rows = conn.execute("""
            SELECT s.date,
                   sm_eff.value AS efficiency,
                   sm_rem.value AS rem_pct,
                   sm_awk.value AS awake_s
            FROM sessions s
            LEFT JOIN session_metrics sm_eff
                   ON sm_eff.session_id = s.id AND sm_eff.metric = 'sleep_efficiency_pct'
            LEFT JOIN session_metrics sm_rem
                   ON sm_rem.session_id = s.id AND sm_rem.metric = 'sleep_rem_pct'
            LEFT JOIN session_metrics sm_awk
                   ON sm_awk.session_id = s.id AND sm_awk.metric = 'sleep_awake_s'
            WHERE s.type = 'sleep'
              AND s.date >= ? AND s.date <= ?
              AND s.person = ?
            ORDER BY s.date
        """, (d_from, d_to, person)).fetchall()
        result = {}
        for r in rows:
            d = r[0]
            if d not in result:
                result[d] = {"efficiency": r[1], "rem_pct": r[2], "awake_s": r[3]}
        return result
    except Exception:
        return {}


def load_stress(conn, d_from, d_to, person: str = OWN_PERSON_ID):
    """Load daily stress scores. Returns dict {date: stress_score}."""
    if not _table_exists(conn, "daily_stress"):
        return {}
    try:
        rows = conn.execute("""
            SELECT date, stress_score
            FROM daily_stress
            WHERE date >= ? AND date <= ?
              AND stress_score IS NOT NULL AND stress_score > 0
            ORDER BY date
        """, (d_from, d_to)).fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


def load_oura_sleep_model(conn, d_from, d_to):
    """Load Oura main-sleep sessions with latency, restless, hypnogram.

    Returns dict {date: {latency_s, restless_periods, bedtime_start,
                          bedtime_end, sleep_phase_30_sec}}.
    """
    if not _table_exists(conn, "oura_sleep_model"):
        return {}
    try:
        rows = conn.execute("""
            SELECT day, latency, restless_periods,
                   bedtime_start, bedtime_end, sleep_phase_30_sec
            FROM oura_sleep_model
            WHERE day >= ? AND day <= ?
              AND (sleep_type = 'main' OR sleep_type IS NULL)
              AND total_sleep_duration > 3600
            ORDER BY day
        """, (d_from, d_to)).fetchall()
        result = {}
        for r in rows:
            d = r[0]
            if d not in result:
                result[d] = {
                    "latency_s":          r[1],
                    "restless_periods":   r[2],
                    "bedtime_start":      r[3],
                    "bedtime_end":        r[4],
                    "sleep_phase_30_sec": r[5],
                }
        return result
    except Exception:
        return {}


def _find_schlafstadium(ep_ts: str, oura_schlaf: dict) -> str | None:
    """Match episode timestamp to Oura session window, return sleep stage label."""
    _labels = {"1": t("Tiefschlaf","Deep"), "2": t("Leichtschlaf","Light"),
               "3": t("REM","REM"),         "4": t("Wach","Awake")}
    try:
        ep_dt = datetime.fromisoformat(ep_ts.replace("Z", "+00:00"))
        for sess in oura_schlaf.values():
            bs, be, ph = sess.get("bedtime_start"), sess.get("bedtime_end"), sess.get("sleep_phase_30_sec")
            if not bs or not be or not ph:
                continue
            bt = datetime.fromisoformat(bs.replace("Z", "+00:00"))
            bte = datetime.fromisoformat(be.replace("Z", "+00:00"))
            if bt <= ep_dt <= bte:
                idx = int((ep_dt - bt).total_seconds() // 30)
                return _labels.get(ph[idx]) if 0 <= idx < len(ph) else None
    except Exception:
        pass
    return None


def load_gewicht(conn, d_from, d_to, person: str = OWN_PERSON_ID):
    """Load body weight from body_composition. Returns list of (date, weight_kg)."""
    if not _table_exists(conn, "body_composition"):
        return []
    try:
        return conn.execute("""
            SELECT date, weight_kg
            FROM body_composition
            WHERE date >= ? AND date <= ?
              AND person = ?
              AND weight_kg IS NOT NULL
            ORDER BY date
        """, (d_from, d_to, person)).fetchall()
    except Exception:
        return []




def freq_woechentlich(episoden):
    """Return sorted list of (week_str, count) and dict {week: count}."""
    by_week = defaultdict(int)
    for r in episoden:
        w = _iso_week(r[0])
        by_week[w] += 1
    weeks_sorted = sorted(by_week.keys())
    return weeks_sorted, by_week


def freq_monatlich(episoden):
    """Return sorted list of (month_str, count) and dict {month: count}."""
    by_month = defaultdict(int)
    for r in episoden:
        ym = r[0][:7]
        by_month[ym] += 1
    months_sorted = sorted(by_month.keys())
    return months_sorted, by_month


def dauer_trend(episoden):
    """Return list of (date_str, dauer_min) pairs sorted chronologically."""
    return [(r[0][:10], r[2]) for r in episoden if r[2] is not None]


def tageszeit_verteilung(episoden):
    """Return dict {tageszeit: count}."""
    dist = defaultdict(int)
    for r in episoden:
        dist[r[7] or t("Unbekannt", "Unknown")] += 1
    return dict(dist)


def ecg_zusammenfassung(ecg_rows):
    """Return dict {classification: count} and list of afib rows."""
    by_class = defaultdict(int)
    afib_rows = []
    for r in ecg_rows:
        cls = r[1] or t("Unbekannt", "Unknown")
        by_class[cls] += 1
        if cls == "atrial_fibrillation":
            afib_rows.append(r)
    return dict(by_class), afib_rows


def burden_monatlich(episoden, d_from, d_to):
    """Estimate AFib burden % per month = episode minutes / total minutes."""
    by_month_min = defaultdict(float)
    by_month_total = defaultdict(float)

    # Total minutes per calendar month in range
    try:
        dt = datetime.strptime(d_from, "%Y-%m-%d")
        dt_end = datetime.strptime(d_to, "%Y-%m-%d")
        while dt <= dt_end:
            ym = dt.strftime("%Y-%m")
            by_month_total[ym] += 24 * 60
            dt += timedelta(days=1)
    except Exception:
        pass

    for r in episoden:
        ym = r[0][:7]
        if r[2]:
            by_month_min[ym] += r[2]

    result = {}
    for ym in sorted(by_month_total.keys()):
        total = by_month_total[ym]
        epi = by_month_min.get(ym, 0.0)
        result[ym] = round(epi / total * 100, 4) if total > 0 else 0.0
    return result


def hrv_korrelation(episoden, hrv_dict):
    """
    Compare RMSSD on nights before/after episode days vs. episode-free days.

    Returns dict with keys: 'vor_epi', 'nach_epi', 'ohne_epi', 'n_vor', 'n_nach', 'n_ohne'.
    """
    epi_dates = set(r[0][:10] for r in episoden)

    vor_vals, nach_vals, ohne_vals = [], [], []

    for date_str, rmssd in hrv_dict.items():
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        next_d = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
        prev_d = (dt - timedelta(days=1)).strftime("%Y-%m-%d")

        is_vor  = next_d in epi_dates   # HRV measured night before an episode day
        is_nach = prev_d in epi_dates   # HRV measured night after an episode day
        is_epi  = date_str in epi_dates

        if is_vor:
            vor_vals.append(rmssd)
        if is_nach:
            nach_vals.append(rmssd)
        if not is_epi and not is_vor and not is_nach:
            ohne_vals.append(rmssd)

    return {
        "vor_epi":  _avg(vor_vals),
        "nach_epi": _avg(nach_vals),
        "ohne_epi": _avg(ohne_vals),
        "n_vor":   len(vor_vals),
        "n_nach":  len(nach_vals),
        "n_ohne":  len(ohne_vals),
    }


def druck_korrelation(episoden, druck_dict):
    """
    Compare mean pressure on episode days vs. episode-free days.

    Also computes day-to-day delta and checks if delta is higher on episode days.
    Returns dict with relevant stats.
    """
    if not druck_dict:
        return None

    epi_dates = set(r[0][:10] for r in episoden)
    dates_sorted = sorted(druck_dict.keys())

    # Day-to-day delta
    delta_by_date = {}
    for i in range(1, len(dates_sorted)):
        prev_d = dates_sorted[i - 1]
        curr_d = dates_sorted[i]
        delta_by_date[curr_d] = druck_dict[curr_d] - druck_dict[prev_d]

    epi_hpa, no_epi_hpa = [], []
    epi_delta, no_epi_delta = [], []

    for d in dates_sorted:
        hpa = druck_dict[d]
        if d in epi_dates:
            epi_hpa.append(hpa)
            if d in delta_by_date:
                epi_delta.append(delta_by_date[d])
        else:
            no_epi_hpa.append(hpa)
            if d in delta_by_date:
                no_epi_delta.append(delta_by_date[d])

    return {
        "epi_hpa_avg":     _avg(epi_hpa),
        "no_epi_hpa_avg":  _avg(no_epi_hpa),
        "n_epi_days":      len(epi_hpa),
        "n_no_epi_days":   len(no_epi_hpa),
        "epi_delta_avg":   _avg(epi_delta),
        "no_epi_delta_avg": _avg(no_epi_delta),
        "n_epi_delta":     len(epi_delta),
        "n_no_epi_delta":  len(no_epi_delta),
    }


# ── Report builder ────────────────────────────────────────────────────────────

def build_report(episoden, ecg_rows, hrv_dict, druck_dict, trainings,
                     blutdruck, atemfrequenz, spo2_nacht, schlaf, stress_scores, gewicht,
                     d_from, d_to, afes_spo2=None, oura_schlaf=None, pre_ep_ctx=None,
                     ecg_logger_rows=None, pollen_dict=None, air_quality=None,
                     indoor_air=None, hrv_sources=None, hrv_confidence=None):
    lines = [
        t(f"## AFib-Burden-Analyse — {d_from} bis {d_to}\n",
          f"## AFib Burden Analysis — {d_from} to {d_to}\n"),
    ]

    # ── 0. Data availability overview
    lines.append(t("### Datenverfügbarkeit\n", "### Data Availability\n"))
    lines.append(t(f"  Arrhythmie-Episoden:  {len(episoden)}",
                   f"  Arrhythmia episodes:  {len(episoden)}"))
    lines.append(t(f"  ECG-Sessions (AW):    {len(ecg_rows)}",
                   f"  ECG sessions (AW):    {len(ecg_rows)}"))
    _ecg_log = ecg_logger_rows or []
    lines.append(t(f"  ECGLogger-Sessions:   {len(_ecg_log)}",
                   f"  ECGLogger sessions:   {len(_ecg_log)}"))
    _hrv_src_str = ", ".join(f"{src}: {n}" for src, n in (hrv_sources or {}).items()) or "–"
    lines.append(t(
        f"  HRV-Nächte:           {len(hrv_dict)}  (Quelle: {_hrv_src_str}; Konfidenz: {hrv_confidence or '–'})",
        f"  HRV nights:           {len(hrv_dict)}  (source: {_hrv_src_str}; confidence: {hrv_confidence or '–'})"))
    lines.append(t(f"  Luftdrucktage:        {len(druck_dict)}",
                   f"  Pressure days:        {len(druck_dict)}"))
    lines.append(t(f"  Blutdruck-Messungen:  {len(blutdruck)}",
                   f"  Blood pressure meas.: {len(blutdruck)}"))
    lines.append(t(f"  Atemfrequenz-Tage:    {len(atemfrequenz)}",
                   f"  Resp. rate days:      {len(atemfrequenz)}"))
    lines.append(t(f"  SpO2-Nächte:          {len(spo2_nacht)}",
                   f"  SpO2 nights:          {len(spo2_nacht)}"))
    lines.append(t(f"  Schlaf-Nächte:        {len(schlaf)}",
                   f"  Sleep nights:         {len(schlaf)}"))
    lines.append(t(f"  Stress-Score-Tage:    {len(stress_scores)}",
                   f"  Stress score days:    {len(stress_scores)}"))
    lines.append(t(f"  Gewichtsmessungen:    {len(gewicht)}\n",
                   f"  Weight measurements:  {len(gewicht)}\n"))

    # Sparse data warnings
    if len(episoden) < 10:
        lines.append(t(
            f"  WARNUNG:  Nur {len(episoden)} Episode(n) — Trendaussagen nicht belastbar.",
            f"  WARNING: Only {len(episoden)} episode(s) — trend statements are not reliable."
        ))
    if len(hrv_dict) < 14:
        lines.append(t(
            "  WARNUNG:  Weniger als 14 HRV-Nächte — Korrelation nicht aussagekräftig.",
            "  WARNING: Fewer than 14 HRV nights — correlation not meaningful."
        ))
    if len(druck_dict) < 7:
        lines.append(t(
            "  WARNUNG:  Keine oder unzureichende Luftdruckdaten (weather_station).",
            "  WARNING: No or insufficient pressure data (weather_station)."
        ))
    lines.append("")

    if not episoden:
        lines.append(t(
            "Keine Arrhythmie-Episoden im gewählten Zeitraum. "
            "Bitte zuerst compute_arrhythmia.py ausführen.",
            "No arrhythmia episodes in the selected period. "
            "Please run compute_arrhythmia.py first."
        ))
        return "\n".join(lines)

    # ── 0b. CV-basierte Klassifikation
    cv_tiers = cv_klassifikation(episoden)
    n_total = len(episoden)
    n_afib_suspect = len(cv_tiers["suspect"]) + len(cv_tiers["high"])
    n_no_afib      = len(cv_tiers["low"]) + len(cv_tiers["borderline"])

    lines.append(t(
        "### 0b. CV-basierte Arrhythmie-Klassifikation\n",
        "### 0b. CV-Based Arrhythmia Classification\n",
    ))
    lines.append(t(
        "  Arrhythmie-Episoden aus ppi_raw werden per Coefficient of Variation (CV = SD/Mean × 100 %)\n"
        "  der PPI-Intervalle klassifiziert. CV ≥ 10 % ist charakteristisch für Vorhofflimmern,\n"
        "  niedrigere CV-Werte deuten auf Ektopie, PVCs oder Mess-Artefakte hin.",
        "  Arrhythmia episodes from ppi_raw are classified by Coefficient of Variation (CV = SD/Mean × 100 %)\n"
        "  of PPI intervals. CV ≥ 10 % is characteristic of atrial fibrillation;\n"
        "  lower CV values suggest ectopy, PVCs, or measurement artefacts.",
    ))
    lines.append("")

    def _pct(v): return int(v * 100)
    tier_labels = [
        ("no_cv_data", t("Kein CV-Wert (NULL)", "No CV data (NULL)"),        "—"),
        ("low",        t(f"< {_pct(CV_AFIB_LOW)} %  — physiolog. HRV / Artefakt",
                          f"< {_pct(CV_AFIB_LOW)} %  — physiological HRV / artefact"), "✓ kein AFib-Signal"),
        ("borderline", t(f"{_pct(CV_AFIB_LOW)}–{_pct(CV_AFIB_MID)} %  — Ektopie / PVCs",
                          f"{_pct(CV_AFIB_LOW)}–{_pct(CV_AFIB_MID)} %  — ectopy / PVCs"),  "~ Grauzone"),
        ("suspect",    t(f"{_pct(CV_AFIB_MID)}–{_pct(CV_AFIB_HIGH)} %  — AFib-verdächtig",
                          f"{_pct(CV_AFIB_MID)}–{_pct(CV_AFIB_HIGH)} %  — AFib suspect"),  "⚠ AFib-Verdacht"),
        ("high",       t(f"≥ {_pct(CV_AFIB_HIGH)} %  — hochgr. AFib-verdächtig",
                          f"≥ {_pct(CV_AFIB_HIGH)} %  — highly AFib suspect"),        "⚠⚠ AFib wahrscheinlich"),
    ]
    for key, label, flag in tier_labels:
        n = len(cv_tiers[key])
        pct = round(n / n_total * 100, 1) if n_total > 0 else 0.0
        bar = "█" * int(pct / 5)
        lines.append(f"  {label:<48}  {n:>4}  ({pct:>5.1f}%)  {bar}")

    lines.append("")
    lines.append(t(
        f"  AFib-verdächtig gesamt (CV ≥ {_pct(CV_AFIB_MID)} %):  {n_afib_suspect} / {n_total} "
        f"({round(n_afib_suspect/n_total*100,1) if n_total else 0} %)",
        f"  AFib suspect total (CV ≥ {_pct(CV_AFIB_MID)} %):      {n_afib_suspect} / {n_total} "
        f"({round(n_afib_suspect/n_total*100,1) if n_total else 0} %)",
    ))
    lines.append(t(
        f"  Nicht-AFib-Signal  (CV <  {_pct(CV_AFIB_MID)} %):  {n_no_afib} / {n_total} "
        f"({round(n_no_afib/n_total*100,1) if n_total else 0} %)",
        f"  Non-AFib signal    (CV <  {_pct(CV_AFIB_MID)} %):  {n_no_afib} / {n_total} "
        f"({round(n_no_afib/n_total*100,1) if n_total else 0} %)",
    ))
    if n_afib_suspect == 0:
        lines.append(t(
            f"\n  HINWEIS: Keine Episode überschreitet den CV-Schwellwert für AFib-Verdacht (≥ {_pct(CV_AFIB_MID)} %).\n"
            "  Die Apple Watch EKG-Klassifikationen (atrial_fibrillation) sind die einzige\n"
            "  verlässliche AFib-Quelle in diesem Datensatz.",
            f"\n  NOTE: No episode exceeds the CV threshold for AFib suspicion (≥ {_pct(CV_AFIB_MID)} %).\n"
            "  Apple Watch ECG classifications (atrial_fibrillation) are the only\n"
            "  reliable AFib source in this dataset.",
        ))
    lines.append("")

    # AFib-Verdacht: Burden getrennt berechnen
    if n_afib_suspect > 0:
        lines.append(t(
            f"  AFib-Burden (nur CV ≥ {_pct(CV_AFIB_MID)} % Episoden):",
            f"  AFib burden (CV ≥ {_pct(CV_AFIB_MID)} % episodes only):",
        ))
        episoden_afib = cv_tiers["suspect"] + cv_tiers["high"]
        burden_afib = burden_monatlich(episoden_afib, d_from, d_to)
        for ym, pct in burden_afib.items():
            if pct > 0:
                bar = "█" * int(pct * 10)
                lines.append(f"    {ym}  {pct:.4f}%  {bar}")
        lines.append("")

    # ── 0c. Sport-Überlappung
    sport_stats = sport_mapping(episoden, trainings)
    n_during  = len(sport_stats["during"])
    n_outside = len(sport_stats["outside"])
    sport_counts = sport_stats["sport_counts"]

    lines.append(t("### 0c. Sport-Überlappung\n", "### 0c. Exercise Overlap\n"))
    lines.append(t(
        "  Prüft ob Episoden zeitlich mit einer Training-Session überlappen\n"
        "  (Artefakt-Test: Brustgurt-Bewegungsartefakte erhöhen den CV).\n",
        "  Checks whether episodes temporally overlap a training session\n"
        "  (artefact test: chest strap motion artefacts elevate CV).\n",
    ))

    pct_during = round(n_during / n_total * 100, 1) if n_total else 0
    pct_outside = round(n_outside / n_total * 100, 1) if n_total else 0
    lines.append(t(
        f"  Während Training:     {n_during:>4}  ({pct_during} %)",
        f"  During training:      {n_during:>4}  ({pct_during} %)",
    ))
    lines.append(t(
        f"  Außerhalb Training:   {n_outside:>4}  ({pct_outside} %)",
        f"  Outside training:     {n_outside:>4}  ({pct_outside} %)",
    ))

    if sport_counts:
        lines.append("")
        lines.append(t("  Sportarten bei Trainings-Episoden:", "  Sports during training episodes:"))
        for sport, cnt in sorted(sport_counts.items(), key=lambda x: -x[1]):
            pct = round(cnt / n_during * 100, 1) if n_during else 0
            bar = "█" * int(pct / 5)
            lines.append(f"    {sport:<24}  {cnt:>4}  ({pct:.1f}%)  {bar}")

    if n_outside > 0:
        outside_cv = [ep[4] for ep in sport_stats["outside"] if ep[4]]
        outside_tz = {}
        for ep in sport_stats["outside"]:
            tz = ep[7] or "?"
            outside_tz[tz] = outside_tz.get(tz, 0) + 1
        lines.append("")
        lines.append(t(
            "  Episoden außerhalb Training — Tageszeit:",
            "  Episodes outside training — time of day:",
        ))
        for tz, cnt in sorted(outside_tz.items(), key=lambda x: -x[1]):
            lines.append(f"    {tz:<14}  {cnt}")
        if outside_cv:
            avg_cv_out = sum(outside_cv) / len(outside_cv)
            lines.append(t(
                f"  Ø CV außerhalb Training: {avg_cv_out*100:.1f} %  — "
                + ("⚠ AFib-Verdacht auch ohne Training" if avg_cv_out >= CV_AFIB_MID else "niedrig"),
                f"  Avg CV outside training: {avg_cv_out*100:.1f} %  — "
                + ("⚠ AFib suspect outside training too" if avg_cv_out >= CV_AFIB_MID else "low"),
            ))

    if n_during == n_total:
        lines.append(t(
            "\n  ⚠ ALLE Episoden fallen in Trainingsfenster → hohe Artefakt-Wahrscheinlichkeit.\n"
            "  Empfehlung: Holter-EKG ohne Sport zum Vergleich.",
            "\n  ⚠ ALL episodes fall within training windows → high artefact probability.\n"
            "  Recommendation: Holter ECG without exercise for comparison.",
        ))
    elif n_during > n_total * 0.7:
        lines.append(t(
            f"\n  ⚠ {pct_during} % der Episoden während Training → Artefakt möglich, aber\n"
            f"  {n_outside} Episoden außerhalb Training deuten auf echtes Rhythmusproblem.",
            f"\n  ⚠ {pct_during} % of episodes during training → artefacts possible, but\n"
            f"  {n_outside} episodes outside training suggest a genuine rhythm problem.",
        ))
    elif n_outside > n_total * 0.5:
        lines.append(t(
            f"\n  Mehrheit ({pct_outside} %) der Episoden außerhalb Training →\n"
            "  Artefakt als alleinige Erklärung unwahrscheinlich.",
            f"\n  Majority ({pct_outside} %) of episodes outside training →\n"
            "  artefact alone unlikely to explain all findings.",
        ))
    lines.append("")

    # ── 0d. Multi-Source Vorlauf-Kontext (60 Min vor Episodenbeginn)
    lines.append(t("### 0d. Physiologischer Vorlauf-Kontext (60 Min vor Episode)\n",
                   "### 0d. Physiological Pre-Episode Context (60 min before)\n"))
    ctx_list = pre_ep_ctx or []
    ctx_with_data = [c for c in ctx_list if c["n_readings"] > 0]
    if not ctx_list:
        lines.append(t("  Keine Kontextdaten geladen.", "  No context data loaded."))
    elif not ctx_with_data:
        lines.append(t(
            "  Für keine Episode waren Messdaten im 60-Min-Fenster verfügbar.",
            "  No measurement data available in the 60-min window for any episode."
        ))
    else:
        n_bursts = len(ctx_with_data)
        n_burst_ep = sum(c["burst_size"] for c in ctx_with_data)
        multi = [c for c in ctx_with_data if c["burst_size"] > 1]
        burst_info = (t(f"  ({len(multi)} Bursts mit je ≥2 Episoden zusammengefasst)",
                        f"  ({len(multi)} bursts with ≥2 episodes merged)")
                      if multi else "")
        lines.append(t(
            f"  {n_bursts} Bursts / {n_burst_ep} Episoden haben Kontextdaten.  {burst_info}\n",
            f"  {n_bursts} bursts / {n_burst_ep} episodes have context data.  {burst_info}\n",
        ))

        # ── Aggregierte Statistik
        hr_avgs     = [c["hr_avg"]      for c in ctx_with_data if c["hr_avg"]      is not None]
        stress_avgs = [c["stress_avg"]  for c in ctx_with_data if c["stress_avg"]  is not None]
        hrv_avgs    = [c["hrv_avg"]     for c in ctx_with_data if c["hrv_avg"]     is not None]
        bb_vals_ctx = [c["body_battery"]for c in ctx_with_data if c["body_battery"]is not None]
        rr_avgs     = [c["rr_avg"]      for c in ctx_with_data if c["rr_avg"]      is not None]
        oura_s_avgs = [c["oura_stress_avg"]   for c in ctx_with_data if c["oura_stress_avg"]   is not None]
        oura_r_avgs = [c["oura_recovery_avg"] for c in ctx_with_data if c["oura_recovery_avg"] is not None]

        # HR
        if hr_avgs:
            src_label = ctx_with_data[0]["hr_source"] or "?"
            lines.append(t(
                f"  Herzfrequenz ({src_label}):  Ø {_avg(hr_avgs)} bpm  "
                f"[{min(hr_avgs):.0f}–{max(hr_avgs):.0f}]  (n={len(hr_avgs)} Episoden)",
                f"  Heart rate ({src_label}):    avg {_avg(hr_avgs)} bpm  "
                f"[{min(hr_avgs):.0f}–{max(hr_avgs):.0f}]  (n={len(hr_avgs)} episodes)",
            ))
            trend_counts: dict[str, int] = {}
            for c in ctx_with_data:
                if c["hr_trend"]:
                    trend_counts[c["hr_trend"]] = trend_counts.get(c["hr_trend"], 0) + 1
            if trend_counts:
                trend_str = "  ".join(f"{k}: {v}" for k, v in sorted(trend_counts.items()))
                lines.append(t(f"  HR-Trend vor Episode:  {trend_str}",
                               f"  HR trend pre-episode:  {trend_str}"))

        # Garmin Stress
        if stress_avgs:
            lines.append(t(
                f"  Garmin Stress (60 Min Ø): {_avg(stress_avgs):.0f}  "
                f"[{min(stress_avgs):.0f}–{max(stress_avgs):.0f}]  (n={len(stress_avgs)})",
                f"  Garmin stress (60 min avg): {_avg(stress_avgs):.0f}  "
                f"[{min(stress_avgs):.0f}–{max(stress_avgs):.0f}]  (n={len(stress_avgs)})",
            ))
            high_stress = sum(1 for v in stress_avgs if v >= 50)
            if high_stress:
                lines.append(t(
                    f"  ⚠ {high_stress} Episode(n) mit Garmin-Stress ≥ 50 vor Beginn.",
                    f"  ⚠ {high_stress} episode(s) with Garmin stress ≥ 50 before onset."
                ))

        # Oura Daytime Stress
        if oura_s_avgs or oura_r_avgs:
            lines.append(t(
                f"  Oura Stress (Ø):    {_avg(oura_s_avgs) or '—'}  "
                f"  Recovery (Ø): {_avg(oura_r_avgs) or '—'}  (n={len(oura_s_avgs)})",
                f"  Oura stress (avg):  {_avg(oura_s_avgs) or '—'}  "
                f"  Recovery (avg): {_avg(oura_r_avgs) or '—'}  (n={len(oura_s_avgs)})",
            ))

        # HRV
        if hrv_avgs:
            src_label = ctx_with_data[0]["hrv_source"] or "?"
            lines.append(t(
                f"  HRV RMSSD ({src_label}):  Ø {_avg(hrv_avgs)} ms  (n={len(hrv_avgs)})",
                f"  HRV RMSSD ({src_label}):  avg {_avg(hrv_avgs)} ms  (n={len(hrv_avgs)})",
            ))

        # Body Battery
        if bb_vals_ctx:
            lines.append(t(
                f"  Body Battery (Garmin):  Ø {_avg(bb_vals_ctx):.0f}  "
                f"[{min(bb_vals_ctx):.0f}–{max(bb_vals_ctx):.0f}]  (n={len(bb_vals_ctx)})",
                f"  Body Battery (Garmin):  avg {_avg(bb_vals_ctx):.0f}  "
                f"[{min(bb_vals_ctx):.0f}–{max(bb_vals_ctx):.0f}]  (n={len(bb_vals_ctx)})",
            ))
            low_bb = sum(1 for v in bb_vals_ctx if v <= 25)
            if low_bb:
                lines.append(t(
                    f"  ⚠ {low_bb} Episode(n) mit Body Battery ≤ 25 (erschöpft).",
                    f"  ⚠ {low_bb} episode(s) with body battery ≤ 25 (depleted)."
                ))

        # Respiratory Rate
        if rr_avgs:
            src_label = ctx_with_data[0]["rr_source"] or "?"
            lines.append(t(
                f"  Atemfrequenz ({src_label}):  Ø {_avg(rr_avgs)} /min  (n={len(rr_avgs)})",
                f"  Resp. rate ({src_label}):    avg {_avg(rr_avgs)} /min  (n={len(rr_avgs)})",
            ))

        # ── Per-Episode-Detail für auffällige Episoden
        # Zeige Episoden mit hohem Stress oder niedrigem Body Battery
        notable = [c for c in ctx_with_data
                   if (c["stress_avg"] and c["stress_avg"] >= 60)
                   or (c["body_battery"] is not None and c["body_battery"] <= 20)
                   or (c["hr_trend"] == t("steigend","rising"))]
        if notable:
            lines.append("")
            lines.append(t(
                "  Auffällige Bursts (Stress ≥ 60 | BB ≤ 20 | HR steigend):",
                "  Notable bursts (stress ≥ 60 | BB ≤ 20 | HR rising):",
            ))
            for c in notable[:10]:
                parts = []
                if c["hr_avg"]:      parts.append(f"HR {c['hr_avg']:.0f} bpm {c['hr_trend'] or ''}")
                if c["stress_avg"]:  parts.append(f"Stress {c['stress_avg']:.0f}")
                if c["body_battery"] is not None: parts.append(f"BB {c['body_battery']:.0f}")
                if c["hrv_avg"]:     parts.append(f"HRV {c['hrv_avg']:.0f} ms")
                ts_label = (f"{c['ep_ts'][:16]}–{c['burst_end'][11:]}"
                            if c["burst_end"] else c["ep_ts"][:16])
                n_label  = f" ×{c['burst_size']}" if c["burst_size"] > 1 else ""
                lines.append(f"    {ts_label}{n_label}  {' | '.join(parts)}")

    lines.append("")

    # ── 1. Episode frequency: weekly and monthly
    weeks_sorted, by_week = freq_woechentlich(episoden)
    months_sorted, by_month = freq_monatlich(episoden)

    lines.append(t("### 1. Episodenhäufigkeit\n", "### 1. Episode Frequency\n"))

    if weeks_sorted:
        w_counts = [by_week[w] for w in weeks_sorted]
        avg_week = _avg(w_counts)
        max_week = max(w_counts)
        lines.append(t(f"  Wochen erfasst:      {len(weeks_sorted)}",
                       f"  Weeks recorded:      {len(weeks_sorted)}"))
        lines.append(t(f"  Episoden/Woche Ø:    {avg_week}",
                       f"  Episodes/week avg:   {avg_week}"))
        lines.append(t(f"  Maximale Woche:      {max_week} Episoden ({weeks_sorted[w_counts.index(max_week)]})",
                       f"  Peak week:           {max_week} episodes ({weeks_sorted[w_counts.index(max_week)]})"))

    if months_sorted:
        lines.append("")
        lines.append(t("  Monatliche Häufigkeit:", "  Monthly frequency:"))
        for ym in months_sorted:
            bar = "█" * min(by_month[ym], 40)
            lines.append(f"    {ym}  {by_month[ym]:>4}  {bar}")

    lines.append("")

    # ── 2. Episode duration trend
    dauer_pairs = dauer_trend(episoden)
    lines.append(t("### 2. Episodendauer-Trend\n", "### 2. Episode Duration Trend\n"))

    if dauer_pairs:
        dauer_vals = [d for _, d in dauer_pairs]
        lines.append(t(f"  Ø Dauer:    {_avg(dauer_vals)} min",
                       f"  Avg dur.:   {_avg(dauer_vals)} min"))
        lines.append(t(f"  Median:     {_median(dauer_vals)} min",
                       f"  Median:     {_median(dauer_vals)} min"))
        lines.append(t(f"  Min / Max:  {min(dauer_vals):.1f} / {max(dauer_vals):.1f} min",
                       f"  Min / Max:  {min(dauer_vals):.1f} / {max(dauer_vals):.1f} min"))
        n_kurz  = sum(1 for v in dauer_vals if v < 10)
        n_mittel = sum(1 for v in dauer_vals if 10 <= v < 60)
        n_lang  = sum(1 for v in dauer_vals if v >= 60)
        lines.append(t(f"  <10 min: {n_kurz}  |  10–60 min: {n_mittel}  |  ≥60 min: {n_lang}",
                       f"  <10 min: {n_kurz}  |  10–60 min: {n_mittel}  |  ≥60 min: {n_lang}"))

        # Trend: first third vs. last third
        if len(dauer_vals) >= 6:
            third = len(dauer_vals) // 3
            early_avg = _avg(dauer_vals[:third])
            late_avg  = _avg(dauer_vals[-third:])
            if early_avg and late_avg:
                delta = round(late_avg - early_avg, 2)
                direction = (t("länger werdend", "lengthening") if delta > 0
                             else t("kürzer werdend", "shortening") if delta < 0
                             else t("stabil", "stable"))
                lines.append(t(
                    f"  Trend: {direction} (früh: {early_avg} min → spät: {late_avg} min, Δ{delta:+.2f})",
                    f"  Trend: {direction} (early: {early_avg} min → late: {late_avg} min, Δ{delta:+.2f})"
                ))

    lines.append("")

    # ── 3. Circadian pattern
    tz_dist = tageszeit_verteilung(episoden)
    n_total = len(episoden)
    lines.append(t("### 3. Zirkadianes Muster (Tageszeit)\n",
                   "### 3. Circadian Pattern (Time of Day)\n"))
    tz_order = [
        t("Nacht", "Night"), t("Morgen", "Morning"),
        t("Tag", "Day"), t("Nachmittag", "Afternoon"),
        t("Abend", "Evening"), t("Unbekannt", "Unknown"),
    ]
    # Also handle any values not in the fixed order
    all_tz = set(tz_dist.keys()) | set(tz_order)
    for tz in tz_order:
        cnt = tz_dist.get(tz, 0)
        if cnt == 0:
            continue
        pct = round(cnt / n_total * 100, 1)
        bar = "█" * int(pct / 5)
        lines.append(f"  {tz:<14}  {cnt:>4}  ({pct:>5.1f}%)  {bar}")
    for tz in sorted(all_tz - set(tz_order)):
        cnt = tz_dist.get(tz, 0)
        if cnt == 0:
            continue
        pct = round(cnt / n_total * 100, 1)
        bar = "█" * int(pct / 5)
        lines.append(f"  {tz:<14}  {cnt:>4}  ({pct:>5.1f}%)  {bar}")

    if tz_dist:
        peak_tz = max(tz_dist, key=tz_dist.get)
        lines.append(t(f"\n  Häufigste Tageszeit: {peak_tz} ({tz_dist[peak_tz]} Episoden)",
                       f"\n  Most frequent time:  {peak_tz} ({tz_dist[peak_tz]} episodes)"))
    lines.append("")

    # ── 4. ECG classification summary
    lines.append(t("### 4. ECG-Klassifikationen (Apple Watch)\n",
                   "### 4. ECG Classifications (Apple Watch)\n"))
    if ecg_rows:
        by_class, afib_ecg = ecg_zusammenfassung(ecg_rows)
        n_ecg = len(ecg_rows)
        for cls in sorted(by_class.keys()):
            cnt = by_class[cls]
            pct = round(cnt / n_ecg * 100, 1)
            lines.append(f"  {cls:<30}  {cnt:>3}  ({pct:.1f}%)")
        if afib_ecg:
            lines.append("")
            lines.append(t(f"  AFib-Klassifikationen: {len(afib_ecg)} von {n_ecg} ({round(len(afib_ecg)/n_ecg*100,1)}%)",
                           f"  AFib classifications: {len(afib_ecg)} of {n_ecg} ({round(len(afib_ecg)/n_ecg*100,1)}%)"))
            # Trend of afib ECGs over time
            afib_months = defaultdict(int)
            for r in afib_ecg:
                afib_months[r[0][:7]] += 1
            if len(afib_months) >= 2:
                lines.append(t("  AFib-EKG Monatsverteilung:", "  AFib ECG monthly distribution:"))
                for ym in sorted(afib_months.keys()):
                    lines.append(f"    {ym}: {afib_months[ym]}")
        else:
            lines.append(t("  Keine Apple Watch AFib-Klassifikationen im Zeitraum.",
                           "  No Apple Watch AFib classifications in the period."))
    else:
        lines.append(t("  WARNUNG:  Keine ECG-Sessions im gewählten Zeitraum.",
                       "  WARNING: No ECG sessions in the selected period."))
    lines.append("")

    # ── 4b. ECGLogger-Sessionen (Polar H10)
    lines.append(t("### 4b. ECGLogger-Sessionen (Polar H10)\n",
                   "### 4b. ECGLogger Sessions (Polar H10)\n"))
    _ecg_log = ecg_logger_rows or []
    if not _ecg_log:
        lines.append(t(
            "  Keine ECGLogger-Sessionen im Zeitraum (ecg_logger_sessions).",
            "  No ECGLogger sessions in the period (ecg_logger_sessions).",
        ))
    else:
        n_log      = len(_ecg_log)
        n_suspected = sum(1 for r in _ecg_log if r[2])   # afib_suspected
        n_tachy    = sum(1 for r in _ecg_log if r[11])   # tachy_sustained
        n_brady    = sum(1 for r in _ecg_log if r[12])   # brady_flag
        scores     = [r[3] for r in _ecg_log if r[3] is not None]
        durations  = [r[1] for r in _ecg_log if r[1] is not None]
        lines.append(t(
            f"  Sessionen gesamt:    {n_log}  |  Ø Dauer: {_avg(durations) or '—'} s",
            f"  Sessions total:      {n_log}  |  Avg duration: {_avg(durations) or '—'} s",
        ))
        lines.append(t(
            f"  AFib vermutet:       {n_suspected} / {n_log}"
            + (f"  ({round(n_suspected/n_log*100,1)} %)" if n_log else ""),
            f"  AFib suspected:      {n_suspected} / {n_log}"
            + (f"  ({round(n_suspected/n_log*100,1)} %)" if n_log else ""),
        ))
        if n_tachy or n_brady:
            lines.append(t(
                f"  Tachykardie (HR>100 ≥30 Schläge): {n_tachy}  |  Bradykardie (<50): {n_brady}",
                f"  Tachycardia (HR>100 ≥30 beats): {n_tachy}  |  Bradycardia (<50): {n_brady}",
            ))

        # AFib-Score-Verteilung
        if scores:
            n_low  = sum(1 for s in scores if s < 0.2)
            n_mid  = sum(1 for s in scores if 0.2 <= s < 0.5)
            n_high = sum(1 for s in scores if 0.5 <= s < 0.8)
            n_vhigh= sum(1 for s in scores if s >= 0.8)
            lines.append(t(
                "\n  AFib-Score-Verteilung (0–1, Konsens aus 5 Metriken):",
                "\n  AFib score distribution (0–1, consensus of 5 metrics):",
            ))
            for label, cnt in [("<0.2 — unauffällig", n_low), ("0.2–0.5 — grenzwertig", n_mid),
                                ("0.5–0.8 — AFib-Verdacht", n_high), ("≥0.8 — AFib wahrscheinlich", n_vhigh)]:
                bar = "█" * cnt
                lines.append(f"    {label:<36}  {cnt:>3}  {bar}")

        # Detail-Tabelle für auffällige Sessionen
        suspected_rows = [r for r in _ecg_log if r[2]]
        if suspected_rows:
            lines.append(t(
                "\n  AFib-verdächtige Sessionen (afib_suspected=1):",
                "\n  AFib-suspected sessions (afib_suspected=1):",
            ))
            lines.append(f"  {'Datum/Zeit':<20} {'Score':>6} {'Votes':>6} {'Poinc.':>7} {'SampEn':>7} {'TPR':>6} {'CV_RR':>6} {'HR':>5}  Tags")
            for r in suspected_rows:
                sid, dur, _, score, votes, poinc, sampen, tpr, cv_rr, hr, art, _, _, tags = r
                tags_s = (tags or "")[:20]
                lines.append(
                    f"  {sid[:19]:<20} {score or 0:>6.2f} {votes or 0:>6}  "
                    f"{poinc or 0:>6.3f}  {sampen or 0:>6.3f}  {tpr or 0:>5.3f}  "
                    f"{cv_rr or 0:>5.3f}  {hr or 0:>4.0f}  {tags_s}"
                )
        elif n_log > 0:
            lines.append(t(
                "\n  Keine Session mit afib_suspected=1 im Zeitraum.",
                "\n  No session with afib_suspected=1 in the period.",
            ))

        # Monatlicher Trend
        by_month_log: dict[str, dict] = {}
        for r in _ecg_log:
            ym = r[0][:7]
            e  = by_month_log.setdefault(ym, {"n": 0, "susp": 0})
            e["n"]    += 1
            e["susp"] += 1 if r[2] else 0
        if len(by_month_log) >= 2:
            lines.append(t("\n  Monatlicher Trend:", "\n  Monthly trend:"))
            for ym in sorted(by_month_log):
                e = by_month_log[ym]
                bar = "▪" * e["susp"]
                lines.append(f"    {ym}  {e['n']:>3} Sessions  {e['susp']:>2} AFib-verd.  {bar}")
    lines.append("")

    # ── 5. Burden estimate per month
    lines.append(t("### 5. AFib-Burden-Schätzung (Episodenminuten / Gesamtminuten)\n",
                   "### 5. AFib Burden Estimate (episode minutes / total minutes)\n"))
    burden = burden_monatlich(episoden, d_from, d_to)
    if burden:
        for ym, pct in burden.items():
            bar = "█" * int(pct * 10)  # 1 block per 0.1%
            has_epi = any(r[0][:7] == ym for r in episoden)
            tag = "" if has_epi else t("  (keine Episoden)", "  (no episodes)")
            lines.append(f"  {ym}  {pct:>7.4f}%  {bar}{tag}")
        valid_burdens = [v for v in burden.values() if v > 0]
        if valid_burdens:
            lines.append(t(f"\n  Ø Burden (Monate mit Episoden): {_avg(valid_burdens):.4f}%",
                           f"\n  Avg burden (months with episodes): {_avg(valid_burdens):.4f}%"))
            max_b = max(valid_burdens)
            # ASSERT (Healey 2012, NEJM): subklin. AF >6 min/Tag → 2.5× Schlaganfallrisiko.
            # 6 min × 30 Tage = 180 min/Monat ÷ 43 800 min/Monat ≈ 0.41 % → Schwelle 0.4 %.
            # ESC 2020: jede detektierte AF ist klinisch dokumentationspflichtig.
            # LOOP (Svendsen 2021, NEJM): ILR-gesteuertes OAK → kein sign. Schlaganfall-Reduktion
            #   (HR 0.80, 95%-KI 0.61–1.06) — Burden allein beweist keine Kausalität.
            if max_b > 0.4:
                lines.append(t(
                    "  ⚠ HINWEIS: Monatlicher Burden >0.4% (≈ >6 min/Tag).\n"
                    "    ASSERT-Studie (2012): subklinische AF >6 min/Tag → 2.5× Schlaganfallrisiko.\n"
                    "    ESC 2020: Jede detektierte AF ist klinisch dokumentationspflichtig.\n"
                    "    Einschränkung — LOOP-Studie (2021): ILR-gesteuertes OAK reduzierte\n"
                    "    Schlaganfall nicht signifikant (HR 0.80) — Burden ≠ bewiesene Kausalität.",
                    "  ⚠ NOTE: Monthly burden >0.4% (≈ >6 min/day).\n"
                    "    ASSERT trial (2012): subclinical AF >6 min/day → 2.5× stroke risk.\n"
                    "    ESC 2020: Every detected AF requires clinical documentation.\n"
                    "    Caveat — LOOP trial (2021): ILR-guided OAC did not significantly reduce\n"
                    "    stroke (HR 0.80) — burden alone is not proven causal.",
                ))
            # TRENDS (Daoud 2009, JACC EP): AF-Burden ≥5.5 h/Tag (~23%/Monat) → 2× Schlaganfallrisiko.
            if max_b > 23.0:
                lines.append(t(
                    "  ⚠⚠ KRITISCH: Burden >23% — TRENDS-Studie (2009): AF ≥5.5 h/Tag assoziiert\n"
                    "     mit 2× Schlaganfallrisiko gegenüber AF <5.5 h/Tag.",
                    "  ⚠⚠ CRITICAL: Burden >23% — TRENDS trial (2009): AF ≥5.5 h/day associated\n"
                    "     with 2× stroke risk compared to AF <5.5 h/day.",
                ))

    # Apple Watch AFib event count per month (parallel to PPI burden — not a burden %)
    aw_afib_by_month: dict[str, int] = defaultdict(int)
    aw_total_by_month: dict[str, int] = defaultdict(int)
    for r in ecg_rows:
        ym = r[0][:7]
        aw_total_by_month[ym] += 1
        if r[1] == "atrial_fibrillation":
            aw_afib_by_month[ym] += 1

    n_aw_afib_total = sum(aw_afib_by_month.values())
    if n_aw_afib_total > 0:
        lines.append("")
        lines.append(t(
            "  Apple Watch AFib-Klassifikationen (Ereigniszähler — kein Burden-%):",
            "  Apple Watch AFib classifications (event count — not a burden %):",
        ))
        all_months = sorted(set(burden.keys()) | set(aw_total_by_month.keys()))
        for ym in all_months:
            n_afib = aw_afib_by_month.get(ym, 0)
            n_ecg  = aw_total_by_month.get(ym, 0)
            if n_ecg == 0:
                continue
            pct_ecg = round(n_afib / n_ecg * 100, 0)
            bar = "▪" * n_afib
            lines.append(f"    {ym}  {n_afib:>2} AFib / {n_ecg:>3} EKGs  ({pct_ecg:.0f}%)  {bar}")
        n_aw_total_ecg = sum(aw_total_by_month.values())
        pct_total = round(n_aw_afib_total / n_aw_total_ecg * 100, 1) if n_aw_total_ecg else 0
        lines.append(t(
            f"\n  AW gesamt: {n_aw_afib_total} AFib-EKG(s) / {n_aw_total_ecg} Sessions ({pct_total}%)",
            f"\n  AW total:  {n_aw_afib_total} AFib ECG(s) / {n_aw_total_ecg} sessions ({pct_total}%)",
        ))
        lines.append(t(
            "  Hinweis: 30-Sek.-Spot-Messung — kein Zeitanteil ableitbar, nur Ereignisfrequenz.\n"
            "  ESC 2020: Jede klinisch detektierte AF ist dokumentationspflichtig (unabhängig von Burden).",
            "  Note: 30-sec spot measurement — time fraction not derivable, event frequency only.\n"
            "  ESC 2020: Every clinically detected AF requires documentation (regardless of burden).",
        ))
    lines.append("")

    # ── 6. HRV correlation
    lines.append(t("### 6. HRV-Korrelation (Schlaf-RMSSD vor/nach Episodentagen)\n",
                   "### 6. HRV Correlation (sleep RMSSD before/after episode days)\n"))
    if hrv_dict:
        hrv_stats = hrv_korrelation(episoden, hrv_dict)
        lines.append(t(
            f"  HRV Nacht vor Episode:    {hrv_stats['vor_epi']} ms  (n={hrv_stats['n_vor']})",
            f"  HRV night before episode: {hrv_stats['vor_epi']} ms  (n={hrv_stats['n_vor']})"
        ))
        lines.append(t(
            f"  HRV Nacht nach Episode:   {hrv_stats['nach_epi']} ms  (n={hrv_stats['n_nach']})",
            f"  HRV night after episode:  {hrv_stats['nach_epi']} ms  (n={hrv_stats['n_nach']})"
        ))
        lines.append(t(
            f"  HRV episodenfreie Nächte: {hrv_stats['ohne_epi']} ms  (n={hrv_stats['n_ohne']})",
            f"  HRV episode-free nights:  {hrv_stats['ohne_epi']} ms  (n={hrv_stats['n_ohne']})"
        ))

        if hrv_stats["vor_epi"] and hrv_stats["ohne_epi"]:
            diff = round(hrv_stats["vor_epi"] - hrv_stats["ohne_epi"], 2)
            direction = t("niedriger", "lower") if diff < 0 else t("höher", "higher")
            lines.append(t(
                f"\n  Δ vor Episode vs. episodenfrei: {diff:+.2f} ms ({direction})",
                f"\n  Δ before episode vs. episode-free: {diff:+.2f} ms ({direction})"
            ))
        if hrv_stats["n_vor"] < 5:
            lines.append(t(
                "  WARNUNG:  Zu wenige überlappende Datenpunkte für belastbare HRV-Aussage.",
                "  WARNING: Too few overlapping data points for a reliable HRV statement."
            ))
    else:
        lines.append(t("  WARNUNG:  Keine HRV-Daten (hrv_rmssd) im gewählten Zeitraum, auf keinem Gerät.",
                       "  WARNING: No HRV data (hrv_rmssd) in the selected period, on any device."))
    lines.append("")

    # ── 7. Pressure correlation
    lines.append(t("### 7. Luftdruck-Korrelation\n", "### 7. Barometric Pressure Correlation\n"))
    if druck_dict:
        d_stats = druck_korrelation(episoden, druck_dict)
        if d_stats:
            lines.append(t(
                f"  Mittlerer Luftdruck an Episodentagen:       {d_stats['epi_hpa_avg']} hPa  (n={d_stats['n_epi_days']})",
                f"  Mean pressure on episode days:              {d_stats['epi_hpa_avg']} hPa  (n={d_stats['n_epi_days']})"
            ))
            lines.append(t(
                f"  Mittlerer Luftdruck an episodenfreien Tagen: {d_stats['no_epi_hpa_avg']} hPa  (n={d_stats['n_no_epi_days']})",
                f"  Mean pressure on episode-free days:          {d_stats['no_epi_hpa_avg']} hPa  (n={d_stats['n_no_epi_days']})"
            ))
            lines.append(t(
                f"  Ø Druckveränderung Vortag (Episodentage):    {d_stats['epi_delta_avg']:+.2f} hPa  (n={d_stats['n_epi_delta']})"
                if d_stats["epi_delta_avg"] is not None else
                "  Ø Druckveränderung Vortag (Episodentage):    n.a.",
                f"  Avg pressure change prev day (episode days): {d_stats['epi_delta_avg']:+.2f} hPa  (n={d_stats['n_epi_delta']})"
                if d_stats["epi_delta_avg"] is not None else
                "  Avg pressure change prev day (episode days): n/a"
            ))
            lines.append(t(
                f"  Ø Druckveränderung Vortag (ohne Episode):    {d_stats['no_epi_delta_avg']:+.2f} hPa  (n={d_stats['n_no_epi_delta']})"
                if d_stats["no_epi_delta_avg"] is not None else
                "  Ø Druckveränderung Vortag (ohne Episode):    n.a.",
                f"  Avg pressure change prev day (no episode):   {d_stats['no_epi_delta_avg']:+.2f} hPa  (n={d_stats['n_no_epi_delta']})"
                if d_stats["no_epi_delta_avg"] is not None else
                "  Avg pressure change prev day (no episode):   n/a"
            ))
            if d_stats["n_epi_days"] < 5:
                lines.append(t(
                    "  WARNUNG:  Wenige Episodentage mit Luftdruckdaten — Korrelation unsicher.",
                    "  WARNING: Few episode days with pressure data — correlation uncertain."
                ))
    else:
        lines.append(t(
            "  WARNUNG:  Keine Luftdruckdaten in weather_station für diesen Zeitraum.",
            "  WARNING: No pressure data in weather_station for this period."
        ))

    lines.append("")

    # ── 7b. Umgebungskontext (Pollen, Luftqualität, Indoor)
    pollen_dict = pollen_dict or {}
    air_quality = air_quality or {}
    indoor_air  = indoor_air  or {}
    epi_dates_env = set(r[0][:10] for r in episoden)

    def _env_avg(data_dict, key):
        epi_v  = [data_dict[d][key] for d in epi_dates_env  if d in data_dict and data_dict[d].get(key) is not None]
        rest_v = [data_dict[d][key] for d in data_dict if d not in epi_dates_env and data_dict[d].get(key) is not None]
        ea = round(sum(epi_v)  / len(epi_v),  1) if epi_v  else None
        ra = round(sum(rest_v) / len(rest_v), 1) if rest_v else None
        return ea, ra

    lines.append(t("### 7b. Umgebungskontext\n", "### 7b. Environmental Context\n"))

    if pollen_dict:
        lines.append(t("**Pollen (grains/m³) — Episodentag vs. sonstige Tage:**",
                       "**Pollen (grains/m³) — episode day vs. other days:**"))
        for key, label in [("birch","Birke"), ("alder","Erle"), ("grass","Gräser"),
                           ("mugwort","Beifuß"), ("ragweed","Ragweed"), ("total","Gesamt")]:
            ea, ra = _env_avg(pollen_dict, key)
            if ea is not None or ra is not None:
                lines.append(f"  {label:<10} Episodentag: {ea or '—':>6}  |  ohne Episode: {ra or '—':>6}")
    else:
        lines.append(t("  Keine Pollen-Daten.", "  No pollen data."))

    if air_quality:
        lines.append(t("\n**Luftqualität — Episodentag vs. sonstige Tage:**",
                       "\n**Air quality — episode day vs. other days:**"))
        for key, label in [("aqi_eu_mean","AQI EU"), ("pm25_mean","PM2.5 µg/m³"),
                           ("pm10_mean","PM10 µg/m³"), ("o3_mean","O₃ µg/m³"),
                           ("dust_mean","Staub µg/m³")]:
            ea, ra = _env_avg(air_quality, key)
            if ea is not None or ra is not None:
                lines.append(f"  {label:<15} Episodentag: {ea or '—':>6}  |  ohne Episode: {ra or '—':>6}")
    else:
        lines.append(t("  Keine Luftqualitätsdaten.", "  No air quality data."))

    if indoor_air:
        n_indoor = len(indoor_air)
        lines.append(t(f"\n**Indoor-Luft (n={n_indoor} Tage):**",
                       f"\n**Indoor air (n={n_indoor} days):**"))
        all_stypes = sorted({st for day in indoor_air.values() for st in day})
        for stype in all_stypes:
            vals = [indoor_air[d][stype] for d in indoor_air if stype in indoor_air[d]]
            if vals:
                lines.append(f"  {stype:<20} Ø {round(sum(vals)/len(vals),2)}")

    lines.append("")

    # ── 8. Blutdruck
    lines.append(t("### 8. Blutdruck\n", "### 8. Blood Pressure\n"))
    if blutdruck:
        epi_dates_bp = set(r[0][:10] for r in episoden)
        epi_sys, noepi_sys, epi_dia, noepi_dia = [], [], [], []
        for row in blutdruck:
            d, sys, dia, _ = row
            if d in epi_dates_bp:
                if sys:  epi_sys.append(sys)
                if dia:  epi_dia.append(dia)
            else:
                if sys:  noepi_sys.append(sys)
                if dia:  noepi_dia.append(dia)
        lines.append(t(
            f"  Messungen gesamt: {len(blutdruck)}  |  an Episodentagen: {len(epi_sys)}",
            f"  Total measurements: {len(blutdruck)}  |  on episode days: {len(epi_sys)}"
        ))
        lines.append(t(
            f"  Systolisch  — Episodentag: {_avg(epi_sys) or '—'} mmHg  |  ohne Episode: {_avg(noepi_sys) or '—'} mmHg",
            f"  Systolic    — episode day: {_avg(epi_sys) or '—'} mmHg  |  no episode:  {_avg(noepi_sys) or '—'} mmHg"
        ))
        lines.append(t(
            f"  Diastolisch — Episodentag: {_avg(epi_dia) or '—'} mmHg  |  ohne Episode: {_avg(noepi_dia) or '—'} mmHg",
            f"  Diastolic   — episode day: {_avg(epi_dia) or '—'} mmHg  |  no episode:  {_avg(noepi_dia) or '—'} mmHg"
        ))
        lines.append("")
        lines.append(t("  Alle Messungen:", "  All measurements:"))
        for row in blutdruck:
            d, sys, dia, hr_bp = row
            ep_flag = " ⚠ Episode" if d in epi_dates_bp else ""
            lines.append(f"    {d}  {sys or '?'}/{dia or '?'} mmHg  HR {hr_bp or '?'} bpm{ep_flag}")
        high_sys = [r[1] for r in blutdruck if r[1] and r[1] >= 140]
        if high_sys:
            lines.append(t(
                f"\n  ⚠ {len(high_sys)} Messung(en) mit Systole ≥ 140 mmHg.",
                f"\n  ⚠ {len(high_sys)} measurement(s) with systolic ≥ 140 mmHg."
            ))
    else:
        lines.append(t(
            "  Keine Blutdruckmessungen im Zeitraum (blood_pressure).",
            "  No blood pressure measurements in the period (blood_pressure)."
        ))
    lines.append("")

    # ── 9. Atemfrequenz
    lines.append(t("### 9. Atemfrequenz\n", "### 9. Respiratory Rate\n"))
    if atemfrequenz:
        epi_dates_rr = set(r[0][:10] for r in episoden)
        epi_rr, noepi_rr = [], []
        for d, rr in atemfrequenz.items():
            (epi_rr if d in epi_dates_rr else noepi_rr).append(rr)
        all_rr = list(atemfrequenz.values())
        lines.append(t(
            f"  Tage mit Daten: {len(atemfrequenz)}  |  Ø Atemfrequenz: {_avg(all_rr)} /min",
            f"  Days with data: {len(atemfrequenz)}  |  Avg resp. rate: {_avg(all_rr)} /min"
        ))
        lines.append(t(
            f"  Episodentage:  {_avg(epi_rr) or '—'} /min  (n={len(epi_rr)})",
            f"  Episode days:  {_avg(epi_rr) or '—'} /min  (n={len(epi_rr)})"
        ))
        lines.append(t(
            f"  Ohne Episode:  {_avg(noepi_rr) or '—'} /min  (n={len(noepi_rr)})",
            f"  No episode:    {_avg(noepi_rr) or '—'} /min  (n={len(noepi_rr)})"
        ))
        high_rr = sum(1 for rr in all_rr if rr > 20)
        if high_rr:
            lines.append(t(
                f"\n  ⚠ {high_rr} Tag(e) mit Atemfrequenz > 20 /min.",
                f"\n  ⚠ {high_rr} day(s) with respiratory rate > 20 /min."
            ))
    else:
        lines.append(t(
            "  Keine Atemfrequenz-Daten im Zeitraum (measurements: respiratory_rate).",
            "  No respiratory rate data in the period (measurements: respiratory_rate)."
        ))
    lines.append("")

    # ── 10. SpO2 nächtlich
    lines.append(t("### 10. SpO2 (nächtlich)\n", "### 10. SpO2 (Nocturnal)\n"))
    if spo2_nacht:
        epi_dates_spo2 = set(r[0][:10] for r in episoden)
        epi_spo2, noepi_spo2 = [], []
        for d, spo2 in spo2_nacht.items():
            (epi_spo2 if d in epi_dates_spo2 else noepi_spo2).append(spo2)
        all_spo2 = list(spo2_nacht.values())
        n_low90 = sum(1 for v in all_spo2 if v < 90)
        n_low94 = sum(1 for v in all_spo2 if v < 94)
        lines.append(t(
            f"  Nächte mit Daten:    {len(spo2_nacht)}  |  Ø min. SpO2: {_avg(all_spo2)} %",
            f"  Nights with data:    {len(spo2_nacht)}  |  Avg min SpO2: {_avg(all_spo2)} %"
        ))
        lines.append(t(
            f"  Episodennächte:  {_avg(epi_spo2) or '—'} % min  (n={len(epi_spo2)})",
            f"  Episode nights:  {_avg(epi_spo2) or '—'} % min  (n={len(epi_spo2)})"
        ))
        lines.append(t(
            f"  Ohne Episode:    {_avg(noepi_spo2) or '—'} % min  (n={len(noepi_spo2)})",
            f"  No episode:      {_avg(noepi_spo2) or '—'} % min  (n={len(noepi_spo2)})"
        ))
        if n_low90 > 0:
            lines.append(t(
                f"\n  ⚠ {n_low90} Nacht/Nächte mit SpO2 < 90 % — Verdacht auf nächtliche Hypoxie.",
                f"\n  ⚠ {n_low90} night(s) with SpO2 < 90 % — nocturnal hypoxia suspected."
            ))
        elif n_low94 > 0:
            lines.append(t(
                f"\n  ⚠ {n_low94} Nacht/Nächte mit SpO2 < 94 % — grenzwertig niedrig.",
                f"\n  ⚠ {n_low94} night(s) with SpO2 < 94 % — borderline low."
            ))
    else:
        lines.append(t(
            "  Keine nächtlichen SpO2-Daten im Zeitraum.",
            "  No nocturnal SpO2 data in the period."
        ))
    lines.append("")

    # ── 10b. SpO2-Vornacht × AFES-Level
    lines.append(t("### 10b. SpO2-Vornacht × AFES-Level\n",
                   "### 10b. Previous-night SpO2 × AFES Level\n"))
    level_stats, afes_detail = afes_spo2 if afes_spo2 else ({}, [])
    if level_stats:
        lines.append(t(
            "  SpO2 <90% in der Nacht vor dem AFES-Tag:",
            "  SpO2 <90% the night before each AFES day:"
        ))
        for lvl in ("critical", "high", "moderate", "low"):
            s = level_stats.get(lvl)
            if not s:
                continue
            pct90 = (100 * s["n_under90"] / s["n_spo2"]) if s["n_spo2"] else None
            pct_str = f"{pct90:.0f}%" if pct90 is not None else "—"
            lines.append(
                f"  {lvl:<10}  n={s['n_total']:4d}  mit SpO2={s['n_spo2']:3d}"
                f"  <90%: {s['n_under90']:2d} ({pct_str})"
                f"  <94%: {s['n_under94']:2d}"
            )
        lines.append("")
        # Detail-Tabelle: high+critical mit SpO2 <90% Vornacht
        low_detail = [(d, sc, lv, sp) for d, sc, lv, sp in afes_detail
                      if sp is not None and sp < 90]
        if low_detail:
            lines.append(t(
                "  High/Critical-Tage mit SpO2 <90% Vornacht:",
                "  High/critical days with SpO2 <90% the previous night:"
            ))
            for d, sc, lv, sp in sorted(low_detail):
                lines.append(f"    {d}  Score={sc:3d}  [{lv}]  SpO2-Min {sp:.1f}%  ⚠")
        elif afes_detail:
            lines.append(t(
                "  Kein High/Critical-Tag mit SpO2 <90% Vornacht im Zeitraum.",
                "  No high/critical day with SpO2 <90% previous night in period."
            ))
    else:
        lines.append(t("  Keine AFES-Daten im Zeitraum.",
                       "  No AFES data in period."))
    lines.append("")

    # ── 11. Schlafqualität
    lines.append(t("### 11. Schlafqualität\n", "### 11. Sleep Quality\n"))
    if schlaf:
        epi_dates_sl = set(r[0][:10] for r in episoden)
        epi_eff, noepi_eff = [], []
        epi_rem, noepi_rem = [], []
        epi_awk, noepi_awk = [], []
        for d, m in schlaf.items():
            in_epi = d in epi_dates_sl
            if m["efficiency"] is not None:
                (epi_eff if in_epi else noepi_eff).append(m["efficiency"])
            if m["rem_pct"] is not None:
                (epi_rem if in_epi else noepi_rem).append(m["rem_pct"])
            if m["awake_s"] is not None:
                (epi_awk if in_epi else noepi_awk).append(m["awake_s"])
        lines.append(t(f"  Nächte mit Daten: {len(schlaf)}", f"  Nights with data: {len(schlaf)}"))
        all_eff = epi_eff + noepi_eff
        if all_eff:
            lines.append("")
            lines.append(t("  Schlafeffizienz:", "  Sleep efficiency:"))
            lines.append(t(
                f"    Gesamt Ø:      {_avg(all_eff)} %",
                f"    Overall avg:   {_avg(all_eff)} %"
            ))
            lines.append(t(
                f"    Episodennacht: {_avg(epi_eff) or '—'} %  (n={len(epi_eff)})",
                f"    Episode night: {_avg(epi_eff) or '—'} %  (n={len(epi_eff)})"
            ))
            lines.append(t(
                f"    Ohne Episode:  {_avg(noepi_eff) or '—'} %  (n={len(noepi_eff)})",
                f"    No episode:    {_avg(noepi_eff) or '—'} %  (n={len(noepi_eff)})"
            ))
        all_rem = epi_rem + noepi_rem
        if all_rem:
            lines.append("")
            lines.append(t("  REM-Anteil:", "  REM fraction:"))
            lines.append(t(
                f"    Episodennacht: {_avg(epi_rem) or '—'} %  |  Ohne Episode: {_avg(noepi_rem) or '—'} %",
                f"    Episode night: {_avg(epi_rem) or '—'} %  |  No episode:   {_avg(noepi_rem) or '—'} %"
            ))
        all_awk = epi_awk + noepi_awk
        if all_awk:
            lines.append("")
            lines.append(t("  Wachzeit (Minuten):", "  Awake time (minutes):"))

            def _awk_min(lst):
                v = _avg(lst)
                return round(v / 60, 1) if v else "—"

            lines.append(t(
                f"    Episodennacht: {_awk_min(epi_awk)} min  |  Ohne Episode: {_awk_min(noepi_awk)} min",
                f"    Episode night: {_awk_min(epi_awk)} min  |  No episode:   {_awk_min(noepi_awk)} min"
            ))
    else:
        lines.append(t(
            "  Keine Schlafdaten im Zeitraum (sessions + session_metrics).",
            "  No sleep data in the period (sessions + session_metrics)."
        ))

    # Oura-Erweiterung: Latenz + Restless Periods (aus oura_sleep_model)
    oura_schlaf = oura_schlaf or {}
    if oura_schlaf:
        epi_dates_ou = set(r[0][:10] for r in episoden)
        epi_lat, noepi_lat = [], []
        epi_rst, noepi_rst = [], []
        for d, s in oura_schlaf.items():
            in_epi = d in epi_dates_ou
            if s["latency_s"] is not None:
                (epi_lat if in_epi else noepi_lat).append(s["latency_s"])
            if s["restless_periods"] is not None:
                (epi_rst if in_epi else noepi_rst).append(s["restless_periods"])
        lines.append("")
        lines.append(t("  Oura Schlaf-Latenz (Einschlafdauer):", "  Oura sleep latency (onset):"))
        lines.append(t(
            f"    Episodennacht: {_avg(epi_lat) or '—'} s  (n={len(epi_lat)})"
            f"  |  Ohne Episode: {_avg(noepi_lat) or '—'} s  (n={len(noepi_lat)})",
            f"    Episode night: {_avg(epi_lat) or '—'} s  (n={len(epi_lat)})"
            f"  |  No episode:   {_avg(noepi_lat) or '—'} s  (n={len(noepi_lat)})",
        ))
        lines.append(t("  Oura Restless Periods:", "  Oura restless periods:"))
        lines.append(t(
            f"    Episodennacht: {_avg(epi_rst) or '—'}  (n={len(epi_rst)})"
            f"  |  Ohne Episode: {_avg(noepi_rst) or '—'}  (n={len(noepi_rst)})",
            f"    Episode night: {_avg(epi_rst) or '—'}  (n={len(epi_rst)})"
            f"  |  No episode:   {_avg(noepi_rst) or '—'}  (n={len(noepi_rst)})",
        ))
    lines.append("")

    # ── 11b. Schlafstadium bei nächtlichen Episoden (Oura Hypnogramm)
    lines.append(t("### 11b. Schlafstadium bei nächtlichen Episoden (Oura)\n",
                   "### 11b. Sleep Stage During Nocturnal Episodes (Oura)\n"))
    nacht_episoden = [ep for ep in episoden
                      if ep[7] in (t("Nacht","Night"), t("Morgen","Morning"), "Nacht", "Morgen", "Night", "Morning")]
    if not oura_schlaf:
        lines.append(t("  Keine Oura-Schlafdaten im Zeitraum (oura_sleep_model).",
                       "  No Oura sleep data in period (oura_sleep_model)."))
    elif not nacht_episoden:
        lines.append(t(
            "  Keine nächtlichen Episoden im Zeitraum — Schlafstadium-Lookup n.v.",
            "  No nocturnal episodes in period — sleep stage lookup n/a."
        ))
    else:
        stage_counts: dict[str, int] = {}
        no_match = 0
        for ep in nacht_episoden:
            stage = _find_schlafstadium(ep[0], oura_schlaf)
            if stage:
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
            else:
                no_match += 1
        if stage_counts:
            n_match = sum(stage_counts.values())
            lines.append(t(
                f"  {n_match} von {len(nacht_episoden)} nächtlichen Episoden zugeordnet:",
                f"  {n_match} of {len(nacht_episoden)} nocturnal episodes matched:"
            ))
            for stage in (t("REM","REM"), t("Leichtschlaf","Light"),
                          t("Tiefschlaf","Deep"), t("Wach","Awake")):
                cnt = stage_counts.get(stage, 0)
                if cnt == 0:
                    continue
                pct = round(cnt / n_match * 100, 1)
                bar = "█" * int(pct / 10)
                lines.append(f"    {stage:<14}  {cnt:>3}  ({pct:.1f}%)  {bar}")
            if no_match:
                lines.append(t(
                    f"  {no_match} Episode(n) außerhalb Oura-Schlaffenster (kein Match).",
                    f"  {no_match} episode(s) outside Oura sleep window (no match)."
                ))
        else:
            lines.append(t(
                "  Nächtliche Episoden gefunden, aber kein Oura-Schlaffenster passend.",
                "  Nocturnal episodes found but no matching Oura sleep window."
            ))
    lines.append("")

    # ── 12. Stress-Score
    lines.append(t("### 12. Stress-Score\n", "### 12. Stress Score\n"))
    if stress_scores:
        epi_dates_st = set(r[0][:10] for r in episoden)
        epi_stress, noepi_stress = [], []
        for d, score in stress_scores.items():
            (epi_stress if d in epi_dates_st else noepi_stress).append(score)
        all_stress = list(stress_scores.values())
        lines.append(t(
            f"  Tage mit Daten: {len(stress_scores)}  |  Ø Score: {_avg(all_stress)}",
            f"  Days with data: {len(stress_scores)}  |  Avg score: {_avg(all_stress)}"
        ))
        lines.append(t(
            f"  Episodentage:  {_avg(epi_stress) or '—'}  (n={len(epi_stress)})",
            f"  Episode days:  {_avg(epi_stress) or '—'}  (n={len(epi_stress)})"
        ))
        lines.append(t(
            f"  Ohne Episode:  {_avg(noepi_stress) or '—'}  (n={len(noepi_stress)})",
            f"  No episode:    {_avg(noepi_stress) or '—'}  (n={len(noepi_stress)})"
        ))
        if epi_stress and noepi_stress:
            avg_e = _avg(epi_stress) or 0
            avg_n = _avg(noepi_stress) or 0
            diff = round(avg_e - avg_n, 1)
            lines.append(t(
                f"\n  Δ Episodentag vs. episodenfrei: {diff:+.1f}",
                f"\n  Δ episode day vs. episode-free: {diff:+.1f}"
            ))
            if diff > 5:
                lines.append(t(
                    "  → Stress-Score an Episodentagen erhöht.",
                    "  → Stress score elevated on episode days."
                ))
            elif diff < -5:
                lines.append(t(
                    "  → Stress-Score an Episodentagen niedriger (kein klarer Stressauslöser).",
                    "  → Stress score lower on episode days (no clear stress trigger)."
                ))
    else:
        lines.append(t(
            "  Keine Stress-Score-Daten im Zeitraum (daily_stress).",
            "  No stress score data in the period (daily_stress)."
        ))
    lines.append("")

    # ── 13. Körpergewicht
    lines.append(t("### 13. Körpergewicht\n", "### 13. Body Weight\n"))
    if gewicht:
        w_vals = [r[1] for r in gewicht]
        lines.append(t(
            f"  Messungen: {len(gewicht)}  |  Ø {_avg(w_vals)} kg  |  "
            f"Min {min(w_vals):.1f} kg  |  Max {max(w_vals):.1f} kg",
            f"  Measurements: {len(gewicht)}  |  Avg {_avg(w_vals)} kg  |  "
            f"Min {min(w_vals):.1f} kg  |  Max {max(w_vals):.1f} kg"
        ))
        if len(gewicht) >= 2:
            first_d, first_w = gewicht[0]
            last_d,  last_w  = gewicht[-1]
            delta_w = round(last_w - first_w, 1)
            lines.append(t(
                f"  Verlauf: {first_w} kg ({first_d}) → {last_w} kg ({last_d})  Δ{delta_w:+.1f} kg",
                f"  Trend:   {first_w} kg ({first_d}) → {last_w} kg ({last_d})  Δ{delta_w:+.1f} kg"
            ))
    else:
        lines.append(t(
            "  Keine Körpergewicht-Daten im Zeitraum (body_composition).",
            "  No body weight data in the period (body_composition)."
        ))
    lines.append("")

    return "\n".join(lines)


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(episoden, hrv_dict, d_from, d_to):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        BG   = "#1A1A2E"
        AXES = "#16213E"
        TXT  = "#E0E0E0"
        TICK = "#AAAAAA"
        SPINE = "#555577"

        fig, axes = plt.subplots(3, 1, figsize=(14, 11), facecolor=BG)
        fig.suptitle(
            t(f"AFib-Burden-Analyse  {d_from} – {d_to}",
              f"AFib Burden Analysis  {d_from} – {d_to}"),
            color=TXT, fontsize=13, fontweight="bold"
        )

        for ax in axes:
            ax.set_facecolor(AXES)
            ax.tick_params(colors=TICK, labelsize=8)
            for spine in ax.spines.values():
                spine.set_edgecolor(SPINE)

        # ── Subplot 1: weekly episode count bar chart
        ax1 = axes[0]
        weeks_sorted, by_week = freq_woechentlich(episoden)
        if weeks_sorted:
            week_dts  = [_week_monday(w) for w in weeks_sorted]
            week_cnts = [by_week[w] for w in weeks_sorted]
            # Filter None dates
            valid = [(dt, cnt) for dt, cnt in zip(week_dts, week_cnts) if dt]
            if valid:
                dts, cnts = zip(*valid)
                ax1.bar(dts, cnts, width=5, color="#E17055", alpha=0.85,
                        label=t("Episoden/Woche", "Episodes/week"))
                ax1.set_ylabel(t("Episoden / Woche", "Episodes / week"), color=TXT, fontsize=9)
                ax1.set_title(t("Wöchentliche Episodenhäufigkeit", "Weekly Episode Frequency"),
                              color=TXT, fontsize=10)
                ax1.legend(fontsize=8, facecolor=AXES, labelcolor=TXT)
                ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
                fig.autofmt_xdate(rotation=30)
        else:
            ax1.text(0.5, 0.5, t("Keine Daten", "No data"),
                     ha="center", va="center", color=TXT, transform=ax1.transAxes)

        # ── Subplot 2: episode duration scatter + moving average
        ax2 = axes[1]
        dauer_pairs = dauer_trend(episoden)
        if dauer_pairs:
            try:
                dts2  = [datetime.strptime(d, "%Y-%m-%d") for d, _ in dauer_pairs]
                vals2 = [v for _, v in dauer_pairs]
                ax2.scatter(dts2, vals2, color="#74B9FF", alpha=0.65, s=25, zorder=3,
                            label=t("Episodendauer", "Episode duration"))
                # Moving average (window 8 episodes)
                ma = _moving_avg(vals2, window=8)
                ma_dts  = [dts2[i] for i in range(len(ma)) if ma[i] is not None]
                ma_vals = [v for v in ma if v is not None]
                if ma_dts:
                    ax2.plot(ma_dts, ma_vals, color="#FDCB6E", linewidth=2,
                             alpha=0.9, label=t("8-Ep. gleitender Ø", "8-ep. moving avg"))
                ax2.set_ylabel(t("Dauer (min)", "Duration (min)"), color=TXT, fontsize=9)
                ax2.set_title(t("Episodendauer-Trend", "Episode Duration Trend"), color=TXT, fontsize=10)
                ax2.legend(fontsize=8, facecolor=AXES, labelcolor=TXT)
                ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
            except Exception:
                ax2.text(0.5, 0.5, t("Plot-Fehler", "Plot error"),
                         ha="center", va="center", color=TXT, transform=ax2.transAxes)
        else:
            ax2.text(0.5, 0.5, t("Keine Dauerdaten", "No duration data"),
                     ha="center", va="center", color=TXT, transform=ax2.transAxes)

        # ── Subplot 3: tageszeit bar chart
        ax3 = axes[2]
        tz_dist = tageszeit_verteilung(episoden)
        if tz_dist:
            tz_labels = sorted(tz_dist.keys())
            tz_values = [tz_dist[k] for k in tz_labels]
            bar_colors = {
                t("Nacht", "Night"):      "#6C5CE7",
                t("Morgen", "Morning"):   "#FDCB6E",
                t("Tag", "Day"):          "#00B894",
                t("Nachmittag", "Afternoon"): "#FD79A8",
                t("Abend", "Evening"):    "#E17055",
                t("Unbekannt", "Unknown"): "#636E72",
            }
            colors = [bar_colors.get(lbl, "#74B9FF") for lbl in tz_labels]
            bars = ax3.bar(tz_labels, tz_values, color=colors, alpha=0.85)
            ax3.set_ylabel(t("Anzahl Episoden", "Episode count"), color=TXT, fontsize=9)
            ax3.set_title(t("Zirkadianes Muster (Tageszeit)", "Circadian Pattern (Time of Day)"),
                          color=TXT, fontsize=10)
            ax3.tick_params(axis="x", colors=TXT, labelsize=9)
            # Value labels on bars
            for bar, val in zip(bars, tz_values):
                ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                         str(val), ha="center", va="bottom", color=TXT, fontsize=8)
        else:
            ax3.text(0.5, 0.5, t("Keine Tageszeitdaten", "No time-of-day data"),
                     ha="center", va="center", color=TXT, transform=ax3.transAxes)

        plt.tight_layout(rect=[0, 0, 1, 0.97])
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUT_DIR / f"afib_burden_{ts}.png"
        fig.savefig(str(path), dpi=130, bbox_inches="tight", facecolor=BG)
        plt.close()
        print(t(f"Plot: {path}", f"Plot: {path}"))
    except Exception as e:
        print(t(f"Plot fehlgeschlagen: {e}", f"Plot failed: {e}"))


# ── LLM ──────────────────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1200)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


# ── Save ──────────────────────────────────────────────────────────────────────

def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"afib_burden_{ts}.md"
    content = f"# AFib-Burden-Analyse\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(
        description=t("AFib-Burden-Analyse — Häufigkeit, Dauer und Trends",
                      "AFib burden analysis — frequency, duration and trends")
    )
    parser.add_argument("--from",   dest="date_from", default=(datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d"),
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to",     dest="date_to",   default=today,
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--all",    dest="all_data",  action="store_true",
                        help=t("Alle verfügbaren Daten (überschreibt --from/--to)",
                               "All available data (overrides --from/--to)"))
    parser.add_argument("--plot",   action="store_true",
                        help=t("Plots erzeugen und speichern", "Generate and save plots"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Interpretation überspringen", "Skip LLM interpretation"))
    parser.add_argument("--person", default=None,
                        help=t("Person (default: OWN_PERSON_ID)", "Person (default: OWN_PERSON_ID)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    person = args.person or OWN_PERSON_ID

    if args.all_data:
        conn_tmp = open_db()
        earliest = conn_tmp.execute(
            "SELECT MIN(DATE(episode_start)) FROM arrhythmie_episoden WHERE person=?"
            , (person,)).fetchone()[0]
        if not earliest:
            # Device-agnostic: polar_nightly_hrv is empty without a Polar
            # device, so the fallback must look at measurements directly,
            # not one brand's table (cross-cutting-conventions: device-
            # agnostic data loading).
            earliest = conn_tmp.execute(
                "SELECT MIN(date) FROM measurements "
                "WHERE metric IN ('hrv_rmssd','rmssd_ms') AND person=?"
                , (person,)).fetchone()[0]
        conn_tmp.close()
        args.date_from = earliest or "2020-01-01"
        args.date_to   = today

    print(t(
        f"AFib-Burden-Analyse  {args.date_from} → {args.date_to}",
        f"AFib Burden Analysis  {args.date_from} → {args.date_to}"
    ))
    print(t(f"Datenbank: {DB_PATH}", f"Database: {DB_PATH}"))

    conn = open_db()
    episoden      = load_episoden(conn, args.date_from, args.date_to, person)
    ecg_rows      = load_ecg(conn, args.date_from, args.date_to, person)
    hrv_dict, hrv_sources, hrv_confidence = load_hrv(conn, args.date_from, args.date_to, person)
    druck_dict    = load_druck(conn, args.date_from, args.date_to)
    trainings     = load_trainings(conn, args.date_from, args.date_to, person)
    blutdruck     = load_blutdruck(conn, args.date_from, args.date_to, person)
    atemfrequenz  = load_atemfrequenz(conn, args.date_from, args.date_to, person)
    spo2_nacht    = load_spo2_nacht(conn, args.date_from, args.date_to, person)
    schlaf        = load_sleep(conn, args.date_from, args.date_to, person)
    stress_scores = load_stress(conn, args.date_from, args.date_to, person)
    gewicht       = load_gewicht(conn, args.date_from, args.date_to, person)
    afes_spo2     = load_afes_spo2(conn, args.date_from, args.date_to, person)
    oura_schlaf   = load_oura_sleep_model(conn, args.date_from, args.date_to)
    pre_ep_ctx      = load_pre_episode_context(conn, episoden)
    ecg_logger_rows = load_ecg_logger(conn, args.date_from, args.date_to, person)
    pollen          = load_pollen(conn, args.date_from, args.date_to)
    aq              = load_air_quality(conn, args.date_from, args.date_to)
    indoor          = load_indoor_air(conn, args.date_from, args.date_to)
    conn.close()

    print(t(
        f"Episoden: {len(episoden)}  |  ECG: {len(ecg_rows)}  |  HRV: {len(hrv_dict)}  |  "
        f"Druck: {len(druck_dict)}  |  Trainings: {len(trainings)}  |  "
        f"RR: {len(atemfrequenz)}  |  SpO2: {len(spo2_nacht)}  |  "
        f"Schlaf: {len(schlaf)}  |  Stress: {len(stress_scores)}  |  Gewicht: {len(gewicht)}  |  OuraNächte: {len(oura_schlaf)}",
        f"Episodes: {len(episoden)}  |  ECG: {len(ecg_rows)}  |  HRV: {len(hrv_dict)}  |  "
        f"Pressure: {len(druck_dict)}  |  Trainings: {len(trainings)}  |  "
        f"RR: {len(atemfrequenz)}  |  SpO2: {len(spo2_nacht)}  |  "
        f"Sleep: {len(schlaf)}  |  Stress: {len(stress_scores)}  |  Weight: {len(gewicht)}  |  OuraNights: {len(oura_schlaf)}"
    ))

    report = build_report(
        episoden, ecg_rows, hrv_dict, druck_dict, trainings,
        blutdruck, atemfrequenz, spo2_nacht, schlaf, stress_scores, gewicht,
        args.date_from, args.date_to, afes_spo2=afes_spo2,
        oura_schlaf=oura_schlaf, pre_ep_ctx=pre_ep_ctx,
        ecg_logger_rows=ecg_logger_rows,
        pollen_dict=pollen, air_quality=aq, indoor_air=indoor,
        hrv_sources=hrv_sources, hrv_confidence=hrv_confidence,
    )
    print("\n" + report)

    if args.plot:
        _plot(episoden, hrv_dict, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
