#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Kognitive Funktion — Verlaufsanalyse

Wertet kognitive Kurztests (cognitive_tests) aus:
  - Reaktionszeit, SDMT, Digit Span, räumliches Gedächtnis, N-Back
  - Trend über Zeit (Prä/Post-Infektion)
  - Tageszeit-Effekte (morning/afternoon/evening)
  - Korrelation mit HRV (RMSSD), Fatigue-Symptomen, Schlafqualität

Wissenschaftliche Grundlage:
  - Matschinger et al. 2021: Kognitive Symptome bei Long COVID
  - Davis et al. 2023 (Nature Reviews): Brain fog als ME/CFS-Merkmal
  - Cognitive battery validation: Stroop, SDMT, Trail Making (Reitan 1955)

Usage:
  python3 analyse_cognitive.py
  python3 analyse_cognitive.py --plot
  python3 analyse_cognitive.py --test reaction_time
  python3 analyse_cognitive.py --plot --no-llm

@tier        experimental
@purpose.de  Wertet kognitive Kurztests (Reaktionszeit, SDMT, Digit Span, N-Back)
             aus: Verlauf über Zeit, Tageszeit-Effekte und Korrelation mit HRV sowie
             Fatigue-Symptomen.
@purpose.en  Evaluates cognitive short tests (reaction time, SDMT, digit span, N-back):
             trend over time, time-of-day effects and correlation with HRV and fatigue symptoms.
@method.de   Pearson-Korrelation kognitiver Scores × HRV/Fatigue; Prä/Post-Gruppenvergleich
             über konfigurierten Ereignis-Cutoff. Kein Holdout, keine Normierung auf
             Bevölkerungsreferenz. Test-Batterie nicht formal für diese Anwendung validiert.
@method.en   Pearson correlation of cognitive scores × HRV/fatigue; pre/post group comparison
             via configured event cutoff. No holdout, no normalisation to population reference.
             Test battery not formally validated for this application.
@refs        Davis HE, McCorkell L, Vogel JM, Topol EJ (2023). Long COVID: major findings, mechanisms and recommendations. Nature Reviews Microbiology, 21(3):133-146. doi:10.1038/s41579-022-00846-2
             Reitan 1955 (Trail Making Test — referenced in docstring)

@relevance.de  Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik
@relevance.en  Enables neurological analysis, essential for nervous system diagnostics
@limits.de   Experimentelle Methode: Selbst administrierte Tests ohne standardisierte Testbedingungen. Keine
             Normwerte aus Bevölkerungsstudien. Lerneffekte und Tagesverfassung nicht
             kontrolliert. Explorativ, keine diagnostischen Schlussfolgerungen.
@limits.en   Experimental method: Self-administered tests without standardised conditions. No population norms.
             Practice effects and daily condition not controlled. Exploratory,
             no diagnostic conclusions.
