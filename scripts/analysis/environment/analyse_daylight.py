#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Tageslicht-Exposition & Circadiane Gesundheit

Analysiert tägliche Zeit im Freien (Apple Watch, minutes Tageslicht)
and deren Einfluss auf Sleepqualität, HRV, Energie and Stimmung.

Usage:
  python analyse_daylight.py --plot
  python analyse_daylight.py --from YYYY-MM-DD --plot
  python analyse_daylight.py --plot --no-llm

@tier        heuristic
@refs        Lewy AJ, Wehr TA, Goodwin FK, Newsome DA, Markey SP (1980). Light suppresses melatonin secretion in humans. Science, 210(4475):1267-1269. doi:10.1126/science.7434030
             Wirz-Justice A, Benedetti F, Terman M (2013). Chronotherapeutics for Affective Disorders: A Clinician's Manual for Light and Wake Therapy (2nd ed.). Karger. doi:10.1159/isbn.978-3-318-02091-5

@relevance.de  Analysiert den Einfluss von Tageslichtexposition auf Schlafqualität, Stimmung und zirkadianen Rhythmus, essentiell für die Erkennung von Schlafstörungen und die Optimierung der Lichttherapie
@relevance.en  Analyzes the impact of daylight exposure on sleep quality, mood, and circadian rhythm, essential for identifying sleep disorders and optimizing light therapy
@purpose.de  Analysiert tägliche Tageslichtexposition (Apple Watch) und deren Zusammenhang
             mit Schlafqualität, HRV, Energie und Stimmung via Spearman-Korrelation.
@purpose.en  Analyses daily daylight exposure (Apple Watch) and its association with sleep
             quality, HRV, energy and mood via Spearman correlation.
@method.de   Summiert time_in_daylight-Einträge aus apple_records; Spearman-Korrelation
             ohne Multiple-Testing-Korrektur. Richtwert 30 min/Tag als Mindest-Exposition
             (zirkadiane Rhythmik) ohne RCT-Backing.
@method.en   Sums time_in_daylight entries from apple_records; Spearman correlation
             without multiple-testing correction. Minimum 30 min/day guideline (circadian
             rhythm) without RCT backing.
@limits.de   Heuristische Methode: Apple Watch misst Tageslicht indirekt (UV-Sensor oder Bewegungsdaten);
             keine Lux-Kalibrierung. Konfundierung durch Saisonalität nicht kontrolliert.
             Korrelationen sind explorativ. n=1.
@limits.en   Heuristic method: Apple Watch measures daylight indirectly (UV sensor or motion data);
             no lux calibration. Confounding by seasonality not controlled.
             Correlations are exploratory. n=1.
@scoring
    Daylight exposure: <30 min/day low | 30-60 min/day moderate | >60 min/day high (circadian rhythm guideline)
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
@reads       apple_records (time_in_daylight), daily_stress, polar_sleep_score,
             symptoms, weather_station
