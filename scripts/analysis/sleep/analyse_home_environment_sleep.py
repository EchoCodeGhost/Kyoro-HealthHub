#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Raumklima × Schlaf-Analyse — Temperatur, Luftfeuchtigkeit, CO2, Luftqualität

Korreliert Umgebungssensoren (Home Assistant) mit Schlafqualität.
Hinweis: Datenbasis aktuell sehr begrenzt (49 Tage). Analyse wird valider
wenn fetch_daily.py regelmäßig Dyson/HA-Daten importiert.

Datenquellen:
  - home_environment: Temperatur, Luftfeuchtigkeit, CO2, Lärm, Licht (HA)
  - indoor_air_quality: Dyson Luftreiniger (PM2.5, VOC, HCHO, NO2)
  - measurements (hrv_rmssd/rmssd_ms): Schlaf-HRV, geräteunabhängig geladen ueber
    modules/metric_loader.py (nicht auf Polar beschraenkt)
  - oura_sleep_model: Schlafeffizienz

@tier        heuristic
@purpose.de  Korreliert Raumklima-Sensordaten (Temperatur, Luftfeuchtigkeit, CO2, PM2.5, VOC, Lärm) mit Schlafqualitäts-Metriken (HRV geräteunabhängig, Schlafeffizienz aus Oura).
@purpose.en  Correlates indoor climate sensor data (temperature, humidity, CO2, PM2.5, VOC, noise) with sleep quality metrics (HRV device-agnostic, sleep efficiency from Oura).
@method.de   Pearson-Korrelation (Pure-Python) je Umgebungsvariable × Schlafeffizienz/HRV; WHO-, UBA- und EU-Richtwerte als Orientierungsschwellen.
@method.en   Pearson correlation (pure Python) per environmental variable × sleep efficiency/HRV; WHO, UBA (German Federal Environment Agency), and EU guidelines used as orientation thresholds.
@limits.de   Heuristische Methode: Datenbasis sehr begrenzt (Stand 2026: ~49 Tage); Korrelationen ohne Signifikanztests; WHO/UBA-Richtwerte als Orientierung, nicht als validierte Schlafmedizin-Grenzwerte; kausale Wirkrichtung nicht bestimmbar.
@limits.en   Heuristic method: Very limited data basis (as of 2026: ~49 days); correlations without significance tests; WHO/UBA thresholds used as orientation, not as validated sleep medicine limits; causal direction not determinable.
@scoring
    Temperature: 16-19°C optimal bedroom | <16°C too cold | >19°C too warm (Lack & Gradisar 2019)
    Humidity: 40-60% optimal | <40% too dry | >60% too humid
    CO2: <1000ppm hygienically unobjectionable | 1000-2000ppm elevated, ventilation recommended | >2000ppm unacceptable, ventilate urgently (UBA 2008)
    PM2.5: <15 µg/m³ acceptable | 15-35 µg/m³ moderate | >35 µg/m³ high (WHO 2021)
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
@refs        WHO Air Quality Guidelines 2021 (PM2.5 24h: 15 µg/m³),
             doi:https://iris.who.int/handle/10665/345329
             WHO Night Noise Guidelines for Europe 2009 (Lnight <40 dB, Intervention >55 dB),
             doi:https://iris.who.int/handle/10665/326486
             WHO/IARC 2023: Formaldehyd als Gruppe-1-Karzinogen; 0.1 mg/m³ Kurzzeit-Richtwert
             Lack & Gradisar 2019, Sleep Med Rev 45:123-135 (Schlafzimmertemperatur 18–20°C)
             UBA 2008 (Ad-hoc-Arbeitsgruppe IRK/AOLG): Leitfaden für die Innenraumhygiene —
             CO2 als Lüftungsindikator, 1000/2000ppm-Stufung ("Pettenkofer-Zahl")

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@reads       home_environment, indoor_air_quality, measurements, oura_sleep_model
@writes      analyses/sleep/home_environment_sleep_*.{md,png}

Usage:
  python analyse_home_environment_sleep.py --plot
  python analyse_home_environment_sleep.py --from 2026-01-01 --to 2026-06-02
  python analyse_home_environment_sleep.py --plot --no-llm

@usage
    python analyse_home_environment_sleep.py
    python analyse_home_environment_sleep.py --help
    python analyse_home_environment_sleep.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_sleep import (
    SYSTEM_PROMPT_ANALYSE_HOME_ENVIRONMENT_SLEEP_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_HOME_ENVIRONMENT_SLEEP_EN as SYSTEM_PROMPT_EN,
)
from modules.metric_loader import load_metric_daily, source_summary, weakest_confidence
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "sleep"

TEMP_OPT_MIN = 18.0   # Experten-Konsens Schlafzimmer; Lack & Gradisar 2019, Sleep Med Rev 45:123-135
TEMP_OPT_MAX = 20.0   # Experten-Konsens Schlafzimmer; Lack & Gradisar 2019
HUMID_OPT_MIN = 40.0  # Konventioneller Innenraum-Komfortbereich (kein spezifischer WHO-Schlafwert)
HUMID_OPT_MAX = 60.0  # Konventioneller Innenraum-Komfortbereich

