# SPDX-License-Identifier: GPL-3.0-or-later
"""
arrhythmia_utils.py — Hilfsfunktionen für Arrhythmie-Analyse

@tier        infrastructure
@purpose.de  Gemeinsame Hilfsfunktionen für Arrhythmie-Analyse-Skripte.
@purpose.en  Shared utility functions for arrhythmia analysis scripts.
@method.de   Abdeckt: CV-Klassifizierung, Burst-Gruppierung, Pre-Episode-Kontext-Loading,
             Trainings-Überlappungs-Erkennung und Hilfsdaten-Lader (Blutdruck, etc.).
             Definiert Schwellwerte für AFib-Klassifizierung basierend auf CV-Werten.
@method.en   Covers: CV classification, burst grouping, pre-episode context loading,
             training-overlap detection, and auxiliary data loaders (pressure, BP).
             Defines thresholds for AFib classification based on CV values.
@reads       arrhythmie_episoden, blood_pressure Tabellen
@writes      Keine Tabellen (Hilfsfunktionen)

@limits.de   Internes Hilfsmodul — nicht direkt aufrufen. Aenderungen koennen Analyse-Skripte brechen.

@relevance.de  Bietet Hilfsfunktionen für die Arrhythmie-Erkennung, essentiell für die kardiologische Analyse
@relevance.en  Provides utility functions for arrhythmia detection, essential for cardiological analysis
@limits.en   Internal helper module — do not call directly. Changes may break analysis scripts.
@usage
    python arrhythmia_utils.py
    python arrhythmia_utils.py --help
    python arrhythmia_utils.py --from 2024-01-01 --to 2024-12-31
"""

from datetime import datetime
from health_config import OWN_PERSON_ID, Config as _Cfg

# ── CV thresholds (fraction, as stored in arrhythmie_episoden) ────────────────
CV_AFIB_LOW  = 0.05   # < 5 %  — physiological HRV / artefact
CV_AFIB_MID  = 0.10   # 5–10 % — borderline: ectopy, PVCs, SVPB
CV_AFIB_HIGH = 0.15   # > 15 % — highly AFib-suspect

# Sensor-type priority for device selection (accuracy-based, best first):
#   HR:  chest ECG > wrist optical > ring optical
#   HRV: chest ECG > ring optical (finger = more accurate than wrist) > wrist optical
#   RR:  wrist optical/GPS (Garmin dedicated RR) > ring
_SENSOR_HR_TYPES  = ["chest_strap", "optical_wrist_gps", "ring"]
_SENSOR_HRV_TYPES = ["chest_strap", "ring", "optical_wrist_gps"]
_SENSOR_RR_TYPES  = ["optical_wrist_gps", "ring"]


import math as _math


def _load_cfg():
    try:
        return _Cfg()
    except Exception:
        return None


_CFG      = _load_cfg()
_REGISTRY = _CFG.device_registry if _CFG else []


def _build_device_prio(sensor_types: list[str]) -> list[str]:
    """Build ordered device_id list from device_registry, ranked by sensor_type."""
    result = []
    for stype in sensor_types:
        for dev in _REGISTRY:
            if dev.get("sensor_type") == stype:
                dev_id = dev.get("device_id")
                if dev_id and dev_id not in result:
                    result.append(dev_id)
    return result


def _build_brand_ids(brand: str) -> list[str]:
    return [d["device_id"] for d in _REGISTRY
            if d.get("brand", "").lower() == brand.lower() and d.get("device_id")]


def _closest_row(candidates: list, exp_lat, exp_lon):
    """From rows with (lat, lon) at index 1/2, return the closest to expected location."""
    if len(candidates) == 1 or exp_lat is None or exp_lon is None:
        return candidates[0]
    return min(candidates, key=lambda r: _math.sqrt(
        (r[1] - exp_lat) ** 2 + (r[2] - exp_lon) ** 2
    ))


_HR_PRIO         = _build_device_prio(_SENSOR_HR_TYPES)
_HRV_PRIO        = _build_device_prio(_SENSOR_HRV_TYPES)
_RR_PRIO         = _build_device_prio(_SENSOR_RR_TYPES)
_GARMIN_IDS      = _build_brand_ids("Garmin")
_APPLE_WATCH_IDS = [d for d in _build_brand_ids("Apple") if "watch" in d.lower()]

SPORT_ALIAS = {
    "Sport 83": "Walking",          "Sport 11": "Laufen",
    "Sport 57": "Kraft",            "Sport 9":  "Radfahren (Indoor)",
    "Sport 15": "Yoga/Stretching",  "Sport 38": "Schwimmen",
    "Sport 30": "Tanzen",           "Sport 34": "Wandern",
    "Sport 55": "Radfahren",        "Sport 29": "Outdoor",
    "Sport 103": "Skifahren",       "Sport 111": "Rudern",
    "Sport 03": "Walking",
}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _avg(lst):
    valid = [x for x in lst if x is not None]
    return round(sum(valid) / len(valid), 2) if valid else None


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()[0] > 0


