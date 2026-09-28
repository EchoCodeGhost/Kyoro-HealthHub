#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Intraday-Stress-Architektur

Analysiert den Tagesverlauf der autonomen Load aus Garmin (5-min
Stress-Score) und Oura-Erholungswert. Identifiziert kritische
Tageszeiten, Stressmuster und Zusammenhang mit Symptomen.

@tier        heuristic
@refs        Thayer JF, Åhs F, Fredrikson M, Sollers JJ, Wager TD (2012). A meta-analysis of heart rate variability and neuroimaging studies: implications for heart rate variability as a marker of stress and health. Neuroscience & Biobehavioral Reviews, 36(2), 747-756. doi:10.1016/j.neubiorev.2011.11.009
             Kim HG, Cheon EJ, Bai DS, Lee YH, Koo BH (2018). Stress and heart rate variability: a meta-analysis and review of the literature. Psychiatry Investigation, 15(3), 235-245. doi:10.30773/pi.2017.08.17

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@purpose.de  Analysiert den Tagesverlauf der autonomen Belastung aus Garmin-Stress-Scores (5-Minuten) und Oura-Erholungswerten; identifiziert kritische Tageszeiten und Wochentagsmuster.
@purpose.en  Analyses the intraday autonomic load from Garmin stress scores (5-minute) and Oura recovery values; identifies critical times of day and weekday patterns.
@method.de   Stundenmittelwerte der Stress/Recovery-Skalen (Garmin 0–100, Oura 0–100) aggregiert über alle Tage; kein formal validierter Stress-Algorithmus.
@method.en   Hourly averages of stress/recovery scales (Garmin 0–100, Oura 0–100) aggregated across all days; no formally validated stress algorithm.
@limits.de   Heuristische Methode: Garmin-Stress und Oura-Recovery sind proprietäre Scores ohne offengelegte Validierungsstudien; Aggregation über viele Tage verliert tagesspezifische Variation; keine Kausalitätsaussagen.
@limits.en   Heuristic method: Garmin stress and Oura recovery are proprietary scores without published validation studies; aggregation over many days loses day-specific variation; no causal conclusions.
@scoring
    Garmin stress: 0-25 recovery | 25-50 low | 50-75 moderate | >75 high
    Oura recovery: 0-100 (higher = better recovery)
@reads       measurements, oura_daytime_stress, symptoms
@writes      analyses/cardiovascular/intraday_stress_*.{md,png}

Usage:
  python analyse_intraday_stress.py --plot
  python analyse_intraday_stress.py --from YYYY-MM-DD --plot
  python analyse_intraday_stress.py --plot --no-llm

@usage
    python analyse_intraday_stress.py
    python analyse_intraday_stress.py --help
    python analyse_intraday_stress.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.base import resolve_timezone
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_INTRADAY_STRESS_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_INTRADAY_STRESS_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "cardiovascular"


def _local_hour(ts_str: str, tz) -> int:
    """UTC-ISO-Timestamp -> lokale Stunde (0-23), sommer-/winterzeitkorrekt.

    ts ist laut Konvention (CLAUDE.md) UTC. strftime('%H', ts) auf dem rohen
    String liefert die UTC-Stunde, keine Ortszeit — bei einer Zeitverschiebung
    von mehreren Stunden landet z.B. der Nachmittags-Stresspeak im falschen
    Stundenbalken. astimezone() pro Zeitstempel behandelt auch die Sommer-/
    Winterzeit-Umstellung korrekt, ein fixer UTC-Offset würde das nicht.
    """
    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).hour