# WHO / EU indoor air quality thresholds
PM25_WARN    = 15.0   # µg/m³  WHO Air Quality Guidelines 2021: 24h-Mittelwert; doi:10665/345329
HCHO_WARN    =  0.1   # mg/m³  WHO/IARC 2023: Formaldehyd-Kurzzeit-Richtwert (Gruppe 1)
VOC_WARN     =  0.3   # mg/m³  Orientierungswert (AgBB 2012); kein WHO-Grenzwert — heuristisch
NOISE_WARN   = 45.0   # dB     WHO Night Noise Guidelines 2009 (Lnight <40 dB / Intervention >55 dB); doi:10665/326486
CO2_OK_MAX      = 1000.0  # ppm  UBA 2008 (IRK/AOLG-Leitfaden): "hygienisch unbedenklich"
CO2_ELEVATED_MAX = 2000.0  # ppm  UBA 2008: 1000-2000 "hygienisch auffaellig" (lueften), >2000 "inakzeptabel"


# ── Pure-Python statistics helpers ──────────────────────────────────────────

def _pearson(xs, ys):
    """Pearson r, pure Python. Returns (r, n). None if n < 5."""
    n = len(xs)
    if n < 5:
        return None, n
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0, n
    return round(num / (dx * dy), 3), n


def _avg(lst):
    return round(sum(lst) / len(lst), 2) if lst else None


def _pct_in_range(lst, lo, hi):
    return round(sum(1 for v in lst if lo <= v <= hi) / len(lst) * 100, 1) if lst else None


def _filter_pairs(xs, ys):
    """Return (xs_clean, ys_clean) dropping any pair with a None."""
    paired = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if not paired:
        return [], []
    return zip(*paired)


# ── Data loading ─────────────────────────────────────────────────────────────

def _tables(conn):
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}