# ── CV classification ─────────────────────────────────────────────────────────

def cv_klassifikation(episoden, cv_idx: int = 4):
    """Classify episodes into AFib-suspect tiers by CV of PPI intervals.

    cv_idx: position of cv_max in the episode tuple.
      afib_burden query: idx 4 (has n_fenster at idx 3)
      arrhythmia query:  idx 3 (no n_fenster column)

    Returns dict {tier: [episodes]}.
    """
    tiers = {
        "no_cv_data": [],
        "low":        [],   # CV < CV_AFIB_LOW    — physiolog. HRV / artefact
        "borderline": [],   # CV_AFIB_LOW ≤ CV < CV_AFIB_MID  — ectopy / PVCs
        "suspect":    [],   # CV_AFIB_MID ≤ CV < CV_AFIB_HIGH — AFib suspect
        "high":       [],   # CV ≥ CV_AFIB_HIGH   — highly AFib suspect
    }
    for ep in episoden:
        cv = ep[cv_idx]
        if cv is None:
            tiers["no_cv_data"].append(ep)
        elif cv < CV_AFIB_LOW:
            tiers["low"].append(ep)
        elif cv < CV_AFIB_MID:
            tiers["borderline"].append(ep)
        elif cv < CV_AFIB_HIGH:
            tiers["suspect"].append(ep)
        else:
            tiers["high"].append(ep)
    return tiers


# ── Burst grouping ────────────────────────────────────────────────────────────

def group_bursts(episoden, gap_min: int = 30) -> list[list]:
    """Group consecutive episodes within gap_min of each other into bursts.

    Returns list of burst groups; each group is a list of episode rows.
    """
    if not episoden:
        return []
    bursts, current = [], [episoden[0]]
    for ep in episoden[1:]:
        try:
            prev_dt = datetime.fromisoformat(current[-1][0][:19])
            curr_dt = datetime.fromisoformat(ep[0][:19])
            gap_s   = (curr_dt - prev_dt).total_seconds()
        except Exception:
            gap_s = float("inf")
        if 0 <= gap_s <= gap_min * 60:
            current.append(ep)
        else:
            bursts.append(current)
            current = [ep]
    bursts.append(current)
    return bursts


# ── Pre-episode context ───────────────────────────────────────────────────────

def load_pre_episode_context(conn, episoden, window_min: int = 60,
                              burst_gap_min: int = 30) -> list[dict]:
    """Load multi-source physiological context in the window before each episode burst.

    Episodes within burst_gap_min of each other share one lookup to avoid
    triple-counting clustered episodes with identical windows.

    Returns one dict per burst (not per episode).
    """
    def _pick(by_md, metric, sources):
        for src in sources:
            vals = by_md.get((metric, src), [])
            if len(vals) >= 2:
                return vals, src
        for src in sources:
            vals = by_md.get((metric, src), [])
            if vals:
                return vals, src
        return [], None

    bursts = group_bursts(episoden, burst_gap_min)
    out = []
    for burst in bursts:
        ep_ts = burst[0][0]

        rows = conn.execute("""
            SELECT ts, metric, value, device_id
            FROM measurements
            WHERE ts >= datetime(?, ? || ' minutes')
              AND ts < ?
              AND metric IN (
                  'heart_rate','hrv_rmssd','hrv_sdnn','stress',
                  'body_battery','respiratory_rate','respiration_rate'
              )
            ORDER BY ts
        """, (ep_ts, f"-{window_min}", ep_ts)).fetchall()

        by_md: dict = {}
        for r in rows:
            by_md.setdefault((r[1], r[3]), []).append((r[0], r[2]))

        hr_vals,  hr_src  = _pick(by_md, "heart_rate",  _HR_PRIO)
        hrv_vals, hrv_src = _pick(by_md, "hrv_rmssd",   _HRV_PRIO)
        if not hrv_vals:
            hrv_vals, _s = _pick(by_md, "hrv_sdnn", _APPLE_WATCH_IDS)
            if hrv_vals:
                hrv_src = f"{_s}(SDNN)"
        stress_g = []
        for _gid in _GARMIN_IDS:
            stress_g = [v for _, v in by_md.get(("stress", _gid), [])]
            if stress_g:
                break
        bb_vals = []
        for _gid in _GARMIN_IDS:
            bb_vals = by_md.get(("body_battery", _gid), [])
            if bb_vals:
                break
        rr_vals, rr_src = _pick(by_md, "respiratory_rate", _RR_PRIO)
        if not rr_vals:
            rr_vals, rr_src = _pick(by_md, "respiration_rate", _GARMIN_IDS)

        oura_rows = conn.execute("""
            SELECT stress_value, recovery_value FROM oura_daytime_stress
            WHERE timestamp >= datetime(?, ? || ' minutes') AND timestamp < ?
        """, (ep_ts, f"-{window_min}", ep_ts)).fetchall()
        oura_sv = [r[0] for r in oura_rows if r[0] is not None]
        oura_rv = [r[1] for r in oura_rows if r[1] is not None]

        hr_trend = None
        if len(hr_vals) >= 6:
            t3    = len(hr_vals) // 3
            early = _avg([v for _, v in hr_vals[:t3]])
            late  = _avg([v for _, v in hr_vals[-t3:]])
            if early and late:
                d = late - early
                hr_trend = ("steigend" if d > 5 else "fallend" if d < -5 else "stabil")

        out.append({
            "ep_ts":             ep_ts,
            "burst_size":        len(burst),
            "burst_end":         burst[-1][0][:16] if len(burst) > 1 else None,
            "hr_avg":            _avg([v for _, v in hr_vals]),
            "hr_trend":          hr_trend,
            "hr_source":         hr_src,
            "stress_avg":        _avg(stress_g),
            "oura_stress_avg":   _avg(oura_sv),
            "oura_recovery_avg": _avg(oura_rv),
            "hrv_avg":           _avg([v for _, v in hrv_vals]),
            "hrv_source":        hrv_src,
            "body_battery":      bb_vals[-1][1] if bb_vals else None,
            "rr_avg":            _avg([v for _, v in rr_vals]),
            "rr_source":         rr_src,
            "n_readings":        len(rows),
        })
    return out


