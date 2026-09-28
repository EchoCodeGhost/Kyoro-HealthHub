#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Körpertemperatur-Analyse — Oura, Apple Watch, Polar

Analysiert Hauttemperatur-Daten auf Krankheitsmuster, Zirkadianrhythmus
und Zusammenhang mit Zyklus und Symptomen.

Datenquellen:
  - oura_temperature_raw: minütige Temperaturabweichung (Oura Ring)
  - measurements: skin_temperature (Polar), wrist_temp_sleep (Apple Watch)
  - symptoms: Krankheitstage
  - reproductive_health: Zyklusdaten

Hinweis zu Skalen:
  Oura Ring     → Abweichung von persönlicher Baseline (typisch -1.0 bis +1.0 °C)
  Apple Watch   → absolute Handgelenktemperatur im Schlaf (°C)
  Polar         → absolute distale Hauttemperatur (°C)

@tier        heuristic
@refs        Grant A, Smarr B (2022). Feasibility of continuous distal body temperature for passive, early pregnancy detection. PLOS Digital Health, 1(5), e0000034. doi:10.1371/journal.pdig.0000034 (Zyklus-/Schwangerschaftsbezug)
             Pho GN, Thigpen N, Patel S, Tily H (2023). Feasibility of measuring physiological responses to breakthrough infections and COVID-19 vaccine using a wearable ring sensor. Digital Biomarkers, 1-6. doi:10.1159/000528874 (Ring-Temperaturabweichung als Infektions-Frühwarnsignal)
             Smarr BL, Aschbacher K, Fisher SM, et al. (2020). Feasibility of continuous fever monitoring using wearable devices. Scientific Reports, 10(1):21640. doi:10.1038/s41598-020-78355-6 (peer-reviewt, n=50, gleiche Autor:innengruppe wie Grant/Smarr 2022 oben; periphere Hauttemperatur korreliert mit selbstberichtetem Fieber, Krankheit vor Symptomerkennung feststellbar)

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@purpose.de  Analysiert Hauttemperatur-Daten aus Oura, Apple Watch und Polar auf Krankheitsmuster, Zirkadianrhythmus, zyklische Schwankungen und Frühwarnsignale.
@purpose.en  Analyses skin temperature data from Oura, Apple Watch and Polar for patterns patterns, circadian rhythm, cycle-related fluctuations and early warning signals.
@method.de   Tagesaggregat je Quelle; Spearman-Korrelation mit Zyklusphase und Symptomen; eigener Fieber-Schwellenwert (--fever-threshold, Default 0.5 °C Oura-Abweichung); Zirkadianer Vergleich über Stundenmittelwerte.
@method.en   Daily aggregate per source; Spearman correlation with cycle phase and symptoms; own fever threshold (--fever-threshold, default 0.5°C Oura deviation); circadian comparison via hourly averages.
@limits.de   Heuristische Methode: Drei Quellen mit unterschiedlichen Skalen (Abweichung vs. Absolutwert) nicht direkt vergleichbar; Fieberschwellenwert (Default 0.5 °C Oura-Abweichung) heuristisch; Oura-Abweichung ist relativ zur persönlichen Baseline, nicht zu einem absoluten Grenzwert; Apple-Watch-Schwelle 37.0 °C (absolute Handgelenktemperatur im Schlaf) ist heuristisch — Hauttemperatur am Handgelenk liegt typischerweise unter 37 °C und ist kein direktes Surrogat für Kerntemperatur.
@limits.en   Heuristic method: Three sources with different scales (deviation vs. absolute) not directly comparable; fever threshold (default 0.5°C Oura deviation) is heuristic; Oura deviation is relative to personal baseline, not an absolute limit; Apple Watch threshold 37.0°C (absolute wrist sleep temperature) is heuristic — skin temperature at the wrist is typically below 37°C and is not a direct surrogate for core body temperature.
@scoring
    Fever threshold: >=0.5°C Oura deviation | >=37.0°C Apple Watch wrist temperature
    Temperature baseline: personal mean (Oura) | absolute (Apple Watch, Polar)
@reads       oura_temperature_raw, measurements, symptoms, reproductive_health
@writes      analyses/cardiovascular/oura_temperature_*.{md,png}

Usage:
  python analyse_oura_temperature.py --plot
  python analyse_oura_temperature.py --from 2026-05-01
  python analyse_oura_temperature.py --fever-threshold 0.7 --plot --no-llm