def load_home_environment(conn, d_from, d_to):
    """Returns {date: {sensor_type: mean_value}}."""
    rows = conn.execute("""
        SELECT date, sensor_type, AVG(mean_value)
        FROM home_environment
        WHERE date >= ? AND date <= ?
          AND mean_value IS NOT NULL
          AND sensor_type IN ('temperature', 'humidity', 'co2', 'noise', 'light')
        GROUP BY date, sensor_type
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    result = {}
    for date, stype, val in rows:
        result.setdefault(date, {})[stype] = round(val, 2)
    return result


def load_indoor_air_quality(conn, d_from, d_to):
    """Returns {date: {sensor_type: mean_value}}."""
    rows = conn.execute("""
        SELECT date, sensor_type, AVG(mean_value)
        FROM indoor_air_quality
        WHERE date >= ? AND date <= ?
          AND mean_value IS NOT NULL
          AND sensor_type IN ('pm25', 'pm10', 'voc', 'hcho', 'no2', 'aqi',
                              'temperature', 'humidity')
        GROUP BY date, sensor_type
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    result = {}
    for date, stype, val in rows:
        result.setdefault(date, {})[stype] = round(val, 3)
    return result


def load_hrv_daily(conn, d_from, d_to):
    """Returns ({date: {rmssd_ms}}, source_summary, weakest_confidence).

    HRV used to be read exclusively from polar_nightly_hrv — a table that
    stays empty on any installation without a Polar device. The metric
    lives generically in measurements (hrv_rmssd/rmssd_ms) regardless of
    which device produced it (mainly Garmin in this DB), so load it
    device-agnostically via metric_loader instead.
    """
    days = load_metric_daily(conn, ("hrv_rmssd", "rmssd_ms"), d_from, d_to,
                             person=OWN_PERSON_ID, agg="avg")
    hrv = {d: {"rmssd_ms": day.value} for d, day in days.items()}
    return hrv, source_summary(days), weakest_confidence(days)


def load_oura_sleep(conn, d_from, d_to):
    """Returns {date: {efficiency, total_sleep_h, deep_sleep_h, avg_hrv, restless}}."""
    rows = conn.execute(
        "SELECT day, AVG(efficiency), AVG(total_sleep_duration),"
        " AVG(deep_sleep_duration), AVG(average_hrv), AVG(restless_periods)"
        " FROM oura_sleep_model"
        " WHERE day >= ? AND day <= ? AND person = ?"
        " GROUP BY day ORDER BY day",
        (d_from, d_to, OWN_PERSON_ID)
    ).fetchall()
    result = {}
    for row in rows:
        date = row[0]
        result[date] = {
            "efficiency":    round(row[1], 1)  if row[1] is not None else None,
            "total_sleep_h": round(row[2] / 3600, 2) if row[2] is not None else None,
            "deep_sleep_h":  round(row[3] / 3600, 2) if row[3] is not None else None,
            "avg_hrv":       round(row[4], 1)  if row[4] is not None else None,
            "restless":      round(row[5], 1)  if row[5] is not None else None,
        }
    return result


def load_noise_measurements(conn, d_from, d_to):
    """Audio exposure from Apple Watch measurements (daily avg dB)."""
    rows = conn.execute("""
        SELECT date, AVG(value)
        FROM measurements
        WHERE metric = 'audio_exposure_env'
          AND date >= ? AND date <= ?
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    return {r[0]: round(r[1], 2) for r in rows if r[1] is not None}


# ── Analysis & report ─────────────────────────────────────────────────────────

def _data_availability_summary(home_env, iaq, polar_hrv, oura_sleep, noise_meas,
                                hrv_sources=None, hrv_confidence=None):
    """Print data availability with warnings for sparse data."""
    lines = ["## Datenverfügbarkeit\n"]

    sources = [
        ("home_environment (Temp/Feuchte/CO2/Lärm)", len(home_env)),
        ("HRV RMSSD (measurements, geräteunabhängig)", len(polar_hrv)),
        ("indoor_air_quality (Dyson Purifier)",  len(iaq)),
        ("oura_sleep_model",                     len(oura_sleep)),
        ("measurements/audio_exposure_env",      len(noise_meas)),
    ]
    for name, n in sources:
        warn = " [!] WENIG DATEN — Ergebnisse explorativ" if 0 < n < 30 else (
               " [!] KEINE DATEN" if n == 0 else "")
        lines.append(f"  {name:<42} {n:>5} Tage{warn}")

    if hrv_sources:
        src_str = ", ".join(f"{src}: {n}" for src, n in hrv_sources.items())
        lines.append(f"    -> HRV-Quelle: {src_str}  |  Konfidenz: {hrv_confidence}")

    total_env = len(home_env)
    if total_env < 30:
        lines.append(
            f"\n  HINWEIS: Nur {total_env} Tage Umgebungsdaten vorhanden. "
            "Mindestens 30 Tage werden fuer aussagekraeftige Korrelationen empfohlen.\n"
            "  Regelmaessiger Import via fetch_daily.py (Home Assistant + Dyson) verbessert die Analyse."
        )
    return "\n".join(lines)


def build_report(home_env, iaq, polar_hrv, oura_sleep, noise_meas, d_from, d_to,
                  hrv_sources=None, hrv_confidence=None):
    lines = [f"## Raumklima x Schlaf-Analyse — {d_from} bis {d_to}\n"]

    # ── 1. Datenverfügbarkeit ──────────────────────────────────────────────
    lines.append(_data_availability_summary(home_env, iaq, polar_hrv, oura_sleep, noise_meas,
                                             hrv_sources, hrv_confidence))

    all_env_dates = sorted(home_env.keys())
    all_iaq_dates = sorted(iaq.keys())

    # ── 2. Temperature statistics ─────────────────────────────────────────
    lines.append("\n### Raumtemperatur (home_environment)\n")
    temp_vals = [home_env[d]["temperature"] for d in all_env_dates
                 if "temperature" in home_env[d]]
    if temp_vals:
        avg_t = _avg(temp_vals)
        pct   = _pct_in_range(temp_vals, TEMP_OPT_MIN, TEMP_OPT_MAX)
        flag  = " [!] ausserhalb Optimum" if avg_t and not (TEMP_OPT_MIN <= avg_t <= TEMP_OPT_MAX) else ""
        lines.append(f"  Mittelwert:   {avg_t} degC{flag}")
        lines.append(f"  Min / Max:    {min(temp_vals):.1f} / {max(temp_vals):.1f} degC")
        lines.append(f"  Optimal ({TEMP_OPT_MIN:.0f}-{TEMP_OPT_MAX:.0f} degC): {pct}% der Tage")
        lines.append(f"  n = {len(temp_vals)} Tage")

        # Dyson temperature cross-check
        dyson_t = [iaq[d]["temperature"] for d in all_iaq_dates if "temperature" in iaq[d]]
        if dyson_t:
            lines.append(f"  Dyson-Sensor (n={len(dyson_t)}): Ø {_avg(dyson_t)} degC")
    else:
        lines.append("  Keine Temperaturdaten vorhanden.")

    # ── 3. Humidity statistics ────────────────────────────────────────────
    lines.append("\n### Luftfeuchtigkeit\n")
    humid_ha   = [home_env[d]["humidity"] for d in all_env_dates if "humidity" in home_env[d]]
    humid_dyson = [iaq[d]["humidity"] for d in all_iaq_dates if "humidity" in iaq[d]]

    for label, vals in [("HA-Sensor", humid_ha), ("Dyson-Sensor", humid_dyson)]:
        if vals:
            avg_h = _avg(vals)
            pct   = _pct_in_range(vals, HUMID_OPT_MIN, HUMID_OPT_MAX)
            flag  = " [!]" if avg_h and not (HUMID_OPT_MIN <= avg_h <= HUMID_OPT_MAX) else ""
            lines.append(f"  {label}: Ø {avg_h}%  |  Optimal ({HUMID_OPT_MIN:.0f}-{HUMID_OPT_MAX:.0f}%): {pct}%  |  n={len(vals)}{flag}")

    if not humid_ha and not humid_dyson:
        lines.append("  Keine Feuchtigkeitsdaten vorhanden.")

    # ── 3b. CO2 ─────────────────────────────────────────────────────────────
    lines.append("\n### CO2 (Lueftungsindikator)\n")
    co2_vals = [home_env[d]["co2"] for d in all_env_dates if "co2" in home_env[d]]
    if co2_vals:
        avg_c = _avg(co2_vals)
        pct_ok = _pct_in_range(co2_vals, 0, CO2_OK_MAX)
        pct_elevated = round(
            sum(1 for v in co2_vals if CO2_OK_MAX < v <= CO2_ELEVATED_MAX)
            / len(co2_vals) * 100, 1
        )
        pct_high = round(sum(1 for v in co2_vals if v > CO2_ELEVATED_MAX) / len(co2_vals) * 100, 1)
        flag = " [!] im Mittel erhoeht — lueften" if avg_c and avg_c > CO2_OK_MAX else ""
        lines.append(f"  Mittelwert:   {avg_c} ppm{flag}")
        lines.append(f"  Min / Max:    {min(co2_vals):.0f} / {max(co2_vals):.0f} ppm")
        lines.append(f"  Unbedenklich (<{CO2_OK_MAX:.0f} ppm):     {pct_ok}% der Tage")
        lines.append(f"  Erhoeht ({CO2_OK_MAX:.0f}-{CO2_ELEVATED_MAX:.0f} ppm):  {pct_elevated}% der Tage")
        lines.append(f"  Inakzeptabel (>{CO2_ELEVATED_MAX:.0f} ppm): {pct_high}% der Tage")
        lines.append(f"  n = {len(co2_vals)} Tage")
        bad_co2 = [(d, home_env[d]["co2"]) for d in all_env_dates
                   if "co2" in home_env[d] and home_env[d]["co2"] > CO2_ELEVATED_MAX]
        if bad_co2:
            lines.append(f"\n  Tage ueber der Inakzeptabel-Schwelle ({CO2_ELEVATED_MAX:.0f} ppm):")
            for d, v in bad_co2:
                lines.append(f"    {d}: {v:.0f} ppm")
    else:
        lines.append("  Keine CO2-Daten vorhanden.")

    # ── 4. Indoor air quality (Dyson) ─────────────────────────────────────
    lines.append("\n### Innenraumluftqualitaet (Dyson Purifier)\n")
    if iaq:
        aiq_metrics = [
            ("pm25",  "PM2.5 (µg/m³)",  PM25_WARN),
            ("pm10",  "PM10 (µg/m³)",   None),
            ("voc",   "VOC (mg/m³)",     VOC_WARN),
            ("hcho",  "HCHO (mg/m³)",    HCHO_WARN),
            ("no2",   "NO2 (µg/m³)",     None),
            ("aqi",   "AQI (Dyson)",     None),
        ]
        lines.append(f"  {'Metrik':<18} {'Mittel':>8} {'Min':>8} {'Max':>8} {'n':>4}")
        lines.append("  " + "-" * 52)
        concerning = []
        for key, label, warn_thresh in aiq_metrics:
            vals = [iaq[d][key] for d in all_iaq_dates if key in iaq[d]]
            if not vals:
                continue
            avg_v = _avg(vals)
            flag  = ""
            if warn_thresh is not None and avg_v and avg_v > warn_thresh:
                flag = " [!] erhoehter Wert"
                concerning.append(f"{label}: Ø {avg_v} > Schwelle {warn_thresh}")
            lines.append(
                f"  {label:<18} {avg_v or 0:>8.3f} {min(vals):>8.3f} {max(vals):>8.3f} {len(vals):>4}{flag}"
            )
        if concerning:
            lines.append("\n  Bedenkenswerte Werte:")
            for c in concerning:
                lines.append(f"    - {c}")

        # Concerning individual days for PM2.5
        bad_pm25 = [(d, iaq[d]["pm25"]) for d in all_iaq_dates
                    if "pm25" in iaq[d] and iaq[d]["pm25"] > PM25_WARN]
        if bad_pm25:
            lines.append(f"\n  PM2.5-Tage ueber WHO-Schwelle ({PM25_WARN} µg/m³):")
            for d, v in bad_pm25:
                lines.append(f"    {d}: {v:.2f} µg/m³")
    else:
        lines.append("  Keine Dyson-Daten vorhanden.")
        lines.append("  -> Regelmaessiger Import via fetch_daily.py (HA-Integration) empfohlen.")

    # ── 5. Noise ──────────────────────────────────────────────────────────
    lines.append("\n### Laermbelastung\n")
    noise_ha = [home_env[d]["noise"] for d in all_env_dates if "noise" in home_env[d]]
    noise_aw = list(noise_meas.values())

    for label, vals in [("HA-Sensor (dB)", noise_ha), ("Apple Watch Audio (dB)", noise_aw)]:
        if vals:
            avg_n = _avg(vals)
            flag  = " [!] ueber WHO Nacht-Grenze (45 dB)" if avg_n and avg_n > NOISE_WARN else ""
            lines.append(f"  {label}: Ø {avg_n} dB  |  Min/Max: {min(vals):.1f}/{max(vals):.1f}  |  n={len(vals)}{flag}")

    if not noise_ha and not noise_aw:
        lines.append("  Keine Laermdaten vorhanden.")

    # ── 6. Correlations: environment x sleep ─────────────────────────────
    lines.append("\n### Korrelationen Raumklima x Schlaf (Pearson r)\n")

    overlap_polar  = sorted(set(all_env_dates) & set(polar_hrv.keys()))
    overlap_oura   = sorted(set(all_env_dates) & set(oura_sleep.keys()))
    overlap_noise_polar = sorted(set(noise_meas.keys()) & set(polar_hrv.keys()))

    if len(overlap_polar) < 5 and len(overlap_oura) < 5 and len(overlap_noise_polar) < 5:
        lines.append(
            "  Keine ausreichenden Ueberlappungstage fuer Korrelationsanalyse.\n"
            f"  HRV x Umgebung: {len(overlap_polar)} Tage  |  "
            f"Oura x Umgebung: {len(overlap_oura)} Tage\n"
            "  (mind. 5 Ueberlappungstage benoetigt)"
        )
    else:
        corr_pairs = []

        # Temperature x HRV
        if len(overlap_polar) >= 5:
            xs = [home_env[d].get("temperature") for d in overlap_polar]
            ys = [polar_hrv[d]["rmssd_ms"] for d in overlap_polar]
            xs_c, ys_c = list(_filter_pairs(xs, ys))
            r, n = _pearson(xs_c, ys_c)
            corr_pairs.append(("Temp. (HA)", "HRV RMSSD", r, n))

        # Humidity x HRV
        if len(overlap_polar) >= 5:
            xs = [home_env[d].get("humidity") for d in overlap_polar]
            ys = [polar_hrv[d]["rmssd_ms"] for d in overlap_polar]
            xs_c, ys_c = list(_filter_pairs(xs, ys))
            r, n = _pearson(xs_c, ys_c)
            corr_pairs.append(("Feuchte (HA)", "HRV RMSSD", r, n))

        # Noise (HA) x HRV
        if len(overlap_polar) >= 5:
            xs = [home_env[d].get("noise") for d in overlap_polar]
            ys = [polar_hrv[d]["rmssd_ms"] for d in overlap_polar]
            xs_c, ys_c = list(_filter_pairs(xs, ys))
            r, n = _pearson(xs_c, ys_c)
            corr_pairs.append(("Laerm/dB (HA)", "HRV RMSSD", r, n))

        # CO2 (HA) x HRV
        if len(overlap_polar) >= 5:
            xs = [home_env[d].get("co2") for d in overlap_polar]
            ys = [polar_hrv[d]["rmssd_ms"] for d in overlap_polar]
            xs_c, ys_c = list(_filter_pairs(xs, ys))
            r, n = _pearson(xs_c, ys_c)
            corr_pairs.append(("CO2/ppm (HA)", "HRV RMSSD", r, n))

        # CO2 (HA) x Oura efficiency
        if len(overlap_oura) >= 5:
            xs = [home_env[d].get("co2") for d in overlap_oura]
            ys = [oura_sleep[d]["efficiency"] for d in overlap_oura]
            xs_c, ys_c = list(_filter_pairs(xs, ys))
            r, n = _pearson(xs_c, ys_c)
            corr_pairs.append(("CO2/ppm (HA)", "Schlafeffizienz (Oura)", r, n))

        # Temperature x Oura efficiency
        if len(overlap_oura) >= 5:
            xs = [home_env[d].get("temperature") for d in overlap_oura]
            ys = [oura_sleep[d]["efficiency"] for d in overlap_oura]
            xs_c, ys_c = list(_filter_pairs(xs, ys))
            r, n = _pearson(xs_c, ys_c)
            corr_pairs.append(("Temp. (HA)", "Schlafeffizienz (Oura)", r, n))

        # Humidity x Oura efficiency
        if len(overlap_oura) >= 5:
            xs = [home_env[d].get("humidity") for d in overlap_oura]
            ys = [oura_sleep[d]["efficiency"] for d in overlap_oura]
            xs_c, ys_c = list(_filter_pairs(xs, ys))
            r, n = _pearson(xs_c, ys_c)
            corr_pairs.append(("Feuchte (HA)", "Schlafeffizienz (Oura)", r, n))

        # Noise (Apple Watch) x HRV
        if len(overlap_noise_polar) >= 5:
            xs = [noise_meas[d] for d in overlap_noise_polar]
            ys = [polar_hrv[d]["rmssd_ms"] for d in overlap_noise_polar]
            xs_c, ys_c = list(_filter_pairs(xs, ys))
            r, n = _pearson(xs_c, ys_c)
            corr_pairs.append(("Audio dB (Apple Watch)", "HRV RMSSD", r, n))

        valid = [(env_m, sleep_m, r, n) for env_m, sleep_m, r, n in corr_pairs if r is not None]
        if valid:
            lines.append(f"  {'Umgebung':<26} {'Schlaf-Metrik':<26} {'r':>6} {'n':>4}")
            lines.append("  " + "-" * 66)
            for env_m, sleep_m, r, n in sorted(valid, key=lambda x: abs(x[2] or 0), reverse=True):
                interp = ""
                if abs(r) >= 0.5:
                    interp = " [stark]"
                elif abs(r) >= 0.3:
                    interp = " [moderat]"
                lines.append(f"  {env_m:<26} {sleep_m:<26} {r:>+6.3f} {n:>4}{interp}")
        else:
            lines.append("  Korrelationen konnten nicht berechnet werden (zu wenig Ueberlappung).")

        n_polar = len(overlap_polar)
        n_oura  = len(overlap_oura)
        lines.append(f"\n  Ueberlappungstage: HRV={n_polar}, Oura={n_oura}, "
                     f"Noise-HRV={len(overlap_noise_polar)}")

    # ── 7. Sleep statistics on days with env data ─────────────────────────
    lines.append("\n### Schlafkennzahlen (Tage mit Umgebungsdaten)\n")
    polar_on_env = [polar_hrv[d]["rmssd_ms"] for d in overlap_polar if polar_hrv[d]["rmssd_ms"]]
    oura_eff     = [oura_sleep[d]["efficiency"] for d in overlap_oura if oura_sleep[d]["efficiency"]]
    oura_sleepm  = [oura_sleep[d]["total_sleep_h"] for d in overlap_oura if oura_sleep[d]["total_sleep_h"]]

    if polar_on_env:
        lines.append(f"  HRV RMSSD (Tage mit Umgebungsdaten): Ø {_avg(polar_on_env)} ms  |  n={len(polar_on_env)}")
    if oura_eff:
        lines.append(f"  Schlafeffizienz (Oura):  Ø {_avg(oura_eff)}%  |  n={len(oura_eff)}")
    if oura_sleepm:
        lines.append(f"  Schlafdauer (Oura):      Ø {_avg(oura_sleepm)} h  |  n={len(oura_sleepm)}")

    if not polar_on_env and not oura_eff:
        lines.append("  Keine Schlaf-Ueberlappungstage mit Umgebungsdaten.")

    # ── 8. Future potential ───────────────────────────────────────────────
    lines.append("\n### Datenpotenzial & Empfehlungen\n")
    lines.append(
        "  Fuer aussagekraeftige Analysen werden benoetigt:\n"
        "  - home_environment: mind. 30 Tage (aktuell: "
        f"{len(all_env_dates)} Tage, ab {min(all_env_dates) if all_env_dates else 'n/a'})\n"
        "  - indoor_air_quality: mind. 14 Tage (aktuell: "
        f"{len(all_iaq_dates)} Tage)\n"
        "  - Massnahmen: fetch_daily.py taeglich per Cron ausfuehren\n"
        "  - Prioritaet: Dyson-Sensor Nacht vs. Tag trennen (entity_id-Filter)\n"
        "  - Optional: Schlafzimmer-spezifische HA-Sensoren hinzufuegen"
    )

    return "\n".join(lines)


# ── LLM ──────────────────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


# ── Plotting ──────────────────────────────────────────────────────────────────

def _plot(home_env, iaq, polar_hrv, oura_sleep, noise_meas, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    BG    = "#1A1A2E"
    PANEL = "#16213E"
    CLR   = {
        "temp":   "#fdcb6e",
        "humid":  "#a29bfe",
        "pm25":   "#ff6b6b",
        "voc":    "#55efc4",
        "hrv":    "#74b9ff",
        "opt":    "#2ecc71",
    }

    def _filter_none(dates_in, vals):
        pairs = [(d, v) for d, v in zip(dates_in, vals) if v is not None]
        if not pairs:
            return [], []
        ds, vs = zip(*pairs)
        return list(ds), list(vs)

    all_env_dates = sorted(home_env.keys())

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), facecolor=BG)
    fig.suptitle(f"Raumklima x Schlaf  |  {d_from} bis {d_to}",
                 color="#E0E0E0", fontsize=13, y=0.98)

    for ax in axes:
        ax.set_facecolor(PANEL)
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # ── Panel 1: Temperature + Humidity (dual y-axis, time series) ────────
    ax1  = axes[0]
    ax1b = ax1.twinx()

    dts_env = [datetime.fromisoformat(d) for d in all_env_dates]
    temp_v  = [home_env[d].get("temperature") for d in all_env_dates]
    humid_v = [home_env[d].get("humidity") for d in all_env_dates]

    dt_t, v_t = _filter_none(dts_env, temp_v)
    dt_h, v_h = _filter_none(dts_env, humid_v)

    if dt_t:
        ax1.plot(dt_t, v_t, color=CLR["temp"], lw=1.5, label="Temperatur (°C)")
        ax1.axhspan(TEMP_OPT_MIN, TEMP_OPT_MAX, color=CLR["opt"], alpha=0.07,
                    label=f"Optimal {TEMP_OPT_MIN:.0f}-{TEMP_OPT_MAX:.0f}°C")
    if dt_h:
        ax1b.plot(dt_h, v_h, color=CLR["humid"], lw=1.2, ls="--",
                  alpha=0.85, label="Luftfeuchte (%)")
        ax1b.axhspan(HUMID_OPT_MIN, HUMID_OPT_MAX, color=CLR["humid"], alpha=0.04)

    ax1.set_ylabel("Temperatur (°C)", color=CLR["temp"], fontsize=9)
    ax1.tick_params(axis="y", colors=CLR["temp"])
    ax1b.set_ylabel("Luftfeuchte (%)", color=CLR["humid"], fontsize=9)
    ax1b.tick_params(colors="#aaa", labelsize=8)
    ax1b.tick_params(axis="y", colors=CLR["humid"])
    ax1b.set_facecolor(PANEL)
    for spine in ax1b.spines.values():
        spine.set_edgecolor("#444")

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax1b.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, fontsize=8, facecolor="#2a2a3e", labelcolor="white",
               loc="upper left")
    ax1.set_title("Temperatur & Luftfeuchtigkeit (HA-Sensor)", color="#ccc", fontsize=9, loc="left")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))

    # ── Panel 2: Indoor air quality (PM2.5, VOC) ──────────────────────────
    ax2 = axes[1]
    all_iaq_dates = sorted(iaq.keys())
    if all_iaq_dates:
        dts_iaq = [datetime.fromisoformat(d) for d in all_iaq_dates]
        pm25_v  = [iaq[d].get("pm25") for d in all_iaq_dates]
        voc_v   = [iaq[d].get("voc")  for d in all_iaq_dates]

        dt_pm, v_pm = _filter_none(dts_iaq, pm25_v)
        dt_vc, v_vc = _filter_none(dts_iaq, voc_v)

        if dt_pm:
            ax2.bar(dt_pm, v_pm, color=CLR["pm25"], alpha=0.7, width=0.5, label="PM2.5 (µg/m³)")
            ax2.axhline(PM25_WARN, color="#ff4757", ls="--", lw=0.9, alpha=0.7,
                        label=f"WHO-Grenze PM2.5 ({PM25_WARN} µg/m³)")
        if dt_vc:
            ax2b = ax2.twinx()
            ax2b.plot(dt_vc, v_vc, color=CLR["voc"], lw=1.2, marker="o", ms=5,
                      label="VOC (mg/m³)")
            ax2b.set_ylabel("VOC (mg/m³)", color=CLR["voc"], fontsize=9)
            ax2b.tick_params(colors="#aaa", labelsize=8)
            ax2b.tick_params(axis="y", colors=CLR["voc"])
            ax2b.set_facecolor(PANEL)
            for spine in ax2b.spines.values():
                spine.set_edgecolor("#444")
            h2b, l2b = ax2b.get_legend_handles_labels()
            ax2.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white", loc="upper left")
            ax2b.legend(h2b, l2b, fontsize=8, facecolor="#2a2a3e", labelcolor="white",
                        loc="upper right")
        else:
            ax2.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")

        ax2.set_ylabel("PM2.5 (µg/m³)", color=CLR["pm25"], fontsize=9)
        ax2.tick_params(axis="y", colors=CLR["pm25"])
        ax2.set_title("Dyson Luftreiniger — PM2.5 & VOC", color="#ccc", fontsize=9, loc="left")
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    else:
        ax2.text(0.5, 0.5, "Keine Dyson-Daten verfuegbar\n(indoor_air_quality leer)",
                 ha="center", va="center", transform=ax2.transAxes,
                 color="#888", fontsize=10)
        ax2.set_title("Dyson Luftreiniger — keine Daten", color="#ccc", fontsize=9, loc="left")

    # ── Panel 3: Temperature vs HRV scatter ───────────────────────────────
    ax3 = axes[2]
    overlap_polar = sorted(set(all_env_dates) & set(polar_hrv.keys()))

    if len(overlap_polar) >= 3:
        sc_t  = [home_env[d].get("temperature") for d in overlap_polar]
        sc_hrv = [polar_hrv[d]["rmssd_ms"] for d in overlap_polar]
        sc_t_c, sc_hrv_c = _filter_none(sc_t, sc_hrv)

        if len(sc_t_c) >= 3:
            ax3.scatter(sc_t_c, sc_hrv_c, c=CLR["hrv"], alpha=0.8, s=50,
                             edgecolors="#444", lw=0.5)
            ax3.axvspan(TEMP_OPT_MIN, TEMP_OPT_MAX, color=CLR["opt"], alpha=0.08,
                        label=f"Opt. Temp. {TEMP_OPT_MIN:.0f}-{TEMP_OPT_MAX:.0f}°C")

            # Regression line
            if len(sc_t_c) >= 5:
                n = len(sc_t_c)
                mx = sum(sc_t_c) / n
                my = sum(sc_hrv_c) / n
                num = sum((x - mx) * (y - my) for x, y in zip(sc_t_c, sc_hrv_c))
                den = sum((x - mx) ** 2 for x in sc_t_c)
                if den != 0:
                    slope = num / den
                    intercept = my - slope * mx
                    x_range = [min(sc_t_c), max(sc_t_c)]
                    y_range = [slope * x + intercept for x in x_range]
                    ax3.plot(x_range, y_range, color="#ff6b6b", lw=1.0, ls="--",
                             alpha=0.7, label="Trend")

            r, n = _pearson(sc_t_c, sc_hrv_c)
            r_str = f"r={r:+.3f}" if r is not None else "n.a."
            ax3.set_xlabel("Raumtemperatur (°C)", color="#ccc", fontsize=9)
            ax3.set_ylabel("HRV RMSSD (ms)", color=CLR["hrv"], fontsize=9)
            ax3.tick_params(axis="y", colors=CLR["hrv"])
            ax3.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
            ax3.set_title(
                f"Temperatur vs. HRV RMSSD  |  {r_str}, n={n}",
                color="#ccc", fontsize=9, loc="left"
            )
        else:
            ax3.text(0.5, 0.5, f"Zu wenig Ueberlappungstage ({len(sc_t_c)})\nfuer Scatter-Plot",
                     ha="center", va="center", transform=ax3.transAxes,
                     color="#888", fontsize=10)
            ax3.set_title("Temperatur vs. HRV — zu wenig Daten", color="#ccc", fontsize=9, loc="left")
    else:
        ax3.text(0.5, 0.5, f"Nur {len(overlap_polar)} gemeinsame Tage\nTemp. + HRV vorhanden",
                 ha="center", va="center", transform=ax3.transAxes,
                 color="#888", fontsize=10)
        ax3.set_title("Temperatur vs. HRV — unzureichend", color="#ccc", fontsize=9, loc="left")

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"home_environment_sleep_{ts}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=BG)
    print(t(f"Plot: {out}", f"Plot: {out}"))
    plt.close()


# ── Save report ───────────────────────────────────────────────────────────────

def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"home_environment_sleep_{ts}.md"
    content = "# Raumklima x Schlaf-Analyse\n\n" + report + "\n"
    if llm_text:
        content += "\n## Klinische Interpretation\n\n" + llm_text + "\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t(
            "Raumklima x Schlaf-Analyse (Temperatur, Luftfeuchtigkeit, Luftqualitaet)",
            "Home environment x sleep analysis (temperature, humidity, air quality)"
        )
    )
    parser.add_argument("--from",   dest="date_from", default=(datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d"),
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to",     dest="date_to",
                        default=str(datetime.now().date()),
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--all",    dest="all_data",  action="store_true",
                        help=t("Alle verfügbaren Daten (überschreibt --from/--to)",
                               "All available data (overrides --from/--to)"))
    parser.add_argument("--plot",   action="store_true",
                        help=t("Diagramme erstellen", "Generate charts"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Analyse ueberspringen", "Skip LLM analysis"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    if args.all_data:
        args.date_from = _cfg.data_start or "1900-01-01"
        args.date_to   = datetime.today().strftime("%Y-%m-%d")

    if not DB_PATH.exists():
        print(t(f"Datenbank nicht gefunden: {DB_PATH}",
                f"Database not found: {DB_PATH}"))
        return

    conn = open_db()
    tabs = _tables(conn)

    home_env   = load_home_environment(conn, args.date_from, args.date_to) \
                 if "home_environment" in tabs else {}
    iaq        = load_indoor_air_quality(conn, args.date_from, args.date_to) \
                 if "indoor_air_quality" in tabs else {}
    # measurements always exists (created by create_schema.py), so HRV is loaded
    # unconditionally — unlike polar_nightly_hrv, which only ever has rows on a
    # Polar-equipped installation.
    polar_hrv, hrv_sources, hrv_confidence = load_hrv_daily(conn, args.date_from, args.date_to)
    oura_sleep = load_oura_sleep(conn, args.date_from, args.date_to) \
                 if "oura_sleep_model" in tabs else {}
    noise_meas = load_noise_measurements(conn, args.date_from, args.date_to) \
                 if "measurements" in tabs else {}
    conn.close()

    print(t(
        f"Umgebungstage: HA={len(home_env)}, Dyson={len(iaq)} | "
        f"Schlaf: HRV={len(polar_hrv)}, Oura={len(oura_sleep)} | "
        f"Audio: {len(noise_meas)} Tage",
        f"Environment days: HA={len(home_env)}, Dyson={len(iaq)} | "
        f"Sleep: HRV={len(polar_hrv)}, Oura={len(oura_sleep)} | "
        f"Audio: {len(noise_meas)} days"
    ))

    if not home_env and not iaq:
        print(t(
            "Keine Umgebungsdaten gefunden. "
            "Import via: python fetch_daily.py (Home Assistant + Dyson)",
            "No environment data found. "
            "Import via: python fetch_daily.py (Home Assistant + Dyson)"
        ))
        return

    report = build_report(home_env, iaq, polar_hrv, oura_sleep,
                               noise_meas, args.date_from, args.date_to,
                               hrv_sources=hrv_sources, hrv_confidence=hrv_confidence)
    print("\n" + report)

    if args.plot:
        try:
            _plot(home_env, iaq, polar_hrv, oura_sleep, noise_meas,
                  args.date_from, args.date_to)
        except ImportError:
            print(t(
                "matplotlib nicht installiert — kein Plot erstellt.",
                "matplotlib not installed — no plot generated."
            ))

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