# ── Training overlap ──────────────────────────────────────────────────────────

def load_trainings(conn, d_from, d_to, person: str = OWN_PERSON_ID):
    """Return list of (ts_start, ts_end, sport_label) for training sessions in range."""
    try:
        if not _table_exists(conn, "sessions"):
            return []
        rows = conn.execute("""
            SELECT ts_start, ts_end, sport
            FROM sessions
            WHERE type = 'training'
              AND date >= ? AND date <= ?
              AND person = ?
              AND ts_start IS NOT NULL AND ts_end IS NOT NULL
            ORDER BY ts_start
        """, (d_from, d_to, person)).fetchall()
        return [(r[0], r[1], SPORT_ALIAS.get(r[2] or "", r[2] or "Unbekannt")) for r in rows]
    except Exception:
        return []


def sport_mapping(episoden, trainings):
    """Map each episode to a training session if temporally overlapping.

    An episode matches when episode_start falls within [ts_start, ts_end],
    or a training starts while an episode is still running.

    Returns dict: {during: [...], outside: [...], sport_counts: {sport: n}}.
    """
    during, outside = [], []
    sport_counts = {}
    for ep in episoden:
        ep_start, ep_end = ep[0], ep[1]
        matched = None
        for ts_start, ts_end, sport in trainings:
            if ts_start <= ep_start <= ts_end:
                matched = sport
                break
            if ep_start <= ts_start <= ep_end:
                matched = sport
                break
        if matched:
            during.append(ep)
            sport_counts[matched] = sport_counts.get(matched, 0) + 1
        else:
            outside.append(ep)
    return {"during": during, "outside": outside, "sport_counts": sport_counts}


# ── Auxiliary data loaders ────────────────────────────────────────────────────

def load_pollen(conn, d_from: str, d_to: str) -> dict:
    """Return {date: dict} with daily pollen levels (grains/m³) for date range.

    Keys per date: birch, alder, grass, mugwort, ragweed, olive, total.
    When multiple location rows exist per date (after backfill), the row
    closest to the user's actual location on that day is selected.
    Priority: travel_history > location_history > current home.
    """
    if not _table_exists(conn, "pollen"):
        return {}
    try:
        rows = conn.execute("""
            SELECT date, lat, lon, birch, alder, grass, mugwort, ragweed, olive
            FROM pollen
            WHERE date >= ? AND date <= ?
            ORDER BY date
        """, (d_from, d_to)).fetchall()
        by_date: dict = {}
        for r in rows:
            by_date.setdefault(r[0], []).append(r)
        result = {}
        for d, candidates in by_date.items():
            _, exp_lat, exp_lon = _CFG.location_for_date(d) if _CFG else ("", None, None)
            r = _closest_row(candidates, exp_lat, exp_lon)
            vals = {
                "birch": r[3], "alder": r[4], "grass":   r[5],
                "mugwort": r[6], "ragweed": r[7], "olive": r[8],
            }
            vals["total"] = sum(v for v in vals.values() if v is not None)
            result[d] = vals
        return result
    except Exception:
        return {}


