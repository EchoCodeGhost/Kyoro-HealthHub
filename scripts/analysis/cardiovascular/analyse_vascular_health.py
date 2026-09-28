#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Gefäßgesundheit — Überblick vaskulärer Parameter aus Wearable-Quellen

Abgedeckte Parameter und Quellen:
  SpO2              alle Wearables (measurements.spo2 / .oxygen_saturation)
  Ruhepuls          Garmin + Apple Watch (daily_stress.resting_hr)
  Aktivität         Garmin + Apple Watch (daily_stress.steps, measurements.stand_time,
                    measurements.level_sedentary_s)
  Hauttemperatur    Polar Brustgurt (measurements.skin_temperature)
                    Oura Ring (oura_temperature_raw)
  Atemfrequenz      Apple Watch (measurements.respiratory_rate)
  PWV               Polar/Kompatibel (measurements.pulse_wave_velocity)
  Körpergewicht     Waage (body_composition.weight_kg)
  Oura Erholung     Oura Ring (oura_daytime_stress.recovery_value)

Orthostase-Reaktion: separates Script → analyse_orthostatic.py

@tier        heuristic
@purpose.de  Überblicksanalyse vaskulärer Wearable-Parameter: SpO2, Ruhepuls, Aktivität, Hauttemperatur, Atemfrequenz, Pulswellengeschwindigkeit, Körpergewicht und Oura-Erholungsscore.
@purpose.en  Overview analysis of vascular wearable parameters: SpO2, resting HR, activity, skin temperature, respiratory rate, pulse wave velocity, body weight and Oura recovery score.
@method.de   Monatliche Aggregation und Trendberechnung je Parameter; Einordnung gegen klinische Referenzbereiche (ESC 2018 PWV <10 m/s, Ruhepuls 50–90 bpm); Pearson-Korrelation zwischen Parametern.
@method.en   Monthly aggregation and trend calculation per parameter; comparison against clinical reference ranges (ESC 2018 PWV <10 m/s, resting HR 50–90 bpm); Pearson correlation between parameters.
@refs        Williams B, Mancia G, Spiering W et al. (2018). 2018 ESC/ESH Guidelines for the management of arterial hypertension. European Heart Journal, 39(33):3021-3104. doi:10.1093/eurheartj/ehy339
             Mancia G, Fagard R, Narkiewicz K et al. (2013). 2013 ESH/ESC Guidelines for the management of arterial hypertension. European Heart Journal, 34(28):2159-2219. doi:10.1093/eurheartj/eht151 (PWV-Klassifikation)
             Ashwell M, Gibson S (2016). Waist-to-height ratio as an indicator of 'early health risk'. BMJ Open, 6(3):e010159. doi:10.1136/bmjopen-2015-010159 (WHtR ≥0.5)

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@limits.de   Heuristische Methode: Wearable-basierte PWV (Polar PTT) nicht klinisch validiert für Gefäßsteifigkeit; ESC-Referenz gilt für applanationstonometrische Messung (Mancia 2013). Validierte Normwerte: SpO2 <95% (WHO/ESC), Ruhepuls 60-100 bpm (AHA), Atemfrequenz 12-20/min, WHtR >=0.5 (Ashwell 2016). Viszeralfett-Schwellen (>13 erhoet, >17 hoch) sind Geraetehersteller-Klassifikation, nicht WHO/klinisch validiert. Analyse ist beschreibend, ohne Kausalhypothesen.
@limits.en   Heuristic method: Wearable-based PWV (Polar PTT) is not clinically validated for vascular stiffness; ESC reference applies to applanation tonometry (Mancia 2013). Validated norms: SpO2 <95% (WHO/ESC), resting HR 60-100 bpm (AHA), respiratory rate 12-20/min, WHtR >=0.5 (Ashwell 2016). Visceral fat thresholds (>13 elevated, >17 high) are device-manufacturer classifications, not WHO/clinical standards. Analysis is descriptive without causal hypotheses.
@scoring
    SpO2: normal >=95% | mild 90-95% | moderate 85-90% | severe <85%
    PWV: normal <10 m/s | elevated 10-12 m/s | high >12 m/s (ESC 2018)
    Resting HR: normal 60-100 bpm | bradycardic <60 | tachycardic >100 (AHA)