@reads       cognitive_tests, measurements (HRV via modules/metric_loader), symptoms
@writes      analyses/neurology/*.{md,png} (kein DB-Write)

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_cognitive.py
    python analyse_cognitive.py --help
    python analyse_cognitive.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db, DB_OPERATIONAL_ERRORS
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.metric_loader import load_metric_daily, source_summary, weakest_confidence
_cfg = _Cfg()

OUT_DIR = _cfg.analyses_dir / "neurology"

from modules.prompts.analysis_neurology import (
    SYSTEM_PROMPT_ANALYSE_COGNITIVE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_COGNITIVE_EN as SYSTEM_PROMPT_EN,
)


def _pearson(xs, ys):
    n = len(xs)
    if n < 5:
        return None, n
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx  = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy  = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0, n
    return round(num / (dx * dy), 3), n


def _load_cognitive(conn, d_from, d_to, test_filter=None):
    query = """
        SELECT date, test_name, score, reaction_ms, errors, percentile, session_type
        FROM cognitive_tests
        WHERE date >= ? AND date <= ?
    """
    params = [d_from, d_to]
    if test_filter:
        query += " AND test_name = ?"
        params.append(test_filter)
    query += " ORDER BY date, test_name"
    try:
        return conn.execute(query, params).fetchall()
    except DB_OPERATIONAL_ERRORS:
        return []


def _load_hrv(conn, d_from, d_to, person=None):
    """Naechtliche HRV geraeteunabhaengig laden (modules/metric_loader).

    Frueher ausschliesslich aus polar_nightly_hrv gelesen — auf Installationen
    ohne Polar-Geraet blieb diese Tabelle leer, obwohl measurements HRV-Werte
    anderer Hersteller enthaelt. Rueckgabeform bleibt {date: float}, wie von
    den nachgelagerten Stellen (Paarbildung, Korrelation) erwartet; Quelle und
    Konfidenz werden separat zurueckgegeben, da ein reiner float sie nicht
    tragen kann.
    """
    try:
        days = load_metric_daily(conn, ("hrv_rmssd", "rmssd_ms"), d_from, d_to,
                                  person=person, agg="avg")
    except DB_OPERATIONAL_ERRORS:
        return {}, {}, "lead"
    hrv = {date: day.value for date, day in days.items()}
    return hrv, source_summary(days), weakest_confidence(days)


def _load_fatigue(conn, d_from, d_to):
    try:
        rows = conn.execute("""
            SELECT date, AVG(value_num) as avg_fatigue
            FROM symptoms
            WHERE symptom IN ('Erschöpfung/Fatigue', 'Fatigue', 'PEM', 'erschoepfung_fatigue', 'fatigue')
              AND date >= ? AND date <= ?
              AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)).fetchall()
        return {r[0]: r[1] for r in rows}
    except DB_OPERATIONAL_ERRORS:
        return {}


def _compute_primary_metric(rows):
    """Returns dict: date → primary score (reaction_ms inverted or score)."""
    result = {}
    for date, test_name, score, react_ms, errors, pctile, session_type in rows:
        if test_name == "reaction_time" and react_ms:
            result[date] = react_ms          # niedriger = besser
        elif score is not None:
            result[date] = score             # höher = besser
        elif react_ms is not None:
            result[date] = react_ms
    return result


def _moving_avg(series: dict, window=7):
    dates = sorted(series.keys())
    result = {}
    for i, d in enumerate(dates):
        vals = [series[dates[j]] for j in range(max(0, i - window + 1), i + 1)
                if series[dates[j]] is not None]
        result[d] = round(sum(vals) / len(vals), 2) if vals else None
    return result


def _bericht(rows, hrv, fatigue, infection_date, d_from, d_to,
             hrv_sources=None, hrv_confidence=None):
    if not rows:
        return t("Keine kognitiven Testdaten vorhanden.\nDaten importieren mit: python3 importers/import_cognitive_tests.py",
                 "No cognitive test data available.\nImport data with: python3 importers/import_cognitive_tests.py")

    tests_by_name = defaultdict(list)
    for row in rows:
        tests_by_name[row[1]].append(row)

    lines = [
        t(f"## Kognitive Funktion — {d_from} bis {d_to}",
          f"## Cognitive function — {d_from} to {d_to}"),
        t(f"Zeitraum: {d_from} bis {d_to}  |  Tests: {len(rows)}  |  Typen: {len(tests_by_name)}",
          f"Period: {d_from} to {d_to}  |  tests: {len(rows)}  |  types: {len(tests_by_name)}"),
        "",
    ]

    for test_name, test_rows in sorted(tests_by_name.items()):
        lines.append(t(f"### {test_name}", f"### {test_name}"))
        n = len(test_rows)
        scores  = [r[2] for r in test_rows if r[2] is not None]
        reacts  = [r[3] for r in test_rows if r[3] is not None]
        pctiles = [r[5] for r in test_rows if r[5] is not None]

        if reacts:
            avg_r = sum(reacts) / len(reacts)
            min_r = min(reacts)
            max_r = max(reacts)
            trend = reacts[-1] - reacts[0] if len(reacts) > 1 else 0
            lines.append(t(
                f"  Reaktionszeit: Ø {avg_r:.0f} ms  (Min {min_r:.0f} / Max {max_r:.0f} ms)  "
                f"Trend: {'+' if trend > 0 else ''}{trend:.0f} ms",
                f"  Reaction time: avg {avg_r:.0f} ms  (min {min_r:.0f} / max {max_r:.0f} ms)  "
                f"trend: {'+' if trend > 0 else ''}{trend:.0f} ms",
            ))
        if scores:
            avg_s = sum(scores) / len(scores)
            trend_s = scores[-1] - scores[0] if len(scores) > 1 else 0
            lines.append(t(
                f"  Score: Ø {avg_s:.1f}  Trend: {'+' if trend_s > 0 else ''}{trend_s:.1f}",
                f"  Score: avg {avg_s:.1f}  trend: {'+' if trend_s > 0 else ''}{trend_s:.1f}",
            ))
        if pctiles:
            avg_p = sum(pctiles) / len(pctiles)
            lines.append(t(f"  Percentile: Ø {avg_p:.0f}%", f"  Percentile: avg {avg_p:.0f}%"))

        # Tageszeit-Effekt
        by_time = defaultdict(list)
        for r in test_rows:
            if r[6]:
                val = r[3] or r[2]
                if val is not None:
                    by_time[r[6]].append(val)
        if len(by_time) > 1:
            time_summary = "  " + t("Tageszeit: ", "Time of day: ")
            time_summary += "  ".join(
                f"{k} Ø{sum(v)/len(v):.1f}" for k, v in sorted(by_time.items())
            )
            lines.append(time_summary)

        # Prä/Post-Infektion
        if infection_date:
            pre  = [r[3] or r[2] for r in test_rows if r[0] < infection_date and (r[3] or r[2])]
            post = [r[3] or r[2] for r in test_rows if r[0] >= infection_date and (r[3] or r[2])]
            if pre and post:
                avg_pre  = sum(pre)  / len(pre)
                avg_post = sum(post) / len(post)
                diff_pct = (avg_post - avg_pre) / avg_pre * 100 if avg_pre else 0
                lines.append(t(
                    f"  Prä-Inf.: Ø {avg_pre:.1f}  Post-Inf.: Ø {avg_post:.1f}  "
                    f"Δ {diff_pct:+.1f}%",
                    f"  Pre-inf.: avg {avg_pre:.1f}  Post-inf.: avg {avg_post:.1f}  "
                    f"Δ {diff_pct:+.1f}%",
                ))
        lines.append("")

    # HRV-Korrelation
    if hrv:
        src_str = ", ".join(f"{src} ({n})" for src, n in (hrv_sources or {}).items())
        lines.append(t(
            f"  HRV-Tage: {len(hrv)}  |  Quelle(n): {src_str or 'unbekannt'}  |  "
            f"Konfidenz: {hrv_confidence or 'lead'}",
            f"  HRV days: {len(hrv)}  |  source(s): {src_str or 'unknown'}  |  "
            f"confidence: {hrv_confidence or 'lead'}",
        ))
        primary = _compute_primary_metric(rows)
        pairs   = [(primary[d], hrv[d]) for d in primary if d in hrv]
        if len(pairs) >= 5:
            xs, ys = zip(*pairs)
            r, n   = _pearson(list(xs), list(ys))
            if r is not None:
                interp = (
                    t("starker Zusammenhang", "strong association") if abs(r) > 0.5 else
                    t("mäßiger Zusammenhang", "moderate association") if abs(r) > 0.3 else
                    t("schwacher Zusammenhang", "weak association")
                )
                lines.append(t(
                    f"### HRV-Korrelation\n  r = {r:.2f}  (n={n}, {interp})",
                    f"### HRV correlation\n  r = {r:.2f}  (n={n}, {interp})",
                ))
                lines.append("")

    # Fatigue-Korrelation
    if fatigue:
        primary = _compute_primary_metric(rows)
        pairs   = [(primary[d], fatigue[d]) for d in primary if d in fatigue]
        if len(pairs) >= 5:
            xs, ys = zip(*pairs)
            r, n   = _pearson(list(xs), list(ys))
            if r is not None:
                lines.append(t(
                    f"### Fatigue-Korrelation\n  r = {r:.2f}  (n={n})",
                    f"### Fatigue correlation\n  r = {r:.2f}  (n={n})",
                ))
                lines.append("")

    return "\n".join(lines)


def _plot(rows, hrv, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    if not rows:
        return

    tests_by_name = defaultdict(list)
    for row in rows:
        tests_by_name[row[1]].append(row)

    n_plots = len(tests_by_name) + (1 if hrv else 0)
    fig, axes = plt.subplots(n_plots, 1, figsize=(14, 4 * n_plots), facecolor="#1e1e2e")
    if n_plots == 1:
        axes = [axes]

    colors = ["#a29bfe", "#74b9ff", "#00cec9", "#fd79a8", "#fdcb6e", "#55efc4"]

    for idx, (test_name, test_rows) in enumerate(sorted(tests_by_name.items())):
        ax = axes[idx]
        ax.set_facecolor("#2d2d44")
        dates  = [datetime.strptime(r[0], "%Y-%m-%d") for r in test_rows]
        react  = [r[3] for r in test_rows]
        score  = [r[2] for r in test_rows]
        vals   = react if any(v is not None for v in react) else score
        color  = colors[idx % len(colors)]
        ax.scatter(dates, vals, color=color, s=40, zorder=5, alpha=0.8)
        # 7-day MA
        date_val = {r[0]: (r[3] or r[2]) for r in test_rows if (r[3] or r[2]) is not None}
        ma = _moving_avg(date_val, 7)
        ma_dates = [datetime.strptime(d, "%Y-%m-%d") for d in sorted(ma)]
        ma_vals  = [ma[d] for d in sorted(ma)]
        ax.plot(ma_dates, ma_vals, color=color, lw=1.5, alpha=0.9)
        unit = "ms" if test_name == "reaction_time" else "Punkte"
        ax.set_ylabel(t(f"{test_name} ({unit})", f"{test_name} ({unit})"),
                      color="white", fontsize=9)
        ax.tick_params(colors="white", labelsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
        ax.grid(True, alpha=0.15)
        for spine in ax.spines.values():
            spine.set_visible(False)

    if hrv and len(axes) > len(tests_by_name):
        ax = axes[-1]
        ax.set_facecolor("#2d2d44")
        hrv_dates = [datetime.strptime(d, "%Y-%m-%d") for d in sorted(hrv)]
        hrv_vals  = [hrv[d] for d in sorted(hrv)]
        ax.plot(hrv_dates, hrv_vals, color="#fdcb6e", lw=1.2, label="HRV RMSSD")
        ax.set_ylabel("RMSSD (ms)", color="white", fontsize=9)
        ax.tick_params(colors="white", labelsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
        ax.grid(True, alpha=0.15)
        for spine in ax.spines.values():
            spine.set_visible(False)

    fig.patch.set_facecolor("#1e1e2e")
    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"cognitive_{ts}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(t(f"  Plot: {out}", f"  Plot: {out}"))


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=2000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"cognitive_{ts}.md"
    content = report
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"  Bericht: {out}", f"  Report: {out}"))


def main():
    parser = argparse.ArgumentParser(
        description=t("Kognitive Funktion analysieren", "Analyse cognitive function"))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--test",   type=str, default=None,
                        help=t("Nur diesen Test", "Only this test"))
    parser.add_argument("--from",   dest="date_from", type=str, default=None)
    parser.add_argument("--to",     dest="date_to",   type=str, default=None)
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    cfg          = _cfg
    infection    = cfg.infection_date
    d_from       = args.date_from or cfg.birthdate or "2020-01-01"
    d_to         = args.date_to   or datetime.now().strftime("%Y-%m-%d")

    conn = open_db()
    rows    = _load_cognitive(conn, d_from, d_to, args.test)
    hrv, hrv_sources, hrv_confidence = _load_hrv(conn, d_from, d_to, args.person)
    fatigue = _load_fatigue(conn, d_from, d_to)
    conn.close()

    if not rows:
        print(t("Keine kognitiven Testdaten — zuerst import_cognitive_tests.py ausführen.",
                "No cognitive test data — run import_cognitive_tests.py first."))
        return

    report = _bericht(rows, hrv, fatigue, infection, d_from, d_to, hrv_sources, hrv_confidence)
    print(report)

    if args.plot:
        _plot(rows, hrv, d_from, d_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