def load_data(conn, d_from, d_to, person=OWN_PERSON_ID):
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(resolve_timezone(conn, person))

    # Stress liegt unter zwei Garmin-Pipelines vor: source_app='garmin_connect'
    # (Live-API, erst ab 2026-02-28) und 'garmin_gdpr' (Datenauskunft-Export,
    # seit 2021). Ein Filter auf nur eine Quelle liess >90% der Werte und fast
    # den gesamten Zeitraum vor 2026 stillschweigend aus (device-agnostisch,
    # siehe cross-cutting-conventions). Ueberlappende (ts, value)-Paare beider
    # Pipelines werden per DISTINCT dedupliziert statt doppelt gezaehlt.
    garmin_stress_raw = conn.execute("""
        SELECT DISTINCT ts, value
        FROM measurements
        WHERE metric = 'stress'
          AND date >= ? AND date <= ? AND value IS NOT NULL AND value >= 0
    """, (d_from, d_to)).fetchall()
    hour_vals = defaultdict(list)
    for ts, val in garmin_stress_raw:
        hour_vals[_local_hour(ts, tz)].append(val)
    garmin_stress = [(h, sum(vs) / len(vs)) for h, vs in sorted(hour_vals.items())]

    daily_vals = defaultdict(list)
    for date, ts, val in conn.execute("""
        SELECT DISTINCT date, ts, value
        FROM measurements
        WHERE metric = 'stress'
          AND date >= ? AND date <= ? AND value IS NOT NULL AND value >= 0
    """, (d_from, d_to)):
        daily_vals[date].append(val)
    garmin_daily = [(d, sum(vs) / len(vs)) for d, vs in sorted(daily_vals.items())]

    oura_recovery = conn.execute("""
        SELECT DATE(timestamp) AS date,
               AVG(recovery_value) AS avg_recovery
        FROM oura_daytime_stress
        WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?
          AND recovery_value IS NOT NULL
        GROUP BY DATE(timestamp)
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    # Oura Stunden-Profil — ebenfalls lokale Stunde statt UTC-Rohstunde
    oura_raw = conn.execute("""
        SELECT timestamp, recovery_value
        FROM oura_daytime_stress
        WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?
          AND recovery_value IS NOT NULL
    """, (d_from, d_to)).fetchall()
    oura_hour_vals = defaultdict(list)
    for ts, val in oura_raw:
        oura_hour_vals[_local_hour(ts, tz)].append(val)
    oura_hourly = [(h, sum(vs) / len(vs)) for h, vs in sorted(oura_hour_vals.items())]

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    symptome = {}
    if "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND category='Ressourcen' AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert
    elif "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND category='Ressourcen' AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert

    stress_daily = {}
    if "daily_stress" in tables:
        for d, rmssd, *_ in conn.execute("""
            SELECT date, rmssd_ms FROM daily_stress
            WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            stress_daily[d] = rmssd

    return garmin_stress, garmin_daily, oura_recovery, oura_hourly, symptome, stress_daily


def spearman_r(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    n = len(pairs)
    def ranks(vals):
        sv = sorted(range(n), key=lambda i: vals[i])
        r = [0] * n
        for rank, idx in enumerate(sv, 1):
            r[idx] = rank
        return r
    xv, yv = zip(*pairs)
    rx, ry = ranks(list(xv)), ranks(list(yv))
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return round(1 - 6 * d2 / (n * (n ** 2 - 1)), 3)


def build_report(garmin_stress, garmin_daily, oura_recovery, oura_hourly,
                     symptome, stress_daily, d_from, d_to):
    if not garmin_stress and not oura_recovery:
        return "No Intraday-Stressdaten im angefragten Time range."

    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

    lines = [f"## Intraday-Stress-Architektur — {d_from} bis {d_to}\n"]

    if garmin_stress:
        peak_h = max(garmin_stress, key=lambda x: x[1])
        rest_h = min(garmin_stress, key=lambda x: x[1])
        lines += [
            f"### Garmin Stress-Profile (Tageszeit, n={len(garmin_daily)} days)\n",
            f"  Highest Load: {peak_h[0]:02d}:00 Uhr (Ø {peak_h[1]:.0f})",
            f"  Lowest Load: {rest_h[0]:02d}:00 Uhr (Ø {rest_h[1]:.0f})\n",
            f"  {'Uhrzeit':<10} {'Ø Stress':>10} {'Niveau':<20}",
            "  " + "-" * 42,
        ]
        for h, s in garmin_stress:
            niveau = "Recovery" if s < 25 else "Niedrig" if s < 50 else \
                     "Withtel" if s < 75 else "Hoch ⚠"
            lines.append(f"  {h:02d}:00      {s:>8.0f}  {niveau}")

    if oura_hourly:
        peak_r = max(oura_hourly, key=lambda x: x[1] or 0)
        low_r  = min(oura_hourly, key=lambda x: x[1] or 100)
        lines += [
            "\n### Oura Recovery-Profile (Tageszeit)\n",
            f"  Beste Recovery:  {peak_r[0]:02d}:00 Uhr (Ø {peak_r[1]:.0f})",
            f"  Schwächste Recovery: {low_r[0]:02d}:00 Uhr (Ø {low_r[1]:.0f})",
        ]

    # Wochentag-Muster
    if garmin_daily:
        dow_stress = defaultdict(list)
        for r in garmin_daily:
            try:
                dow = datetime.fromisoformat(r[0]).strftime("%a")
                dow_stress[dow].append(r[1])
            except ValueError:
                pass
        if dow_stress:
            lines.append("\n### Wochentag-Muster (Garmin Stress)\n")
            for dow in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
                if dow in dow_stress:
                    a = avg(dow_stress[dow])
                    lines.append(f"  {dow}  Ø {a}")

    # Trend
    if garmin_daily and len(garmin_daily) >= 20:
        st_vals = [r[1] for r in garmin_daily if r[1]]
        q = len(st_vals) // 5
        early = avg(st_vals[:q])
        late  = avg(st_vals[-q:])
        if early and late:
            delta = round(late - early, 1)
            lines.append(f"\nTrend Garmin Stress: {delta:+.1f} (früh: {early} → spät: {late})")

    # Correlationen
    dates_g = [r[0] for r in garmin_daily]
    stress_g = [r[1] for r in garmin_daily]
    sym_y   = [symptome.get(d) for d in dates_g]
    hrv_y   = [stress_daily.get(d) for d in dates_g]
    r_s_sym = spearman_r(stress_g, sym_y)
    r_s_hrv = spearman_r(stress_g, hrv_y)
    if any(r is not None for r in [r_s_sym, r_s_hrv]):
        lines += [
            "\n### Correlation Tages-Stress × (Spearman r)\n",
            f"  × HRV RMSSD: {r_s_hrv if r_s_hrv else 'n.a.'}",
            f"  × Energie:   {r_s_sym if r_s_sym else 'n.a.'}",
        ]

    return "\n".join(lines)


def _plot(garmin_stress, garmin_daily, oura_hourly, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(2, 2, figsize=(14, 8), facecolor="#1e1e2e")
    fig.suptitle(f"Intraday-Stress-Architektur {d_from}–{d_to}",
                 color="#E0E0E0", fontsize=13)
    axes_flat = axes.flatten()
    for ax in axes_flat:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # Garmin Stunden-Profile
    if garmin_stress:
        hours = [r[0] for r in garmin_stress]
        vals  = [r[1] for r in garmin_stress]
        colors = ["#e17055" if v > 75 else "#fdcb6e" if v > 50
                  else "#74b9ff" if v > 25 else "#2ecc71" for v in vals]
        axes_flat[0].bar(hours, vals, color=colors, alpha=0.85)
        axes_flat[0].axhline(50, color="#fdcb6e", lw=0.6, ls="--", alpha=0.5)
        axes_flat[0].set_title("Garmin Stress (Uhrzeit)", color="#ccc", fontsize=9)
        axes_flat[0].set_xticks(range(0, 24, 2))
        axes_flat[0].set_xticklabels([f"{h}" for h in range(0, 24, 2)], fontsize=7)

    # Oura Recovery Stunden-Profile
    if oura_hourly:
        hours = [r[0] for r in oura_hourly]
        vals  = [r[1] for r in oura_hourly if r[1]]
        hours = [r[0] for r in oura_hourly if r[1]]
        axes_flat[1].bar(hours, vals, color="#2ecc71", alpha=0.8)
        axes_flat[1].set_title("Oura Recovery (Uhrzeit)", color="#ccc", fontsize=9)
        axes_flat[1].set_xticks(range(0, 24, 2))
        axes_flat[1].set_xticklabels([f"{h}" for h in range(0, 24, 2)], fontsize=7)

    # Garmin Tages-Trend
    if garmin_daily:
        dts  = [datetime.fromisoformat(r[0]) for r in garmin_daily if r[1]]
        vals = [r[1] for r in garmin_daily if r[1]]
        if dts:
            axes_flat[2].plot(dts, vals, color="#fd79a8", lw=1.0, alpha=0.7)
            axes_flat[2].set_title("Garmin Stress (täglich)", color="#ccc", fontsize=9)
            axes_flat[2].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Oura Recovery täglich
    axes_flat[3].set_title("Oura Recovery (täglich)", color="#ccc", fontsize=9)

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"intraday_stress_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(t(f"Plot: {p}", f"Plot: {p}"))
    plt.close()


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=700)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"intraday_stress_{ts}.md"
    content = f"# Intraday-Stress-Architektur\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


def main():
    parser = argparse.ArgumentParser(description=t("Intraday-Stress-Architektur", "Intraday stress architecture"))
    parser.add_argument("--from",   dest="date_from", default=_cfg.birthdate or "1900-01-01")
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    garmin_stress, garmin_daily, oura_recovery, oura_hourly, symptome, stress_daily = \
        load_data(conn, args.date_from, args.date_to, person=args.person)
    conn.close()

    if not garmin_stress and not oura_recovery:
        print(t("Keine Intraday-Stressdaten. Zuerst: python3 importers/import_garmin.py "
                "und/oder import_oura.py",
                "No intraday stress data. First run: python3 importers/import_garmin.py "
                "and/or import_oura.py"))
        return

    print(t(f"Garmin-Stundenmittel: {len(garmin_stress)}  |  Oura-Tage: {len(oura_recovery)}",
            f"Garmin hourly avg: {len(garmin_stress)}  |  Oura days: {len(oura_recovery)}"))
    report = build_report(garmin_stress, garmin_daily, oura_recovery, oura_hourly,
                               symptome, stress_daily, args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(garmin_stress, garmin_daily, oura_hourly, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
