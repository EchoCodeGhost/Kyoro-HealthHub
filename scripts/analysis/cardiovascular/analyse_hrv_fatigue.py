#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
HRV × Erschöpfung — Lag-Correlationsanalyse

Untersucht, ob Night-HRV (RMSSD) and subjektive Erschöpfung zusammenhängen
and ob es einen zeitlichen Vorlauf gibt (Lag ±7 days).

Datenquellen:
  - polar_nightly_hrv / garmin_daily: objektive HRV/RHR
  - symptoms WHERE symptom='Erschöpfung': subjektive Werte (0–10)

Note: Symptom diary wird with der neuen PWA befüllt — aktuell still
         wenige Datenpunkte. Analyse wird with wachsender Datenbasis valider.

@tier        heuristic
@refs        Shaffer F, Ginsberg JP (2017). An overview of heart rate variability metrics and norms. Frontiers in Public Health, 5:258. doi:10.3389/fpubh.2017.00258
             Davenport TE, Stevens SR, VanNess MJ, Snell CR, Little T (2010). Conceptual model for physical therapist management of chronic fatigue syndrome/myalgic encephalomyelitis. Physical Therapy, 90(4):602-614. doi:10.2522/ptj.20090047

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@purpose.de  Untersucht den zeitverzögerten Zusammenhang zwischen nächtlicher HRV (RMSSD) und subjektiver Erschöpfung mittels Lag-Korrelation (±7 Tage).
@purpose.en  Examines the time-lagged relationship between nocturnal HRV (RMSSD) and subjective fatigue using lag correlation (±7 days).
@method.de   Pearson-Korrelation (Pure-Python) für HRV(t) × Erschöpfung(t+lag) über alle überlappenden Tage; Lag-Scan von −7 bis +7.
@method.en   Pearson correlation (pure Python) for HRV(t) × fatigue(t+lag) over all overlapping days; lag scan from −7 to +7.
@limits.de   Heuristische Methode: Explorative Analyse ohne Signifikanzschwelle; Symptomtagebuch-Datenmenge aktuell sehr gering (kein konsistentes Logging); Kausalrichtung nicht bestimmbar; keine Adjustierung für Confounding.
@limits.en   Heuristic method: Exploratory analysis without significance threshold; symptom diary data currently very sparse (no consistent logging); causal direction not determinable; no adjustment for confounding.
@scoring
    Fatigue scale: 0-10 (subjective, from symptom diary)
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
    Lag direction: negative (HRV leads fatigue) | positive (fatigue leads HRV)
@reads       measurements, symptoms
@writes      analyses/cardiovascular/hrv_fatigue_*.{md,png}

Usage:
  python analyse_hrv_fatigue.py --plot
  python analyse_hrv_fatigue.py --symptom "Fatigue" --plot
  python analyse_hrv_fatigue.py --lag 5 --plot

@usage
    python analyse_hrv_fatigue.py
    python analyse_hrv_fatigue.py --help
    python analyse_hrv_fatigue.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_HRV_FATIGUE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_HRV_FATIGUE_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "cardiovascular"

def load_hrv(conn, d_from, d_to):
    # HRV aus measurements (hrv_rmssd; Polar-Stub ist leer ohne Polar-Gerät)
    rows = conn.execute("""
        SELECT date, AVG(value) FROM measurements
        WHERE metric = 'hrv_rmssd' AND value > 0
          AND date >= ? AND date <= ?
        GROUP BY date ORDER BY date
    """, (d_from, d_to)).fetchall()
    return {r[0]: r[1] for r in rows}