@reads       measurements, daily_stress, oura_temperature_raw, oura_daytime_stress, body_composition
@writes      analyses/cardiovascular/*.{md,png}

Usage:
  python analyse_vascular_health.py --plot
  python analyse_vascular_health.py --from 2024-01-01 --plot
  python analyse_vascular_health.py --no-llm
  python analyse_vascular_health.py --lang en

@usage
    python analyse_vascular_health.py
    python analyse_vascular_health.py --help
    python analyse_vascular_health.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_VASCULAR_HEALTH_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_VASCULAR_HEALTH_EN as SYSTEM_PROMPT_EN,
)

cfg = Config()
OUT_DIR = cfg.analyses_dir / "cardiovascular"



# ── Helpers ───────────────────────────────────────────────────────────────────

def _table_exists(conn, name):
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return bool(row and row[0])


def _moving_avg(values, window=30):
    result = []
    for i, v in enumerate(values):
        chunk = [x for x in values[max(0, i - window + 1): i + 1] if x is not None]
        result.append(round(sum(chunk) / len(chunk), 2) if chunk else None)
    return result


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def _monthly_avg(rows_date_value):
    """Group (date_str, value) rows by YYYY-MM and return sorted list of (month, avg, n)."""
    buckets = defaultdict(list)
    for d, v in rows_date_value:
        if v is not None:
            buckets[d[:7]].append(v)
    return [(m, round(sum(vs) / len(vs), 2), len(vs)) for m, vs in sorted(buckets.items())]


# ── Data loading ──────────────────────────────────────────────────────────────

def load_spo2(conn, d_from, d_to):
    """SpO2 as percentage. Reads both metric names: 'spo2' (Garmin/Polar/Oura,
    already %) and 'oxygen_saturation' (Apple, fraction 0..1), normalising per row."""
    if not _table_exists(conn, "measurements"):
        return []
    # Geraeteagnostisch: 'oxygen_saturation' (Apple, Bruchwert 0..1) und 'spo2'
    # (Garmin/Polar/Oura, bereits %) werden beide gelesen und je Messwert auf
    # Prozent normalisiert. Vorher wurde ausschliesslich der Apple-Name mit
    # pauschalem *100 abgefragt — in jeder DB ohne Apple-Watch-Daten lieferte
    # die Funktion still eine leere Reihe, und der Bericht wies SpO2 dennoch
    # als "Quelle: Apple Watch" aus.
    rows = conn.execute(
        "SELECT date, "
        "  AVG(CASE WHEN value <= 1.5 THEN value*100.0 ELSE value END), "
        "  MIN(CASE WHEN value <= 1.5 THEN value*100.0 ELSE value END), "
        "  MAX(CASE WHEN value <= 1.5 THEN value*100.0 ELSE value END), "
        "  COUNT(*) "
        "FROM measurements "
        "WHERE metric IN ('spo2','oxygen_saturation') AND person=? AND date>=? AND date<=? "
        "GROUP BY date ORDER BY date",
        (OWN_PERSON_ID, d_from, d_to),
    ).fetchall()
    return [(r[0], round(r[1], 1), round(r[2], 1), round(r[3], 1), r[4]) for r in rows]


def load_resting_hr(conn, d_from, d_to):
    """Daily resting HR from daily_stress (multi-source composite: Garmin + Apple + Polar)."""
    if not _table_exists(conn, "daily_stress"):
        return []
    return conn.execute(
        "SELECT date, resting_hr FROM daily_stress "
        "WHERE date>=? AND date<=? AND resting_hr IS NOT NULL AND resting_hr>0 "
        "ORDER BY date",
        (d_from, d_to),
    ).fetchall()


def load_steps(conn, d_from, d_to):
    """Daily steps from daily_stress."""
    if not _table_exists(conn, "daily_stress"):
        return []
    return conn.execute(
        "SELECT date, steps FROM daily_stress "
        "WHERE date>=? AND date<=? AND steps IS NOT NULL AND steps>0 "
        "ORDER BY date",
        (d_from, d_to),
    ).fetchall()


def load_stand_time(conn, d_from, d_to):
    """Daily stand time in minutes (Apple Watch, measurements.stand_time, unit=min)."""
    if not _table_exists(conn, "measurements"):
        return []
    rows = conn.execute(
        "SELECT date, SUM(value) FROM measurements "
        "WHERE metric='stand_time' AND person=? AND date>=? AND date<=? "
        "GROUP BY date ORDER BY date",
        (OWN_PERSON_ID, d_from, d_to),
    ).fetchall()
    return [(r[0], round(r[1], 0)) for r in rows if r[1] is not None]


def load_sedentary(conn, d_from, d_to):
    """Daily sedentary time in hours (Garmin/Polar, measurements.level_sedentary_s, unit=s)."""
    if not _table_exists(conn, "measurements"):
        return []
    rows = conn.execute(
        "SELECT date, SUM(value)/3600.0 FROM measurements "
        "WHERE metric='level_sedentary_s' AND person=? AND date>=? AND date<=? "
        "GROUP BY date ORDER BY date",
        (OWN_PERSON_ID, d_from, d_to),
    ).fetchall()
    return [(r[0], round(r[1], 1)) for r in rows if r[1] is not None]


def load_skin_temp_polar(conn, d_from, d_to):
    """Daily Polar chest-strap skin temperature (°C)."""
    if not _table_exists(conn, "measurements"):
        return []
    rows = conn.execute(
        "SELECT date, AVG(value), MIN(value), MAX(value) FROM measurements "
        "WHERE metric='skin_temperature' AND person=? AND date>=? AND date<=? "
        "GROUP BY date ORDER BY date",
        (OWN_PERSON_ID, d_from, d_to),
    ).fetchall()
    return [(r[0], round(r[1], 2), round(r[2], 2), round(r[3], 2)) for r in rows if r[1]]


def load_skin_temp_oura(conn, d_from, d_to):
    """Daily Oura ring skin temperature (°C)."""
    if not _table_exists(conn, "oura_temperature_raw"):
        return []
    rows = conn.execute(
        "SELECT DATE(timestamp), AVG(skin_temp), COUNT(*) FROM oura_temperature_raw "
        "WHERE DATE(timestamp)>=? AND DATE(timestamp)<=? "
        "GROUP BY DATE(timestamp) ORDER BY DATE(timestamp)",
        (d_from, d_to),
    ).fetchall()
    return [(r[0], round(r[1], 2), r[2]) for r in rows if r[1]]


def load_resp_rate(conn, d_from, d_to):
    """Daily respiratory rate (br/min) — Apple Watch + Polar (two metric names)."""
    if not _table_exists(conn, "measurements"):
        return {}
    rows = conn.execute(
        "SELECT date, AVG(value) FROM measurements "
        "WHERE metric IN ('respiratory_rate', 'respiration_rate') "
        "AND person=? AND date>=? AND date<=? "
        "GROUP BY date ORDER BY date",
        (OWN_PERSON_ID, d_from, d_to),
    ).fetchall()
    return {r[0]: round(r[1], 1) for r in rows if r[1]}


def load_pwv(conn, d_from, d_to):
    """Daily pulse wave velocity (m/s)."""
    if not _table_exists(conn, "measurements"):
        return []
    rows = conn.execute(
        "SELECT date, AVG(value) FROM measurements "
        "WHERE metric='pulse_wave_velocity' AND person=? AND date>=? AND date<=? "
        "GROUP BY date ORDER BY date",
        (OWN_PERSON_ID, d_from, d_to),
    ).fetchall()
    return [(r[0], round(r[1], 2)) for r in rows if r[1]]


def load_weight(conn, d_from, d_to):
    """Body weight + composition metrics from body_composition."""
    if not _table_exists(conn, "body_composition"):
        return []
    return conn.execute(
        "SELECT date, weight_kg, muscle_pct, water_pct, body_fat_pct, "
        "       visceral_fat, fat_visceral_pct, waist_cm, hip_cm "
        "FROM body_composition "
        "WHERE person=? AND date>=? AND date<=? AND weight_kg IS NOT NULL "
        "ORDER BY date",
        (OWN_PERSON_ID, d_from, d_to),
    ).fetchall()


def load_oura_recovery(conn, d_from, d_to):
    """Oura daytime stress recovery_value (0–100); no person column."""
    if not _table_exists(conn, "oura_daytime_stress"):
        return []
    rows = conn.execute(
        "SELECT DATE(timestamp), AVG(recovery_value) FROM oura_daytime_stress "
        "WHERE DATE(timestamp)>=? AND DATE(timestamp)<=? AND recovery_value IS NOT NULL "
        "GROUP BY DATE(timestamp) ORDER BY DATE(timestamp)",
        (d_from, d_to),
    ).fetchall()
    return [(r[0], round(r[1], 1)) for r in rows if r[1]]


# ── Report sections ───────────────────────────────────────────────────────────

def section_header(d_from, d_to):
    return [
        t(f"# Gefäßgesundheit — {d_from} bis {d_to}",
          f"# Vascular Health — {d_from} to {d_to}"),
        t(f"Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
          f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
        "",
        t("*Orthostase-Reaktion (HR-Delta Lage→Stand): → `analyse_orthostatic.py`*",
          "*Orthostatic response (HR delta supine→stand): → `analyse_orthostatic.py`*"),
        "",
    ]


def section_spo2(spo2):
    lines = [
        t("## 1. Sauerstoffsättigung (SpO2)", "## 1. Oxygen Saturation (SpO2)"),
        t("Quelle: Wearables (measurements.spo2 / .oxygen_saturation)",
          "Source: wearables (measurements.spo2 / .oxygen_saturation)"),
        "",
    ]
    if not spo2:
        lines.append(t("  Keine SpO2-Daten im Zeitraum.", "  No SpO2 data in period."))
        return lines, {}

    avg_vals = [r[1] for r in spo2]
    min_vals = [r[2] for r in spo2]
    overall_avg = round(sum(avg_vals) / len(avg_vals), 1)
    overall_min = round(min(min_vals), 1)

    below_95 = sum(1 for v in avg_vals if v < 95.0)
    below_90 = sum(1 for v in avg_vals if v < 90.0)

    lines += [
        t(f"  Messtage            : {len(spo2)}  ({spo2[0][0]} – {spo2[-1][0]})",
          f"  Measurement days    : {len(spo2)}  ({spo2[0][0]} – {spo2[-1][0]})"),
        t(f"  Ø SpO2              : **{overall_avg} %** (Referenz: ≥95 %)",
          f"  Avg SpO2            : **{overall_avg} %** (reference: ≥95 %)"),
        t(f"  Tages-Minimum       : {overall_min} % (absoluter Tiefstwert)",
          f"  Daily minimum       : {overall_min} % (absolute lowest value)"),
        t(f"  Tage <95 %          : {below_95}/{len(spo2)} ({round(below_95/len(spo2)*100,1)} %)",
          f"  Days <95 %          : {below_95}/{len(spo2)} ({round(below_95/len(spo2)*100,1)} %)"),
        t(f"  Tage <90 %          : {below_90}/{len(spo2)} ({round(below_90/len(spo2)*100,1)} %)",
          f"  Days <90 %          : {below_90}/{len(spo2)} ({round(below_90/len(spo2)*100,1)} %)"),
        "",
    ]

    monthly = _monthly_avg([(r[0], r[1]) for r in spo2])
    if len(monthly) > 1:
        lines += [
            t(f"  {'Monat':<9} {'Ø SpO2 %':>9} {'n':>5}", f"  {'Month':<9} {'Avg SpO2 %':>10} {'n':>5}"),
            "  " + "-" * 28,
        ]
        for m, avg, n in monthly:
            flag = " !" if avg < 95.0 else ""
            lines.append(f"  {m:<9} {avg:>9.1f} {n:>5}{flag}")

    return lines, {"spo2_monthly": monthly, "spo2_data": spo2, "overall_avg": overall_avg}


def section_resting_hr(rhr_rows):
    lines = [
        "",
        t("## 2. Ruhepuls-Trend", "## 2. Resting Heart Rate Trend"),
        t("Quelle: Garmin + Apple Watch (daily_stress.resting_hr, Mehrquellen-Komposit)",
          "Source: Garmin + Apple Watch (daily_stress.resting_hr, multi-source composite)"),
        "",
    ]
    if not rhr_rows:
        lines.append(t("  Keine Ruhepuls-Daten.", "  No resting HR data."))
        return lines, {}

    vals = [r[1] for r in rhr_rows]
    overall_avg = round(sum(vals) / len(vals), 1)
    overall_min = round(min(vals), 1)
    overall_max = round(max(vals), 1)
    days_tachy = sum(1 for v in vals if v >= 100)
    days_brady = sum(1 for v in vals if v < 50)

    lines += [
        t(f"  Messtage             : {len(rhr_rows)}  ({rhr_rows[0][0]} – {rhr_rows[-1][0]})",
          f"  Measurement days     : {len(rhr_rows)}  ({rhr_rows[0][0]} – {rhr_rows[-1][0]})"),
        t(f"  Ø Ruhepuls           : **{overall_avg} bpm** (Referenz: 50–90 bpm)",
          f"  Avg resting HR       : **{overall_avg} bpm** (reference: 50–90 bpm)"),
        t(f"  Min / Max            : {overall_min} / {overall_max} bpm",
          f"  Min / Max            : {overall_min} / {overall_max} bpm"),
        t(f"  Tage ≥100 bpm (Tachy): {days_tachy}/{len(rhr_rows)} ({round(days_tachy/len(rhr_rows)*100,1)} %)",
          f"  Days ≥100 bpm (tachy): {days_tachy}/{len(rhr_rows)} ({round(days_tachy/len(rhr_rows)*100,1)} %)"),
        t(f"  Tage <50 bpm (Brady) : {days_brady}/{len(rhr_rows)} ({round(days_brady/len(rhr_rows)*100,1)} %)",
          f"  Days <50 bpm (brady) : {days_brady}/{len(rhr_rows)} ({round(days_brady/len(rhr_rows)*100,1)} %)"),
        "",
    ]

    monthly = _monthly_avg(rhr_rows)
    # Show last 24 months max
    display_monthly = monthly[-24:] if len(monthly) > 24 else monthly
    lines += [
        t(f"  {'Monat':<9} {'Ø RHR':>7} {'n':>5}", f"  {'Month':<9} {'Avg RHR':>7} {'n':>5}"),
        "  " + "-" * 26,
    ]
    for m, avg, n in display_monthly:
        flag = " !" if avg >= 100 or avg < 50 else ""
        lines.append(f"  {m:<9} {avg:>7.1f} {n:>5}{flag}")

    return lines, {"rhr_monthly": monthly, "rhr_data": rhr_rows}


def section_activity(steps_rows, stand_rows, sedentary_rows):
    lines = [
        "",
        t("## 3. Aktivität als Venenpumpe", "## 3. Activity as Venous Pump"),
        t("Quellen: Garmin+Apple Watch (Schritte), Apple Watch (Stehzeit), Garmin/Polar (Sitzzeit)",
          "Sources: Garmin+Apple Watch (steps), Apple Watch (stand time), Garmin/Polar (sedentary)"),
        "",
    ]

    # Steps
    if steps_rows:
        step_vals = [r[1] for r in steps_rows]
        avg_steps = round(sum(step_vals) / len(step_vals))
        days_lt5k = sum(1 for v in step_vals if v < 5000)
        days_gt10k = sum(1 for v in step_vals if v >= 10000)
        lines += [
            t("### Schritte", "### Steps"),
            t(f"  Messtage    : {len(steps_rows)}  ({steps_rows[0][0]} – {steps_rows[-1][0]})",
              f"  Days        : {len(steps_rows)}  ({steps_rows[0][0]} – {steps_rows[-1][0]})"),
            t(f"  Ø Schritte  : **{avg_steps:,}**  (WHO-Empfehlung: ≥7 500/Tag)",
              f"  Avg steps   : **{avg_steps:,}**  (WHO recommendation: ≥7 500/day)"),
            t(f"  Tage <5 000 : {days_lt5k}/{len(steps_rows)} ({round(days_lt5k/len(steps_rows)*100,1)} %)",
              f"  Days <5 000 : {days_lt5k}/{len(steps_rows)} ({round(days_lt5k/len(steps_rows)*100,1)} %)"),
            t(f"  Tage ≥10 000: {days_gt10k}/{len(steps_rows)} ({round(days_gt10k/len(steps_rows)*100,1)} %)",
              f"  Days ≥10 000: {days_gt10k}/{len(steps_rows)} ({round(days_gt10k/len(steps_rows)*100,1)} %)"),
            "",
        ]
        # Monthly steps
        monthly_steps = _monthly_avg(steps_rows)
        display_ms = monthly_steps[-24:] if len(monthly_steps) > 24 else monthly_steps
        if len(display_ms) > 1:
            lines += [
                t(f"  {'Monat':<9} {'Ø Schritte':>11} {'n':>5}",
                  f"  {'Month':<9} {'Avg steps':>11} {'n':>5}"),
                "  " + "-" * 30,
            ]
            for m, avg, n in display_ms:
                flag = " !" if avg < 5000 else ""
                lines.append(f"  {m:<9} {int(avg):>11,} {n:>5}{flag}")
            lines.append("")
    else:
        lines += [t("  Keine Schrittzahl-Daten.", "  No step data."), ""]

    # Stand time
    if stand_rows:
        stand_vals = [r[1] for r in stand_rows]
        avg_stand = round(sum(stand_vals) / len(stand_vals), 1)
        lines += [
            t("### Stehzeit (Apple Watch, Minuten/Tag)", "### Stand Time (Apple Watch, minutes/day)"),
            t(f"  Messtage   : {len(stand_rows)}  ({stand_rows[0][0]} – {stand_rows[-1][0]})",
              f"  Days       : {len(stand_rows)}  ({stand_rows[0][0]} – {stand_rows[-1][0]})"),
            t(f"  Ø Stehzeit : **{avg_stand} min/Tag**",
              f"  Avg stand  : **{avg_stand} min/day**"),
            t(f"  Min / Max  : {int(min(stand_vals))} / {int(max(stand_vals))} min",
              f"  Min / Max  : {int(min(stand_vals))} / {int(max(stand_vals))} min"),
            "",
        ]
    else:
        lines += [t("  Keine Stehzeit-Daten.", "  No stand time data."), ""]

    # Sedentary
    if sedentary_rows:
        sed_vals = [r[1] for r in sedentary_rows]
        avg_sed = round(sum(sed_vals) / len(sed_vals), 1)
        days_gt8h = sum(1 for v in sed_vals if v >= 8.0)
        lines += [
            t("### Sitzzeit (Garmin/Polar, Stunden/Tag)", "### Sedentary Time (Garmin/Polar, hours/day)"),
            t(f"  Messtage      : {len(sedentary_rows)}  ({sedentary_rows[0][0]} – {sedentary_rows[-1][0]})",
              f"  Days          : {len(sedentary_rows)}  ({sedentary_rows[0][0]} – {sedentary_rows[-1][0]})"),
            t(f"  Ø Sitzzeit    : **{avg_sed} h/Tag**",
              f"  Avg sedentary : **{avg_sed} h/day**"),
            t(f"  Tage ≥8 h     : {days_gt8h}/{len(sedentary_rows)} ({round(days_gt8h/len(sedentary_rows)*100,1)} %)",
              f"  Days ≥8 h     : {days_gt8h}/{len(sedentary_rows)} ({round(days_gt8h/len(sedentary_rows)*100,1)} %)"),
        ]
    else:
        lines.append(t("  Keine Sitzzeit-Daten.", "  No sedentary data."))

    return lines


def section_skin_temp(polar_rows, oura_rows):
    lines = [
        "",
        t("## 4. Hauttemperatur", "## 4. Skin Temperature"),
        "",
    ]

    # Polar
    lines.append(t("### 4a. Polar Brustgurt (°C)", "### 4a. Polar Chest Strap (°C)"))
    if polar_rows:
        vals = [r[1] for r in polar_rows]
        avg = round(sum(vals) / len(vals), 2)
        # 30-day rolling baseline deviation
        baseline_window = 30
        deviations = []
        for i, (d, v, _, _) in enumerate(polar_rows):
            window = [polar_rows[j][1] for j in range(max(0, i - baseline_window), i + 1)]
            baseline = sum(window) / len(window)
            deviations.append(round(v - baseline, 2))

        avg_dev = round(sum(deviations) / len(deviations), 2)
        max_dev = round(max(deviations), 2)
        min_dev = round(min(deviations), 2)

        lines += [
            t(f"  Messtage           : {len(polar_rows)}  ({polar_rows[0][0]} – {polar_rows[-1][0]})",
              f"  Days               : {len(polar_rows)}  ({polar_rows[0][0]} – {polar_rows[-1][0]})"),
            t(f"  Ø Temperatur       : **{avg} °C** (Brusthaut, abhängig von Umgebungstemperatur)",
              f"  Avg temperature    : **{avg} °C** (chest skin, ambient-dependent)"),
            t(f"  Ø Abweichung (30d) : {avg_dev:+.2f} °C vom gleitenden Baseline",
              f"  Avg deviation (30d): {avg_dev:+.2f} °C from rolling baseline"),
            t(f"  Max / Min Abw.     : {max_dev:+.2f} / {min_dev:+.2f} °C",
              f"  Max / Min dev.     : {max_dev:+.2f} / {min_dev:+.2f} °C"),
        ]
        # Monthly avg
        monthly = _monthly_avg([(r[0], r[1]) for r in polar_rows])
        display = monthly[-24:] if len(monthly) > 24 else monthly
        if len(display) > 1:
            lines += [
                "",
                t(f"  {'Monat':<9} {'Ø Temp':>8} {'n':>5}", f"  {'Month':<9} {'Avg T':>8} {'n':>5}"),
                "  " + "-" * 27,
            ]
            for m, avg_m, n in display:
                lines.append(f"  {m:<9} {avg_m:>8.2f} {n:>5}")
    else:
        lines.append(t("  Keine Polar-Temperaturdaten im Zeitraum.",
                       "  No Polar temperature data in period."))

    # Oura
    lines += ["", t("### 4b. Oura Ring (°C)", "### 4b. Oura Ring (°C)")]
    if oura_rows:
        oura_vals = [r[1] for r in oura_rows]
        oura_avg = round(sum(oura_vals) / len(oura_vals), 2)
        oura_dev = [round(v - oura_avg, 2) for v in oura_vals]
        lines += [
            t(f"  Messtage        : {len(oura_rows)}  ({oura_rows[0][0]} – {oura_rows[-1][0]})",
              f"  Days            : {len(oura_rows)}  ({oura_rows[0][0]} – {oura_rows[-1][0]})"),
            t(f"  Ø Temperatur    : **{oura_avg} °C** (Fingerring-Hauttemperatur)",
              f"  Avg temperature : **{oura_avg} °C** (finger ring skin temperature)"),
            "",
            t(f"  {'Datum':<12} {'Temp °C':>8} {'Δ Baseline':>12} {'n Messwerte':>12}",
              f"  {'Date':<12} {'Temp °C':>8} {'Δ Baseline':>12} {'n readings':>12}"),
            "  " + "-" * 50,
        ]
        for (d, v, n), dev in zip(oura_rows, oura_dev):
            lines.append(f"  {d:<12} {v:>8.2f} {dev:>+12.2f} {n:>12}")
    else:
        lines.append(t("  Keine Oura-Temperaturdaten im Zeitraum.",
                       "  No Oura temperature data in period."))

    return lines


def section_resp_rate(resp_dict):
    lines = [
        "",
        t("## 5. Atemfrequenz", "## 5. Respiratory Rate"),
        t("Quelle: Apple Watch + Polar (measurements.respiratory_rate / respiration_rate)",
          "Source: Apple Watch + Polar (measurements.respiratory_rate / respiration_rate)"),
        "",
    ]
    if not resp_dict:
        lines.append(t("  Keine Atemfrequenz-Daten.", "  No respiratory rate data."))
        return lines

    vals = list(resp_dict.values())
    avg_rr = round(sum(vals) / len(vals), 1)
    days_tachy = sum(1 for v in vals if v > 20)
    days_brady = sum(1 for v in vals if v < 12)

    lines += [
        t(f"  Messtage             : {len(resp_dict)}  ({min(resp_dict)} – {max(resp_dict)})",
          f"  Days                 : {len(resp_dict)}  ({min(resp_dict)} – {max(resp_dict)})"),
        t(f"  Ø Atemfrequenz       : **{avg_rr} /min** (Referenz: 12–20 /min normal)",
          f"  Avg respiratory rate : **{avg_rr} /min** (reference: 12–20 /min normal)"),
        t(f"  Min / Max            : {min(vals):.1f} / {max(vals):.1f} /min",
          f"  Min / Max            : {min(vals):.1f} / {max(vals):.1f} /min"),
        t(f"  Tage >20 /min (Tachy): {days_tachy}/{len(vals)} ({round(days_tachy/len(vals)*100,1)} %)",
          f"  Days >20 /min (tachy): {days_tachy}/{len(vals)} ({round(days_tachy/len(vals)*100,1)} %)"),
        t(f"  Tage <12 /min        : {days_brady}/{len(vals)} ({round(days_brady/len(vals)*100,1)} %)",
          f"  Days <12 /min        : {days_brady}/{len(vals)} ({round(days_brady/len(vals)*100,1)} %)"),
        "",
    ]

    monthly = _monthly_avg(list(resp_dict.items()))
    if len(monthly) > 1:
        lines += [
            t(f"  {'Monat':<9} {'Ø /min':>7} {'n':>5}", f"  {'Month':<9} {'Avg /min':>8} {'n':>5}"),
            "  " + "-" * 26,
        ]
        for m, avg, n in monthly:
            flag = " !" if avg > 20 else ""
            lines.append(f"  {m:<9} {avg:>7.1f} {n:>5}{flag}")

    return lines


def section_pwv(pwv_rows):
    def _classify(v):
        if v < 7.0:
            return t("gut (<7 m/s)", "good (<7 m/s)")
        if v < 9.0:
            return t("normal (7–9 m/s)", "normal (7–9 m/s)")
        if v < 10.0:
            return t("grenzwertig (9–10 m/s)", "borderline (9–10 m/s)")
        return t("erhöht >10 m/s (ESC-Schwelle)", "elevated >10 m/s (ESC threshold)")

    lines = [
        "",
        t("## 6. Pulswellengeschwindigkeit (PWV)", "## 6. Pulse Wave Velocity (PWV)"),
        t("Quelle: Polar (measurements.pulse_wave_velocity) — direkter Steifigkeitsmarker",
          "Source: Polar (measurements.pulse_wave_velocity) — direct stiffness marker"),
        "",
    ]
    if not pwv_rows:
        lines.append(t("  Keine PWV-Daten im Zeitraum.", "  No PWV data in period."))
        return lines

    vals = [r[1] for r in pwv_rows]
    avg = round(sum(vals) / len(vals), 2)
    lines += [
        t(f"  Messtage     : {len(pwv_rows)}  ({pwv_rows[0][0]} – {pwv_rows[-1][0]})",
          f"  Days         : {len(pwv_rows)}  ({pwv_rows[0][0]} – {pwv_rows[-1][0]})"),
        t(f"  Ø PWV        : **{avg} m/s** → {_classify(avg)}",
          f"  Avg PWV      : **{avg} m/s** → {_classify(avg)}"),
        t(f"  Min / Max    : {min(vals):.2f} / {max(vals):.2f} m/s",
          f"  Min / Max    : {min(vals):.2f} / {max(vals):.2f} m/s"),
        t("  Referenz (ESC 2018): <7 gut · 7–9 normal · 9–10 grenzwertig · >10 erhöht",
          "  Reference (ESC 2018): <7 good · 7–9 normal · 9–10 borderline · >10 elevated"),
        "",
        t(f"  {'Datum':<12} {'PWV m/s':>9}   {'Bewertung'}", f"  {'Date':<12} {'PWV m/s':>9}   {'Assessment'}"),
        "  " + "-" * 46,
    ]
    for d, v in pwv_rows:
        lines.append(f"  {d:<12} {v:>9.2f}   {_classify(v)}")

    return lines


def section_weight(weight_rows):
    lines = [
        "",
        t("## 7. Körperzusammensetzung (Gefäßrisikofaktoren)",
          "## 7. Body Composition (Vascular Risk Factors)"),
        t("Quelle: Waage (body_composition)", "Source: Scale (body_composition)"),
        "",
    ]
    if not weight_rows:
        lines.append(t("  Keine Gewichtsdaten.", "  No weight data."))
        return lines

    # weight_rows: (date, weight_kg, muscle_pct, water_pct, body_fat_pct,
    #               visceral_fat, fat_visceral_pct, waist_cm, hip_cm)
    w_vals    = [(r[0], r[1]) for r in weight_rows if r[1] is not None]
    mus_vals  = [(r[0], r[2]) for r in weight_rows if r[2] is not None]
    wat_vals  = [(r[0], r[3]) for r in weight_rows if r[3] is not None]
    vf_vals   = [(r[0], r[5]) for r in weight_rows if r[5] is not None]
    wst_vals  = [(r[0], r[7]) for r in weight_rows if len(r) > 7 and r[7] is not None]

    span_days = (datetime.fromisoformat(weight_rows[-1][0]) -
                 datetime.fromisoformat(weight_rows[0][0])).days or 1

    lines.append(t(
        f"  Messungen: {len(weight_rows)}  ({weight_rows[0][0]} – {weight_rows[-1][0]})",
        f"  Measurements: {len(weight_rows)}  ({weight_rows[0][0]} – {weight_rows[-1][0]})",
    ))

    # Gewicht
    if w_vals:
        w_first, w_last = w_vals[0][1], w_vals[-1][1]
        delta = round(w_last - w_first, 1)
        lines += [
            "",
            t("  **Gewicht**", "  **Weight**"),
            t(f"    Aktuell: {w_last:.1f} kg  |  Δ {delta:+.1f} kg über {span_days} Tage",
              f"    Current: {w_last:.1f} kg  |  Δ {delta:+.1f} kg over {span_days} days"),
        ]

    # Muskelmasse %
    if mus_vals:
        m_first, m_last = mus_vals[0][1], mus_vals[-1][1]
        delta_m = round(m_last - m_first, 1)
        # Reference: >33% women, >40% men is good; these are general population refs
        lines += [
            "",
            t("  **Muskelmasse %**", "  **Muscle %**"),
            t(f"    Aktuell: {m_last:.1f}%  |  Δ {delta_m:+.1f}% über {span_days} Tage",
              f"    Current: {m_last:.1f}%  |  Δ {delta_m:+.1f}% over {span_days} days"),
            t("    (Rückgang = Sarkopenie-Signal; relevant für ME/CFS-Verlauf)",
              "    (Decline = sarcopenia signal; relevant for ME/CFS trajectory)"),
        ]

    # Körperwasser %
    if wat_vals:
        wt_first, wt_last = wat_vals[0][1], wat_vals[-1][1]
        delta_wt = round(wt_last - wt_first, 1)
        lines += [
            "",
            t("  **Körperwasser %**", "  **Body Water %**"),
            t(f"    Aktuell: {wt_last:.1f}%  |  Δ {delta_wt:+.1f}% über {span_days} Tage",
              f"    Current: {wt_last:.1f}%  |  Δ {delta_wt:+.1f}% over {span_days} days"),
            t("    (Abfall = Dehydratation / Ödemverschiebung; MCAS/OI-relevant)",
              "    (Drop = dehydration / fluid shift; MCAS/OI-relevant)"),
        ]

    # Viszeralfett
    if vf_vals:
        vf_last = vf_vals[-1][1]
        vf_risiko = (t("erhöht ⚠ (>13)", "elevated ⚠ (>13)") if vf_last > 13
                     else t("normal ✓ (≤13)", "normal ✓ (≤13)"))
        lines += [
            "",
            t("  **Viszeralfett-Index**", "  **Visceral Fat Index**"),
            t(f"    Aktuell: {int(vf_last)}  →  {vf_risiko}",
              f"    Current: {int(vf_last)}  →  {vf_risiko}"),
            t("    (Kardiovaskulärer Risikofaktor; Referenz: ≤13 = normal, >17 = hoch)",
              "    (Cardiovascular risk factor; ref: ≤13 normal, >17 high)"),
        ]

    # WHtR
    height_cm = cfg.height_cm if hasattr(cfg, "height_cm") else None
    if wst_vals and height_cm:
        wst_last = wst_vals[-1][1]
        whtr = round(wst_last / height_cm, 3)
        whtr_risiko = (t("erhöht ⚠ (≥0.5)", "elevated ⚠ (≥0.5)") if whtr >= 0.5
                       else t("normal ✓ (<0.5)", "normal ✓ (<0.5)"))
        lines += [
            "",
            t("  **Taillenumfang / WHtR**", "  **Waist / WHtR**"),
            t(f"    Taille: {wst_last:.1f} cm  |  WHtR: {whtr:.3f}  →  {whtr_risiko}",
              f"    Waist: {wst_last:.1f} cm  |  WHtR: {whtr:.3f}  →  {whtr_risiko}"),
            t("    (WHtR ≥0.5 = erhöhtes kardiometabolisches Risiko unabhängig von BMI)",
              "    (WHtR ≥0.5 = elevated cardiometabolic risk independent of BMI)"),
        ]
        if len(wst_vals) > 1:
            wst_first = wst_vals[0][1]
            delta_wst = round(wst_last - wst_first, 1)
            lines.append(t(
                f"    Δ {delta_wst:+.1f} cm seit {wst_vals[0][0]}",
                f"    Δ {delta_wst:+.1f} cm since {wst_vals[0][0]}",
            ))

    # Verlaufstabelle wenn mehrere Messungen
    if len(weight_rows) > 1:
        has_mus = bool(mus_vals)
        has_wat = bool(wat_vals)
        has_vf  = bool(vf_vals)
        has_wst = bool(wst_vals)
        header = f"  {'Datum':<12} {'kg':>6}"
        if has_mus: header += f"  {'Mus%':>5}"
        if has_wat: header += f"  {'H2O%':>5}"
        if has_vf:  header += f"  {'VF':>4}"
        if has_wst: header += f"  {'Taille':>7}"
        lines += ["", header, "  " + "-" * len(header.rstrip())]
        for r in weight_rows:
            row = f"  {r[0]:<12} {r[1]:>6.1f}"
            if has_mus: row += f"  {r[2]:>5.1f}" if r[2] is not None else "      –"
            if has_wat: row += f"  {r[3]:>5.1f}" if r[3] is not None else "      –"
            if has_vf:  row += f"  {int(r[5]):>4}" if r[5] is not None else "     –"
            if has_wst:
                wc = r[7] if len(r) > 7 else None
                row += f"  {wc:>6.1f}" if wc is not None else "       –"
            lines.append(row)

    return lines


def section_oura_recovery(recovery_rows):
    lines = [
        "",
        t("## 8. Oura Erholung (Daytime Recovery)", "## 8. Oura Recovery (Daytime)"),
        t("Quelle: Oura Ring (oura_daytime_stress.recovery_value, Skala 0–100)",
          "Source: Oura Ring (oura_daytime_stress.recovery_value, scale 0–100)"),
        "",
    ]
    if not recovery_rows:
        lines.append(t("  Keine Oura-Recovery-Daten im Zeitraum.",
                       "  No Oura recovery data in period."))
        return lines

    vals = [r[1] for r in recovery_rows]
    avg = round(sum(vals) / len(vals), 1)
    low = sum(1 for v in vals if v < 33)
    high = sum(1 for v in vals if v >= 67)

    lines += [
        t(f"  Messtage         : {len(recovery_rows)}  ({recovery_rows[0][0]} – {recovery_rows[-1][0]})",
          f"  Days             : {len(recovery_rows)}  ({recovery_rows[0][0]} – {recovery_rows[-1][0]})"),
        t(f"  Ø Recovery       : **{avg} / 100**",
          f"  Avg recovery     : **{avg} / 100**"),
        t(f"  Min / Max        : {min(vals):.0f} / {max(vals):.0f}",
          f"  Min / Max        : {min(vals):.0f} / {max(vals):.0f}"),
        t(f"  Tage niedrig (<33)   : {low}/{len(vals)}",
          f"  Days low (<33)       : {low}/{len(vals)}"),
        t(f"  Tage hoch (≥67)      : {high}/{len(vals)}",
          f"  Days high (≥67)      : {high}/{len(vals)}"),
        "",
        t(f"  {'Datum':<12} {'Recovery':>10}", f"  {'Date':<12} {'Recovery':>10}"),
        "  " + "-" * 26,
    ]
    for d, v in recovery_rows:
        lines.append(f"  {d:<12} {v:>10.0f}")

    return lines


def section_sources(spo2, rhr, steps, stand, sedentary, polar_temp, oura_temp,
                    resp, pwv, weight, recovery):
    """Summary of which sources contributed data."""
    lines = [
        "",
        t("## 9. Datenquellen-Übersicht", "## 9. Data Sources Summary"),
        "",
        t(f"  {'Parameter':<28} {'Quelle':<30} {'Tage/Eintr.':>12} {'Zeitraum'}",
          f"  {'Parameter':<28} {'Source':<30} {'Days/entries':>12} {'Period'}"),
        "  " + "-" * 95,
    ]

    def _row(param_de, param_en, source, rows, date_col=0):
        n = len(rows)
        if n == 0:
            period = t("keine Daten", "no data")
        else:
            try:
                dates = [r[date_col] for r in rows]
                period = f"{min(dates)} – {max(dates)}"
            except Exception:
                period = "–"
        param = t(param_de, param_en)
        lines.append(f"  {param:<28} {source:<30} {n:>12}   {period}")

    _row("SpO2", "SpO2", "Apple Watch", spo2)
    _row("Ruhepuls", "Resting HR", "Garmin + Apple Watch", rhr)
    _row("Schritte", "Steps", "Garmin + Apple Watch", steps)
    _row("Stehzeit", "Stand time", "Apple Watch", stand)
    _row("Sitzzeit", "Sedentary", "Garmin/Polar", sedentary)
    _row("Hauttemp. Polar", "Skin temp Polar", "Polar Brustgurt", polar_temp)
    _row("Hauttemp. Oura", "Skin temp Oura", "Oura Ring", oura_temp)
    _row("Atemfrequenz", "Respiratory rate", "Apple Watch + Polar", list(resp.items()))
    _row("PWV", "PWV", "Polar", pwv)
    _row("Gewicht", "Weight", "Waage", weight)
    _row("Oura Recovery", "Oura Recovery", "Oura Ring", recovery)

    return lines


# ── Full report ───────────────────────────────────────────────────────────────

def build_report(d_from, d_to, spo2, rhr, steps, stand, sedentary,
                 polar_temp, oura_temp, resp, pwv, weight, recovery):
    header = section_header(d_from, d_to)
    spo2_lines, spo2_meta = section_spo2(spo2)
    rhr_lines, rhr_meta = section_resting_hr(rhr)
    act_lines = section_activity(steps, stand, sedentary)
    temp_lines = section_skin_temp(polar_temp, oura_temp)
    resp_lines = section_resp_rate(resp)
    pwv_lines = section_pwv(pwv)
    wt_lines = section_weight(weight)
    rec_lines = section_oura_recovery(recovery)
    src_lines = section_sources(spo2, rhr, steps, stand, sedentary,
                                polar_temp, oura_temp, resp, pwv, weight, recovery)

    all_lines = (
        header + spo2_lines + rhr_lines + act_lines + temp_lines
        + resp_lines + pwv_lines + wt_lines + rec_lines + src_lines
    )
    return "\n".join(all_lines), {"spo2_meta": spo2_meta, "rhr_meta": rhr_meta}


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(spo2, rhr, steps, polar_temp, resp, pwv, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    BG = "#1A1A2E"
    PANEL = "#16213E"
    GRID = "#2a2a4e"

    fig, axes = plt.subplots(2, 2, figsize=(16, 10), facecolor=BG)
    fig.suptitle(
        t(f"Gefäßgesundheit  {d_from} – {d_to}",
          f"Vascular Health  {d_from} – {d_to}"),
        color="#E0E0E0", fontsize=13, fontweight="bold",
    )

    for ax in axes.flat:
        ax.set_facecolor(PANEL)
        ax.tick_params(colors="#aaaaaa", labelsize=8)
        ax.grid(color=GRID, linewidth=0.5, linestyle="--", alpha=0.6)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444466")

    def _parse_dates(rows, date_idx=0, val_idx=1):
        dts, vals = [], []
        for r in rows:
            try:
                dts.append(datetime.fromisoformat(r[date_idx]))
                vals.append(r[val_idx])
            except Exception:
                pass
        return dts, vals

    # ── Panel 1: SpO2 ─────────────────────────────────────────────────────────
    ax1 = axes[0, 0]
    if spo2:
        dts, avgs = _parse_dates(spo2, 0, 1)
        mins = [r[2] for r in spo2]
        ax1.fill_between(dts, mins, avgs, alpha=0.25, color="#74b9ff")
        ax1.plot(dts, avgs, color="#74b9ff", lw=1.5, label=t("Ø SpO2", "Avg SpO2"), zorder=3)
        ax1.axhline(95, color="#fdcb6e", lw=1.2, ls="--", alpha=0.8,
                    label="95 % (Referenz)")
        ax1.axhline(90, color="#ff6b6b", lw=1.0, ls="--", alpha=0.7,
                    label="90 % (klinisch)")
        ax1.set_ylim(85, 102)
        ax1.set_ylabel(t("SpO2 (%)", "SpO2 (%)"), color="#cccccc", fontsize=9)
    ax1.set_title(t("Sauerstoffsättigung (SpO2)", "Oxygen Saturation (SpO2)"),
                  color="#cccccc", fontsize=9)
    ax1.legend(fontsize=7, facecolor="#0d0d1e", labelcolor="#dddddd", framealpha=0.8)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))

    # ── Panel 2: Resting HR ───────────────────────────────────────────────────
    ax2 = axes[0, 1]
    if rhr:
        dts, vals = _parse_dates(rhr)
        ax2.scatter(dts, vals, color="#ff6b6b", s=4, alpha=0.3, zorder=2)
        # 30-day MA
        vals_ma = _moving_avg(vals, 30)
        valid = [(d, v) for d, v in zip(dts, vals_ma) if v is not None]
        if valid:
            ma_dts, ma_vals = zip(*valid)
            ax2.plot(ma_dts, ma_vals, color="#ff2244", lw=2.0,
                     label=t("30-Tage-MA", "30-day MA"), zorder=3)
        ax2.axhline(100, color="#fdcb6e", lw=1.0, ls="--", alpha=0.7, label="100 bpm")
        ax2.axhline(50, color="#74b9ff", lw=1.0, ls="--", alpha=0.7, label="50 bpm")
        ax2.set_ylabel(t("Ruhepuls (bpm)", "Resting HR (bpm)"), color="#cccccc", fontsize=9)
    ax2.set_title(t("Ruhepuls-Trend", "Resting HR Trend"), color="#cccccc", fontsize=9)
    ax2.legend(fontsize=7, facecolor="#0d0d1e", labelcolor="#dddddd", framealpha=0.8)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))

    # ── Panel 3: Steps ────────────────────────────────────────────────────────
    ax3 = axes[1, 0]
    if steps:
        dts, vals = _parse_dates(steps)
        ax3.bar(dts, vals, color="#a29bfe", alpha=0.6, width=1.5, zorder=2)
        ax3.axhline(7500, color="#fdcb6e", lw=1.2, ls="--", alpha=0.8,
                    label="7 500 (WHO)")
        ax3.set_ylabel(t("Schritte/Tag", "Steps/day"), color="#cccccc", fontsize=9)
    ax3.set_title(t("Tägliche Schritte", "Daily Steps"), color="#cccccc", fontsize=9)
    ax3.legend(fontsize=7, facecolor="#0d0d1e", labelcolor="#dddddd", framealpha=0.8)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))

    # ── Panel 4: PWV or Respiratory Rate ─────────────────────────────────────
    ax4 = axes[1, 1]
    if pwv:
        dts_p, vals_p = _parse_dates(pwv)
        ax4.plot(dts_p, vals_p, color="#00cec9", lw=2.0, marker="o", ms=5,
                 label="PWV (m/s)", zorder=3)
        ax4.axhline(10.0, color="#ff6b6b", lw=1.2, ls="--", alpha=0.8,
                    label=t("10 m/s (ESC-Schwelle)", "10 m/s (ESC threshold)"))
        ax4.axhline(7.0, color="#74b9ff", lw=1.0, ls="--", alpha=0.6,
                    label="7 m/s (gut)")
        ax4.set_ylabel("PWV (m/s)", color="#cccccc", fontsize=9)
        ax4.set_title(t("Pulswellengeschwindigkeit", "Pulse Wave Velocity"),
                      color="#cccccc", fontsize=9)
    elif resp:
        dts_r = [datetime.fromisoformat(d) for d in sorted(resp.keys())]
        vals_r = [resp[d] for d in sorted(resp.keys())]
        ax4.plot(dts_r, vals_r, color="#55efc4", lw=1.5, alpha=0.8,
                 label=t("Atemfrequenz", "Resp. rate"), zorder=3)
        ax4.axhline(20, color="#fdcb6e", lw=1.2, ls="--", alpha=0.8, label="20 /min")
        ax4.axhline(12, color="#74b9ff", lw=1.0, ls="--", alpha=0.6, label="12 /min")
        ax4.set_ylabel(t("Atemfrequenz (/min)", "Resp. rate (/min)"), color="#cccccc", fontsize=9)
        ax4.set_title(t("Atemfrequenz", "Respiratory Rate"), color="#cccccc", fontsize=9)
    else:
        ax4.text(0.5, 0.5, t("Keine Daten", "No data"),
                 ha="center", va="center", color="#888888", transform=ax4.transAxes)
    ax4.legend(fontsize=7, facecolor="#0d0d1e", labelcolor="#dddddd", framealpha=0.8)
    ax4.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax4.xaxis.set_major_locator(mdates.MonthLocator(interval=3))

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.autofmt_xdate(rotation=30, ha="right")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    path = OUT_DIR / f"vascular_health_{ts}.png"
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(t(f"Plot gespeichert: {path}", f"Plot saved: {path}"))
    return path


# ── LLM ──────────────────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


# ── Save ──────────────────────────────────────────────────────────────────────

def _save(report_text, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"vascular_health_{ts}.md"
    content = f"{report_text}\n"
    if llm_text:
        content += t(
            f"\n## Klinische Einordnung\n\n{llm_text}\n",
            f"\n## Clinical Assessment\n\n{llm_text}\n",
        )
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht gespeichert: {out}", f"Report saved: {out}"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t(
            "Gefäßgesundheit: SpO2, Ruhepuls, Aktivität, Hauttemperatur, "
            "Atemfrequenz, PWV, Gewicht, Oura-Erholung",
            "Vascular health: SpO2, resting HR, activity, skin temperature, "
            "respiratory rate, PWV, weight, Oura recovery",
        )
    )
    parser.add_argument("--from", dest="date_from",
                        default=cfg.data_start or "2018-01-01",
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to", dest="date_to",
                        default=datetime.now().strftime("%Y-%m-%d"),
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--plot", action="store_true",
                        help=t("Diagramm erzeugen", "Generate plot"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Analyse überspringen", "Skip LLM analysis"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    spo2       = load_spo2(conn, args.date_from, args.date_to)
    rhr        = load_resting_hr(conn, args.date_from, args.date_to)
    steps      = load_steps(conn, args.date_from, args.date_to)
    stand      = load_stand_time(conn, args.date_from, args.date_to)
    sedentary  = load_sedentary(conn, args.date_from, args.date_to)
    polar_temp = load_skin_temp_polar(conn, args.date_from, args.date_to)
    oura_temp  = load_skin_temp_oura(conn, args.date_from, args.date_to)
    resp       = load_resp_rate(conn, args.date_from, args.date_to)
    pwv        = load_pwv(conn, args.date_from, args.date_to)
    weight     = load_weight(conn, args.date_from, args.date_to)
    recovery   = load_oura_recovery(conn, args.date_from, args.date_to)
    conn.close()

    print(t(
        f"SpO2: {len(spo2)} Tage  |  RHR: {len(rhr)} Tage  |  Schritte: {len(steps)} Tage  |  "
        f"Stehzeit: {len(stand)} Tage  |  Sitzzeit: {len(sedentary)} Tage",
        f"SpO2: {len(spo2)} days  |  RHR: {len(rhr)} days  |  Steps: {len(steps)} days  |  "
        f"Stand: {len(stand)} days  |  Sedentary: {len(sedentary)} days",
    ))
    print(t(
        f"Hauttemp Polar: {len(polar_temp)} Tage  |  Oura Temp: {len(oura_temp)} Tage  |  "
        f"Atemfreq.: {len(resp)} Tage  |  PWV: {len(pwv)} Tage  |  "
        f"Gewicht: {len(weight)} Eintr.  |  Oura Recovery: {len(recovery)} Tage",
        f"Skin temp Polar: {len(polar_temp)} days  |  Oura temp: {len(oura_temp)} days  |  "
        f"Resp. rate: {len(resp)} days  |  PWV: {len(pwv)} days  |  "
        f"Weight: {len(weight)} entries  |  Oura recovery: {len(recovery)} days",
    ))

    report_text, _ = build_report(
        args.date_from, args.date_to,
        spo2, rhr, steps, stand, sedentary,
        polar_temp, oura_temp, resp, pwv, weight, recovery,
    )
    print("\n" + report_text)

    if args.plot:
        _plot(spo2, rhr, steps, polar_temp, resp, pwv, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report_text)
    _save(report_text, llm_text)


if __name__ == "__main__":
    main()
