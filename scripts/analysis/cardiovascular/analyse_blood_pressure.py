#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Blutdruck-Trendanalyse (Blutdruckmessgerät)

Analysiert Blutdruckmessungen: Zeitreihe, Tageszeit-Profil, ESC-2023-Klassifikation,
Korrelation mit HRV und AFib, Medikamenten-Effekt auf den Blutdruck.

Usage:
  python analyse_blood_pressure.py --plot
  python analyse_blood_pressure.py --from 2025-01-01 --plot
  python analyse_blood_pressure.py --plot --no-llm
  python analyse_blood_pressure.py --lang en --plot

@tier        validated
@purpose.de  Analysiert Langzeit-Blutdruckdaten: Zeitreihe, Tageszeit-Profil, ESC-Klassifikation,
             Korrelation mit HRV und Arrhythmie sowie Medikamenten-Effekt.
@purpose.en  Analyses long-term blood pressure data: time series, time-of-day profile,
             ESC classification, correlation with HRV and arrhythmia, and medication effect.
@method.de   BP-Klassifikation nach ESC 2024 (McEvoy et al., Eur Heart J 2024) mit 6 Klassen.
             ESC 2024 definiert offiziell 4 Klassen (Normal <130/85, Erhöhter Blutdruck 130–139/
             85–89, Grad 1 140–159/90–99, Grad 2 ≥160/≥100). Zwei bewusste Abweichungen:
             (1) "Optimal" (<120/80) wird zusätzlich ausgewiesen — als Orientierung, wohin die
             Reise idealerweise gehen sollte (aspiratorischer Zielwert, pädagogisch sinnvoll).
             (2) "Grad 3" (≥180/≥110) wird trotz Zusammenlegung mit Grad 2 in ESC 2024 separat
             ausgewiesen — damit erkennbar bleibt, wann allerhöchste Eisenbahn ist und sofortiges
             ärztliches Handeln erforderlich wäre. Terminologie-Update: "Hochnormal" →
             "Erhöhter Blutdruck" gemäß ESC 2024. PWV-Referenz: ESC 2018 PWV >10 m/s.
@method.en   BP classification per ESC 2024 (McEvoy et al., Eur Heart J 2024) with 6 classes.
             ESC 2024 officially defines 4 classes (Normal <130/85, Elevated BP 130–139/85–89,
             Grade 1 140–159/90–99, Grade 2 ≥160/≥100). Two intentional deviations:
             (1) "Optimal" (<120/80) is retained as an additional class — as an aspirational
             target showing where BP ideally should be headed (pedagogically valuable).
             (2) "Grade 3" (≥180/≥110) is kept despite being merged into Grade 2 in ESC 2024 —
             to make it immediately visible when the situation is truly urgent and immediate
             medical action would be required. Terminology update: "High-normal" →
             "Elevated BP" per ESC 2024. PWV reference: ESC 2018 PWV >10 m/s.
@refs        McEvoy JW, McCarthy CP, Bruno RM, et al. (2024). 2024 ESC Guidelines for the management of elevated blood pressure and hypertension. European Heart Journal. doi:10.1093/eurheartj/ehae178
             Williams B, Mancia G, Spiering W et al. (2018). 2018 ESC/ESH Guidelines for the management of arterial hypertension. European Heart Journal, 39(33):3021-3104. doi:10.1093/eurheartj/ehy339

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@limits.de   Heimblutdruckmessungen ohne standardisiertes Protokoll (Ruhe, Wiederholung).
             Keine 24h-ABPM. n=1, Consumer-Gerät, Messzeitpunkte nicht kontrolliert.
@limits.en   Home BP measurements without standardised protocol (rest, repetition).
             No 24h-ABPM. n=1, consumer device, measurement timing not controlled.
