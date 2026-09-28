#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Oura-Stress & Erholung — Tagesbelastung und Erholungskapazität

Analysiert minütige Stress/Erholungs-Daten von Oura Ring und deren
Zusammenhang mit der folgenden Schlaf-HRV.

Datenquellen:
  - oura_daytime_stress: minütige Stress/Recovery (0–100)
  - oura_sleep_model: Schlaf-HRV und Schlafeffizienz
  - measurements (hrv_rmssd/rmssd_ms), geräteunabhängig über modules/metric_loader:
    Langzeit-HRV-Referenz

@tier        heuristic
@refs        [UNVERIFIZIERT] "Hautala et al. 2010, Int J Sports Physiol Perform, doi:10.1123/ijspp.5.4.486" — DOI löst nicht auf, kein passendes Paper in diesem Journal/Jahr auffindbar (Crossref-Journal-Direktsuche negativ). Vor Verwendung/Vertrauen manuell prüfen.
             Goldstone A, Baker FC, de Zambotti M (2018). Actigraphy in the digital health revolution: still asleep? Sleep, 41(9). doi:10.1093/sleep/zsy120

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@purpose.de  Analysiert minütige Oura-Stress/Erholungs-Daten auf Tagesbelastungsmuster, Stressintoleranz und deren Zusammenhang mit der folgenden nächtlichen HRV.
@purpose.en  Analyses minute-level Oura stress/recovery data for daily load patterns, stress intolerance and their relationship with subsequent nocturnal HRV.
@method.de   Tages- und Stunden-Aggregation von oura_daytime_stress; Pearson-Korrelation Tagesbelastung × nächste Nacht-HRV; Schwellenwerte (stress >60, recovery >60) nach Oura-Dokumentation.
@method.en   Daily and hourly aggregation of oura_daytime_stress; Pearson correlation of daily load × next night HRV; thresholds (stress >60, recovery >60) per Oura documentation.
@scoring     Recovery-Quality-Score (projektintern, Beispielformel):
               Score = 100 − (Ø Tagesstress × 0.5) + (Ø Tageserholung × 0.3) + (HRV-Nacht / 2)
               Stress-Level-Klassifikation (Tagesaggregat, heuristisch):
                 <30 = Niedrig, 30–49 = Mittel, 50–69 = Hoch, ≥70 = Sehr hoch
               Basis: projektinterne Formel ohne externe Validierung; Oura-Scores proprietär.
@limits.de   Heuristische Methode: Oura-Stress und -Recovery sind proprietäre Scores ohne veröffentlichte Validierungsstudie; Recovery-Quality-Score ist eine projektinterne Beispielformel ohne klinische Validierung; minütige Auflösung ergibt nur grobe Stressarchitektur; Datenbasis aktuell begrenzt.
@limits.en   Heuristic method: Oura stress and recovery are proprietary scores without published validation study; Recovery-Quality-Score is a project-internal example formula without clinical validation; minute-level resolution provides only coarse stress architecture; data basis currently limited.
@reads       oura_daytime_stress, oura_sleep_model, measurements
@writes      analyses/cardiovascular/recovery_*.{md,png}

Usage:
  python analyse_recovery.py --plot
  python analyse_recovery.py --from 2026-05-01 --plot
  python analyse_recovery.py --plot --no-llm

@usage
    python analyse_recovery.py
    python analyse_recovery.py --help
    python analyse_recovery.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.metric_loader import load_metric_daily, source_summary, weakest_confidence
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_RECOVERY_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_RECOVERY_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "cardiovascular"

# ── Data loading ──────────────────────────────────────────────────────────────

def load_daily_stress(conn, d_from, d_to):
    """Aggregate minute-level oura_daytime_stress to daily values."""
    rows = conn.execute("""
        SELECT
            DATE(timestamp)             AS day,
            AVG(stress_value)           AS avg_stress,
            AVG(recovery_value)         AS avg_recovery,
            SUM(CASE WHEN stress_value > 60 THEN 1 ELSE 0 END) AS min_high_stress,
            SUM(CASE WHEN recovery_value > 60 THEN 1 ELSE 0 END) AS min_recovery
        FROM oura_daytime_stress
        WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?
        GROUP BY DATE(timestamp)
        ORDER BY DATE(timestamp)
    """, (d_from, d_to)).fetchall()
    # columns: day, avg_stress, avg_recovery, min_high_stress, min_recovery
    return rows