@writes      analyses/environment/*.{md,png} (kein DB-Write)

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_daylight.py
    python analyse_daylight.py --help
    python analyse_daylight.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "environment"

from modules.prompts.analysis_environment import (
    SYSTEM_PROMPT_ANALYSE_DAYLIGHT_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_DAYLIGHT_EN as SYSTEM_PROMPT_EN,
)

MINDEST_MIN = 30


def load_data(conn, d_from, d_to):
    # Tageslicht: Summe der 5-min-Blöcke pro day in minutes
    licht = conn.execute("""
        SELECT DATE(start_date) AS date, SUM(value) AS total_min
        FROM apple_records
        WHERE type = 'time_in_daylight'
          AND DATE(start_date) >= ? AND DATE(start_date) <= ?
          AND value IS NOT NULL
        GROUP BY DATE(start_date)
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    stress = {}
    if "daily_stress" in tables:
        for d, rmssd, stress_s, sleep_h in conn.execute("""
            SELECT date, rmssd_ms, stress_score, sleep_hours FROM daily_stress
            WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            stress[d] = {"hrv": rmssd, "stress": stress_s, "sleep_h": sleep_h}

    schlaf_polar = {}
    if "polar_sleep_score" in tables:
        for d, score in conn.execute("""
            SELECT date, sleep_score FROM polar_sleep_score
            WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            schlaf_polar[d] = score

    symptome = {}
    if "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND category='Ressourcen' AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert

    solar = {}
    if "weather_station" in tables:
        for d, sol in conn.execute("""
            SELECT date, solar_wm2_max FROM weather_station
            WHERE date >= ? AND date <= ? AND solar_wm2_max IS NOT NULL
        """, (d_from, d_to)):
            solar[d] = sol

    return licht, stress, schlaf_polar, symptome, solar


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


def build_report(licht, stress, schlaf_polar, symptome, solar, d_from, d_to):
    if not licht:
        return "No Tageslicht-Daten im angefragten Time range."

    n = len(licht)
    licht_vals = [r[1] for r in licht if r[1] is not None]
    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

    a = avg(licht_vals)
    n_zu_wenig = sum(1 for v in licht_vals if v < MINDEST_MIN)

    lines = [
        f"## Tageslicht-Exposition — {d_from} bis {d_to}\n",
        f"days: **{n}**  |  Time range: {licht[0][0]} – {licht[-1][0]}\n",
        "### Tageslicht\n",
        f"  Ø pro day: **{a} min**",
        f"  Zu wenig (<{MINDEST_MIN} min): {n_zu_wenig} ({round(n_zu_wenig/n*100,1)}%)",
        f"  Maximum: {max(licht_vals):.0f} min  |  Median: {sorted(licht_vals)[n//2]:.0f} min",
    ]

    # Saisonal: Monatswithtel
    by_month = defaultdict(list)
    for r in licht:
        if r[1]:
            by_month[r[0][:7]].append(r[1])
    if len(by_month) >= 3:
        lines.append("\n### Saisonales Muster (Monatswithtel)\n")
        for ym in sorted(by_month):
            a_m = avg(by_month[ym])
            bar = "█" * int(a_m / 15)
            lines.append(f"  {ym}  {a_m:>5.0f} min  {bar}")

    # Quartilanalyse
    licht_sorted = sorted(licht_vals)
    if len(licht_sorted) >= 12:
        q = len(licht_sorted) // 4
        wenig = licht_sorted[:q]
        viel  = licht_sorted[-q:]
        dates_licht = [r[0] for r in licht]

        hrv_wenig = [stress[d]["hrv"] for d, v in zip(dates_licht, licht_vals)
                     if v in wenig and d in stress and stress[d].get("hrv")]
        hrv_viel  = [stress[d]["hrv"] for d, v in zip(dates_licht, licht_vals)
                     if v in viel and d in stress and stress[d].get("hrv")]
        slp_wenig = [schlaf_polar[d] for d, v in zip(dates_licht, licht_vals)
                     if v in wenig and d in schlaf_polar]
        slp_viel  = [schlaf_polar[d] for d, v in zip(dates_licht, licht_vals)
                     if v in viel and d in schlaf_polar]

        lines.append("\n### Wirkung: wenig vs. viel Tageslicht\n")
        lines.append(f"  {'Gruppe':<20} {'HRV Ø':>8} {'Sleep Score Ø':>15}")
        lines.append("  " + "-" * 45)
        lines.append(f"  {'Wenig (<' + str(int(avg(wenig))) + ' min)':<20} "
                     f"{str(avg(hrv_wenig)) + ' ms' if hrv_wenig else 'n.a.':>8} "
                     f"{str(avg(slp_wenig)) if slp_wenig else 'n.a.':>15}")
        lines.append(f"  {'Viel (>' + str(int(avg(viel))) + ' min)':<20} "
                     f"{str(avg(hrv_viel)) + ' ms' if hrv_viel else 'n.a.':>8} "
                     f"{str(avg(slp_viel)) if slp_viel else 'n.a.':>15}")

    # Correlationen
    dates = [r[0] for r in licht]
    licht_x = [r[1] for r in licht]
    hrv_y   = [stress[d]["hrv"]     if d in stress else None for d in dates]
    slp_y   = [schlaf_polar.get(d) for d in dates]
    sym_y   = [symptome.get(d) for d in dates]
    sol_y   = [solar.get(d) for d in dates]

    r_l_hrv = spearman_r(licht_x, hrv_y)
    r_l_slp = spearman_r(licht_x, slp_y)
    r_l_sym = spearman_r(licht_x, sym_y)
    r_l_sol = spearman_r(licht_x, sol_y)

    if any(r is not None for r in [r_l_hrv, r_l_slp]):
        lines += [
            "\n### Correlation Tageslicht × (Spearman r)\n",
            f"  × HRV RMSSD:     {r_l_hrv if r_l_hrv else 'n.a.'}",
            f"  × Sleep Score:   {r_l_slp if r_l_slp else 'n.a.'}",
            f"  × Energie:       {r_l_sym if r_l_sym else 'n.a.'}",
            f"  × Solar W/m²:    {r_l_sol if r_l_sol else 'n.a.'} (Tageslicht↔Sonnenstrahlung)",
        ]

    return "\n".join(lines)


def _plot(licht, stress, schlaf_polar, solar, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), facecolor="#1e1e2e")
    fig.suptitle(f"Tageslicht & Circadiane Gesundheit {d_from}–{d_to}",
                 color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    dts  = [datetime.fromisoformat(r[0]) for r in licht if r[1]]
    vals = [r[1] for r in licht if r[1]]
    if dts:
        axes[0].bar(dts, vals, color="#fdcb6e", alpha=0.7, width=0.8)
        axes[0].axhline(MINDEST_MIN, color="#e17055", lw=0.8, ls="--", alpha=0.6,
                        label=f"Mindest {MINDEST_MIN} min")
        if len(vals) >= 14:
            ma14 = [sum(vals[max(0,i-13):i+1])/len(vals[max(0,i-13):i+1]) for i in range(len(vals))]
            axes[0].plot(dts, ma14, color="#f7b731", lw=1.5, label="14-days-Ø")
        axes[0].set_ylabel("Tageslicht (min)", color="#ccc", fontsize=9)
        axes[0].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # HRV + Sleep Score overlay
    hrv_dts  = [datetime.fromisoformat(d) for d in stress if stress[d].get("hrv")]
    hrv_vals = [stress[d]["hrv"] for d in stress if stress[d].get("hrv")]
    slp_dts  = [datetime.fromisoformat(d) for d in schlaf_polar if schlaf_polar[d]]
    slp_vals = [schlaf_polar[d] for d in schlaf_polar if schlaf_polar[d]]

    if hrv_dts:
        ax2b = axes[1].twinx()
        axes[1].plot(hrv_dts, hrv_vals, color="#a29bfe", lw=1.0, alpha=0.7, label="HRV")
        axes[1].set_ylabel("HRV RMSSD (ms)", color="#ccc", fontsize=9)
        if slp_dts:
            ax2b.plot(slp_dts, slp_vals, color="#2ecc71", lw=1.0, ls="--", alpha=0.7,
                      label="Sleep Score")
            ax2b.set_ylabel("Sleep Score", color="#aaa", fontsize=8)
            ax2b.tick_params(colors="#aaa", labelsize=7)
            ax2b.set_facecolor("#2a2a3e")
        axes[1].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white", loc="upper left")
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"daylight_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(f"Plot: {p}")
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
    out = OUT_DIR / f"daylight_{ts}.md"
    content = f"# Tageslicht & Circadiane Gesundheit\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("Tageslicht & Circadiane Gesundheit", "Daylight & circadian health"))
    parser.add_argument("--from",   dest="date_from", default=_cfg.data_start or "1900-01-01")
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    licht, stress, schlaf_polar, symptome, solar = load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not licht:
        print("No Tageslicht-Daten. Zuerst: python3 importers/import_apple_health.py")
        return

    print(f"Tageslicht-days: {len(licht)}")
    report = build_report(licht, stress, schlaf_polar, symptome, solar,
                               args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(licht, stress, schlaf_polar, solar, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