@reads       blood_pressure, arrhythmie_episoden, daily_stress, measurements
@writes      analyses/cardiovascular/*.{md,png} (kein DB-Write)

@usage
    python analyse_blood_pressure.py
    python analyse_blood_pressure.py --help
    python analyse_blood_pressure.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config, OWN_PERSON_ID, KYORO_CONFIG_DIR
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_BLOOD_PRESSURE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_BLOOD_PRESSURE_EN as SYSTEM_PROMPT_EN,
)

cfg = Config()
DB_PATH = cfg.db_path
OUT_DIR = cfg.analyses_dir / "cardiovascular"

MEDICATION_START = None  # Set via config: clinical.medication_start (YYYY-MM-DD)


# ESC 2024 classification — McEvoy et al. 2024, Eur Heart J, doi:10.1093/eurheartj/ehae178
#
# Offizielle ESC-2024-Klassen: Normal <130/85, Erhöhter Blutdruck 130–139/85–89,
# Grad 1 140–159/90–99, Grad 2 ≥160/≥100.
#
# Bewusste Abweichungen (dokumentiert in @method.de):
#   "Optimal" (<120/80): In ESC 2024 nicht mehr als eigene Klasse ausgewiesen.
#     Wird hier behalten als aspiratorischer Zielwert — damit sichtbar bleibt,
#     wo der Blutdruck idealerweise liegen sollte.
#   "Grad 3" (≥180/≥110): In ESC 2024 in Grad 2 aufgegangen.
#     Wird hier separat behalten — damit sofort erkennbar ist, wenn allerhöchste
#     Eisenbahn ist und umgehend ärztliches Handeln erforderlich wäre.
#
# Terminologie-Update gegenüber ESC 2018: "Hochnormal" → "Erhöhter Blutdruck" (ESC 2024).
ESC_CLASSES = [
    (120, 80,  "Optimal",                          "Optimal"),
    (130, 85,  "Normal",                            "Normal"),
    (140, 90,  "Erhöhter Blutdruck",               "Elevated BP"),
    (160, 100, "Grad 1 (leichte Hypertonie)",       "Grade 1 (mild hypertension)"),
    (180, 110, "Grad 2 (moderate Hypertonie)",      "Grade 2 (moderate hypertension)"),
    (999, 999, "Grad 3 (schwere Hypertonie)",       "Grade 3 (severe hypertension)"),
]


def _classify_esc(sys_val, dia_val):
    for s_thr, d_thr, label_de, label_en in ESC_CLASSES:
        if sys_val < s_thr and dia_val < d_thr:
            return t(label_de, label_en)
    return t("Grad 3 (schwere Hypertonie)", "Grade 3 (severe hypertension)")


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


def _time_slot(ts_str):
    """Map timestamp string to time-of-day slot."""
    if not ts_str or len(ts_str) < 13:
        return t("Unbekannt", "Unknown")
    try:
        h = int(ts_str[11:13])
    except ValueError:
        return t("Unbekannt", "Unknown")
    if 6 <= h < 10:
        return t("Morgen (06-10)", "Morning (06-10)")
    if 10 <= h < 14:
        return t("Mittag (10-14)", "Noon (10-14)")
    if 14 <= h < 18:
        return t("Nachmittag (14-18)", "Afternoon (14-18)")
    if 18 <= h < 22:
        return t("Abend (18-22)", "Evening (18-22)")
    return t("Nacht (22-06)", "Night (22-06)")


def _moving_avg(values, window=14):
    """Simple moving average — returns list of same length (leading values = None)."""
    result = []
    for i, v in enumerate(values):
        if i < window - 1:
            result.append(None)
        else:
            chunk = values[i - window + 1 : i + 1]
            result.append(sum(chunk) / len(chunk))
    return result


def _conn():
    return open_db()


# ── Data loading ──────────────────────────────────────────────────────────────

def _table_exists(conn, name):
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return bool(row and row[0])


def load_bp(conn, d_from, d_to):
    """Load blood_pressure rows for OWN_PERSON_ID in date range.
    Tuple: (ts, date, systolic, diastolic, pulse, ihb_flag, afib_possible)
    """
    rows = conn.execute(
        """
        SELECT ts, date, systolic, diastolic, pulse,
               COALESCE(ihb_flag, 0), COALESCE(afib_possible, 0)
        FROM blood_pressure
        WHERE person = ?
          AND date >= ? AND date <= ?
          AND systolic IS NOT NULL
          AND diastolic IS NOT NULL
        ORDER BY ts
        """,
        (OWN_PERSON_ID, d_from, d_to),
    ).fetchall()
    return rows


def load_hrv(conn, d_from, d_to):
    """Multi-source HRV RMSSD keyed by date: measurements → polar_nightly_hrv → daily_stress."""
    hrv = {}
    # Primary: Apple/canonical aggregated HRV
    if _table_exists(conn, "measurements"):
        for row in conn.execute(
            "SELECT DATE(ts) AS d, AVG(value) FROM measurements "
            "WHERE metric='hrv_rmssd' AND person=? AND DATE(ts)>=? AND DATE(ts)<=? "
            "GROUP BY d",
            (OWN_PERSON_ID, d_from, d_to),
        ):
            if row[1] is not None:
                hrv[row[0]] = round(row[1], 1)
    # Supplement: Polar nightly HRV
    if _table_exists(conn, "polar_nightly_hrv"):
        for row in conn.execute(
            "SELECT date, rmssd_ms FROM polar_nightly_hrv WHERE date>=? AND date<=?",
            (d_from, d_to),
        ):
            if row[0] not in hrv and row[1] is not None:
                hrv[row[0]] = row[1]
    # Supplement: daily_stress RMSSD (Garmin + multi-source composite)
    if _table_exists(conn, "daily_stress"):
        for row in conn.execute(
            "SELECT date, rmssd_ms FROM daily_stress "
            "WHERE date>=? AND date<=? AND rmssd_ms IS NOT NULL AND rmssd_ms>0",
            (d_from, d_to),
        ):
            if row[0] not in hrv and row[1] is not None:
                hrv[row[0]] = row[1]
    return hrv


def load_pwv(conn, d_from, d_to):
    """Load pulse wave velocity (m/s) from measurements, daily average."""
    if not _table_exists(conn, "measurements"):
        return {}
    rows = conn.execute(
        "SELECT DATE(ts) AS d, AVG(value) FROM measurements "
        "WHERE metric='pulse_wave_velocity' AND person=? AND DATE(ts)>=? AND DATE(ts)<=? "
        "GROUP BY d ORDER BY d",
        (OWN_PERSON_ID, d_from, d_to),
    ).fetchall()
    return {r[0]: round(r[1], 2) for r in rows if r[1] is not None}


def load_resting_hr(conn, d_from, d_to):
    """Load resting heart rate from daily_stress, keyed by date."""
    if not _table_exists(conn, "daily_stress"):
        return {}
    rows = conn.execute(
        "SELECT date, resting_hr FROM daily_stress "
        "WHERE date>=? AND date<=? AND resting_hr IS NOT NULL AND resting_hr>0",
        (d_from, d_to),
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def load_afib_dates(conn, d_from, d_to):
    """Return set of dates that contain at least one AFib episode."""
    if not _table_exists(conn, "arrhythmie_episoden"):
        return set()
    rows = conn.execute(
        "SELECT date(episode_start) FROM arrhythmie_episoden "
        "WHERE date(episode_start) >= ? AND date(episode_start) <= ?",
        (d_from, d_to),
    ).fetchall()
    return {r[0] for r in rows if r[0]}


# ── Report sections ───────────────────────────────────────────────────────────

def section_overview(bp):
    n = len(bp)
    dates = sorted({r[1] for r in bp})
    d_first, d_last = dates[0], dates[-1]
    span_days = (datetime.fromisoformat(d_last) - datetime.fromisoformat(d_first)).days + 1
    weeks = max(span_days / 7, 1)
    meas_per_week = round(n / weeks, 1)

    sys_vals = [r[2] for r in bp]
    dia_vals = [r[3] for r in bp]
    pul_vals = [r[4] for r in bp if r[4]]
    avg_sys = round(sum(sys_vals) / n, 1)
    avg_dia = round(sum(dia_vals) / n, 1)
    avg_pul = round(sum(pul_vals) / len(pul_vals), 1) if pul_vals else None
    pp_vals = [s - d for s, d in zip(sys_vals, dia_vals)]
    avg_pp = round(sum(pp_vals) / n, 1)

    overall_class = _classify_esc(avg_sys, avg_dia)

    lines = [
        t("## 1. Datenübersicht", "## 1. Data Overview"),
        "",
        t(f"Messungen gesamt : **{n}**", f"Total measurements : **{n}**"),
        t(f"Zeitraum         : {d_first} – {d_last} ({span_days} Tage)",
          f"Date range        : {d_first} – {d_last} ({span_days} days)"),
        t(f"Messfrequenz     : **{meas_per_week} / Woche** im Durchschnitt",
          f"Measurement freq  : **{meas_per_week} / week** on average"),
        t(f"Ø Systolisch     : **{avg_sys} mmHg**",
          f"Avg systolic      : **{avg_sys} mmHg**"),
        t(f"Ø Diastolisch    : **{avg_dia} mmHg**",
          f"Avg diastolic     : **{avg_dia} mmHg**"),
    ]
    if avg_pul:
        lines.append(t(f"Ø Puls           : {avg_pul} bpm",
                       f"Avg pulse         : {avg_pul} bpm"))
    n_ihb   = sum(1 for r in bp if r[5])
    n_afib  = sum(1 for r in bp if r[6])
    lines += [
        t(f"Ø Pulsdruck      : {avg_pp} mmHg",
          f"Avg pulse pressure: {avg_pp} mmHg"),
        t(f"ESC-Klasse (Ø)   : **{overall_class}**",
          f"ESC class (avg)   : **{overall_class}**"),
        t(f"Omron IHB-Flag   : {n_ihb}/{n} Messungen",
          f"Omron IHB flag    : {n_ihb}/{n} measurements"),
        t(f"Omron AFib-Flag  : {n_afib}/{n} Messungen"
          + (" ⚠" if n_afib > 0 else ""),
          f"Omron AFib flag   : {n_afib}/{n} measurements"
          + (" ⚠" if n_afib > 0 else "")),
    ]
    return lines, {"avg_sys": avg_sys, "avg_dia": avg_dia, "avg_pp": avg_pp,
                   "sys_vals": sys_vals, "dia_vals": dia_vals, "pp_vals": pp_vals,
                   "n": n, "dates": dates, "overall_class": overall_class}


def section_esc_distribution(bp):
    n = len(bp)
    dist = defaultdict(int)
    for r in bp:
        dist[_classify_esc(r[2], r[3])] += 1

    order_de = [
        "Optimal", "Normal", "Erhöhter Blutdruck",
        "Grad 1 (leichte Hypertonie)", "Grad 2 (moderate Hypertonie)",
        "Grad 3 (schwere Hypertonie)",
    ]
    order_en = [
        "Optimal", "Normal", "Elevated BP",
        "Grade 1 (mild hypertension)", "Grade 2 (moderate hypertension)",
        "Grade 3 (severe hypertension)",
    ]
    order = t(order_de, order_en)

    lines = [
        "",
        t("## 2. ESC-2024-Klassifikation (Verteilung)", "## 2. ESC-2024 Classification (Distribution)"),
        "",
        t(f"  {'Klasse':<35} {'n':>5}  {'%':>6}", f"  {'Category':<35} {'n':>5}  {'%':>6}"),
        "  " + "-" * 50,
    ]
    for label in order:
        count = dist.get(label, 0)
        pct = round(count / n * 100, 1) if n else 0
        marker = " <--" if count == max(dist.values()) else ""
        lines.append(f"  {label:<35} {count:>5}  {pct:>5.1f}%{marker}")
    return lines


def section_monthly_trend(bp):
    monthly_sys = defaultdict(list)
    monthly_dia = defaultdict(list)
    for r in bp:
        ym = r[1][:7]  # YYYY-MM
        monthly_sys[ym].append(r[2])
        monthly_dia[ym].append(r[3])

    months = sorted(monthly_sys)
    lines = [
        "",
        t("## 3. Monatlicher Trend", "## 3. Monthly Trend"),
        "",
        t(f"  {'Monat':<9} {'Ø Sys':>7} {'Ø Dia':>7} {'n':>5}",
          f"  {'Month':<9} {'Avg Sys':>8} {'Avg Dia':>8} {'n':>5}"),
        "  " + "-" * 35,
    ]
    for ym in months:
        s = monthly_sys[ym]
        d = monthly_dia[ym]
        avg_s = round(sum(s) / len(s), 1)
        avg_d = round(sum(d) / len(d), 1)
        flag = ""
        if avg_s >= 140:
            flag = t(" ⚠ Grad 1", " ⚠ Grade 1")
        elif avg_s >= 130:
            flag = t(" ! Hochnormal", " ! High-normal")
        lines.append(f"  {ym:<9} {avg_s:>7.1f} {avg_d:>7.1f} {len(s):>5}{flag}")
    return lines, {"monthly_sys": monthly_sys, "monthly_dia": monthly_dia}


def section_time_of_day(bp):
    slot_order = [
        t("Morgen (06-10)", "Morning (06-10)"),
        t("Mittag (10-14)", "Noon (10-14)"),
        t("Nachmittag (14-18)", "Afternoon (14-18)"),
        t("Abend (18-22)", "Evening (18-22)"),
        t("Nacht (22-06)", "Night (22-06)"),
    ]
    slot_sys = defaultdict(list)
    slot_dia = defaultdict(list)

    has_time = any(r[0] and len(r[0]) >= 13 for r in bp)

    for r in bp:
        slot = _time_slot(r[0])
        slot_sys[slot].append(r[2])
        slot_dia[slot].append(r[3])

    lines = [
        "",
        t("## 4. Tageszeit-Profil", "## 4. Time-of-Day Profile"),
        "",
    ]

    if not has_time:
        lines.append(t("  (Kein Zeitstempel mit Uhrzeit vorhanden — Profil nicht verfügbar)",
                       "  (No timestamps with time-of-day info — profile unavailable)"))
        return lines, {}

    lines += [
        t(f"  {'Zeitslot':<22} {'Ø Sys':>7} {'±SD':>6} {'Ø Dia':>7} {'±SD':>6} {'n':>5}",
          f"  {'Time slot':<22} {'Avg Sys':>8} {'±SD':>6} {'Avg Dia':>8} {'±SD':>6} {'n':>5}"),
        "  " + "-" * 62,
    ]

    def _sd(vals, mean):
        if len(vals) < 2:
            return 0.0
        return math.sqrt(sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)) if len(vals) > 1 else 0.0

    tod_stats = {}
    for slot in slot_order:
        s = slot_sys.get(slot, [])
        d = slot_dia.get(slot, [])
        if not s:
            continue
        avg_s = round(sum(s) / len(s), 1)
        avg_d = round(sum(d) / len(d), 1)
        sd_s = round(_sd(s, avg_s), 1)
        sd_d = round(_sd(d, avg_d), 1)
        tod_stats[slot] = (avg_s, sd_s, avg_d, sd_d, len(s))
        lines.append(
            f"  {slot:<22} {avg_s:>7.1f} {sd_s:>6.1f} {avg_d:>7.1f} {sd_d:>6.1f} {len(s):>5}"
        )
    return lines, {"tod_stats": tod_stats, "slot_sys": slot_sys, "slot_dia": slot_dia}


def section_medication_effect(bp, medication_start):
    """Compare blood pressure 30 days before/after a configurable medication start date."""
    if not medication_start:
        return [
            "",
            t("## 5. Medikamenten-Effekt", "## 5. Medication Effect"),
            "",
            t("  (Kein Medikamenten-Startdatum konfiguriert — "
              "in health_config.json unter clinical.medication_start setzen)",
              "  (No medication start date configured — "
              "set clinical.medication_start in health_config.json)"),
        ]

    med_dt = datetime.fromisoformat(medication_start)
    before_start = (med_dt - timedelta(days=30)).strftime("%Y-%m-%d")
    after_end = (med_dt + timedelta(days=30)).strftime("%Y-%m-%d")

    before_sys, before_dia = [], []
    after_sys, after_dia = [], []

    for r in bp:
        d = r[1]
        if before_start <= d < medication_start:
            before_sys.append(r[2])
            before_dia.append(r[3])
        elif medication_start <= d <= after_end:
            after_sys.append(r[2])
            after_dia.append(r[3])

    lines = [
        "",
        t(f"## 5. Medikamenten-Effekt (Start {medication_start})",
          f"## 5. Medication Effect (started {medication_start})"),
        "",
        t(f"  Vergleichsfenster: 30 Tage vorher ({before_start} – {medication_start}) "
          f"vs. 30 Tage nachher ({medication_start} – {after_end})",
          f"  Comparison window: 30 days before ({before_start} – {medication_start}) "
          f"vs. 30 days after ({medication_start} – {after_end})"),
        "",
    ]

    if not before_sys and not after_sys:
        lines.append(t("  Keine Daten in diesem Zeitfenster.",
                       "  No data in this time window."))
        return lines

    if before_sys:
        bs = round(sum(before_sys) / len(before_sys), 1)
        bd = round(sum(before_dia) / len(before_dia), 1)
    else:
        bs, bd = None, None

    if after_sys:
        as_ = round(sum(after_sys) / len(after_sys), 1)
        ad = round(sum(after_dia) / len(after_dia), 1)
    else:
        as_, ad = None, None

    hdr = t(f"  {'Zeitraum':<20} {'Ø Sys':>8} {'Ø Dia':>8} {'n':>5}",
            f"  {'Period':<20} {'Avg Sys':>8} {'Avg Dia':>8} {'n':>5}")
    lines.append(hdr)
    lines.append("  " + "-" * 46)

    if bs is not None:
        lines.append(t(f"  {'Vorher (−30d)':<20} {bs:>8.1f} {bd:>8.1f} {len(before_sys):>5}",
                       f"  {'Before (−30d)':<20} {bs:>8.1f} {bd:>8.1f} {len(before_sys):>5}"))
    else:
        lines.append(t("  Vorher: keine Daten", "  Before: no data"))

    if as_ is not None:
        lines.append(t(f"  {'Nachher (+30d)':<20} {as_:>8.1f} {ad:>8.1f} {len(after_sys):>5}",
                       f"  {'After (+30d)':<20} {as_:>8.1f} {ad:>8.1f} {len(after_sys):>5}"))
    else:
        lines.append(t("  Nachher: keine Daten", "  After: no data"))

    if bs is not None and as_ is not None:
        delta_s = round(as_ - bs, 1)
        delta_d = round(ad - bd, 1)
        note = t(
            "  (Hinweis: Blutdruckveränderungen nach Therapiebeginn klinisch beobachten.)",
            "  (Note: Monitor blood pressure changes after therapy start closely.)",
        )
        lines += [
            t(f"\n  Δ Systolisch : {delta_s:+.1f} mmHg",
              f"\n  Δ Systolic   : {delta_s:+.1f} mmHg"),
            t(f"  Δ Diastolisch: {delta_d:+.1f} mmHg",
              f"  Δ Diastolic  : {delta_d:+.1f} mmHg"),
            note,
        ]
    return lines


def section_hrv_correlation(bp, hrv):
    lines = [
        "",
        t("## 6. HRV-Korrelation (RMSSD × Blutdruck)",
          "## 6. HRV Correlation (RMSSD × Blood Pressure)"),
        "",
    ]
    if not hrv:
        lines.append(t("  Keine HRV-Daten verfügbar.",
                       "  No HRV data available."))
        return lines

    # Daily average BP per date
    daily_sys = defaultdict(list)
    daily_dia = defaultdict(list)
    for r in bp:
        daily_sys[r[1]].append(r[2])
        daily_dia[r[1]].append(r[3])

    common_dates = sorted(d for d in daily_sys if d in hrv)
    if len(common_dates) < 2:
        lines.append(t(f"  Keine gemeinsamen Datenpunkte (n={len(common_dates)}) — "
                       "Hauptlücke: Jan–Feb 2026 kein Gerät hat HRV aufgezeichnet.",
                       f"  No shared data points (n={len(common_dates)}) — "
                       "main gap: Jan–Feb 2026 no device recorded HRV on those dates."))
        return lines

    # Show data table regardless of n
    lines += [
        t(f"  {'Datum':<12} {'RMSSD (ms)':>11} {'Ø Sys':>8} {'Ø Dia':>8}",
          f"  {'Date':<12} {'RMSSD (ms)':>11} {'Avg Sys':>8} {'Avg Dia':>8}"),
        "  " + "-" * 46,
    ]
    avg_sys_by_date = []
    avg_dia_by_date = []
    rmssd_by_date = []
    for d in common_dates:
        avg_s = round(sum(daily_sys[d]) / len(daily_sys[d]), 1)
        avg_d = round(sum(daily_dia[d]) / len(daily_dia[d]), 1)
        lines.append(f"  {d:<12} {hrv[d]:>11.1f} {avg_s:>8.1f} {avg_d:>8.1f}")
        avg_sys_by_date.append(avg_s)
        avg_dia_by_date.append(avg_d)
        rmssd_by_date.append(hrv[d])
    lines.append("")

    r_sys = _pearson(avg_sys_by_date, rmssd_by_date)
    r_dia = _pearson(avg_dia_by_date, rmssd_by_date)

    def _interpret(r):
        if r is None:
            return t("nicht berechenbar", "not computable")
        ar = abs(r)
        if ar >= 0.5:
            direction = t("stark", "strong")
        elif ar >= 0.3:
            direction = t("moderat", "moderate")
        elif ar >= 0.1:
            direction = t("schwach", "weak")
        else:
            direction = t("kein", "no")
        sign = t("negativ", "negative") if r < 0 else t("positiv", "positive")
        return f"{direction} {sign}"

    lines += [
        t(f"  Gemeinsame Tage         : {len(common_dates)}  "
          f"{'(Korrelation ≥3 Punkte erforderlich)' if len(common_dates) < 3 else ''}",
          f"  Shared days              : {len(common_dates)}  "
          f"{'(correlation requires ≥3 points)' if len(common_dates) < 3 else ''}"),
        t(f"  r(Systolisch × RMSSD)   : {r_sys:.3f}  → {_interpret(r_sys)}"
          if r_sys is not None else "  r(Systolisch × RMSSD)   : n/a (n<3)",
          f"  r(Systolic × RMSSD)      : {r_sys:.3f}  → {_interpret(r_sys)}"
          if r_sys is not None else "  r(Systolic × RMSSD)      : n/a (n<3)"),
        t(f"  r(Diastolisch × RMSSD)  : {r_dia:.3f}  → {_interpret(r_dia)}"
          if r_dia is not None else "  r(Diastolisch × RMSSD)  : n/a (n<3)",
          f"  r(Diastolic × RMSSD)     : {r_dia:.3f}  → {_interpret(r_dia)}"
          if r_dia is not None else "  r(Diastolic × RMSSD)     : n/a (n<3)"),
        t("  (Negatives r = höherer Blutdruck → niedrigere HRV, klinisch plausibel)",
          "  (Negative r = higher BP → lower HRV, clinically plausible)"),
    ]
    return lines


def section_afib_correlation(bp, afib_dates):
    lines = [
        "",
        t("## 7. AFib-Tage vs. Nicht-AFib-Tage",
          "## 7. AFib Days vs. Non-AFib Days"),
        "",
    ]
    if not afib_dates:
        lines.append(t("  Keine AFib-Episodendaten verfügbar.",
                       "  No AFib episode data available."))
        return lines

    sys_afib, dia_afib = [], []
    sys_no, dia_no = [], []
    for r in bp:
        if r[1] in afib_dates:
            sys_afib.append(r[2])
            dia_afib.append(r[3])
        else:
            sys_no.append(r[2])
            dia_no.append(r[3])

    lines.append(t(f"  {'Gruppe':<22} {'Ø Sys':>8} {'Ø Dia':>8} {'n':>5}",
                   f"  {'Group':<22} {'Avg Sys':>8} {'Avg Dia':>8} {'n':>5}"))
    lines.append("  " + "-" * 48)

    if sys_afib:
        as_ = round(sum(sys_afib) / len(sys_afib), 1)
        ad = round(sum(dia_afib) / len(dia_afib), 1)
        lines.append(t(f"  {'Tage mit AFib':<22} {as_:>8.1f} {ad:>8.1f} {len(sys_afib):>5}",
                       f"  {'Days with AFib':<22} {as_:>8.1f} {ad:>8.1f} {len(sys_afib):>5}"))
    else:
        lines.append(t("  Tage mit AFib: keine Überlappung", "  Days with AFib: no overlap"))

    if sys_no:
        ns = round(sum(sys_no) / len(sys_no), 1)
        nd = round(sum(dia_no) / len(dia_no), 1)
        lines.append(t(f"  {'Tage ohne AFib':<22} {ns:>8.1f} {nd:>8.1f} {len(sys_no):>5}",
                       f"  {'Days without AFib':<22} {ns:>8.1f} {nd:>8.1f} {len(sys_no):>5}"))

    if sys_afib and sys_no:
        delta_s = round(sum(sys_afib) / len(sys_afib) - sum(sys_no) / len(sys_no), 1)
        delta_d = round(sum(dia_afib) / len(dia_afib) - sum(dia_no) / len(dia_no), 1)
        lines += [
            t(f"\n  Δ Systolisch (AFib − kein AFib) : {delta_s:+.1f} mmHg",
              f"\n  Δ Systolic (AFib − no AFib)      : {delta_s:+.1f} mmHg"),
            t(f"  Δ Diastolisch (AFib − kein AFib): {delta_d:+.1f} mmHg",
              f"  Δ Diastolic (AFib − no AFib)     : {delta_d:+.1f} mmHg"),
        ]

    # Omron-eigene Flags (per-measurement, simultan mit BP)
    omron_afib = [r for r in bp if r[6]]
    omron_ihb  = [r for r in bp if r[5]]
    lines += [
        "",
        t("### 7b. Omron-Echtzeit-Flags (simultane Erkennung)",
          "### 7b. Omron real-time flags (concurrent detection)"),
        t("  (IHB = Irregular Heart Beat; AFib-möglich = Vorhofflimmern-Verdacht beim Messen)",
          "  (IHB = Irregular Heart Beat; AFib-possible = AF suspicion during measurement)"),
        "",
    ]
    n_total = len(bp)
    if not omron_afib and not omron_ihb:
        lines.append(t(
            f"  Keine Flags in {n_total} Messungen — alle im Sinusrhythmus.",
            f"  No flags in {n_total} measurements — all in sinus rhythm.",
        ))
    else:
        if omron_ihb:
            ihb_sys = [r[2] for r in omron_ihb]
            ihb_dia = [r[3] for r in omron_ihb]
            lines.append(t(
                f"  IHB-Flag: {len(omron_ihb)}/{n_total} Messungen  "
                f"Ø {round(sum(ihb_sys)/len(ihb_sys),1)}/{round(sum(ihb_dia)/len(ihb_dia),1)} mmHg",
                f"  IHB flag: {len(omron_ihb)}/{n_total} measurements  "
                f"avg {round(sum(ihb_sys)/len(ihb_sys),1)}/{round(sum(ihb_dia)/len(ihb_dia),1)} mmHg",
            ))
            for r in omron_ihb:
                lines.append(f"    {r[0][:16]}  {r[2]}/{r[3]} mmHg  IHB")
        if omron_afib:
            af_sys = [r[2] for r in omron_afib]
            af_dia = [r[3] for r in omron_afib]
            lines.append(t(
                f"  AFib-möglich: {len(omron_afib)}/{n_total} Messungen ⚠  "
                f"Ø {round(sum(af_sys)/len(af_sys),1)}/{round(sum(af_dia)/len(af_dia),1)} mmHg",
                f"  AFib-possible: {len(omron_afib)}/{n_total} measurements ⚠  "
                f"avg {round(sum(af_sys)/len(af_sys),1)}/{round(sum(af_dia)/len(af_dia),1)} mmHg",
            ))
            for r in omron_afib:
                lines.append(f"    {r[0][:16]}  {r[2]}/{r[3]} mmHg  AFib⚠")
    return lines


def section_pulse_pressure(bp, stats):
    pp_vals = stats["pp_vals"]
    avg_pp = stats["avg_pp"]
    n = len(pp_vals)

    elevated = sum(1 for v in pp_vals if v > 40)
    high = sum(1 for v in pp_vals if v > 60)
    trend_note = ""

    # Simple linear trend on pulse pressure over time (ordinal days)
    dates_ord = []
    for r in bp:
        try:
            dates_ord.append((datetime.fromisoformat(r[1]).toordinal(), r[2] - r[3]))
        except Exception:
            pass
    if len(dates_ord) >= 10:
        n_r = len(dates_ord)
        xs = [x for x, _ in dates_ord]
        ys = [y for _, y in dates_ord]
        mx, my = sum(xs) / n_r, sum(ys) / n_r
        cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n_r))
        var = sum((xs[i] - mx) ** 2 for i in range(n_r))
        slope_yr = round(cov / var * 365, 1) if var > 0 else 0.0
        trend_note = t(f"Trend: {slope_yr:+.1f} mmHg/Jahr",
                       f"Trend: {slope_yr:+.1f} mmHg/year")

    if avg_pp > 60:
        clinical_note = t(
            "⚠ Stark erhöhter Pulsdruck (>60 mmHg) — deutet auf erhöhte arterielle Steifigkeit hin.",
            "⚠ Markedly elevated pulse pressure (>60 mmHg) — indicates increased arterial stiffness.",
        )
    elif avg_pp > 40:
        clinical_note = t(
            "! Erhöhter Pulsdruck (>40 mmHg) — arterielle Steifigkeit möglich, Monitoring empfohlen.",
            "! Elevated pulse pressure (>40 mmHg) — possible arterial stiffness, monitoring recommended.",
        )
    else:
        clinical_note = t(
            "Pulsdruck im Normalbereich (≤40 mmHg).",
            "Pulse pressure within normal range (≤40 mmHg).",
        )

    lines = [
        "",
        t("## 8. Pulsdruck (Systolisch − Diastolisch)",
          "## 8. Pulse Pressure (Systolic − Diastolic)"),
        "",
        t(f"  Ø Pulsdruck          : **{avg_pp} mmHg**",
          f"  Avg pulse pressure    : **{avg_pp} mmHg**"),
        t(f"  Min / Max            : {min(pp_vals)} / {max(pp_vals)} mmHg",
          f"  Min / Max             : {min(pp_vals)} / {max(pp_vals)} mmHg"),
        t(f"  >40 mmHg (erhöht)    : {elevated}/{n} ({round(elevated/n*100,1)}%)",
          f"  >40 mmHg (elevated)   : {elevated}/{n} ({round(elevated/n*100,1)}%)"),
        t(f"  >60 mmHg (stark↑)    : {high}/{n} ({round(high/n*100,1)}%)",
          f"  >60 mmHg (markedly↑)  : {high}/{n} ({round(high/n*100,1)}%)"),
    ]
    if trend_note:
        lines.append(f"  {trend_note}")
    lines.append(f"\n  {clinical_note}")
    return lines


def _classify_pwv(v):
    if v < 7.0:
        return t("gut (<7 m/s)", "good (<7 m/s)")
    if v < 9.0:
        return t("normal (7–9 m/s)", "normal (7–9 m/s)")
    if v < 10.0:
        return t("grenzwertig (9–10 m/s)", "borderline (9–10 m/s)")
    return t("erhöht >10 m/s (ESC-Schwelle)", "elevated >10 m/s (ESC threshold)")


def section_arterial_stiffness(bp, pwv, resting_hr):
    lines = [
        "",
        t("## 9. Arterielle Steifigkeit (Ergänzende Faktoren)",
          "## 9. Arterial Stiffness (Supplementary Factors)"),
        "",
    ]

    # ── Pulse Wave Velocity ──────────────────────────────────────────────────
    lines.append(t("### 9a. Pulswellengeschwindigkeit (PWV)",
                   "### 9a. Pulse Wave Velocity (PWV)"))
    lines.append("")

    if pwv:
        pwv_vals = list(pwv.values())
        avg_pwv = round(sum(pwv_vals) / len(pwv_vals), 2)
        min_pwv = round(min(pwv_vals), 2)
        max_pwv = round(max(pwv_vals), 2)

        lines += [
            t(f"  Zeitraum      : {min(pwv)} – {max(pwv)} ({len(pwv)} Tage)",
              f"  Period        : {min(pwv)} – {max(pwv)} ({len(pwv)} days)"),
            t(f"  Ø PWV         : **{avg_pwv} m/s** → {_classify_pwv(avg_pwv)}",
              f"  Avg PWV       : **{avg_pwv} m/s** → {_classify_pwv(avg_pwv)}"),
            t(f"  Min / Max     : {min_pwv} / {max_pwv} m/s",
              f"  Min / Max     : {min_pwv} / {max_pwv} m/s"),
            t("  Referenz (ESC 2018): <7 gut · 7–9 normal · 9–10 grenzwertig · >10 erhöht",
              "  Reference (ESC 2018): <7 good · 7–9 normal · 9–10 borderline · >10 elevated"),
            "",
            t(f"  {'Datum':<12} {'PWV (m/s)':>10}   {'Bewertung'}",
              f"  {'Date':<12} {'PWV (m/s)':>10}   {'Assessment'}"),
            "  " + "-" * 48,
        ]
        for d in sorted(pwv):
            lines.append(f"  {d:<12} {pwv[d]:>10.2f}   {_classify_pwv(pwv[d])}")

        bp_dates = {r[1] for r in bp}
        if not (bp_dates & set(pwv.keys())):
            lines += [
                "",
                t("  ℹ Keine zeitliche Überlappung mit BP-Messungen "
                  "(BP bis 18.05.2026, PWV ab 19.05.2026).",
                  "  ℹ No temporal overlap with BP measurements "
                  "(BP up to 2026-05-18, PWV from 2026-05-19)."),
                t("  PWV zeigt den aktuellen Gefäßsteifigkeitsstatus.",
                  "  PWV reflects current vascular stiffness status."),
            ]
    else:
        lines += [
            t("  Keine PWV-Daten im Auswertungszeitraum.",
              "  No PWV data in the evaluation period."),
            t("  (Quelle: measurements.pulse_wave_velocity — verfügbar ab Mai 2026)",
              "  (Source: measurements.pulse_wave_velocity — available from May 2026)"),
        ]

    # ── Resting HR × BP correlation ──────────────────────────────────────────
    lines += [
        "",
        t("### 9b. Ruheherzfrequenz × Blutdruck",
          "### 9b. Resting Heart Rate × Blood Pressure"),
        "",
    ]

    if resting_hr:
        daily_sys = defaultdict(list)
        for r in bp:
            daily_sys[r[1]].append(r[2])

        common = sorted(d for d in daily_sys if d in resting_hr)

        if len(common) >= 2:
            lines += [
                t(f"  {'Datum':<12} {'RHR (bpm)':>10} {'Ø Sys':>8}",
                  f"  {'Date':<12} {'RHR (bpm)':>10} {'Avg Sys':>8}"),
                "  " + "-" * 35,
            ]
            avg_sys_list = []
            rhr_list = []
            for d in common:
                avg_s = round(sum(daily_sys[d]) / len(daily_sys[d]), 1)
                lines.append(f"  {d:<12} {resting_hr[d]:>10.1f} {avg_s:>8.1f}")
                avg_sys_list.append(avg_s)
                rhr_list.append(resting_hr[d])

            r_rhr = _pearson(avg_sys_list, rhr_list)
            lines.append("")

            if r_rhr is not None:
                ar = abs(r_rhr)
                strength = (t("stark", "strong") if ar >= 0.5
                            else t("moderat", "moderate") if ar >= 0.3
                            else t("schwach", "weak") if ar >= 0.1
                            else t("kein", "no"))
                sign = t("positiv", "positive") if r_rhr > 0 else t("negativ", "negative")
                lines += [
                    t(f"  r(Ruhepuls × Systolisch)  : {r_rhr:.3f}  → {strength} {sign}",
                      f"  r(RHR × Systolic)          : {r_rhr:.3f}  → {strength} {sign}"),
                    t("  (Erhöhter Ruhepuls = sympathische Aktivierung → höhere Gefäßsteifigkeit)",
                      "  (Elevated RHR = sympathetic activation → higher vascular stiffness)"),
                ]
            else:
                lines.append(t(f"  r(Ruhepuls × Systolisch): n/a (n={len(common)}, Minimum: 3)",
                               f"  r(RHR × Systolic): n/a (n={len(common)}, minimum: 3)"))
        else:
            lines.append(t(f"  Zu wenige gemeinsame Tage (n={len(common)}).",
                           f"  Too few shared days (n={len(common)})."))
    else:
        lines.append(t("  Keine Ruheherzfrequenz-Daten verfügbar.",
                       "  No resting heart rate data available."))

    return lines


# ── Full report ───────────────────────────────────────────────────────────────

def build_report(bp, hrv, afib_dates, pwv, resting_hr, d_from, d_to):
    if not bp:
        return t(
            "Keine Blutdruckdaten für den angegebenen Zeitraum.",
            "No blood pressure data for the specified period.",
        ), {}

    header = [
        t(f"# Blutdruck-Analyse — {d_from} bis {d_to}",
          f"# Blood Pressure Analysis — {d_from} to {d_to}"),
        t(f"Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
          f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
        "",
    ]

    overview_lines, stats = section_overview(bp)
    esc_lines = section_esc_distribution(bp)
    monthly_lines, monthly_data = section_monthly_trend(bp)
    tod_lines, tod_data = section_time_of_day(bp)
    # Read medication start from config if available
    import json as _json
    _med_start = MEDICATION_START
    if _med_start is None:
        _cfg_path = KYORO_CONFIG_DIR / "health_config.json"
        if _cfg_path.exists():
            try:
                _raw = _json.loads(_cfg_path.read_text())
                _med_start = (_raw.get("clinical", {}).get("medication_start")
                              or _raw.get("medication_start"))
            except Exception:
                pass
    pred_lines = section_medication_effect(bp, _med_start)
    hrv_lines = section_hrv_correlation(bp, hrv)
    afib_lines = section_afib_correlation(bp, afib_dates)
    pp_lines = section_pulse_pressure(bp, stats)
    stiffness_lines = section_arterial_stiffness(bp, pwv, resting_hr)

    all_lines = (
        header
        + overview_lines
        + esc_lines
        + monthly_lines
        + tod_lines
        + pred_lines
        + hrv_lines
        + afib_lines
        + pp_lines
        + stiffness_lines
    )

    return "\n".join(all_lines), {
        "stats": stats,
        "monthly_data": monthly_data,
        "tod_data": tod_data,
    }


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(bp, d_from, d_to, tod_data):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    BG = "#1A1A2E"
    PANEL = "#16213E"
    GRID = "#2a2a4e"

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), facecolor=BG)
    fig.suptitle(
        t(f"Blutdruck-Verlauf  {d_from} – {d_to}  (Blutdruckmessgerät)",
          f"Blood Pressure Trend  {d_from} – {d_to}  (BP monitor)"),
        color="#E0E0E0",
        fontsize=13,
        fontweight="bold",
    )

    for ax in (ax1, ax2):
        ax.set_facecolor(PANEL)
        ax.tick_params(colors="#aaaaaa", labelsize=8)
        ax.grid(color=GRID, linewidth=0.5, linestyle="--", alpha=0.6)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444466")

    # ── Panel 1: Time series ──────────────────────────────────────────────────
    # Individual measurements as scatter
    dts_all = []
    sys_all = []
    dia_all = []
    for r in bp:
        try:
            ts_str = r[0] if r[0] and len(r[0]) >= 10 else r[1]
            dt = datetime.fromisoformat(ts_str[:19])
            dts_all.append(dt)
            sys_all.append(r[2])
            dia_all.append(r[3])
        except Exception:
            pass

    ax1.scatter(dts_all, sys_all, color="#ff6b6b", s=12, alpha=0.45, label=t("Systolisch", "Systolic"), zorder=3)
    ax1.scatter(dts_all, dia_all, color="#74b9ff", s=12, alpha=0.45, label=t("Diastolisch", "Diastolic"), zorder=3)

    # 14-day moving average per date
    by_date = defaultdict(lambda: {"sys": [], "dia": []})
    for r in bp:
        by_date[r[1]]["sys"].append(r[2])
        by_date[r[1]]["dia"].append(r[3])

    ma_dates = sorted(by_date)
    ma_dts = [datetime.fromisoformat(d) for d in ma_dates]
    ma_sys = [sum(by_date[d]["sys"]) / len(by_date[d]["sys"]) for d in ma_dates]
    ma_dia = [sum(by_date[d]["dia"]) / len(by_date[d]["dia"]) for d in ma_dates]

    ma_sys_14 = _moving_avg(ma_sys, window=14)
    ma_dia_14 = _moving_avg(ma_dia, window=14)

    valid_idx = [i for i, v in enumerate(ma_sys_14) if v is not None]
    if valid_idx:
        ax1.plot([ma_dts[i] for i in valid_idx], [ma_sys_14[i] for i in valid_idx],
                 color="#ff2244", lw=2.0, label=t("14-Tage-MA Sys", "14-day MA Sys"), zorder=4)
        ax1.plot([ma_dts[i] for i in valid_idx], [ma_dia_14[i] for i in valid_idx],
                 color="#0088ff", lw=2.0, label=t("14-Tage-MA Dia", "14-day MA Dia"), zorder=4)

    # Reference lines
    ax1.axhline(140, color="#ff6b6b", lw=1.2, ls="--", alpha=0.7,
                label=t("140 mmHg (Grad 1)", "140 mmHg (Grade 1)"))
    ax1.axhline(130, color="#fdcb6e", lw=1.0, ls="--", alpha=0.6,
                label=t("130 mmHg (Erhöhter Blutdruck)", "130 mmHg (Elevated BP)"))

    # Optional medication start vertical line (from config)
    import json as _json2
    _cfg_path2 = KYORO_CONFIG_DIR / "health_config.json"
    _med_start2 = None
    if _cfg_path2.exists():
        try:
            _raw2 = _json2.loads(_cfg_path2.read_text())
            _med_start2 = (_raw2.get("clinical", {}).get("medication_start")
                           or _raw2.get("medication_start"))
        except Exception:
            pass
    if _med_start2:
        try:
            med_dt2 = datetime.fromisoformat(_med_start2)
            ax1.axvline(med_dt2, color="#a29bfe", lw=1.5, ls=":", alpha=0.9,
                        label=t(f"Medikation {_med_start2}", f"Medication {_med_start2}"))
            ax1.text(med_dt2, ax1.get_ylim()[1] if ax1.get_ylim()[1] > 0 else 160,
                     t(" Medikation", " Medication"),
                     color="#a29bfe", fontsize=7, va="top", rotation=90)
        except ValueError:
            pass

    ax1.set_ylabel(t("Blutdruck (mmHg)", "Blood pressure (mmHg)"), color="#cccccc", fontsize=9)
    ax1.legend(fontsize=7, facecolor="#0d0d1e", labelcolor="#dddddd",
               framealpha=0.8, loc="upper left", ncol=2)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator())
    fig.autofmt_xdate(rotation=30, ha="right")

    # ── Panel 2: Time-of-day bar chart (mean ± SD) ────────────────────────────
    tod_stats = tod_data.get("tod_stats", {})

    slot_order = [
        t("Morgen (06-10)", "Morning (06-10)"),
        t("Mittag (10-14)", "Noon (10-14)"),
        t("Nachmittag (14-18)", "Afternoon (14-18)"),
        t("Abend (18-22)", "Evening (18-22)"),
        t("Nacht (22-06)", "Night (22-06)"),
    ]

    present_slots = [s for s in slot_order if s in tod_stats]
    if present_slots:
        x = range(len(present_slots))
        avg_s = [tod_stats[s][0] for s in present_slots]
        sd_s = [tod_stats[s][1] for s in present_slots]
        avg_d = [tod_stats[s][2] for s in present_slots]
        sd_d = [tod_stats[s][3] for s in present_slots]
        n_each = [tod_stats[s][4] for s in present_slots]

        width = 0.35
        xs = [i - width / 2 for i in x]
        xd = [i + width / 2 for i in x]

        bars_s = ax2.bar(xs, avg_s, width, color="#ff6b6b", alpha=0.8,
                         label=t("Systolisch", "Systolic"), yerr=sd_s,
                         error_kw={"ecolor": "#ffaaaa", "capsize": 4, "lw": 1.2}, zorder=3)
        bars_d = ax2.bar(xd, avg_d, width, color="#74b9ff", alpha=0.8,
                         label=t("Diastolisch", "Diastolic"), yerr=sd_d,
                         error_kw={"ecolor": "#aaddff", "capsize": 4, "lw": 1.2}, zorder=3)

        ax2.axhline(130, color="#fdcb6e", lw=0.9, ls="--", alpha=0.6,
                    label=t("130 mmHg (Erhöhter Blutdruck)", "130 mmHg (Elevated BP)"))
        ax2.axhline(140, color="#ff6b6b", lw=0.9, ls="--", alpha=0.6,
                    label=t("140 mmHg (Grad 1)", "140 mmHg (Grade 1)"))

        short_labels = [s.split(" (")[0] for s in present_slots]
        ax2.set_xticks(list(x))
        ax2.set_xticklabels(short_labels, color="#cccccc", fontsize=8)
        ax2.set_ylabel(t("Blutdruck (mmHg)", "Blood pressure (mmHg)"), color="#cccccc", fontsize=9)
        ax2.set_xlabel(t("Tageszeit", "Time of Day"), color="#cccccc", fontsize=9)

        for i, (b_s, b_d, n_v) in enumerate(zip(bars_s, bars_d, n_each)):
            ax2.text(b_s.get_x() + b_s.get_width() / 2, 2,
                     f"n={n_v}", ha="center", va="bottom", fontsize=6, color="#aaaaaa")

        ax2.legend(fontsize=7, facecolor="#0d0d1e", labelcolor="#dddddd", framealpha=0.8)
        ax2.set_title(t("Tageszeit-Profil (Mittelwert ± SD)",
                        "Time-of-Day Profile (Mean ± SD)"),
                      color="#cccccc", fontsize=9, pad=6)
    else:
        ax2.text(0.5, 0.5,
                 t("Kein Tageszeit-Profil\n(Zeitstempel ohne Uhrzeitinfo)",
                   "No time-of-day profile\n(timestamps lack time info)"),
                 ha="center", va="center", color="#888888", fontsize=10,
                 transform=ax2.transAxes)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    plot_path = OUT_DIR / f"blood_pressure_{ts}.png"
    plt.savefig(plot_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(t(f"Plot gespeichert: {plot_path}", f"Plot saved: {plot_path}"))
    return plot_path


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
    out = OUT_DIR / f"blood_pressure_{ts}.md"
    content = f"{report_text}\n"
    if llm_text:
        content += t(
            f"\n## Klinische Interpretation\n\n{llm_text}\n",
            f"\n## Clinical Interpretation\n\n{llm_text}\n",
        )
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht gespeichert: {out}", f"Report saved: {out}"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t(
            "Blutdruck-Trendanalyse (Blutdruckmessgerät): Zeitreihe, ESC-Klassifikation, HRV, AFib, Medikamenten-Effekt",
            "Blood pressure trend analysis (BP monitor): time series, ESC classification, HRV, AFib, medication effect",
        )
    )
    parser.add_argument("--from",   dest="date_from", default=cfg.birthdate or "2000-01-01",
                        help=t("Startdatum (YYYY-MM-DD, Standard: Geburtsdatum)",
                               "Start date (YYYY-MM-DD, default: birthdate)"))
    parser.add_argument("--to",     dest="date_to",   default=datetime.now().strftime("%Y-%m-%d"),
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--plot",   action="store_true",
                        help=t("Diagramm erzeugen", "Generate plot"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Analyse überspringen", "Skip LLM analysis"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = _conn()

    # Verify blood_pressure table exists
    if not _table_exists(conn, "blood_pressure"):
        conn.close()
        print(t(
            "Tabelle blood_pressure nicht gefunden. Zuerst: python3 importers/import_omron.py",
            "Table blood_pressure not found. Run first: python3 importers/import_omron.py",
        ))
        sys.exit(1)

    bp = load_bp(conn, args.date_from, args.date_to)
    hrv = load_hrv(conn, args.date_from, args.date_to)
    afib_dates = load_afib_dates(conn, args.date_from, args.date_to)
    pwv = load_pwv(conn, args.date_from, args.date_to)
    resting_hr = load_resting_hr(conn, args.date_from, args.date_to)
    conn.close()

    if not bp:
        print(t(
            f"Keine Blutdruckdaten für {args.date_from} – {args.date_to}. "
            "Zuerst: python3 importers/import_omron.py",
            f"No blood pressure data for {args.date_from} – {args.date_to}. "
            "Run first: python3 importers/import_omron.py",
        ))
        sys.exit(0)

    print(t(
        f"Blutdruckmessungen: {len(bp)} ({bp[0][1]} – {bp[-1][1]})",
        f"Blood pressure measurements: {len(bp)} ({bp[0][1]} – {bp[-1][1]})",
    ))
    print(t(
        f"HRV-Datenpunkte: {len(hrv)}  |  AFib-Tage: {len(afib_dates)}  |  "
        f"PWV-Tage: {len(pwv)}  |  RHR-Tage: {len(resting_hr)}",
        f"HRV data points: {len(hrv)}  |  AFib days: {len(afib_dates)}  |  "
        f"PWV days: {len(pwv)}  |  RHR days: {len(resting_hr)}",
    ))

    report_text, extra_data = build_report(
        bp, hrv, afib_dates, pwv, resting_hr, args.date_from, args.date_to
    )
    print("\n" + report_text)

    if args.plot:
        _plot(bp, args.date_from, args.date_to, extra_data.get("tod_data", {}))

    llm_text = "" if args.no_llm else _run_llm(report_text)
    _save(report_text, llm_text)


if __name__ == "__main__":
    main()
