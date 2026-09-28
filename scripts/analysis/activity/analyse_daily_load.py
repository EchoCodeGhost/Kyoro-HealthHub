#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
analyse_daily_load.py — HR-Zonenverteilung und Tagespensum-Analyse.

@tier        heuristic
@refs        ACSM 2022, Guidelines for Exercise Testing and Prescription, 11th ed.
             Borg G 1998, Borg's Perceived Exertion and Pain Scales; ISBN:0-88011-623-4
             Chen MJ, Fan X, Moe ST (2002). Criterion-related validity of the Borg ratings of perceived exertion scale in healthy individuals: a meta-analysis. Journal of Sports Sciences, 20(11), 873-899. doi:10.1080/026404102320761787

@relevance.de  Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse
@relevance.en  Enables activity data analysis, essential for movement and fitness analysis
@purpose.de  Analysiert HR-Zonenverteilung und Tagespensum-Score: Überblick, Belastungsstufen,
             Korrelation Pensum × Folgetag-HRV/PEM und Rote-Zone-Häufigkeit.
@purpose.en  Analyses HR zone distribution and daily load score: overview, load levels,
             correlation load × next-day HRV/PEM, and red-zone frequency.
@method.de   Liest aus compute_hr_zones-generierten daily_hr_zones; empirisch kalibrierte
             Herzfrequenzzonen (Zone 0-4) und gewichteter Tagespensum-Score aus compute-Outputs.
             Datenquellen: daily_hr_zones, measurements (hrv_rmssd), pem_evidence_scores, symptoms.
             Keine publizierten Referenzwerte für Zonengrenzen.
@method.en   Reads from compute_hr_zones-generated daily_hr_zones; empirically calibrated
             HR zones (Zone 0-4) and weighted daily load score from compute outputs.
             Data sources: daily_hr_zones, measurements (hrv_rmssd), pem_evidence_scores, symptoms.
             No published reference values for zone boundaries.
