#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Luftqualität × Symptome & Migräne

Untersucht Zusammenhänge zwischen PM2.5, PM10, NO2, O3 und AQI einerseits
und Symptomkategorien sowie Migräne-Anfällen andererseits.

Methode:
  - Spearman-Rangkorrelation Luftqualität × Symptomkategorie
  - Lag-Analyse Migräne: AQ[Datum-Lag] vs. Migräne[Datum] für Lag 0..−3 Tage
  - Personen-Whitney U: Tage mit/ohne Migräne | hohe vs. niedrige AQ-Belastung

@tier        heuristic
@refs        World Health Organization (2006). Air quality guidelines for particulate matter, ozone, nitrogen dioxide and sulfur dioxide: global update 2005, summary of risk assessment. Geneva: WHO. https://iris.who.int/handle/10665/69477
             Brook RD, Rajagopalan S, Pope CA et al. (2010). Particulate Matter Air Pollution and Cardiovascular Disease. Circulation, 121(21):2331-2378. doi:10.1161/CIR.0b013e3181dbece1

@relevance.de  Ermöglicht die Korrelation von Luftqualitätsdaten mit individuellen Symptomen, essentiell für die Identifikation umweltbedingter Gesundheitsauslöser und die Entwicklung personalisierter Präventionsstrategien
@relevance.en  Enables correlation of air quality data with individual symptoms, essential for identifying environment-related health triggers and developing personalized prevention strategies
@purpose.de  Untersucht Zusammenhänge zwischen Luftqualitätsparametern (PM2.5, PM10,
             NO2, O3, AQI) und Symptomkategorien sowie Migräne-Anfällen mit Lag-Analyse.
@purpose.en  Investigates associations between air quality parameters (PM2.5, PM10,
             NO2, O3, AQI) and symptom categories as well as migraine attacks with lag analysis.
@method.de   Spearman-Rangkorrelation ohne Multiple-Testing-Korrektur; Personen-Whitney-U
             für Gruppenvergleiche; eigene p-Wert-Schwellen ohne vorab publizierte Validierung.
@method.en   Spearman rank correlation without multiple-testing correction; Personen-Whitney U
             for group comparisons; custom p-value thresholds without prior published validation.
@limits.de   Heuristische Methode: Keine Confounder-Kontrolle, keine Multiple-Testing-Korrektur. n=1,
             Consumer-Sensordaten für Luftqualität. Korrelationen sind explorativ.
@limits.en   Heuristic method: No confounder control, no multiple-testing correction. n=1, consumer
             sensor data for air quality. Correlations are exploratory only.
