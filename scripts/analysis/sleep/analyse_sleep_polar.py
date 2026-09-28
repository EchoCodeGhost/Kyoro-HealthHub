#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Sleep-Staging & nächtliche HRV-Analyse

Analysiert die Sleeparchitektur (Deep Sleep/REM/Leichtschlaf/Wach)
from the Polar-Hypnogramm, den Night-HRV-Verlauf sowie den Polar
Sleep Score and deren Zusammenhang with Recovery and Symptomsn.

@tier        calibrated
@purpose.de  Analysiert Polar-Schlafarchitektur (Tiefschlaf/REM/Leichtschlaf/Wach), nächtlichen HRV-Verlauf und Polar-Sleep-Score sowie deren Korrelation mit Erholung und Symptomen.
@purpose.en  Analyses Polar sleep architecture (deep/REM/light/wake), nightly HRV course and Polar sleep score and their correlation with recovery and symptoms.
@method.de   Liest Polar-Hypnogramm-Sequenzen (2-Min-Intervalle) und HRV-Zeitreihen; aggregiert Schlafphasen-Anteile und korreliert mit Folgetag-Metriken. Polar-spezifischer proprietärer Algorithmus.
@method.en   Reads Polar hypnogram sequences (2-minute intervals) and HRV time series; aggregates sleep stage proportions and correlates with next-day metrics. Polar-specific proprietary algorithm.
@limits.de   Polar-Schlafstaging ist nicht AASM-zertifiziert und zeigt geringere Genauigkeit als Polysomnographie. Keine externe Validierung der verwendeten Polar-Normwerte.
@limits.en   Polar sleep staging is not AASM-certified and shows lower accuracy than polysomnography. No external validation of the Polar reference values used.
@reads       polar_sleep_hypnogram, polar_nightly_hrv_series, polar_sleep_score, sessions, session_metrics
@writes      analyses/sleep/*.{md,png}
@refs        Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
             Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)

Usage:
  python analyse_sleep_polar.py --plot
  python analyse_sleep_polar.py --from YYYY-MM-DD --plot
  python analyse_sleep_polar.py --plot --no-llm


@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@usage
    python analyse_sleep_polar.py
    python analyse_sleep_polar.py --help
    python analyse_sleep_polar.py --from 2024-01-01 --to 2024-12-31
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
from modules.prompts.analysis_sleep import (
    SYSTEM_PROMPT_ANALYSE_SLEEP_POLAR_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_SLEEP_POLAR_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "sleep"

STATES = {
    "NONREM3":    "Tiefschlaf",
    "REM":        "REM",
    "NONREM2":    "Leichtschlaf",
    "WAKE":       "Wach",
    "WS_UNKNOWN": "Unbekannt",
}


def load_data(conn, d_from, d_to):
    hypno = conn.execute("""
        SELECT date, state, COUNT(*) * 2 / 60.0 AS minuten
        FROM polar_sleep_hypnogram
        WHERE date >= ? AND date <= ? AND state != 'WS_UNKNOWN'
        GROUP BY date, state
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    nhrv = conn.execute("""
        SELECT DATE(datetime) AS date,
               CAST(SUBSTR(datetime, 12, 2) AS INTEGER) AS stunde,
               AVG(rmssd_ms) AS rmssd
        FROM polar_nightly_hrv_series
        WHERE DATE(datetime) >= ? AND DATE(datetime) <= ?
        GROUP BY date, stunde
        ORDER BY datetime
    """, (d_from, d_to)).fetchall()

    scores = conn.execute("""
        SELECT date, sleep_score, continuity, efficiency, deep_score, rem_score
        FROM polar_sleep_score
        WHERE date >= ? AND date <= ?
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    stress = {}
    if "daily_stress" in tables:
        for d, rmssd, stress_s, sleep_h in conn.execute("""
            SELECT date, rmssd_ms, stress_score, sleep_hours FROM daily_stress
            WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            stress[d] = {"hrv": rmssd, "stress": stress_s, "sleep_h": sleep_h}

    symptome = {}
    if "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND category='Ressourcen' AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert

    return hypno, nhrv, scores, stress, symptome


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


def build_report(hypno, nhrv, scores, stress, symptome, d_from, d_to):
    if not hypno and not scores:
        return "No Schlafdaten im angefragten Time range."

    # Staging aggregiert
    staging_by_date = defaultdict(dict)
    for date, state, minuten in hypno:
        staging_by_date[date][state] = staging_by_date[date].get(state, 0) + minuten

    n_tage = len(staging_by_date)

    def avg_state_pct(state):
        vals = []
        for d, s in staging_by_date.items():
            total = sum(v for k, v in s.items() if k != "WAKE")
            if total > 0 and state in s:
                vals.append(s[state] / total * 100)
        return round(sum(vals) / len(vals), 1) if vals else None

    def avg_min(state):
        vals = [s.get(state, 0) for s in staging_by_date.values()]
        return round(sum(vals) / len(vals), 0) if vals else None

    # Sleep scores
    score_vals = [r[1] for r in scores if r[1]]
    deep_score_vals = [r[4] for r in scores if r[4]]
    rem_score_vals  = [r[5] for r in scores if r[5]]
    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

    # Nächtliche HRV: hours-Profiles
    hrv_by_hour = defaultdict(list)
    for _, stande, rmssd in nhrv:
        hrv_by_hour[stande].append(rmssd)

    peak_hour = max(hrv_by_hour, key=lambda h: sum(hrv_by_hour[h]) / len(hrv_by_hour[h])) \
        if hrv_by_hour else None
    tief_hour = min(hrv_by_hour, key=lambda h: sum(hrv_by_hour[h]) / len(hrv_by_hour[h])) \
        if hrv_by_hour else None

    lines = [
        f"## Sleep-Staging & HRV — {d_from} bis {d_to}\n",
        f"Nights with Staging: **{n_tage}**  |  Sleep-Score-Nights: {len(scores)}\n",
        "### Sleeparchitektur (Ø)\n",
    ]

    for state, label in [("NONREM3","Deep Sleep"), ("REM","REM"), ("NONREM2","Leichtschlaf"), ("WAKE","Wach")]:
        pct = avg_state_pct(state)
        min_val = avg_min(state)
        if pct is not None:
            norm = ""
            if state == "NONREM3" and pct < 15: norm = " ⚠ (Norm: 15–25%)"
            elif state == "REM" and pct < 20:   norm = " ⚠ (Norm: 20–25%)"
            lines.append(f"  {label:<14} {pct:>5.1f}%  ({min_val:.0f} min/Night){norm}")

    if score_vals:
        lines += [
            "\n### Polar Sleep Score\n",
            f"  Ø Total: **{avg(score_vals)}**  (n={len(score_vals)})",
        ]
        if deep_score_vals: lines.append(f"  Ø Deep Sleep-Score: {avg(deep_score_vals)}")
        if rem_score_vals:  lines.append(f"  Ø REM-Score:        {avg(rem_score_vals)}")

    if hrv_by_hour:
        lines.append("\n### Nächtliche HRV (stündlich)\n")
        for h in sorted(hrv_by_hour):
            vals = hrv_by_hour[h]
            a = round(sum(vals) / len(vals), 1)
            marker = " ← Highest" if h == peak_hour else (" ← Lowest" if h == tief_hour else "")
            lines.append(f"  {h:02d}:00  Ø {a:>6.1f} ms  (n={len(vals)}){marker}")

    # Trend (sleep score, letzten 90 vs. ersten 90 days)
    if len(scores) >= 20:
        q = len(scores) // 4
        early = [r[1] for r in scores[:q] if r[1]]
        late  = [r[1] for r in scores[-q:] if r[1]]
        if early and late:
            delta = round(avg(late) - avg(early), 1)
            trend_str = f"{delta:+.1f} Points (frühe {avg(early)} → späte {avg(late)})"
            lines.append(f"\nTrend Sleep Score: {trend_str}")

    # Correlationen
    dates_staging = sorted(staging_by_date.keys())
    deep_pct_series = []
    rem_pct_series  = []
    next_hrv, next_sym = [], []
    for d in dates_staging:
        s = staging_by_date[d]
        total = sum(v for k, v in s.items() if k != "WAKE")
        dp = s.get("NONREM3", 0) / total * 100 if total > 0 else None
        rp = s.get("REM", 0) / total * 100 if total > 0 else None
        try:
            nd = (datetime.fromisoformat(d) + timedelta(days=1)).strftime("%Y-%m-%d")
        except ValueError:
            nd = None
        deep_pct_series.append(dp)
        rem_pct_series.append(rp)
        next_hrv.append(stress[nd]["hrv"] if nd and nd in stress else None)
        next_sym.append(symptome.get(nd))

    r_deep_hrv = spearman_r(deep_pct_series, next_hrv)
    r_rem_hrv  = spearman_r(rem_pct_series,  next_hrv)
    r_deep_sym = spearman_r(deep_pct_series, next_sym)

    if any(r is not None for r in [r_deep_hrv, r_rem_hrv]):
        lines += [
            "\n### Correlation Sleep-Staging → Folgetag (Spearman r)\n",
            f"  {'Parameter':<20} {'× HRV':>7} {'× Energie':>10}",
            "  " + "-" * 40,
            f"  {'Deep Sleep %':<20} {str(r_deep_hrv) if r_deep_hrv else 'n.a.':>7} "
            f"{str(r_deep_sym) if r_deep_sym else 'n.a.':>10}",
            f"  {'REM %':<20} {str(r_rem_hrv) if r_rem_hrv else 'n.a.':>7} {'n.a.':>10}",
        ]

    return "\n".join(lines)


def _plot(hypno, nhrv, scores, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from collections import defaultdict

    staging_by_date = defaultdict(dict)
    for date, state, minuten in hypno:
        staging_by_date[date][state] = staging_by_date[date].get(state, 0) + minuten

    dates_sorted = sorted(staging_by_date)
    dts = [datetime.fromisoformat(d) for d in dates_sorted]

    def get_pct(state):
        res = []
        for d in dates_sorted:
            s = staging_by_date[d]
            total = sum(v for k, v in s.items() if k != "WAKE")
            res.append(s.get(state, 0) / total * 100 if total > 0 else 0)
        return res

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), facecolor="#1e1e2e")
    fig.suptitle(f"Sleep-Staging & HRV {d_from}–{d_to}", color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # Gestapeltes Staging
    deep = get_pct("NONREM3")
    rem  = get_pct("REM")
    n2   = get_pct("NONREM2")
    wake = get_pct("WAKE")
    if dts:
        axes[0].stackplot(dts, deep, rem, n2, wake,
                          labels=["Deep Sleep", "REM", "Leichtschlaf", "Wach"],
                          colors=["#0984e3","#a29bfe","#74b9ff","#636e72"], alpha=0.9)
        axes[0].axhline(20, color="#fdcb6e", lw=0.6, ls=":", alpha=0.5)
        axes[0].set_ylabel("% der Sleepzeit", color="#ccc", fontsize=9)
        axes[0].set_ylim(0, 100)
        axes[0].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white", loc="upper left")
        axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Sleep Score
    if scores:
        sc_dts  = [datetime.fromisoformat(r[0]) for r in scores if r[1]]
        sc_vals = [r[1] for r in scores if r[1]]
        axes[1].plot(sc_dts, sc_vals, color="#2ecc71", lw=1.2, alpha=0.8)
        axes[1].axhline(80, color="#fdcb6e", lw=0.8, ls="--", alpha=0.5)
        axes[1].set_ylabel("Sleep Score", color="#ccc", fontsize=9)
        axes[1].set_ylim(0, 100)
        axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Night-HRV hoursprofil
    hrv_by_hour = defaultdict(list)
    for _, stande, rmssd in nhrv:
        hrv_by_hour[stande].append(rmssd)
    if hrv_by_hour:
        hours = sorted(hrv_by_hour)
        avgs  = [sum(hrv_by_hour[h]) / len(hrv_by_hour[h]) for h in hours]
        axes[2].bar(hours, avgs, color="#a29bfe", alpha=0.8, width=0.7)
        axes[2].set_xlabel("Uhrzeit", color="#ccc", fontsize=9)
        axes[2].set_ylabel("Ø RMSSD (ms)", color="#ccc", fontsize=9)
        axes[2].set_xticks(range(0, 24))
        axes[2].set_xticklabels([f"{h}" for h in range(0, 24)], fontsize=7, color="#aaa")

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"sleep_staging_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(f"Plot: {p}")
    plt.close()


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"sleep_staging_{ts}.md"
    content = f"# Sleep-Staging & HRV\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("Sleep-Staging & nächtliche HRV", "Sleep staging & nocturnal HRV"))
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
    hypno, nhrv, scores, stress, symptome = load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not hypno and not scores:
        print("No Schlafdaten. Zuerst: python3 importers/import_polar.py")
        return

    print(f"Staging-Nights: {len(set(r[0] for r in hypno))}  |  Sleep-Scores: {len(scores)}")

    report = build_report(hypno, nhrv, scores, stress, symptome, args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(hypno, nhrv, scores, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