def load_rhr(conn, d_from, d_to):
    # resting_hr is in measurements (v2 — garmin_daily does not exist)
    rows = conn.execute("""
        SELECT date, AVG(value) AS resting_hr
        FROM measurements
        WHERE metric = 'resting_heart_rate'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    return {r[0]: r[1] for r in rows}


def load_symptoms(conn, d_from, d_to, symptom_name):
    """Loads Erschöpfungswerte aus symptoms."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "symptoms" in tables:
        rows = conn.execute("""
            SELECT date, value_num FROM symptoms
            WHERE date >= ? AND date <= ?
              AND symptom = ?
              AND value_num IS NOT NULL
            ORDER BY date
        """, (d_from, d_to, symptom_name)).fetchall()
    elif "symptoms" in tables:
        rows = conn.execute("""
            SELECT date, value_num FROM symptoms
            WHERE date >= ? AND date <= ?
              AND symptom = ?
              AND value_num IS NOT NULL
            ORDER BY date
        """, (d_from, d_to, symptom_name)).fetchall()
    else:
        rows = []
    return {r[0]: r[1] for r in rows}


def all_symptom_namen(conn, d_from, d_to):
    """Listet availablee Symptoms im Time range auf."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "symptoms" in tables:
        rows = conn.execute("""
            SELECT DISTINCT symptom, COUNT(*) as n
            FROM symptoms
            WHERE date >= ? AND date <= ? AND value_num IS NOT NULL
            GROUP BY symptom ORDER BY n DESC LIMIT 20
        """, (d_from, d_to)).fetchall()
    elif "symptoms" in tables:
        rows = conn.execute("""
            SELECT DISTINCT symptom, COUNT(*) as n
            FROM symptoms
            WHERE date >= ? AND date <= ? AND value_num IS NOT NULL
            GROUP BY symptom ORDER BY n DESC LIMIT 20
        """, (d_from, d_to)).fetchall()
    else:
        rows = []
    return rows


def _pearson_lag(xs_dict, ys_dict, lag):
    """Pearson r for xs(t) × ys(t+lag) über gemeinsame Daten."""
    pairs = []
    for d, x in xs_dict.items():
        d_lag = (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=lag)).strftime("%Y-%m-%d")
        if d_lag in ys_dict and ys_dict[d_lag] is not None:
            pairs.append((x, ys_dict[d_lag]))

    n = len(pairs)
    if n < 5:
        return None, n

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    r = num / (dx * dy) if dx > 0 and dy > 0 else 0.0
    return round(r, 3), n


def build_report(hrv_dict, fatigue_dict, rhr_dict, symptom_name, max_lag):
    n_hrv     = len(hrv_dict)
    n_fatigue = len(fatigue_dict)
    overlap   = sum(1 for d in hrv_dict if d in fatigue_dict)

    lines = [
        "## HRV × Erschöpfung — Lag-Korrelation\n",
        f"Symptom: '{symptom_name}'",
        f"HRV-Daten:   {n_hrv} Tage",
        f"Fatigue:     {n_fatigue} Tage",
        f"Überlappung: {overlap} gemeinsame Tage\n",
    ]

    if overlap < 5:
        lines.append(f"⚠️  Nur {overlap} überlappende Tage — Korrelation nicht berechenbar.")
        lines.append("    Mehr Einträge im Symptomtagebuch (PWA) sammeln.")
        lines.append("    Min. 30 Datenpunkte für valide Korrelation empfohlen.\n")
    elif overlap < 30:
        lines.append(f"⚠️  Nur {overlap} überlappende Datenpunkte (min. 30 empfohlen).")
        lines.append("    Ergebnisse vorläufig — Analyse wird mit mehr Daten valider.\n")

    if overlap < 3:
        return "\n".join(lines)

    # Lag-Correlation
    lags = list(range(-max_lag, max_lag + 1))
    lag_results = []
    for lag in lags:
        r, n = _pearson_lag(hrv_dict, fatigue_dict, lag)
        lag_results.append((lag, r, n))

    lines.append("### Lag-Korrelation HRV → Erschöpfung")
    lines.append("  (negative r: niedrige HRV = hohe Erschöpfung; positiver Lag: HRV geht voraus)")
    lines.append("")
    best = max(lag_results, key=lambda x: abs(x[1]) if x[1] else 0)
    for lag, r, n in lag_results:
        if r is None:
            lines.append(f"  Lag {lag:+2d}d: zu wenig Daten (n={n})")
            continue
        bar = "█" * int(abs(r) * 10)
        marker = " ◀ stärkste" if (lag, r, n) == best else ""
        lines.append(f"  Lag {lag:+2d}d: r={r:+.3f} (n={n:2d})  {bar}{marker}")

    lines.append("")
    if best[1] is not None:
        lag_str = f"HRV {abs(best[0])} Tage vorher" if best[0] < 0 else \
                  f"Erschöpfung {best[0]} Tage vorher" if best[0] > 0 else "gleicher Tag"
        lines.append(f"Stärkste Korrelation: Lag {best[0]:+d}d, r={best[1]:+.3f} ({lag_str})")
        lines.append("")

    # RHR-Correlation (if available)
    rhr_overlap = sum(1 for d in rhr_dict if d in fatigue_dict)
    if rhr_overlap >= 5:
        r_rhr, n_rhr = _pearson_lag(rhr_dict, fatigue_dict, 0)
        if r_rhr is not None:
            lines.append("### Ruhepuls × Erschöpfung (gleicher Tag)")
            lines.append(f"  r={r_rhr:+.3f} (n={n_rhr}) "
                         f"({'positiv — höherer RHR bei mehr Erschöpfung' if r_rhr > 0.2 else 'schwach'})")
            lines.append("")

    return "\n".join(lines)


def _plot(hrv_dict, fatigue_dict, lag_results, symptom_name):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from datetime import datetime as DT

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), facecolor="#1A1A2E")
        fig.suptitle(f"HRV × Erschöpfung — '{symptom_name}'", color="#E0E0E0", fontsize=12)

        # Zeitreihe
        all_dates = sorted(set(list(hrv_dict) + list(fatigue_dict)))
        ax1.set_facecolor("#16213E")
        ax1_r = ax1.twinx()
        ax1_r.set_facecolor("#16213E")

        hrv_xs = [DT.strptime(d, "%Y-%m-%d") for d in all_dates if d in hrv_dict]
        hrv_ys = [hrv_dict[d] for d in all_dates if d in hrv_dict]
        ax1.plot(hrv_xs, hrv_ys, color="#4A90D9", linewidth=1.2, alpha=0.8,
                 label="RMSSD (ms)")
        ax1.set_ylabel("RMSSD (ms)", color="#4A90D9", fontsize=9)
        ax1.tick_params(axis="y", labelcolor="#4A90D9", labelsize=7)

        fat_xs = [DT.strptime(d, "%Y-%m-%d") for d in all_dates if d in fatigue_dict]
        fat_ys = [fatigue_dict[d] for d in all_dates if d in fatigue_dict]
        ax1_r.scatter(fat_xs, fat_ys, color="#E84855", s=30, alpha=0.8, zorder=5,
                      label="Erschöpfung (0–10)")
        ax1_r.set_ylabel("Erschöpfung (0–10)", color="#E84855", fontsize=9)
        ax1_r.tick_params(axis="y", labelcolor="#E84855", labelsize=7)
        ax1_r.set_ylim(0, 10.5)

        lines1, labs1 = ax1.get_legend_handles_labels()
        lines2, labs2 = ax1_r.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labs1 + labs2,
                   fontsize=7, labelcolor="#E0E0E0", facecolor="#16213E")
        ax1.set_title("HRV und Erschöpfung im Zeitverlauf", color="#E0E0E0")
        ax1.tick_params(axis="x", colors="#E0E0E0", labelsize=7)
        for s in ax1.spines.values():
            s.set_color("#8B8B8B")

        # Lag-Correlationsplot
        ax2.set_facecolor("#16213E")
        lags = [r[0] for r in lag_results if r[1] is not None]
        rs   = [r[1] for r in lag_results if r[1] is not None]
        bar_colors = ["#E84855" if abs(r) > 0.4 else "#F4A261" if abs(r) > 0.2 else "#4A90D9"
                      for r in rs]
        ax2.bar(lags, rs, color=bar_colors, alpha=0.8)
        ax2.axhline(0,    color="#E0E0E0", linewidth=0.5, alpha=0.4)
        ax2.axhline(0.4,  color="#E84855", linewidth=0.8, linestyle="--", alpha=0.5)
        ax2.axhline(-0.4, color="#E84855", linewidth=0.8, linestyle="--", alpha=0.5)
        ax2.axvline(0,    color="#8B8B8B", linewidth=0.8, linestyle=":", alpha=0.5)
        ax2.set_xlabel("Lag (Tage) — negativ: HRV geht Erschöpfung voraus",
                       color="#E0E0E0", fontsize=9)
        ax2.set_ylabel("Pearson r", color="#E0E0E0", fontsize=9)
        ax2.set_title("Lag-Korrelation HRV × Erschöpfung", color="#E0E0E0")
        ax2.tick_params(colors="#E0E0E0", labelsize=7)
        ax2.set_ylim(-1, 1)
        for s in ax2.spines.values():
            s.set_color("#8B8B8B")

        import matplotlib.dates as mdates
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        fig.autofmt_xdate(rotation=45)
        fig.tight_layout()

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUT_DIR / f"hrv_fatigue_{ts}.png"
        fig.savefig(str(path), dpi=130, bbox_inches="tight", facecolor="#1A1A2E")
        plt.close()
        print(t(f"Plot: {path}", f"Plot: {path}"))
    except Exception as e:
        print(t(f"Plot fehlgeschlagen: {e}", f"Plot failed: {e}"))


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=2000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, symptom_name, llm_text=""):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"hrv_fatigue_{ts}.md"
    content = f"# HRV × Erschöpfung ({symptom_name})\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


def main():
    parser = argparse.ArgumentParser(description=t("HRV × Erschöpfung Lag-Korrelation", "HRV × fatigue lag correlation"))
    parser.add_argument("--from",    dest="date_from",  default=(datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d"))
    parser.add_argument("--to",      dest="date_to",    default=str(datetime.today().date()))
    parser.add_argument("--all",     dest="all_data",   action="store_true",
                        help=t("Alle verfügbaren Daten (überschreibt --from/--to)",
                               "All available data (overrides --from/--to)"))
    parser.add_argument("--symptom", default="Erschöpfung",
                        help="Symptomname im Symptomtagebuch (Default: Erschöpfung)")
    parser.add_argument("--lag",     type=int, default=7,
                        help="Maximaler Lag in Tagen (Default: 7)")
    parser.add_argument("--list-symptoms", action="store_true",
                        help="Verfügbare Symptome im Zeitraum anzeigen")
    parser.add_argument("--plot",    action="store_true")
    parser.add_argument("--no-llm",  action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    if args.all_data:
        args.date_from = _cfg.birthdate or "1900-01-01"
        args.date_to   = datetime.today().strftime("%Y-%m-%d")

    conn = open_db()

    if args.list_symptoms:
        symptome = all_symptom_namen(conn, args.date_from, args.date_to)
        print(t("Verfügbare Symptome:", "Available symptoms:"))
        for name, n in symptome:
            print(t(f"  {name}: {n} Einträge", f"  {name}: {n} entries"))
        conn.close()
        return

    hrv_dict     = load_hrv(conn, args.date_from, args.date_to)
    rhr_dict     = load_rhr(conn, args.date_from, args.date_to)
    fatigue_dict = load_symptoms(conn, args.date_from, args.date_to, args.symptom)
    conn.close()

    print(t(f"HRV:      {len(hrv_dict)} Tage", f"HRV:      {len(hrv_dict)} days"))
    print(t(f"Symptom '{args.symptom}': {len(fatigue_dict)} Tage",
            f"Symptom '{args.symptom}': {len(fatigue_dict)} days"))
    print(t(f"Überlappung: {sum(1 for d in hrv_dict if d in fatigue_dict)} Tage",
            f"Overlap: {sum(1 for d in hrv_dict if d in fatigue_dict)} days"))

    lags = list(range(-args.lag, args.lag + 1))
    lag_results = [(lag, *_pearson_lag(hrv_dict, fatigue_dict, lag)) for lag in lags]

    report = build_report(hrv_dict, fatigue_dict, rhr_dict, args.symptom, args.lag)
    print("\n" + report)

    if args.plot:
        _plot(hrv_dict, fatigue_dict, lag_results, args.symptom)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, args.symptom, llm_text)


if __name__ == "__main__":
    main()