@scoring
    Air quality levels: good 0-50 | moderate 51-100 | unhealthy 101-150 | very unhealthy 151-200 | hazardous >200 (AQI)
    Lag analysis: 0-3 days before migraine/symptom onset
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
@reads       air_quality, symptoms, sessions
@writes      analyses/environment/*.{md,png} (kein DB-Write)

Usage:
  python analyse_airquality_symptoms.py
  python analyse_airquality_symptoms.py --from 2023-01-01 --plot
  python analyse_airquality_symptoms.py --no-llm

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_airquality_symptoms.py
    python analyse_airquality_symptoms.py --help
    python analyse_airquality_symptoms.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import math
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db, open_medicine_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.symptom_sources import load_symptom_days

_cfg    = _Cfg()
DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "environment"

AQ_COLS = ["pm25_mean", "pm25_max", "pm10_mean", "aqi_eu_max", "no2_mean", "o3_mean"]
AQ_DE   = {
    "pm25_mean": "PM2.5 Ø", "pm25_max": "PM2.5 Max",
    "pm10_mean": "PM10 Ø",  "aqi_eu_max": "AQI EU Max",
    "no2_mean":  "NO₂ Ø",   "o3_mean": "O₃ Ø",
}

from modules.prompts.analysis_environment import (
    SYSTEM_PROMPT_ANALYSE_AIRQUALITY_SYMPTOMS_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_AIRQUALITY_SYMPTOMS_EN as SYSTEM_PROMPT_EN,
)


def _ranks(vals: list) -> list:
    n = len(vals)
    sorted_idx = sorted(range(n), key=lambda i: vals[i])
    r = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j < n - 1 and vals[sorted_idx[j + 1]] == vals[sorted_idx[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[sorted_idx[k]] = avg
        i = j + 1
    return r


def _spearman(xs: list, ys: list) -> tuple[float | None, float | None]:
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 6:
        return None, None
    xs2, ys2 = zip(*pairs)
    rx, ry = _ranks(list(xs2)), _ranks(list(ys2))
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den = (sum((rx[i] - mx) ** 2 for i in range(n)) *
           sum((ry[i] - my) ** 2 for i in range(n))) ** 0.5
    if den == 0:
        return 0.0, None
    rho = num / den
    t_stat = rho * ((n - 2) / max(1e-9, 1 - rho ** 2)) ** 0.5
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(t_stat) / 2 ** 0.5)))
    return round(rho, 3), round(p, 4)


def _mw_test(a: list, b: list) -> float | None:
    """Mann-Whitney-U-Test, Normalapproximation mit Mittelrang-Tiekorrektur
    und Stetigkeitskorrektur (Hollander & Wolfe 1999). Reuses _ranks() for
    mid-rank tie handling — the previous naive positional-rank version
    silently ignored ties and had no continuity correction, which could
    understate p-values (false "significant" result) when tied values are
    present."""
    a = [v for v in a if v is not None]
    b = [v for v in b if v is not None]
    if len(a) < 3 or len(b) < 3:
        return None
    na, nb = len(a), len(b)
    n = na + nb
    ranks = _ranks(a + b)
    rank_sum_a = sum(ranks[:na])
    u = rank_sum_a - na * (na + 1) / 2
    mu = na * nb / 2
    tie_counts = Counter(a + b)
    tie_correction = sum(t ** 3 - t for t in tie_counts.values())
    sigma_sq = (na * nb / 12) * ((n + 1) - tie_correction / (n * (n - 1)))
    if sigma_sq <= 0:
        return None
    sigma = sigma_sq ** 0.5
    z = max(abs(u - mu) - 0.5, 0) / sigma
    return round(2 * (1 - 0.5 * (1 + math.erf(z / 2 ** 0.5))), 4)


def load_air_quality(conn, d_from, d_to) -> dict[str, dict]:
    rows = conn.execute(
        "SELECT date, pm25_mean, pm25_max, pm10_mean, aqi_eu_max, no2_mean, o3_mean "
        "FROM air_quality WHERE date >= ? AND date <= ? ORDER BY date",
        (d_from, d_to)
    ).fetchall()
    return {r[0]: dict(zip(AQ_COLS, r[1:])) for r in rows}


def load_migraine(conn, d_from, d_to) -> set[str]:
    rows = conn.execute(
        "SELECT date FROM sessions WHERE type='migraine' AND date >= ? AND date <= ?",
        (d_from, d_to)
    ).fetchall()
    return {r[0] for r in rows}


def correlate_symptoms(aq: dict, symptome: dict, lag: int = 0) -> dict:
    results = {}
    cats = {cat for d in symptome.values() for cat in d}
    for col in AQ_COLS:
        for cat in cats:
            xs, ys = [], []
            for d, aq_vals in aq.items():
                aq_val = aq_vals.get(col)
                sym_d  = str((datetime.fromisoformat(d) + timedelta(days=lag)).date())
                sym_val = symptome.get(sym_d, {}).get(cat)
                if aq_val is not None and sym_val is not None:
                    xs.append(aq_val)
                    ys.append(sym_val)
            if len(xs) < 6:
                continue
            rho, p = _spearman(xs, ys)
            if rho is None:
                continue
            median = sorted(xs)[len(xs) // 2]
            high_s = [ys[i] for i, v in enumerate(xs) if v >= median]
            low_s  = [ys[i] for i, v in enumerate(xs) if v < median]
            results[(col, cat)] = {
                "n": len(xs), "rho": rho, "p": p,
                "mw_p": _mw_test(high_s, low_s),
                "avg_high": round(sum(high_s)/len(high_s), 2) if high_s else None,
                "avg_low":  round(sum(low_s) /len(low_s),  2) if low_s  else None,
            }
    return results


def migraene_aq_analyse(aq: dict, migraene: set, max_lag: int = 3) -> dict:
    results = {}
    for lag in range(0, max_lag + 1):
        for col in AQ_COLS:
            mig_vals, kein_vals = [], []
            for d, aq_vals in aq.items():
                val = aq_vals.get(col)
                if val is None:
                    continue
                future_d = str((datetime.fromisoformat(d) + timedelta(days=lag)).date())
                if future_d in migraene:
                    mig_vals.append(val)
                else:
                    kein_vals.append(val)
            if not mig_vals or not kein_vals:
                continue
            mw_p = _mw_test(mig_vals, kein_vals)
            results[(lag, col)] = {
                "n_mig":     len(mig_vals),
                "n_kein":    len(kein_vals),
                "avg_mig":   round(sum(mig_vals) / len(mig_vals), 2),
                "avg_kein":  round(sum(kein_vals) / len(kein_vals), 2),
                "mw_p":      mw_p,
            }
    return results


def build_report(aq: dict, symptome: dict, migraene: set,
                     corr: dict[int, dict], mig_aq: dict) -> str:
    overlap = len(set(aq) & set(symptome))
    lines = [
        "## Luftqualität × Symptome & Migräne\n",
        f"AQ-Tage: **{len(aq)}** | Symptom-Tage: **{len(symptome)}** | "
        f"Überlappung: **{overlap}** | Migräne-Tage: **{len(migraene)}**\n",
    ]

    if overlap < 10:
        lines.append(
            "> ⚠️  Wenig überlappende Daten — Ergebnisse explorativ. "
            "Mehr Symptomtagebuch-Einträge nötig.\n"
        )

    # AQ-Statistik
    if aq:
        lines.append("### Luftqualität — Übersicht\n")
        lines.append(f"{'Metrik':<14} {'Mittel':>8} {'Max':>8} {'Min':>8}")
        lines.append("-" * 42)
        for col in AQ_COLS:
            vals = [v.get(col) for v in aq.values() if v.get(col) is not None]
            if vals:
                lines.append(f"  {AQ_DE[col]:<14} {sum(vals)/len(vals):>8.1f} "
                              f"{max(vals):>8.1f} {min(vals):>8.1f}")

    # Symptom-Korrelationen
    for lag, data in corr.items():
        if not data:
            continue
        lag_label = {0: "Lag 0 (gleicher Tag)", -1: "Lag −1 (Symptom 1 Tag nach AQ)",
                     -2: "Lag −2 (Symptom 2 Tage nach AQ)"}.get(lag, f"Lag {lag}")
        lines.append(f"\n### Symptom-Korrelation — {lag_label}\n")
        header = f"{'AQ-Metrik':<14} {'Symptom':<26} {'n':>4} {'ρ':>6} {'p':>7} {'p(MW)':>7}"
        lines.append(header)
        lines.append("-" * len(header))
        shown = sorted(data.items(), key=lambda x: x[1].get("p") or 1)[:12]
        for (col, cat), r in shown:
            p_str  = f"{r['p']:.3f}"   if r["p"]    else "n.a."
            mw_str = f"{r['mw_p']:.3f}" if r["mw_p"] else "n.a."
            sig    = " *" if (r["p"] or 1) < 0.05 else ("†" if (r["p"] or 1) < 0.1 else "")
            lines.append(f"  {AQ_DE[col]:<14} {cat:<26} {r['n']:>4} "
                         f"{r['rho']:>+6.3f} {p_str:>7} {mw_str:>7}{sig}")

    # Migräne × AQ
    if mig_aq and migraene:
        lines.append("\n### Migräne × Luftqualität (Lag-Analyse)\n")
        lines.append(f"{'Lag':>4} {'AQ-Metrik':<14} {'n Mig':>6} {'Ø Mig':>8} {'Ø Kein':>8} {'p(MW)':>7}")
        lines.append("-" * 52)
        shown = sorted(mig_aq.items(), key=lambda x: x[1].get("mw_p") or 1)[:15]
        for (lag, col), r in shown:
            mw_str = f"{r['mw_p']:.3f}" if r["mw_p"] else "n.a."
            sig    = " *" if (r["mw_p"] or 1) < 0.05 else ("†" if (r["mw_p"] or 1) < 0.1 else "")
            lines.append(f"  {lag:>4}d {AQ_DE[col]:<14} {r['n_mig']:>6} "
                         f"{r['avg_mig']:>8.1f} {r['avg_kein']:>8.1f} {mw_str:>7}{sig}")
    elif migraene:
        lines.append(f"\n(Migräne-Analyse: n={len(migraene)} Tage — zu wenig für aussagekräftige Statistik)\n")

    return "\n".join(lines)


def _plot(aq: dict, symptome: dict, migraene: set):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    dates = sorted(aq)
    if len(dates) < 7:
        print(t("Zu wenig Daten für Plot.", "Not enough data for plot."))
        return

    dts    = [datetime.fromisoformat(d) for d in dates]
    aqi    = [aq[d].get("aqi_eu_max") or 0 for d in dates]
    pm25   = [aq[d].get("pm25_mean")  or 0 for d in dates]
    sym_d  = sorted(set(dates) & set(symptome))
    sym_dts = [datetime.fromisoformat(d) for d in sym_d]
    schmerz = [symptome[d].get("Schmerz") for d in sym_d]
    ersch   = [symptome[d].get("Erschöpfung/Neurologie") for d in sym_d]
    mig_dts = [datetime.fromisoformat(d) for d in migraene if d in aq]

    fig, axes = plt.subplots(3, 1, figsize=(14, 9), facecolor="#1e1e2e", sharex=True)
    fig.suptitle("Luftqualität × Symptome & Migräne", color="#E0E0E0", fontsize=13)

    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    axes[0].fill_between(dts, aqi,  alpha=0.6, color="#ff6348", label="AQI EU Max")
    axes[0].fill_between(dts, pm25, alpha=0.5, color="#ffa502", label="PM2.5 Ø")
    axes[0].set_ylabel("AQI / PM2.5", color="#ccc", fontsize=8)
    axes[0].axhline(50, color="#ff4757", ls="--", lw=0.8, alpha=0.6, label="AQI 50 (mäßig)")
    axes[0].legend(fontsize=8, facecolor="#333", labelcolor="#ccc")

    if sym_dts:
        axes[1].plot(sym_dts, [v or 0 for v in schmerz], "o-",
                     color="#a29bfe", lw=1.5, label="Schmerz", ms=4)
        axes[1].plot(sym_dts, [v or 0 for v in ersch], "s-",
                     color="#74b9ff", lw=1.5, label="Erschöpfung", ms=4)
        axes[1].legend(fontsize=8, facecolor="#333", labelcolor="#ccc")
    for md in mig_dts:
        axes[1].axvline(md, color="#ff6b6b", alpha=0.5, lw=1.0)
    axes[1].set_ylabel("Symptom-Score", color="#ccc", fontsize=8)
    axes[1].set_title("Rote Linien = Migränetage", color="#aaa", fontsize=7, loc="right")

    # NO2 + O3
    no2 = [aq[d].get("no2_mean") or 0 for d in dates]
    o3  = [aq[d].get("o3_mean")  or 0 for d in dates]
    axes[2].plot(dts, no2, color="#55efc4", lw=1.0, label="NO₂ Ø (µg/m³)")
    axes[2].plot(dts, o3,  color="#fdcb6e", lw=1.0, label="O₃ Ø (µg/m³)")
    axes[2].set_ylabel("NO₂ / O₃", color="#ccc", fontsize=8)
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    axes[2].legend(fontsize=8, facecolor="#333", labelcolor="#ccc")

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"airquality_symptoms_{ts}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(t(f"Plot: {out}", f"Plot: {out}"))
    plt.close()


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report: str, llm_text: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"airquality_symptoms_{ts}.md"
    content = f"# Luftqualität × Symptome & Migräne\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


def main():
    parser = argparse.ArgumentParser(
        description=t("Luftqualität × Symptome & Migräne", "Air quality × symptoms & migraine")
    )
    parser.add_argument("--from",   dest="date_from",
                        default=_cfg.birthdate or "1900-01-01")
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.now().date()))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn     = open_db()
    mconn    = open_medicine_db()
    aq       = load_air_quality(conn, args.date_from, args.date_to)
    symptome = load_symptom_days(conn, args.date_from, args.date_to, args.person, medicine_conn=mconn)
    migraene = load_migraine(conn, args.date_from, args.date_to)
    conn.close()
    mconn.close()

    print(t(
        f"AQ-Tage: {len(aq)} | Symptom-Tage: {len(symptome)} | "
        f"Migräne-Tage: {len(migraene)}",
        f"AQ days: {len(aq)} | Symptom days: {len(symptome)} | "
        f"Migraine days: {len(migraene)}"
    ))

    corr    = {lag: correlate_symptoms(aq, symptome, lag) for lag in [0, -1, -2]}
    mig_aq  = migraene_aq_analyse(aq, migraene)

    report = build_report(aq, symptome, migraene, corr, mig_aq)
    print("\n" + report)

    if args.plot:
        _plot(aq, symptome, migraene)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