def load_hourly_pattern(conn, d_from, d_to):
    """Average stress and recovery by hour-of-day across all available days."""
    rows = conn.execute("""
        SELECT
            CAST(SUBSTR(timestamp, 12, 2) AS INTEGER) AS hour,
            AVG(stress_value)           AS avg_stress,
            AVG(recovery_value)         AS avg_recovery,
            COUNT(*)                    AS n_minutes
        FROM oura_daytime_stress
        WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?
          AND (stress_value IS NOT NULL OR recovery_value IS NOT NULL)
        GROUP BY hour
        ORDER BY hour
    """, (d_from, d_to)).fetchall()
    return rows


def load_oura_sleep(conn, d_from, d_to):
    """Per-day averaged Oura sleep HRV (RMSSD) and efficiency."""
    rows = conn.execute("""
        SELECT
            day,
            AVG(average_hrv)            AS avg_hrv,
            AVG(efficiency)             AS avg_efficiency,
            AVG(total_sleep_duration)   AS avg_sleep_s,
            AVG(lowest_heart_rate)      AS avg_lhr,
            AVG(restless_periods)       AS avg_restless
        FROM oura_sleep_model
        WHERE day >= ? AND day <= ?
          AND average_hrv IS NOT NULL
        GROUP BY day
        ORDER BY day
    """, (d_from, d_to)).fetchall()
    return {r[0]: {"hrv": r[1], "efficiency": r[2], "sleep_s": r[3],
                   "lhr": r[4], "restless": r[5]}
            for r in rows}


def load_hrv_reference(conn, d_from, d_to, person=OWN_PERSON_ID):
    """Nightly HRV (RMSSD) as long-term reference, device-agnostic.

    Was polar_nightly_hrv-only ('recovery_indicator'/'ans_status' are Polar-
    proprietary scores with no cross-device equivalent, so they are dropped
    rather than silently left blank). polar_nightly_hrv is empty on any
    installation without a Polar device — load_metric_daily() instead picks
    one source per night from measurements (registry-configured device >
    source_priority > most readings that day).
    """
    days = load_metric_daily(conn, ("hrv_rmssd", "rmssd_ms"), d_from, d_to,
                              person=person, agg="avg")
    return {d: {"rmssd": day.value, "source": day.source_app,
                "confidence": day.confidence, "label": day.label}
            for d, day in days.items()}, source_summary(days), weakest_confidence(days)


# ── Analysis helpers ──────────────────────────────────────────────────────────