@reads       daily_hr_zones, measurements (hrv_rmssd), pem_evidence_scores, symptoms
@writes      analyses/activity/*.{md,png} (kein DB-Write)
@limits.de   Heuristische Methode: Zonengrenzen sind empirisch kalibriert, nicht formal validiert.
             Kein Vergleich mit Laktat-Tests oder spiroergometrischen Daten. n=1, Consumer-Sensorik.
@limits.en   Heuristic method: Zone boundaries are empirically calibrated, not formally validated.
             No comparison with lactate tests or spiroergometric data. n=1, consumer sensors.
@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (bilingual)
@prompt.en             SYSTEM_PROMPT (bilingual)

@usage
    python3 scripts/analysis/analyse_daily_load.py [--from YYYY-MM-DD] [--to YYYY-MM-DD]
    python3 scripts/analysis/analyse_daily_load.py --plot
    python3 scripts/analysis/analyse_daily_load.py --no-llm
@scoring direct = Zone_4_Anteil * 50 + Rote-Zone-Tage * 30 + PEM_Korrelation * 20
"""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_activity import (
    SYSTEM_PROMPT_ANALYSE_DAILY_LOAD_DE_STR as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_DAILY_LOAD_EN_STR as SYSTEM_PROMPT_EN
)

_cfg = _Cfg()
DB_PATH   = _cfg.db_path
OUT_DIR   = _cfg.analyses_dir / "activity"



# ── Daten laden ───────────────────────────────────────────────────────────────

def load_data(conn, d_from: str, d_to: str, person: str) -> dict:
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
    )}

    zones: dict[str, dict] = {}
    if "daily_hr_zones" in tables:
        for row in conn.execute("""
            SELECT date, zone0_min, zone1_min, zone2_min, zone3_min, zone4_min,
                   total_min, tagespensum, z1_bpm, z2_bpm, z3_bpm, z4_bpm
            FROM daily_hr_zones
            WHERE person = ? AND date BETWEEN ? AND ?
            ORDER BY date
        """, (person, d_from, d_to)):
            d = row[0]
            zones[d] = {
                "z0": row[1], "z1": row[2], "z2": row[3],
                "z3": row[4], "z4": row[5], "total": row[6],
                "tagespensum": row[7],
                "thresholds": (row[8], row[9], row[10], row[11]),
            }

    # daily_stress.rmssd_ms hat DB-weit nur eine Handvoll Zeilen (nie flaechendeckend
    # befuellt) und ist als Korrelations-Datenquelle statistisch wertlos — die
    # Korrelationen und Quartalswerte kamen dadurch praktisch immer als "n.a." bzw.
    # aus einer Mini-Stichprobe heraus, wurden aber als Ergebnis dargestellt.
    # measurements.hrv_rmssd ist geraeteagnostisch und deutlich dichter befuellt;
    # seit 03/2026 liegen zusaetzlich 5-Min-Einzelwerte vor, daher je Datum
    # aggregiert (AVG) statt Einzelzeilen zu uebernehmen.
    hrv: dict[str, float] = {}
    for d, rmssd in conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE metric = 'hrv_rmssd' AND value > 0 AND person = ?
          AND date BETWEEN ? AND ?
        GROUP BY date
    """, (person, d_from, d_to)):
        if rmssd is not None:
            hrv[d] = rmssd

    pem: dict[str, float] = {}          # alle PEM-Scores
    pem_confirmed: dict[str, float] = {}  # nur confidence='confirmed'
    if "pem_evidence_scores" in tables:
        for d, v, conf in conn.execute("""
            SELECT date, score, confidence FROM pem_evidence_scores
            WHERE date BETWEEN ? AND ? AND score IS NOT NULL
        """, (d_from, d_to)):
            pem[d] = v
            if conf == "confirmed":
                pem_confirmed[d] = v
    elif "pem_correlation" in tables:
        for d, v in conn.execute("""
            SELECT date, pem_staerke FROM pem_correlation
            WHERE date BETWEEN ? AND ? AND pem_staerke IS NOT NULL
        """, (d_from, d_to)):
            pem[d] = v

    energie: dict[str, float] = {}
    if "symptoms" in tables:
        for d, v in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE category = 'Ressourcen' AND value_num IS NOT NULL
              AND date BETWEEN ? AND ?
            GROUP BY date
        """, (d_from, d_to)):
            energie[d] = v

    return {"zones": zones, "hrv": hrv, "pem": pem,
            "pem_confirmed": pem_confirmed, "energie": energie}


# ── Statistik-Helfer ──────────────────────────────────────────────────────────

def _avg(lst):
    lst = [x for x in lst if x is not None]
    return round(sum(lst) / len(lst), 1) if lst else None


def _pct(lst, p):
    lst = sorted(x for x in lst if x is not None)
    if not lst:
        return None
    i = (len(lst) - 1) * p / 100
    lo, hi = int(i), min(int(i) + 1, len(lst) - 1)
    return round(lst[lo] + (lst[hi] - lst[lo]) * (i - lo), 1)


# Mindest-n, ab dem eine Kennzahl als statistisch auswertbar gilt. Vorher gab es
# keine solche Schwelle: spearman_r() rechnete ab n=5 und eine daily_stress-Stichprobe
# von 5 Zeilen DB-weit floss unkommentiert als Zahl in den Bericht ein (n wurde nicht
# einmal ausgewiesen). Unterhalb dieser Schwelle wird die Kennzahl jetzt explizit als
# "nicht auswertbar (n=…)" ausgewiesen statt einer Zahl, die Praezision vortaeuscht.
MIN_N_AUSWERTBAR = 30


def spearman_r(xs, ys, min_n: int = MIN_N_AUSWERTBAR):
    """Gibt (r, n) zurueck. r ist None, wenn n < min_n (Kennzahl nicht auswertbar)."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < min_n:
        return None, n
    def ranks(vals):
        sv = sorted(range(n), key=lambda i: vals[i])
        r = [0] * n
        for rank, idx in enumerate(sv, 1):
            r[idx] = rank
        return r
    xv, yv = zip(*pairs)
    rx, ry = ranks(list(xv)), ranks(list(yv))
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return round(1 - 6 * d2 / (n * (n ** 2 - 1)), 3), n


# ── Bericht ───────────────────────────────────────────────────────────────────

def build_report(data: dict, d_from: str, d_to: str) -> str:
    zones         = data["zones"]
    hrv           = data["hrv"]
    pem           = data["pem"]
    pem_confirmed = data["pem_confirmed"]
    energie       = data["energie"]

    if not zones:
        return t(
            "Keine daily_hr_zones-Daten. Zuerst: python3 scripts/compute/compute_hr_zones.py",
            "No daily_hr_zones data. Run: python3 scripts/compute/compute_hr_zones.py",
        )

    dates      = sorted(zones)
    n          = len(dates)
    last_row   = zones[dates[-1]]
    z1, z2, z3, z4 = last_row["thresholds"]

    tl_vals = [zones[d]["tagespensum"] for d in dates if zones[d]["tagespensum"] is not None]

    lines = [
        t(f"## Daily Load — {d_from} bis {d_to}\n",
          f"## Daily Load — {d_from} to {d_to}\n"),
        t(f"Analysetage: **{n}**  |  HR-Zonen: <{z1} / {z1}–{z2} / {z2}–{z3} / {z3}–{z4} / ≥{z4} bpm\n",
          f"Analysis days: **{n}**  |  HR zones: <{z1} / {z1}–{z2} / {z2}–{z3} / {z3}–{z4} / ≥{z4} bpm\n"),
    ]

    # ── 1. Übersicht ──
    lines.append(t("### 1. Tagespensum — Übersicht\n", "### 1. Daily Load — Overview\n"))
    if tl_vals:
        lines += [
            t(f"  Ø Tagespensum:   {_avg(tl_vals)}",   f"  Avg Daily Load: {_avg(tl_vals)}"),
            t(f"  P25:           {_pct(tl_vals, 25)}", f"  P25:            {_pct(tl_vals, 25)}"),
            t(f"  Median:        {_pct(tl_vals, 50)}", f"  Median:         {_pct(tl_vals, 50)}"),
            t(f"  P75:           {_pct(tl_vals, 75)}", f"  P75:            {_pct(tl_vals, 75)}"),
            t(f"  Maximum:       {max(tl_vals):.0f}",   f"  Maximum:        {max(tl_vals):.0f}"),
        ]

    # Zonenverteilung
    z0_avg = _avg([zones[d]["z0"] for d in dates])
    z1_avg = _avg([zones[d]["z1"] for d in dates])
    z2_avg = _avg([zones[d]["z2"] for d in dates])
    z3_avg = _avg([zones[d]["z3"] for d in dates])
    z4_avg = _avg([zones[d]["z4"] for d in dates])
    tot_avg = _avg([zones[d]["total"] for d in dates])

    def fmt_pct(n_avg, tot):
        if n_avg is None or not tot:
            return "n/a"
        return f"{n_avg:.0f} ({100*n_avg/tot:.0f} %)"

    lines += [
        t("\n### 2. Zonenverteilung (Ø Samples/Tag)\n",
          "\n### 2. Zone Distribution (avg samples/day)\n"),
        t(f"  Zone 0 (<{z1} bpm)    Erholung:   {fmt_pct(z0_avg, tot_avg)}",
          f"  Zone 0 (<{z1} bpm)    Recovery:   {fmt_pct(z0_avg, tot_avg)}"),
        t(f"  Zone 1 ({z1}–{z2} bpm)  Grün/sicher: {fmt_pct(z1_avg, tot_avg)}",
          f"  Zone 1 ({z1}–{z2} bpm)  Green/safe:  {fmt_pct(z1_avg, tot_avg)}"),
        t(f"  Zone 2 ({z2}–{z3} bpm)  Gelb/Grenze: {fmt_pct(z2_avg, tot_avg)}",
          f"  Zone 2 ({z2}–{z3} bpm)  Yellow/limit:{fmt_pct(z2_avg, tot_avg)}"),
        t(f"  Zone 3 ({z3}–{z4} bpm)  Orange/Acht: {fmt_pct(z3_avg, tot_avg)}",
          f"  Zone 3 ({z3}–{z4} bpm)  Orange/warn: {fmt_pct(z3_avg, tot_avg)}"),
        t(f"  Zone 4 (≥{z4} bpm)    Rot/Crash:  {fmt_pct(z4_avg, tot_avg)}",
          f"  Zone 4 (≥{z4} bpm)    Red/crash:  {fmt_pct(z4_avg, tot_avg)}"),
        t(f"  Gesamt Samples/Tag:  {tot_avg:.0f}" if tot_avg else "",
          f"  Total samples/day:   {tot_avg:.0f}" if tot_avg else ""),
    ]

    n_z4_days = sum(1 for d in dates if (zones[d]["z4"] or 0) > 0)
    lines.append(t(f"\n  Tage mit Zone 4 (Crash-Bereich): **{n_z4_days}** von {n}",
                   f"\n  Days with Zone 4 (crash zone): **{n_z4_days}** of {n}"))

    # PEM-Datenverfügbarkeit
    n_pem_all       = sum(1 for d in dates if d in pem)
    n_pem_confirmed = sum(1 for d in dates if d in pem_confirmed)
    n_pem_trigger   = n_pem_all - n_pem_confirmed
    if n_pem_all:
        lines += [
            t("\n### PEM-Datenqualität\n", "\n### PEM Data Quality\n"),
            t(f"  Bestätigt (Trigger + Reaktion):  **{n_pem_confirmed}** Tage",
              f"  Confirmed (trigger + reaction):  **{n_pem_confirmed}** days"),
            t(f"  Nur Trigger (keine HRV-Reaktion): {n_pem_trigger} Tage — Grundrauschen, ausgeblendet",
              f"  Trigger only (no HRV reaction):  {n_pem_trigger} days — noise, excluded"),
        ]

    # ── 3. Belastungsstufen (Quartil-Analyse) ──
    if len(tl_vals) >= 12:
        lines.append(t("\n### 3. Belastungsstufen × Folge-Reaktion\n",
                       "\n### 3. Load Levels × Next-Day Response\n"))
        tl_sorted = sorted(tl_vals)
        q = len(tl_sorted) // 4
        q1 = tl_sorted[q - 1]
        q3 = tl_sorted[3 * q - 1]

        def _next_day_vals(threshold_lo, threshold_hi, target: dict):
            out = []
            for d in dates:
                tl = zones[d]["tagespensum"]
                if tl is None:
                    continue
                if not (threshold_lo <= tl <= threshold_hi):
                    continue
                nd = (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                if nd in target:
                    out.append(target[nd])
            return out

        for label_de, label_en, lo, hi in [
            ("Niedrig (Q1)",  "Low (Q1)",  0,    q1),
            ("Mittel (Q2–3)", "Mid (Q2–3)", q1+1, q3),
            ("Hoch (Q4)",     "High (Q4)", q3+1, 999999),
        ]:
            hrv_next = _next_day_vals(lo, hi, hrv)
            pem_next = _next_day_vals(lo, hi, pem_confirmed)  # nur bestätigte
            n_days_q = sum(1 for d in dates
                           if zones[d]["tagespensum"] is not None
                           and lo <= zones[d]["tagespensum"] <= hi)
            label = t(label_de, label_en)
            parts = [f"  {label:<16}  n={n_days_q}"]
            if hrv_next:
                parts.append(t(f"  Folge-HRV Ø {_avg(hrv_next)} ms",
                               f"  next-HRV Ø {_avg(hrv_next)} ms"))
            if pem_next:
                parts.append(t(f"  PEM bestät. Ø {_avg(pem_next):.1f}",
                               f"  PEM confirmed Ø {_avg(pem_next):.1f}"))
            lines.append("  |  ".join(parts))

    # ── 4. Korrelationen ──
    tl_x      = [zones[d]["tagespensum"] for d in dates]
    hrv_same  = [hrv.get(d) for d in dates]
    pem_same  = [pem_confirmed.get(d) for d in dates]   # nur bestätigt
    energie_x = [energie.get(d) for d in dates]

    def next_vals(target):
        out = []
        for d in dates:
            nd = (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            out.append(target.get(nd))
        return out

    hrv_next_x = next_vals(hrv)
    pem_next_x = next_vals(pem_confirmed)   # nur bestätigt

    r_tl_hrv      = spearman_r(tl_x, hrv_same)
    r_tl_hrv_next = spearman_r(tl_x, hrv_next_x)
    r_tl_pem      = spearman_r(tl_x, pem_same)
    r_tl_pem_next = spearman_r(tl_x, pem_next_x)
    r_tl_energie  = spearman_r(tl_x, energie_x)

    def _fmt_r(r_n):
        r, n = r_n
        if r is None:
            return t(f"nicht auswertbar (n={n})", f"not evaluable (n={n})")
        return f"{r:+.3f} (n={n})"

    n_conf = sum(1 for v in pem_same if v is not None)
    lines += [
        t(f"\n### 4. Korrelationen — Tagespensum × … (Spearman r, PEM nur bestätigt n={n_conf})\n",
          f"\n### 4. Correlations — Daily Load × … (Spearman r, PEM confirmed only n={n_conf})\n"),
        t(f"  × HRV RMSSD (gleicher Tag):          {_fmt_r(r_tl_hrv)}",
          f"  × HRV RMSSD (same day):               {_fmt_r(r_tl_hrv)}"),
        t(f"  × HRV RMSSD (Folgetag):               {_fmt_r(r_tl_hrv_next)}",
          f"  × HRV RMSSD (next day):               {_fmt_r(r_tl_hrv_next)}"),
        t(f"  × PEM-Score bestät. (gleicher Tag):   {_fmt_r(r_tl_pem)}",
          f"  × PEM score confirmed (same day):     {_fmt_r(r_tl_pem)}"),
        t(f"  × PEM-Score bestät. (Folgetag):       {_fmt_r(r_tl_pem_next)}",
          f"  × PEM score confirmed (next day):     {_fmt_r(r_tl_pem_next)}"),
        t(f"  × Energie/Ressourcen:                 {_fmt_r(r_tl_energie)}",
          f"  × Energy/resources:                   {_fmt_r(r_tl_energie)}"),
    ]

    # ── 5. Rote Zone – Ereignisliste ──
    red_days = [(d, zones[d]["z4"], zones[d]["tagespensum"])
                for d in dates if (zones[d]["z4"] or 0) > 0]
    red_days.sort(key=lambda x: -(x[1] or 0))

    if red_days:
        lines += [
            t(f"\n### 5. Rote Zone (≥{z4} bpm) — Einzelereignisse\n",
              f"\n### 5. Red Zone (≥{z4} bpm) — Individual events\n"),
            t(f"  {'Datum':<12}  {'Z4-Samples':>11}  {'Tagespensum':>10}",
              f"  {'Date':<12}  {'Z4-samples':>11}  {'Daily Load':>10}"),
        ]
        for d, z4n, tl in red_days[:20]:
            lines.append(f"  {d:<12}  {z4n:>11}  {tl:>10.0f}")
        if len(red_days) > 20:
            lines.append(t(f"  … {len(red_days)-20} weitere Tage",
                           f"  … {len(red_days)-20} more days"))

    # ── 6. Quartalstrend ──
    if n >= 60:
        lines.append(t("\n### 6. Quartalstrend\n", "\n### 6. Quarterly Trend\n"))
        by_quarter: dict[str, list] = defaultdict(list)
        for d in dates:
            tl = zones[d]["tagespensum"]
            if tl is None:
                continue
            q_label = f"{d[:4]}-Q{(int(d[5:7])-1)//3 + 1}"
            by_quarter[q_label].append(tl)
        for ql in sorted(by_quarter):
            vals = by_quarter[ql]
            if len(vals) < MIN_N_AUSWERTBAR:
                lines.append(t(
                    f"  {ql}  n={len(vals):>3}  nicht auswertbar (n<{MIN_N_AUSWERTBAR})",
                    f"  {ql}  n={len(vals):>3}  not evaluable (n<{MIN_N_AUSWERTBAR})"))
                continue
            lines.append(
                t(f"  {ql}  n={len(vals):>3}  Ø {_avg(vals):>7}  Median {_pct(vals,50):>7}",
                  f"  {ql}  n={len(vals):>3}  avg {_avg(vals):>7}  median {_pct(vals,50):>7}")
            )

    return "\n".join(line for line in lines if line is not None)


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(data: dict, d_from: str, d_to: str) -> Path | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print(t("matplotlib nicht verfügbar — kein Plot.", "matplotlib not available — no plot."))
        return None

    zones = data["zones"]
    hrv   = data["hrv"]
    if not zones:
        return None

    dates_all = sorted(zones)
    dt_all    = [datetime.strptime(d, "%Y-%m-%d") for d in dates_all]

    tl_vals  = [zones[d]["tagespensum"] or 0 for d in dates_all]
    z0_vals  = [zones[d]["z0"] or 0 for d in dates_all]
    z1_vals  = [zones[d]["z1"] or 0 for d in dates_all]
    z2_vals  = [zones[d]["z2"] or 0 for d in dates_all]
    z3_vals  = [zones[d]["z3"] or 0 for d in dates_all]
    z4_vals  = [zones[d]["z4"] or 0 for d in dates_all]

    hrv_dates = [datetime.strptime(d, "%Y-%m-%d") for d in dates_all if d in hrv]
    hrv_vals  = [hrv[d] for d in dates_all if d in hrv]

    # 7-Tage gleitend
    def smooth7(vals):
        out = []
        for i in range(len(vals)):
            w = vals[max(0, i-3):i+4]
            out.append(sum(w) / len(w))
        return out

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), facecolor="#1e1e2e")
    fig.suptitle(t(f"Daily Load — {d_from} bis {d_to}",
                   f"Daily Load — {d_from} to {d_to}"),
                 color="#E0E0E0", fontsize=13)

    BG = "#2a2a3e"
    for ax in axes:
        ax.set_facecolor(BG)
        ax.tick_params(colors="#aaa", labelsize=8)
        for sp in ax.spines.values():
            sp.set_color("#555")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

    # Panel 1 — Tagespensum Balken + 7-Tage-Linie
    ax = axes[0]
    q75 = sorted(tl_vals)[int(len(tl_vals) * 0.75)] if tl_vals else 1
    colors = ["#e74c3c" if v >= q75 * 1.5 else
              "#e67e22" if v >= q75 else
              "#f1c40f" if v >= q75 * 0.5 else
              "#2ecc71" for v in tl_vals]
    ax.bar(dt_all, tl_vals, color=colors, alpha=0.7, width=0.8, label=t("Tagespensum", "Daily Load"))
    ax.plot(dt_all, smooth7(tl_vals), color="#00bfff", lw=1.5,
            label=t("7-Tage-Mittel", "7-day mean"))
    ax.set_ylabel(t("Tagespensum", "Daily Load"), color="#aaa", fontsize=9)
    ax.legend(fontsize=7, facecolor=BG, labelcolor="#ccc")

    # Panel 2 — Zonenverteilung gestapelt
    ax = axes[1]
    ax.stackplot(dt_all,
                 z0_vals, z1_vals, z2_vals, z3_vals, z4_vals,
                 colors=["#3498db", "#2ecc71", "#f1c40f", "#e67e22", "#e74c3c"],
                 labels=[t("Z0 Erholung","Z0 Recovery"),
                         t("Z1 Grün","Z1 Green"),
                         t("Z2 Gelb","Z2 Yellow"),
                         t("Z3 Orange","Z3 Orange"),
                         t("Z4 Rot","Z4 Red")],
                 alpha=0.85)
    ax.set_ylabel(t("Samples/Tag", "Samples/day"), color="#aaa", fontsize=9)
    ax.legend(fontsize=7, facecolor=BG, labelcolor="#ccc", loc="upper left")

    # Panel 3 — HRV RMSSD
    ax = axes[2]
    if hrv_dates:
        ax.plot(hrv_dates, hrv_vals, color="#9b59b6", lw=1.2,
                label=t("HRV RMSSD (ms)", "HRV RMSSD (ms)"))
        ax.set_ylabel("RMSSD (ms)", color="#aaa", fontsize=9)
        ax.legend(fontsize=7, facecolor=BG, labelcolor="#ccc")
    else:
        ax.text(0.5, 0.5, t("Keine HRV-Daten", "No HRV data"),
                transform=ax.transAxes, ha="center", color="#888")

    fig.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M")
    path = OUT_DIR / f"daily_load_{ts}.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(t(f"Plot: {path}", f"Plot: {path}"))
    return path


# ── LLM & Speichern ───────────────────────────────────────────────────────────

def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=900)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report: str, llm_text: str, plot_path=None):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"daily_load_{ts}.md"
    content = t("# Daily Load — HR-Zonenanalyse\n\n",
                "# Daily Load — HR Zone Analysis\n\n") + report + "\n"
    if plot_path:
        content += f"\n![]({plot_path.name})\n"
    if llm_text:
        content += t("\n## Klinische Einordnung\n\n",
                     "\n## Clinical Interpretation\n\n") + llm_text + "\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t("HR-Zonenverteilung und Tagespensum analysieren",
                      "Analyse HR zone distribution and daily load"))
    parser.add_argument("--from",   dest="date_from",
                        default=_cfg.birthdate or "2017-01-01")
    parser.add_argument("--to",     dest="date_to",
                        default=str(datetime.today().date()))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=None)
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    person = args.person or OWN_PERSON_ID

    with open_db(DB_PATH) as conn:
        data = load_data(conn, args.date_from, args.date_to, person)

    n = len(data["zones"])
    if not n:
        print(t("Keine daily_hr_zones-Daten — zuerst compute_hr_zones.py ausführen.",
                "No daily_hr_zones data — run compute_hr_zones.py first."))
        return

    print(t(f"Analysetage mit HR-Zonen: {n}", f"Days with HR zones: {n}"))
    report = build_report(data, args.date_from, args.date_to)
    print("\n" + report)

    plot_path = _plot(data, args.date_from, args.date_to) if args.plot else None
    llm_text  = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text, plot_path)


if __name__ == "__main__":
    main()