@usage
    python analyse_oura_temperature.py
    python analyse_oura_temperature.py --help
    python analyse_oura_temperature.py --from 2024-01-01 --to 2024-12-31
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
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_OURA_TEMPERATURE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_OURA_TEMPERATURE_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "cardiovascular"

# Illness-related symptoms — elevated temp before these is an early-warning signal
KRANKHEITSSYMPTOME = [
    "Husten", "Schnupfen", "Halsschmerzen", "Erschöpfung/Fatigue",
    "Chills", "Malaise", "Body aches", "Körperschmerz", "Muskelschmerzen",
    "Fieber", "Gelenkschmerzen",
]

# Cycle phases (from period_start day 1)
PHASEN = [
    (1,  5,  "Menstruation"),
    (6,  12, "Follikulär"),
    (13, 15, "Ovulation"),
    (16, 99, "Luteal"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _avg(lst):
    clean = [v for v in lst if v is not None]
    return round(sum(clean) / len(clean), 3) if clean else None


def _spearman_r(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    n = len(pairs)

    def ranks(vals):
        sv = sorted(range(n), key=lambda i: vals[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n - 1 and vals[sv[j + 1]] == vals[sv[i]]:
                j += 1
            avg_r = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[sv[k]] = avg_r
            i = j + 1
        return r

    xv, yv = zip(*pairs)
    rx, ry = ranks(list(xv)), ranks(list(yv))
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return round(1 - 6 * d2 / (n * (n ** 2 - 1)), 3)


def _zyklusphase(tag):
    for start, ende, name in PHASEN:
        if start <= tag <= ende:
            return name
    return "Luteal"


def _datum_zu_phase(period_starts, datum_str):
    """Return (cycle_day, phase_name) for a given date, or (None, None)."""
    try:
        ziel = datetime.fromisoformat(datum_str).date()
    except ValueError:
        return None, None
    best_start = None
    for ps in reversed(period_starts):
        try:
            start = datetime.fromisoformat(ps).date()
        except ValueError:
            continue
        if start <= ziel:
            best_start = start
            break
    if best_start is None:
        return None, None
    tag = (ziel - best_start).days + 1
    if tag > 40:
        return None, None
    return tag, _zyklusphase(tag)


# ── Data loading ──────────────────────────────────────────────────────────────

def _detect_oura_scale(conn):
    """
    Auto-detect whether oura_temperature_raw stores deviations or absolute values.

    Oura deviation: typically in range -2.0 to +2.0 °C (mean near 0).
    Absolute skin temp: typically 25–40 °C (mean ~33 °C).

    Returns: 'deviation' or 'absolute'
    """
    row = conn.execute(
        "SELECT AVG(skin_temp), MIN(skin_temp), MAX(skin_temp) FROM oura_temperature_raw"
    ).fetchone()
    if row is None or row[0] is None:
        return "deviation"
    avg_val = row[0]
    # If mean is above 10 °C it is clearly an absolute temperature
    return "absolute" if avg_val > 10.0 else "deviation"


def load_data(conn, d_from, d_to):
    """Load all temperature-related data from DB."""

    # Auto-detect Oura scale once
    oura_scale = _detect_oura_scale(conn)

    # Oura: daily averages (deviation or absolute depending on stored data)
    oura_daily = conn.execute("""
        SELECT DATE(timestamp) AS date, AVG(skin_temp) AS avg_dev
        FROM oura_temperature_raw
        WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?
          AND skin_temp IS NOT NULL
        GROUP BY DATE(timestamp)
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    # Oura: hourly averages for circadian pattern
    oura_hourly = conn.execute("""
        SELECT CAST(SUBSTR(timestamp, 12, 2) AS INTEGER) AS stunde,
               AVG(skin_temp) AS avg_dev
        FROM oura_temperature_raw
        WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?
          AND skin_temp IS NOT NULL
          AND LENGTH(timestamp) >= 13
        GROUP BY stunde
        ORDER BY stunde
    """, (d_from, d_to)).fetchall()

    # Apple Watch: wrist temp during sleep (absolute °C)
    apple_temp = conn.execute("""
        SELECT date, AVG(value) AS avg_temp
        FROM measurements
        WHERE metric = 'wrist_temp_sleep'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    # Polar: skin temperature (absolute °C, distal)
    polar_temp = conn.execute("""
        SELECT date, AVG(value) AS avg_temp
        FROM measurements
        WHERE metric = 'skin_temperature'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    # Symptoms (illness-related, value_num > 0)
    symptome = defaultdict(list)
    krankheitstage = set()
    for date, symptom, value_num in conn.execute("""
        SELECT date, symptom, value_num
        FROM symptoms
        WHERE date >= ? AND date <= ?
          AND symptom IS NOT NULL
    """, (d_from, d_to)):
        if value_num is not None:
            symptome[date].append((symptom, value_num))
        if symptom in KRANKHEITSSYMPTOME and value_num and value_num > 0:
            krankheitstage.add(date)

    # All illness-day symptom burden (sum of active illness symptoms per day)
    krankheit_burden = {}
    for date, sym_list in symptome.items():
        burden = sum(v for s, v in sym_list if s in KRANKHEITSSYMPTOME and v is not None and v > 0)
        if burden > 0:
            krankheit_burden[date] = burden

    # Reproductive health: period starts
    period_starts = []
    for (date,) in conn.execute("""
        SELECT DISTINCT date FROM reproductive_health
        WHERE event_type = 'period_start'
          AND date <= ?
        ORDER BY date
    """, (d_to,)):
        period_starts.append(date)

    # Ovulation dates
    ovulation_dates = []
    for (date,) in conn.execute("""
        SELECT DISTINCT date FROM reproductive_health
        WHERE event_type IN ('ovulation', 'predicted_ovulation')
          AND date >= ? AND date <= ?
        ORDER BY date
    """, (d_from, d_to)):
        ovulation_dates.append(date)

    return (oura_daily, oura_hourly, oura_scale, apple_temp, polar_temp,
            symptome, krankheit_burden, krankheitstage,
            period_starts, ovulation_dates)


# ── Report generation ─────────────────────────────────────────────────────────

def build_report(oura_daily, oura_hourly, oura_scale, apple_temp, polar_temp,
                     symptome, krankheit_burden, krankheitstage,
                     period_starts, ovulation_dates,
                     d_from, d_to, fever_threshold):
    if not oura_daily and not apple_temp and not polar_temp:
        return t(
            "Keine Temperaturdaten im angefragten Zeitraum.",
            "No temperature data in the requested period.",
        )

    # Adjust fever threshold for absolute-scale data
    # For absolute values (~33°C baseline), a +0.5°C exceedance means >33.5°C
    # We detect the effective baseline for absolute mode
    if oura_scale == "absolute" and oura_daily:
        oura_baseline = _avg([r[1] for r in oura_daily])
        effective_threshold = (oura_baseline or 33.5) + fever_threshold
        oura_scale_note = (
            f"Oura-Daten in dieser DB als **absolute Hauttemperatur** gespeichert "
            f"(Ø Baseline: {oura_baseline:.2f} °C). "
            f"Fieber-Schwelle: >{effective_threshold:.2f} °C (Baseline + {fever_threshold:.1f} °C)."
        )
    else:
        effective_threshold = fever_threshold
        oura_scale_note = (
            f"Oura-Daten als **Abweichung von persönlicher Baseline** gespeichert. "
            f"Fieber-Schwelle: >{fever_threshold:+.1f} °C."
        )

    lines = [
        f"## Temperatur-Analyse (Oura / Apple Watch / Polar) — {d_from} bis {d_to}\n",
        f"_{oura_scale_note}_\n",
        "**Skalen-Hinweis:** Apple Watch & Polar = absolute Temperatur (°C), "
        "nicht direkt mit Oura vergleichbar.\n",
    ]

    # ── 1. Oura daily temperature (deviation or absolute) ────────────────────
    if oura_daily:
        oura_devs  = [r[1] for r in oura_daily]
        oura_dates = [r[0] for r in oura_daily]
        n = len(oura_daily)
        avg_dev = _avg(oura_devs)
        min_dev = round(min(oura_devs), 3)
        max_dev = round(max(oura_devs), 3)

        # For absolute-scale: flag relative to personal baseline in window
        n_fever = sum(1 for v in oura_devs if v > effective_threshold)
        low_threshold = ((avg_dev or 33.5) - fever_threshold
                         if oura_scale == "absolute" else -fever_threshold)
        n_low = sum(1 for v in oura_devs if v < low_threshold)

        unit_label = "°C (absolut)" if oura_scale == "absolute" else "°C (Δ Baseline)"
        lines += [
            f"### Oura Hauttemperatur (n={n} Tage, {unit_label})\n",
            f"  Ø: **{avg_dev:.3f} °C**  |  Min: {min_dev:.3f}  |  Max: {max_dev:.3f}",
            f"  Tage über Schwelle (Fieber-Verdacht): **{n_fever}** ({round(n_fever/n*100,1)}%)",
            f"  Tage unter unterer Schwelle: {n_low} ({round(n_low/n*100,1)}%)",
        ]

        # Trend (first vs last quarter)
        if n >= 8:
            q = max(2, n // 4)
            early = _avg(oura_devs[:q])
            late  = _avg(oura_devs[-q:])
            if early is not None and late is not None:
                delta = round(late - early, 3)
                lines.append(
                    f"  Trend: {delta:+.3f} °C "
                    f"(früh Ø {early:.3f} → spät Ø {late:.3f})"
                )

        # Fever days with their symptoms
        fieber_tage = [(oura_dates[i], oura_devs[i])
                       for i in range(n) if oura_devs[i] > effective_threshold]
        if fieber_tage:
            lines.append(f"\n#### Tage mit Temperaturerhöhung (>{effective_threshold:.2f} °C)\n")
            for date, dev in sorted(fieber_tage, key=lambda x: -x[1])[:15]:
                sym_txt = ""
                if date in symptome:
                    aktiv = [s for s, v in symptome[date]
                             if s in KRANKHEITSSYMPTOME and v is not None and v > 0]
                    if aktiv:
                        sym_txt = f"  → Symptome: {', '.join(aktiv[:4])}"
                lines.append(f"  {date}  {dev:.3f} °C{sym_txt}")

    # ── 2. Circadian pattern ─────────────────────────────────────────────────
    if oura_hourly:
        circ_label = ("Stundenø Hauttemperatur (absolut)"
                      if oura_scale == "absolute"
                      else "Stundenø Abweichung von Baseline")
        lines.append(f"\n### Zirkadianrhythmus — Oura {circ_label}\n")
        peak_h = max(oura_hourly, key=lambda x: x[1])
        tief_h = min(oura_hourly, key=lambda x: x[1])
        for stunde, avg_h in oura_hourly:
            marker = ""
            if stunde == peak_h[0]:
                marker = "  ← Maximum"
            elif stunde == tief_h[0]:
                marker = "  ← Minimum"
            lines.append(f"  {stunde:02d}:00  {avg_h:.3f} °C{marker}")
        delta_circ = round(peak_h[1] - tief_h[1], 3)
        lines.append(
            f"\n  Zirkadianer Hub: {delta_circ:.3f} °C  "
            f"(Peak {peak_h[0]:02d}:00 → Trough {tief_h[0]:02d}:00)"
        )

    # ── 3. Apple Watch wrist temp ────────────────────────────────────────────
    if apple_temp:
        aw_vals  = [r[1] for r in apple_temp]
        aw_dates = [r[0] for r in apple_temp]
        n_aw = len(apple_temp)
        aw_avg = _avg(aw_vals)
        aw_min = round(min(aw_vals), 3)
        aw_max = round(max(aw_vals), 3)
        n_hoch = sum(1 for v in aw_vals if v > 37.0)

        lines += [
            f"\n### Apple Watch Handgelenk-Schlaftemperatur (n={n_aw} Nächte)\n",
            f"  Ø: **{aw_avg:.2f} °C**  |  Min: {aw_min:.2f}  |  Max: {aw_max:.2f}",
            f"  Nächte > 37.0 °C: {n_hoch} ({round(n_hoch/n_aw*100,1)}%)",
        ]
        if n_aw >= 8:
            q = max(2, n_aw // 4)
            early = _avg(aw_vals[:q])
            late  = _avg(aw_vals[-q:])
            if early is not None and late is not None:
                delta = round(late - early, 3)
                lines.append(
                    f"  Trend: {delta:+.3f} °C (früh Ø {early:.2f} → spät Ø {late:.2f})"
                )

        # Nights flagged high — cross-ref symptoms
        aw_hoch = [(aw_dates[i], aw_vals[i])
                   for i in range(n_aw) if aw_vals[i] > 37.0]
        if aw_hoch:
            lines.append("\n#### Apple Watch: erhöhte Nächte (>37.0 °C)\n")
            for date, temp in sorted(aw_hoch, key=lambda x: -x[1])[:10]:
                sym_txt = ""
                if date in symptome:
                    aktiv = [s for s, v in symptome[date]
                             if s in KRANKHEITSSYMPTOME and v is not None and v > 0]
                    if aktiv:
                        sym_txt = f"  → {', '.join(aktiv[:4])}"
                lines.append(f"  {date}  {temp:.2f} °C{sym_txt}")

    # ── 4. Polar skin temperature ────────────────────────────────────────────
    if polar_temp:
        po_vals = [r[1] for r in polar_temp]
        n_po = len(polar_temp)
        po_avg = _avg(po_vals)
        po_min = round(min(po_vals), 2)
        po_max = round(max(po_vals), 2)
        lines += [
            f"\n### Polar Hauttemperatur (distales Handgelenk, n={n_po} Tage)\n",
            f"  Ø: **{po_avg:.2f} °C**  |  Min: {po_min:.2f}  |  Max: {po_max:.2f}",
            "  (Distal-Hauttemperatur typisch 18–36 °C je nach Umgebung & Durchblutung)",
        ]
        if n_po >= 10:
            q = max(2, n_po // 4)
            early = _avg(po_vals[:q])
            late  = _avg(po_vals[-q:])
            if early is not None and late is not None:
                delta = round(late - early, 2)
                lines.append(
                    f"  Trend: {delta:+.2f} °C (früh Ø {early:.2f} → spät Ø {late:.2f})"
                )

    # ── 5. Illness fingerprint: temp 1–3 days BEFORE symptom onset ───────────
    if krankheit_burden and oura_daily:
        oura_dict = {r[0]: r[1] for r in oura_daily}
        aw_dict   = {r[0]: r[1] for r in apple_temp} if apple_temp else {}

        # Find illness onset days (burden > 0 but day-1 burden was 0 or absent)
        alle_krankheitstage = sorted(krankheit_burden.keys())
        onset_tage = []
        for date in alle_krankheitstage:
            tag = datetime.fromisoformat(date).date()
            vortag = str(tag - timedelta(days=1))
            if krankheit_burden.get(vortag, 0) == 0:
                onset_tage.append(date)

        if onset_tage:
            lines.append("\n### Krankheits-Frühwarnung: Temperatur vor Symptombeginn\n")
            lines.append(
                "  Analysiert Oura-Abweichung 1–3 Tage VOR erstem Symptomtag\n"
            )
            lines.append(
                f"  {'Symptombeginn':<14} "
                f"{'T-3':>7} {'T-2':>7} {'T-1':>7} {'T+0':>7}  Symptome"
            )
            lines.append("  " + "-" * 70)

            n_vorher_erhoht = 0
            for onset in onset_tage[:20]:
                tag = datetime.fromisoformat(onset).date()
                row_parts = [f"  {onset:<14}"]
                erhoht_vorher = False
                for delta in [-3, -2, -1, 0]:
                    d = str(tag + timedelta(days=delta))
                    dev = oura_dict.get(d)
                    if dev is not None:
                        marker = "*" if dev > fever_threshold else " "
                        row_parts.append(f"{dev:+.2f}{marker}".rjust(8))
                        if delta < 0 and dev > effective_threshold:
                            erhoht_vorher = True
                    else:
                        row_parts.append("   n.a.".rjust(8))
                # Symptoms on onset day
                sym_txt = ""
                if onset in symptome:
                    aktiv = [s for s, v in symptome[onset]
                             if s in KRANKHEITSSYMPTOME and v is not None and v > 0]
                    sym_txt = f"  {', '.join(aktiv[:3])}"
                row_parts.append(sym_txt)
                lines.append("".join(row_parts))
                if erhoht_vorher:
                    n_vorher_erhoht += 1

            if onset_tage:
                pct = round(n_vorher_erhoht / min(len(onset_tage), 20) * 100, 1)
                lines.append(
                    f"\n  Frühwarn-Rate: {n_vorher_erhoht}/{min(len(onset_tage), 20)} "
                    f"Infekte zeigten T-1 bis T-3 Temperaturerhöhung ({pct}%)"
                )

    # ── 6. Menstrual cycle correlation ───────────────────────────────────────
    if period_starts and oura_daily:
        oura_dict = {r[0]: r[1] for r in oura_daily}

        phase_devs = defaultdict(list)
        for date, dev in oura_daily:
            _, phase = _datum_zu_phase(period_starts, date)
            if phase is not None:
                phase_devs[phase].append(dev)

        lines.append("\n### Zykluskorrelation — Oura Abweichung nach Phase\n")
        lines.append(
            f"  {'Phase':<16} {'Ø Abweichung':>14} {'n':>5}  "
            f"{'Erwartung':>10}"
        )
        lines.append("  " + "-" * 55)
        erwartung = {
            "Menstruation": "niedrig",
            "Follikulär":   "niedrig",
            "Ovulation":    "Anstieg",
            "Luteal":       "+0.3 °C",
        }
        for phase in ["Menstruation", "Follikulär", "Ovulation", "Luteal"]:
            vals = phase_devs[phase]
            avg_v = _avg(vals)
            avg_str = f"{avg_v:+.3f} °C" if avg_v is not None else "n.a."
            lines.append(
                f"  {phase:<16} {avg_str:>14} {len(vals):>5}  "
                f"{erwartung.get(phase, ''):>10}"
            )

        # Luteal vs follicular delta
        lut_avg = _avg(phase_devs["Luteal"])
        fol_avg = _avg(phase_devs["Follikulär"])
        if lut_avg is not None and fol_avg is not None:
            delta_lf = round(lut_avg - fol_avg, 3)
            lines.append(
                f"\n  Luteal–Follikulär-Delta: {delta_lf:+.3f} °C  "
                f"(erwartet: ~+0.3 °C bei normaler Lutealphase)"
            )

        # Ovulation dates with temp
        if ovulation_dates:
            lines.append("\n#### Ovulationstage mit Oura-Temperaturabweichung\n")
            for ov_date in ovulation_dates:
                dev = oura_dict.get(ov_date)
                dev_str = f"{dev:+.3f} °C" if dev is not None else "n.a."
                lines.append(f"  {ov_date}  {dev_str}")

    # ── 7. Multi-source summary ──────────────────────────────────────────────
    if oura_daily and apple_temp:
        oura_dict = {r[0]: r[1] for r in oura_daily}
        aw_dict   = {r[0]: r[1] for r in apple_temp}

        common_dates = sorted(set(oura_dict) & set(aw_dict))
        if len(common_dates) >= 5:
            oura_common = [oura_dict[d] for d in common_dates]
            aw_common   = [aw_dict[d]   for d in common_dates]
            r_val = _spearman_r(oura_common, aw_common)
            lines += [
                "\n### Geräte-Vergleich: Oura vs. Apple Watch\n",
                f"  Gemeinsame Tage: {len(common_dates)}",
                f"  Spearman r (Oura-Abweichung × Apple Watch absolut): "
                f"{r_val if r_val is not None else 'n.a.'}",
                "  (Niedrige Korrelation erwartet, da unterschiedliche Skalen)",
            ]

    return "\n".join(lines)


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(oura_daily, oura_hourly, oura_scale, apple_temp, krankheit_burden,
          period_starts, d_from, d_to, fever_threshold, effective_threshold):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), facecolor="#1e1e2e")
    fig.suptitle(
        f"Körpertemperatur — Oura / Apple Watch  |  {d_from}–{d_to}",
        color="#E0E0E0", fontsize=13,
    )
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # ── Subplot 1: Oura daily temp deviation ────────────────────────────────
    ax0 = axes[0]
    if oura_daily:
        dts  = [datetime.fromisoformat(r[0]) for r in oura_daily]
        devs = [r[1] for r in oura_daily]
        ax0.plot(dts, devs, color="#a29bfe", lw=1.0, alpha=0.85, label="Oura Abweichung")
        ax0.axhline(effective_threshold, color="#e17055", lw=1.0, ls="--", alpha=0.8,
                    label=f"Schwelle {effective_threshold:.2f} °C")
        if oura_scale == "absolute":
            # Draw baseline reference and lower bound for absolute mode
            baseline_val = sum(devs) / len(devs) if devs else 33.5
            ax0.axhline(baseline_val, color="#555", lw=0.8, ls="-", alpha=0.5,
                        label=f"Baseline Ø {baseline_val:.2f} °C")
            ax0.axhline(baseline_val - fever_threshold, color="#74b9ff", lw=0.7,
                        ls=":", alpha=0.6, label="Untere Schwelle")
        else:
            ax0.axhline(-fever_threshold, color="#74b9ff", lw=0.7, ls=":", alpha=0.6,
                        label=f"Schwelle -{fever_threshold:.1f} °C")
            ax0.axhline(0, color="#555", lw=0.6, ls="-", alpha=0.5)

        # Highlight fever days
        fever_dts  = [dts[i] for i in range(len(devs)) if devs[i] > effective_threshold]
        fever_devs = [devs[i] for i in range(len(devs)) if devs[i] > effective_threshold]
        if fever_dts:
            ax0.scatter(fever_dts, fever_devs, color="#e17055", s=20, zorder=4,
                        alpha=0.9, label=f"Fieber-Verdacht (>{effective_threshold:.2f}°C)")

        # Mark illness days as vertical lines
        for date_str, burden in krankheit_burden.items():
            try:
                ax0.axvline(datetime.fromisoformat(date_str), color="#fdcb6e",
                            lw=0.5, alpha=min(0.6, burden / 15))
            except ValueError:
                pass

        # Mark period starts
        for ps in period_starts:
            try:
                ps_dt = datetime.fromisoformat(ps)
                if datetime.fromisoformat(d_from) <= ps_dt <= datetime.fromisoformat(d_to):
                    ax0.axvline(ps_dt, color="#fd79a8", lw=0.6, alpha=0.5)
            except ValueError:
                pass

        ax0.set_ylabel("Abweichung von Baseline (°C)", color="#ccc", fontsize=9)
        ax0.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white", loc="upper left")
        ax0.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
        ax0.set_title("Oura Temperatur-Abweichung (täglich)  |  gelb=Symptomtag  |  pink=Zyklusstart",
                      color="#aaa", fontsize=8, pad=4)
    else:
        ax0.text(0.5, 0.5, "Keine Oura-Daten", ha="center", va="center",
                 color="#aaa", transform=ax0.transAxes)

    # ── Subplot 2: Apple Watch wrist temp (sleep) ────────────────────────────
    ax1 = axes[1]
    if apple_temp:
        aw_dts  = [datetime.fromisoformat(r[0]) for r in apple_temp]
        aw_vals = [r[1] for r in apple_temp]
        ax1.plot(aw_dts, aw_vals, color="#2ecc71", lw=1.2, alpha=0.9,
                 label="Apple Watch (Schlaf)")
        ax1.axhline(37.0, color="#e17055", lw=0.8, ls="--", alpha=0.7,
                    label="37.0 °C")

        # Highlight nights above 37°C
        high_dts  = [aw_dts[i] for i in range(len(aw_vals)) if aw_vals[i] > 37.0]
        high_vals = [aw_vals[i] for i in range(len(aw_vals)) if aw_vals[i] > 37.0]
        if high_dts:
            ax1.scatter(high_dts, high_vals, color="#e17055", s=22, zorder=4,
                        alpha=0.85, label=">37.0 °C")

        ax1.set_ylabel("Handgelenk-Temp. absolut (°C)", color="#ccc", fontsize=9)
        ax1.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
        ax1.set_title("Apple Watch — Handgelenktemperatur im Schlaf",
                      color="#aaa", fontsize=8, pad=4)
    else:
        ax1.text(0.5, 0.5, "Keine Apple Watch Schlafdaten", ha="center", va="center",
                 color="#aaa", transform=ax1.transAxes)

    # ── Subplot 3: Circadian pattern (hourly Oura deviation) ─────────────────
    ax2 = axes[2]
    if oura_hourly:
        hours = [r[0] for r in oura_hourly]
        devs_h = [r[1] for r in oura_hourly]

        # Bar chart for circadian pattern
        colors_h = ["#e17055" if v > 0 else "#74b9ff" for v in devs_h]
        ax2.bar(hours, devs_h, color=colors_h, alpha=0.75, width=0.8)
        ax2.plot(hours, devs_h, color="#fdcb6e", lw=1.5, marker="o", ms=4, alpha=0.9,
                 label="Stundenø Abweichung")
        ax2.axhline(0, color="#555", lw=0.8, ls="-")
        ax2.axhline(effective_threshold, color="#e17055", lw=0.7, ls="--", alpha=0.6)

        # Mark peak and trough
        peak_h = max(oura_hourly, key=lambda x: x[1])
        tief_h = min(oura_hourly, key=lambda x: x[1])
        ax2.annotate(f"Max\n{peak_h[1]:+.2f}°C",
                     xy=(peak_h[0], peak_h[1]),
                     xytext=(peak_h[0] + 0.5, peak_h[1] + 0.02),
                     color="#fdcb6e", fontsize=7)
        ax2.annotate(f"Min\n{tief_h[1]:+.2f}°C",
                     xy=(tief_h[0], tief_h[1]),
                     xytext=(tief_h[0] + 0.5, tief_h[1] - 0.04),
                     color="#74b9ff", fontsize=7)

        ax2.set_xticks(range(0, 24))
        ax2.set_xticklabels([f"{h}" for h in range(0, 24)], fontsize=7, color="#aaa")
        ax2.set_xlabel("Uhrzeit (Stunde)", color="#ccc", fontsize=9)
        ax2.set_ylabel("Ø Abweichung (°C)", color="#ccc", fontsize=9)
        ax2.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        circ_title = ("Zirkadianrhythmus — Oura Stundenø Hauttemperatur (absolut)"
                      if oura_scale == "absolute"
                      else "Zirkadianrhythmus — Oura Stundenø (Abweichung von Baseline)")
        ax2.set_title(circ_title, color="#aaa", fontsize=8, pad=4)
    else:
        ax2.text(0.5, 0.5, "Keine Oura Stundendaten", ha="center", va="center",
                 color="#aaa", transform=ax2.transAxes)

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"oura_temperature_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(f"Plot: {p}")
    plt.close()


# ── LLM analysis ──────────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=1000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


# ── Save report ───────────────────────────────────────────────────────────────

def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"oura_temperature_{ts}.md"
    content = "# Körpertemperatur-Analyse — Oura / Apple Watch / Polar\n\n"
    content += report + "\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t(
            "Körpertemperatur-Analyse (Oura / Apple Watch / Polar)",
            "Body temperature analysis (Oura / Apple Watch / Polar)",
        )
    )
    parser.add_argument("--from", dest="date_from", default=(datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d"),
                        help=t("Startdatum (YYYY-MM-DD)", "Start date (YYYY-MM-DD)"))
    parser.add_argument("--to",   dest="date_to",
                        default=datetime.now().strftime("%Y-%m-%d"),
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--all",  dest="all_data",  action="store_true",
                        help=t("Alle verfügbaren Daten (überschreibt --from/--to)",
                               "All available data (overrides --from/--to)"))
    parser.add_argument("--fever-threshold", type=float, default=0.5,
                        help="Oura-Abweichung ab der Fieber vermutet wird (default: 0.5)")
    parser.add_argument("--plot",   action="store_true",
                        help=t("Diagramme erstellen", "Generate plots"))
    parser.add_argument("--no-llm", action="store_true",
                        help=t("LLM-Analyse überspringen", "Skip LLM analysis"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    if args.all_data:
        args.date_from = _cfg.birthdate or "1900-01-01"
        args.date_to   = datetime.today().strftime("%Y-%m-%d")

    conn = open_db()
    (oura_daily, oura_hourly, oura_scale, apple_temp, polar_temp,
     symptome, krankheit_burden, krankheitstage,
     period_starts, ovulation_dates) = load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not oura_daily and not apple_temp and not polar_temp:
        print(t(
            "Keine Temperaturdaten. Zuerst Daten importieren:\n"
            "  python3 importers/import_oura_csv.py\n"
            "  python3 importers/import_apple_health.py",
            "No temperature data found. Import data first:\n"
            "  python3 importers/import_oura_csv.py\n"
            "  python3 importers/import_apple_health.py",
        ))
        return

    # Compute effective fever threshold (accounts for absolute vs. deviation scale)
    if oura_scale == "absolute" and oura_daily:
        oura_baseline = _avg([r[1] for r in oura_daily])
        effective_threshold = (oura_baseline or 33.5) + args.fever_threshold
    else:
        effective_threshold = args.fever_threshold

    print(
        f"Oura-Tage: {len(oura_daily)}  |  "
        f"Oura-Skala: {oura_scale}  |  "
        f"Apple Watch-Nächte: {len(apple_temp)}  |  "
        f"Polar-Tage: {len(polar_temp)}  |  "
        f"Krankheitstage: {len(krankheit_burden)}  |  "
        f"Zyklusstarts: {len(period_starts)}"
    )

    report = build_report(
        oura_daily, oura_hourly, oura_scale, apple_temp, polar_temp,
        symptome, krankheit_burden, krankheitstage,
        period_starts, ovulation_dates,
        args.date_from, args.date_to, args.fever_threshold,
    )
    print("\n" + report)

    if args.plot:
        _plot(
            oura_daily, oura_hourly, oura_scale, apple_temp,
            krankheit_burden, period_starts,
            args.date_from, args.date_to, args.fever_threshold, effective_threshold,
        )

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