def spearman_r(xs, ys):
    """Spearman rank correlation; returns None if < 4 paired points."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 4:
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
    rho = 1 - 6 * d2 / (n * (n ** 2 - 1))
    return round(rho, 3), n


def _next_day(date_str):
    """Return YYYY-MM-DD string for the following day."""
    return (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def _avg(vals):
    v = [x for x in vals if x is not None]
    return round(sum(v) / len(v), 1) if v else None


# ── Report builder ────────────────────────────────────────────────────────────

def build_report(daily_stress, hourly_pattern, oura_sleep, polar_hrv,
                     d_from, d_to, hrv_sources=None, hrv_confidence=None):
    lines = [f"## Oura-Stress & Erholung — {d_from} bis {d_to}\n"]

    n_days = len(daily_stress)
    if n_days == 0:
        lines.append("Keine oura_daytime_stress-Daten im angegebenen Zeitraum.")
        return "\n".join(lines)

    # ── DATA WARNING ──────────────────────────────────────────────────────────
    lines.append("### Hinweis zur Datenlage\n")
    if n_days < 7:
        lines.append(
            f"  !! Nur {n_days} Tage mit Oura-Stressdaten verfuegbar.")
        lines.append(
            "     Alle Aussagen sind vorlaeufig. Min. 30 Tage fuer valide Trends.")
    else:
        lines.append(
            f"  {n_days} Tage verfuegbar — Trends erkennbar, aber noch begrenzt valide.")
        lines.append(
            "     Empfehlung: Analyse nach 30+ Tagen wiederholen.\n")

    # ── DAILY AGGREGATES ──────────────────────────────────────────────────────
    lines.append("\n### Taegliche Stress/Erholungs-Bilanz\n")
    header = f"  {'Datum':<12}  {'Ø Stress':>9}  {'Ø Erholung':>11}  " \
             f"{'S/E-Ratio':>9}  {'Min Hoch-Stress':>16}  {'Min Erholung':>12}"
    lines.append(header)
    lines.append("  " + "-" * 76)

    stress_series = []
    recovery_series = []
    ratio_series = []
    high_stress_series = []

    for row in daily_stress:
        day, avg_s, avg_r, min_hs, min_rec = row
        avg_s   = avg_s   if avg_s   is not None else float("nan")
        avg_r   = avg_r   if avg_r   is not None else float("nan")
        min_hs  = min_hs  if min_hs  is not None else 0
        min_rec = min_rec if min_rec is not None else 0
        ratio   = round(avg_s / avg_r, 2) if avg_r and avg_r > 0 else None

        stress_series.append(avg_s)
        recovery_series.append(avg_r)
        ratio_series.append(ratio)
        high_stress_series.append(min_hs)

        niveau = ("Niedrig" if avg_s < 30 else
                  "Mittel"  if avg_s < 50 else
                  "Hoch"    if avg_s < 70 else "Sehr hoch !")
        ratio_str = f"{ratio:.2f}" if ratio is not None else "n/a"
        lines.append(
            f"  {day:<12}  {avg_s:>8.1f}  {avg_r:>10.1f}  "
            f"{ratio_str:>9}  {min_hs:>15}  {min_rec:>12}  ({niveau})"
        )

    # Summary stats
    valid_s = [x for x in stress_series   if not (x != x)]  # filter NaN
    valid_r = [x for x in recovery_series if not (x != x)]
    if valid_s:
        lines.append(f"\n  Gesamtdurchschnitt Stress:    {_avg(valid_s)}")
        lines.append(f"  Gesamtdurchschnitt Erholung:  {_avg(valid_r)}")
        lines.append(f"  Hoechste Stressbelastung:     {max(valid_s):.1f}"
                     f"  ({daily_stress[valid_s.index(max(valid_s))][0]})")
        lines.append(f"  Niedrigste Stressbelastung:   {min(valid_s):.1f}"
                     f"  ({daily_stress[valid_s.index(min(valid_s))][0]})")
        total_high_min = sum(x for x in high_stress_series if x)
        lines.append(f"  Gesamtminuten mit Stress>60:  {total_high_min} min"
                     f"  (ca. {total_high_min // 60} Std {total_high_min % 60} Min)")

    # ── HOURLY PATTERN ────────────────────────────────────────────────────────
    if hourly_pattern:
        lines.append("\n\n### Intraday-Muster (Stundenmittel ueber alle Tage)\n")
        lines.append(f"  {'Stunde':<8}  {'Ø Stress':>9}  {'Ø Erholung':>11}  {'Niveau':<20}  {'n Minuten':>10}")
        lines.append("  " + "-" * 66)

        peak_stress   = max(hourly_pattern, key=lambda r: r[1] if r[1] else -1)
        low_stress    = min(hourly_pattern, key=lambda r: r[1] if r[1] else 999)
        peak_recovery = max(hourly_pattern, key=lambda r: r[2] if r[2] else -1)

        for hour, avg_s, avg_r, n_min in hourly_pattern:
            avg_s = avg_s if avg_s is not None else float("nan")
            avg_r = avg_r if avg_r is not None else float("nan")
            niveau = ("Erholung" if avg_s < 25 else
                      "Niedrig"  if avg_s < 40 else
                      "Mittel"   if avg_s < 60 else
                      "Hoch"     if avg_s < 75 else "Sehr hoch!")
            marker = ""
            if hour == peak_stress[0]:
                marker = " <- Stress-Peak"
            elif hour == peak_recovery[0]:
                marker = " <- Erholungs-Peak"
            elif hour == low_stress[0]:
                marker = " <- Tiefster Stress"
            s_str = f"{avg_s:.1f}" if avg_s == avg_s else "n/a"
            r_str = f"{avg_r:.1f}" if avg_r == avg_r else "n/a"
            lines.append(
                f"  {hour:02d}:00     {s_str:>9}  {r_str:>11}  {niveau:<20}  {n_min:>10}{marker}"
            )

        lines.append(f"\n  Stress-Peak:    {peak_stress[0]:02d}:00 Uhr "
                     f"(Ø {peak_stress[1]:.1f})" if peak_stress[1] else "")
        lines.append(f"  Ruhigste Zeit:  {low_stress[0]:02d}:00 Uhr "
                     f"(Ø {low_stress[1]:.1f})" if low_stress[1] else "")
        lines.append(f"  Beste Erholung: {peak_recovery[0]:02d}:00 Uhr "
                     f"(Ø {peak_recovery[2]:.1f})" if peak_recovery[2] else "")

    # ── STRESS → NEXT-NIGHT HRV ───────────────────────────────────────────────
    lines.append("\n\n### Stress → Folgenacht-HRV (Oura)\n")
    if not oura_sleep:
        lines.append("  Keine Oura-Schlaf-HRV-Daten verfuegbar.")
    else:
        lines.append(f"  {'Datum':<12}  {'Ø Stress':>9}  {'HRV same night':>15}  "
                     f"{'HRV next night':>15}  {'Effizienz':>10}")
        lines.append("  " + "-" * 68)

        same_night_pairs  = []
        next_night_pairs  = []

        for row in daily_stress:
            day = row[0]
            s   = row[1]
            if s is None:
                continue
            same = oura_sleep.get(day)
            nxt  = oura_sleep.get(_next_day(day))
            same_hrv = same["hrv"] if same else None
            next_hrv = nxt["hrv"]  if nxt  else None
            eff      = same["efficiency"] if same else None

            same_str = f"{same_hrv:.1f}" if same_hrv is not None else "  n/a  "
            next_str = f"{next_hrv:.1f}" if next_hrv is not None else "  n/a  "
            eff_str  = f"{eff:.0f}%"     if eff      is not None else "  n/a  "
            lines.append(
                f"  {day:<12}  {s:>8.1f}  {same_str:>15}  {next_str:>15}  {eff_str:>10}"
            )

            if same_hrv is not None:
                same_night_pairs.append((s, same_hrv))
            if next_hrv is not None:
                next_night_pairs.append((s, next_hrv))

        # Spearman correlations
        if same_night_pairs:
            r_same, n_same = spearman_r(
                [p[0] for p in same_night_pairs],
                [p[1] for p in same_night_pairs]
            )
            lines.append(
                f"\n  Korrelation Stress × gleiche Nacht HRV: "
                f"r={r_same if r_same is not None else 'n/a'} (n={n_same})"
            )
        if next_night_pairs:
            r_next, n_next = spearman_r(
                [p[0] for p in next_night_pairs],
                [p[1] for p in next_night_pairs]
            )
            lines.append(
                f"  Korrelation Stress × Folgenacht HRV:    "
                f"r={r_next if r_next is not None else 'n/a'} (n={n_next})"
            )
        if len(same_night_pairs) < 4:
            lines.append(
                "\n  Noch zu wenige ueberlappende Tage fuer Korrelationsaussagen."
            )

    # ── HRV REFERENCE (device-agnostic, see load_hrv_reference) ───────────────
    # A full per-day table made sense when this was Polar-only and sparse
    # (a handful of nights); with a device-agnostic source it can be
    # thousands of rows, so this reports a summary instead of dumping every
    # day. Source/confidence come from the caller (already computed once by
    # load_hrv_reference via metric_loader) rather than being re-derived here.
    if polar_hrv:
        lines.append("\n\n### HRV-Referenz (verfuegbar im Zeitraum)\n")
        rmssd_vals = [v["rmssd"] for v in polar_hrv.values() if v["rmssd"] is not None]
        _src_str = ", ".join(f"{src}: {n}" for src, n in (hrv_sources or {}).items()) or "–"
        lines.append(f"  Naechte insgesamt:  {len(polar_hrv)}")
        lines.append(f"  RMSSD Mittel:       {_avg(rmssd_vals)} ms  (n={len(rmssd_vals)})")
        lines.append(f"  Quelle:             {_src_str}")
        lines.append(f"  Konfidenz:          {hrv_confidence or '–'}")

    # ── RECOVERY QUALITY SCORE ────────────────────────────────────────────────
    lines.append("\n\n### Recovery-Quality-Score (kombiniert)\n")
    lines.append("  Score = 100 - (Ø Stress × 0.5) + (Ø Erholung × 0.3) + "
                 "(Oura-HRV / 2)  [Beispielformel, normiert]\n")

    rq_rows = []
    for row in daily_stress:
        day, avg_s, avg_r, _, _ = row
        sleep = oura_sleep.get(day, {})
        hrv   = sleep.get("hrv")
        if avg_s is None:
            continue
        avg_r = avg_r if avg_r is not None else 0.0
        hrv_c = hrv   if hrv   is not None else 0.0
        score = round(100 - (avg_s * 0.5) + (avg_r * 0.3) + (hrv_c / 2), 1)
        rq_rows.append((day, score, avg_s, avg_r, hrv_c))

    if rq_rows:
        lines.append(f"  {'Datum':<12}  {'Score':>7}  {'Stress':>8}  {'Erholung':>10}  {'HRV':>6}")
        lines.append("  " + "-" * 50)
        for day, score, avg_s, avg_r, hrv_c in rq_rows:
            hrv_str = f"{hrv_c:.1f}" if hrv_c else "n/a "
            lines.append(
                f"  {day:<12}  {score:>7.1f}  {avg_s:>8.1f}  {avg_r:>10.1f}  {hrv_str:>6}"
            )
        best  = max(rq_rows, key=lambda r: r[1])
        worst = min(rq_rows, key=lambda r: r[1])
        lines.append(f"\n  Bester Tag:     {best[0]}  (Score {best[1]})")
        lines.append(f"  Schlechtester:  {worst[0]}  (Score {worst[1]})")

    return "\n".join(lines)


# ── Plot ──────────────────────────────────────────────────────────────────────

def _plot(daily_stress, hourly_pattern, oura_sleep, d_from, d_to):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        BG   = "#1A1A2E"
        AXES = "#16213E"
        TICK = "#AAAAAA"
        SPINE = "#444466"

        fig, axes = plt.subplots(3, 1, figsize=(13, 13), facecolor=BG)
        fig.suptitle(
            f"Oura — Stress & Erholung  {d_from} bis {d_to}",
            color="#E0E0E0", fontsize=12, y=0.98
        )

        def _style(ax):
            ax.set_facecolor(AXES)
            ax.tick_params(colors=TICK, labelsize=8)
            for sp in ax.spines.values():
                sp.set_edgecolor(SPINE)

        # ── Subplot 1: Daily stress and recovery time series ──────────────────
        ax1 = axes[0]
        _style(ax1)

        days_dt = []
        stress_vals = []
        recovery_vals = []
        for row in daily_stress:
            day, avg_s, avg_r, *_ = row
            try:
                dt = datetime.strptime(day, "%Y-%m-%d")
            except ValueError:
                continue
            days_dt.append(dt)
            stress_vals.append(avg_s)
            recovery_vals.append(avg_r)

        if days_dt:
            ax1.plot(days_dt, stress_vals,   color="#E84855", lw=2.0,
                     marker="o", ms=5, label="Ø Stress (0-100)", alpha=0.9)
            ax1.plot(days_dt, recovery_vals, color="#2ECC71", lw=2.0,
                     marker="s", ms=5, label="Ø Erholung (0-100)", alpha=0.9)
            ax1.fill_between(days_dt, stress_vals, recovery_vals,
                             where=[s > r for s, r in zip(stress_vals, recovery_vals)],
                             alpha=0.12, color="#E84855", label="Stress > Erholung")
            ax1.fill_between(days_dt, stress_vals, recovery_vals,
                             where=[r >= s for s, r in zip(stress_vals, recovery_vals)],
                             alpha=0.12, color="#2ECC71", label="Erholung > Stress")
            ax1.axhline(50, color="#FDCB6E", lw=0.8, ls="--", alpha=0.5,
                        label="Mittellinie (50)")
            ax1.set_ylim(0, 105)
            ax1.set_ylabel("Score (0–100)", color=TICK, fontsize=9)
            ax1.set_title("Taegliche Stressbelastung & Erholung",
                          color="#E0E0E0", fontsize=10, pad=6)
            ax1.legend(fontsize=7, labelcolor="#E0E0E0", facecolor=AXES,
                       edgecolor=SPINE, loc="upper right")
            ax1.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m."))
            ax1.xaxis.set_major_locator(mdates.DayLocator())
            fig.autofmt_xdate(rotation=30)

        # ── Subplot 2: Hourly intraday pattern ────────────────────────────────
        ax2 = axes[1]
        _style(ax2)

        if hourly_pattern:
            hours      = [r[0] for r in hourly_pattern]
            h_stress   = [r[1] if r[1] is not None else 0 for r in hourly_pattern]
            h_recovery = [r[2] if r[2] is not None else 0 for r in hourly_pattern]

            x = list(range(len(hours)))
            w = 0.35
            ax2.bar([xi - w/2 for xi in x], h_stress,   width=w,
                    color="#E84855", alpha=0.8, label="Ø Stress")
            ax2.bar([xi + w/2 for xi in x], h_recovery, width=w,
                    color="#2ECC71", alpha=0.8, label="Ø Erholung")
            ax2.set_xticks(x)
            ax2.set_xticklabels([f"{h:02d}" for h in hours], fontsize=7)
            ax2.set_xlabel("Uhrzeit", color=TICK, fontsize=9)
            ax2.set_ylabel("Score (0–100)", color=TICK, fontsize=9)
            ax2.set_title("Intraday-Muster: Stress & Erholung nach Stunde",
                          color="#E0E0E0", fontsize=10, pad=6)
            ax2.legend(fontsize=8, labelcolor="#E0E0E0", facecolor=AXES,
                       edgecolor=SPINE)
            ax2.set_ylim(0, 105)
            ax2.axhline(50, color="#FDCB6E", lw=0.6, ls="--", alpha=0.4)

        # ── Subplot 3: Scatter stress vs next-night HRV ───────────────────────
        ax3 = axes[2]
        _style(ax3)

        scatter_same_s, scatter_same_h = [], []
        scatter_next_s, scatter_next_h = [], []

        for row in daily_stress:
            day, avg_s, *_ = row
            if avg_s is None:
                continue
            same = oura_sleep.get(day)
            nxt  = oura_sleep.get(_next_day(day))
            if same and same.get("hrv"):
                scatter_same_s.append(avg_s)
                scatter_same_h.append(same["hrv"])
            if nxt and nxt.get("hrv"):
                scatter_next_s.append(avg_s)
                scatter_next_h.append(nxt["hrv"])

        has_data = False
        if scatter_same_s:
            ax3.scatter(scatter_same_s, scatter_same_h,
                        color="#4A90D9", s=70, alpha=0.85, zorder=5,
                        label="HRV gleiche Nacht")
            has_data = True
        if scatter_next_s:
            ax3.scatter(scatter_next_s, scatter_next_h,
                        color="#F39C12", s=70, alpha=0.85, zorder=5,
                        marker="^", label="HRV Folgenacht")
            has_data = True

        if has_data:
            # Trend line (simple linear) for same-night if enough points
            all_s = scatter_same_s + scatter_next_s
            all_h = scatter_same_h + scatter_next_h
            if len(all_s) >= 3:
                n    = len(all_s)
                sx   = sum(all_s) / n
                sy   = sum(all_h) / n
                ssxy = sum((x - sx) * (y - sy) for x, y in zip(all_s, all_h))
                ssxx = sum((x - sx) ** 2 for x in all_s)
                if ssxx > 0:
                    slope = ssxy / ssxx
                    intercept = sy - slope * sx
                    xr = [min(all_s), max(all_s)]
                    yr = [slope * x + intercept for x in xr]
                    ax3.plot(xr, yr, color="#AAAAAA", lw=1.0, ls="--",
                             alpha=0.6, label="Trend (gesamt)")

            ax3.set_xlabel("Taeglicher Stress-Mittelwert (Oura 0–100)",
                           color=TICK, fontsize=9)
            ax3.set_ylabel("Schlaf-HRV RMSSD (ms)", color=TICK, fontsize=9)
            ax3.set_title("Stress-Burden vs. naechste Schlaf-HRV",
                          color="#E0E0E0", fontsize=10, pad=6)
            ax3.legend(fontsize=8, labelcolor="#E0E0E0", facecolor=AXES,
                       edgecolor=SPINE)
        else:
            ax3.text(0.5, 0.5, "Keine ueberlappenden Stress+HRV-Daten",
                     transform=ax3.transAxes, ha="center", va="center",
                     color="#888888", fontsize=10)
            ax3.set_title("Stress-Burden vs. Schlaf-HRV (keine Daten)",
                          color="#E0E0E0", fontsize=10, pad=6)

        plt.tight_layout(rect=[0, 0, 1, 0.97])
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M")
        path = OUT_DIR / f"oura_recovery_{ts}.png"
        fig.savefig(str(path), dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close()
        print(f"Plot: {path}")
    except Exception as e:
        print(f"Plot fehlgeschlagen: {e}")


# ── LLM ──────────────────────────────────────────────────────────────────────

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
    out = OUT_DIR / f"oura_recovery_{ts}.md"
    content = f"# Oura-Stress & Erholung\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=t(
            "Oura-Stress & Erholung — Tagesbelastung und Erholungskapazitaet",
            "Oura stress & recovery — daily burden and recovery capacity"
        )
    )
    parser.add_argument("--from",   dest="date_from",
                        default=(datetime.today() - timedelta(days=45)).strftime("%Y-%m-%d"),
                        help=t("Startdatum (YYYY-MM-DD, Default: 45 Tage)",
                               "Start date (YYYY-MM-DD, default: 45 days)"))
    parser.add_argument("--to",     dest="date_to",
                        default=datetime.today().strftime("%Y-%m-%d"),
                        help=t("Enddatum (YYYY-MM-DD)", "End date (YYYY-MM-DD)"))
    parser.add_argument("--all",    dest="all_data",  action="store_true",
                        help=t("Alle verfügbaren Daten (überschreibt --from/--to)",
                               "All available data (overrides --from/--to)"))
    parser.add_argument("--plot",   action="store_true",
                        help=t("Diagramme erstellen", "Generate plots"))
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

    conn = open_db()

    # Check tables exist
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    if "oura_daytime_stress" not in tables:
        print(t(
            "Tabelle oura_daytime_stress nicht gefunden. Zuerst: python3 importers/import_oura.py",
            "Table oura_daytime_stress not found. Run: python3 importers/import_oura.py"
        ))
        conn.close()
        return

    daily_stress   = load_daily_stress(conn, args.date_from, args.date_to)
    hourly_pattern = load_hourly_pattern(conn, args.date_from, args.date_to)
    oura_sleep     = load_oura_sleep(conn, args.date_from, args.date_to) \
                     if "oura_sleep_model" in tables else {}
    polar_hrv, hrv_sources, hrv_confidence = load_hrv_reference(conn, args.date_from, args.date_to)
    conn.close()

    n_days = len(daily_stress)
    _hrv_src_str = ", ".join(f"{src}: {n}" for src, n in hrv_sources.items()) or "–"
    print(t(
        f"Oura-Stress: {n_days} Tage  |  Schlaf-HRV: {len(oura_sleep)} Tage"
        f"  |  HRV-Referenz: {len(polar_hrv)} Tage (Quelle: {_hrv_src_str}; Konfidenz: {hrv_confidence})",
        f"Oura stress: {n_days} days  |  sleep HRV: {len(oura_sleep)} days"
        f"  |  HRV reference: {len(polar_hrv)} days (source: {_hrv_src_str}; confidence: {hrv_confidence})"
    ))

    if n_days == 0:
        print(t(
            f"Keine Oura-Stressdaten im Zeitraum {args.date_from} – {args.date_to}.",
            f"No Oura stress data in range {args.date_from} – {args.date_to}."
        ))
        return

    if n_days < 7:
        print(t(
            f"HINWEIS: Nur {n_days} Tage verfuegbar — Analyse ist vorlaeufig!",
            f"NOTE: Only {n_days} days available — analysis is preliminary!"
        ))

    report = build_report(
        daily_stress, hourly_pattern, oura_sleep, polar_hrv,
        args.date_from, args.date_to,
        hrv_sources=hrv_sources, hrv_confidence=hrv_confidence,
    )
    print("\n" + report)

    if args.plot:
        _plot(daily_stress, hourly_pattern, oura_sleep, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