def load_air_quality(conn, d_from: str, d_to: str) -> dict:
    """Return {date: dict} with daily air quality metrics for date range.

    Keys per date: aqi_eu_mean, aqi_eu_max, pm25_mean, pm10_mean,
                   no2_mean, o3_mean, dust_mean.
    When multiple location rows exist per date, the closest to the user's
    actual location on that day is selected (travel > residence > home).
    """
    if not _table_exists(conn, "air_quality"):
        return {}
    try:
        rows = conn.execute("""
            SELECT date, lat, lon, aqi_eu_mean, aqi_eu_max, pm25_mean, pm10_mean,
                   no2_mean, o3_mean, dust_mean
            FROM air_quality
            WHERE date >= ? AND date <= ?
            ORDER BY date
        """, (d_from, d_to)).fetchall()
        by_date: dict = {}
        for r in rows:
            by_date.setdefault(r[0], []).append(r)
        result = {}
        for d, candidates in by_date.items():
            _, exp_lat, exp_lon = _CFG.location_for_date(d) if _CFG else ("", None, None)
            r = _closest_row(candidates, exp_lat, exp_lon)
            result[d] = {
                "aqi_eu_mean": r[3], "aqi_eu_max": r[4],
                "pm25_mean":   r[5], "pm10_mean":  r[6],
                "no2_mean":    r[7], "o3_mean":    r[8],
                "dust_mean":   r[9],
            }
        return result
    except Exception:
        return {}


def load_indoor_air(conn, d_from: str, d_to: str) -> dict:
    """Return {date: {sensor_type: mean_value}} from indoor_air_quality.

    Multiple sensors of the same type are averaged.
    """
    if not _table_exists(conn, "indoor_air_quality"):
        return {}
    try:
        rows = conn.execute("""
            SELECT date, sensor_type, AVG(mean_value) as val
            FROM indoor_air_quality
            WHERE date >= ? AND date <= ? AND mean_value IS NOT NULL
            GROUP BY date, sensor_type
            ORDER BY date
        """, (d_from, d_to)).fetchall()
        result: dict = {}
        for d, stype, val in rows:
            result.setdefault(d, {})[stype] = round(val, 2)
        return result
    except Exception:
        return {}


def load_druck(conn, d_from, d_to) -> dict:
    """Return {date: pressure_hpa} from weather_station (fallback: empty)."""
    if _table_exists(conn, "weather_station"):
        try:
            rows = conn.execute("""
                SELECT date, pressure_hpa FROM weather_station
                WHERE date >= ? AND date <= ? AND pressure_hpa IS NOT NULL
                ORDER BY date
            """, (d_from, d_to)).fetchall()
            if rows:
                return {r[0]: r[1] for r in rows}
        except Exception:
            pass
    return {}


def load_blutdruck(conn, d_from, d_to, person: str = OWN_PERSON_ID) -> list:
    """Return list of (date, systolic, diastolic, pulse) from blood_pressure."""
    if not _table_exists(conn, "blood_pressure"):
        return []
    try:
        return conn.execute("""
            SELECT date, systolic, diastolic, pulse
            FROM blood_pressure
            WHERE date >= ? AND date <= ? AND person = ?
            ORDER BY date
        """, (d_from, d_to, person)).fetchall()
    except Exception:
        return []


def load_ecg_logger(conn, d_from, d_to, person: str = OWN_PERSON_ID) -> list:
    """Return ECGLogger sessions (H10) with AFib metrics in date range.

    Each row: (session_id, duration_s, afib_suspected, afib_score, afib_votes,
               poincare_ratio, sampen, turning_pt_ratio, cv_rr, mean_hr_bpm,
               artifact_pct, tachy_sustained, brady_flag, tags)
    """
    if not _table_exists(conn, "ecg_logger_sessions"):
        return []
    cols = {r[1] for r in conn.execute("PRAGMA table_info(ecg_logger_sessions)")}
    if "person" not in cols:
        return []
    try:
        return conn.execute("""
            SELECT session_id, duration_s, afib_suspected, afib_score, afib_votes,
                   poincare_ratio, sampen, turning_pt_ratio, cv_rr, mean_hr_bpm,
                   artifact_pct, tachy_sustained, brady_flag, tags
            FROM ecg_logger_sessions
            WHERE DATE(session_id) >= ? AND DATE(session_id) <= ?
              AND person = ?
            ORDER BY session_id
        """, (d_from, d_to, person)).fetchall()
    except Exception:
        return []
