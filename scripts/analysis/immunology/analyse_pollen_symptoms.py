#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Pollen × Symptom-Korrelation

Untersucht welche Pollentypen (Open-Meteo: Birke, Erle, Gräser, Beifuß, Ragweed, Olive;
DWD: zusätzlich Hasel, Esche, Roggen) mit Symptom-Kategorien zusammenhängen.

Methode:
  - Spearman-Rangkorrelation Pollentyp × Symptomkategorie
  - Lag-Analyse: Pollen[Datum] vs. Symptom[Datum+Lag] für Lag -2..+2 Tage
  - Person-Whitney U: hohe vs. niedrige Pollentage

@tier        heuristic
@refs        D'Amato G, Cecchi L, Bonini S, Nunes C, Annesi-Maesano I, Behrendt H, Liccardi G, Popov T, Van Cauwenberge P (2007). Allergenic pollen and pollen allergy in Europe. Allergy, 62(9):976-990. doi:10.1111/j.1398-9995.2007.01393.x
             Luyten A, Bürgler A, Glick S, Kwiatkowski M, Gehrig R, Beigi M, Hartmann K, Eeftens M (2024). Ambient pollen exposure and pollen allergy symptom severity in the EPOCHAL study. Allergy, 79(7), 1908-1920. doi:10.1111/all.16130

@relevance.de  Ermöglicht die Korrelation von Pollenflugdaten mit individuellen Symptomen, essentiell für die Abgrenzung polleninduzierter allergischer Reaktionen von anderen Auslösern und die personalisierte Allergie-Therapie
@relevance.en  Enables correlation of pollen flight data with individual symptoms, essential for distinguishing pollen-induced allergic reactions from other triggers and personalized allergy therapy
@purpose.de  Untersucht den Zusammenhang zwischen Pollenkonzentrationen und Symptomkategorien anhand von Spearman-Korrelation, Lag-Analyse und Person-Whitney U.
@purpose.en  Investigates the association between pollen concentrations and symptom categories using Spearman correlation, lag analysis and Person-Whitney U.
@method.de   Spearman-Rangkorrelation je Pollentyp × Symptomkategorie mit Lag -2..+2 Tage; Person-Whitney U zum Vergleich hoher vs. niedriger Pollentage. Keine Adjustierung für multiple Vergleiche.
@method.en   Spearman rank correlation per pollen type × symptom category with lag -2..+2 days; Person-Whitney U for high vs. low pollen days. No multiple-comparison adjustment.
@limits.de   Heuristische Methode: Rein observationelle Korrelation ohne Kausalitätsnachweis; keine klinisch validierten Allergie-Schwellenwerte; p<0.2-Berichtsschwelle deutlich liberaler als Standardniveau p<0.05 (erhöhte Falsch-Positiv-Rate); Sensitivität abhängig von Symptomdiary-Vollständigkeit; keine Multiple-Testing-Korrektur.
@limits.en   Heuristic method: Observational correlations only; no clinically validated allergy thresholds; p<0.2 reporting threshold is considerably more liberal than standard p<0.05 (increased false-positive rate); sensitivity depends on diary completeness; no multiple testing correction.
@scoring
    Pollen types: birch | alder | grasses | mugwort | ragweed | olive | hazel | ash | rye (Open-Meteo/DWD)
    Pollen load: low | moderate | high | very high (provider-specific)
    Lag analysis: -2 to +2 days (pollen to symptom correlation)
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
@reads       pollen, pollen_dwd, symptoms
@writes      analyses/immunology/*.{md,png}

Usage:
  python analyse_pollen_symptoms.py
  python analyse_pollen_symptoms.py --from 2023-01-01 --plot
  python analyse_pollen_symptoms.py --no-llm

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_pollen_symptoms.py
    python analyse_pollen_symptoms.py --help
    python analyse_pollen_symptoms.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import math
from collections import defaultdict, Counter
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
OUT_DIR = _cfg.analyses_dir / "immunology"

POLLEN_COLS = ["birch", "alder", "grass", "mugwort", "ragweed", "olive",
               "hazel", "ash", "rye"]
POLLEN_DE   = {"birch": "Birke", "alder": "Erle", "grass": "Gräser",
               "mugwort": "Beifuß", "ragweed": "Ragweed", "olive": "Olive",
               "hazel": "Hasel", "ash": "Esche", "rye": "Roggen"}

ALLERGY_CATS = ["Auge", "Erkältung", "Erschöpfung/Neurologie", "Schmerz", "Ressourcen"]

from modules.prompts.analysis_immunology import (
    SYSTEM_PROMPT_ANALYSE_POLLEN_SYMPTOMS_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_POLLEN_SYMPTOMS_EN as SYSTEM_PROMPT_EN,
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


def load_pollen(conn, d_from, d_to) -> dict[str, dict]:
    # Open-Meteo: historical grains/m³ (birch, alder, grass, mugwort, ragweed, olive)
    om = {r[0]: {"birch": r[1], "alder": r[2], "grass": r[3],
                 "mugwort": r[4], "ragweed": r[5], "olive": r[6]}
          for r in conn.execute(
              "SELECT date, birch, alder, grass, mugwort, ragweed, olive "
              "FROM pollen WHERE date >= ? AND date <= ? ORDER BY date",
              (d_from, d_to)).fetchall()}
    # DWD: index 0-6, adds hazel/ash/rye (recent window only)
    for r in conn.execute(
            "SELECT date, hazel, ash, rye FROM pollen_dwd "
            "WHERE date >= ? AND date <= ? ORDER BY date",
            (d_from, d_to)).fetchall():
        om.setdefault(r[0], {}).update({"hazel": r[1], "ash": r[2], "rye": r[3]})
    return om




def correlate(pollen: dict, symptome: dict, lag: int = 0) -> dict:
    results = {}
    all_dates = sorted(set(pollen) & {
        str((datetime.fromisoformat(d) + timedelta(days=lag)).date())
        for d in symptome
    })
    if not all_dates:
        return results

    for pollen_typ in POLLEN_COLS:
        for cat in ALLERGY_CATS:
            xs, ys = [], []
            for d in all_dates:
                p_val = pollen.get(d, {}).get(pollen_typ)
                sym_d = str((datetime.fromisoformat(d) - timedelta(days=lag)).date())
                s_val = symptome.get(sym_d, {}).get(cat)
                if p_val is not None and s_val is not None:
                    xs.append(p_val)
                    ys.append(s_val)
            if len(xs) < 6:
                continue
            rho, p = _spearman(xs, ys)
            if rho is None:
                continue
            # Hohe vs. niedrige Pollentage
            median = sorted(xs)[len(xs) // 2]
            high_sym = [ys[i] for i, v in enumerate(xs) if v >= median]
            low_sym  = [ys[i] for i, v in enumerate(xs) if v < median]
            mw_p = _mw_test(high_sym, low_sym)
            results[(pollen_typ, cat)] = {
                "n": len(xs), "rho": rho, "p": p, "mw_p": mw_p,
                "avg_high": round(sum(high_sym) / len(high_sym), 2) if high_sym else None,
                "avg_low":  round(sum(low_sym)  / len(low_sym),  2) if low_sym  else None,
            }
    return results


def build_report(pollen: dict, symptome: dict,
                     korr_lag: dict[int, dict]) -> str:
    n_pollen   = len(pollen)
    n_symptome = len(symptome)
    overlap    = len(set(pollen) & set(symptome))

    lines = [
        "## Pollen × Symptom-Korrelation\n",
        f"Pollen-Tage: **{n_pollen}** | Symptom-Tage: **{n_symptome}** | "
        f"Überlappung: **{overlap}** Tage\n",
    ]

    if overlap < 10:
        lines.append(
            "> ⚠️  Zu wenig überlappende Daten für zuverlässige Korrelationen. "
            "Ergebnisse sind explorativ — mehr Symptomtagebuch-Einträge nötig.\n"
        )

    for lag, data in korr_lag.items():
        if not data:
            continue
        lag_label = {0: "Lag 0 (gleicher Tag)", -1: "Lag −1 (Symptom 1 Tag nach Pollen)",
                     1: "Lag +1 (Symptom 1 Tag vor Pollen)", -2: "Lag −2 (Symptom 2 Tage nach Pollen)"}.get(lag, f"Lag {lag}")
        lines.append(f"\n### {lag_label}\n")
        header = f"{'Pollen':<10} {'Symptom':<26} {'n':>4} {'ρ':>6} {'p':>7} {'p(MW)':>7} {'Ø hoch':>8} {'Ø niedrig':>10}"
        lines.append(header)
        lines.append("-" * len(header))

        sig = [(k, v) for k, v in data.items() if v["p"] is not None and v["p"] < 0.2]
        shown = sorted(sig, key=lambda x: x[1]["p"] or 1) or sorted(data.items(), key=lambda x: abs(x[1]["rho"] or 0), reverse=True)[:10]

        for (ptype, cat), r in shown:
            p_str  = f"{r['p']:.3f}"  if r["p"]    else "n.a."
            mw_str = f"{r['mw_p']:.3f}" if r["mw_p"] else "n.a."
            sig_m  = " *" if (r["p"] or 1) < 0.05 else ("†" if (r["p"] or 1) < 0.1 else "")
            lines.append(
                f"  {POLLEN_DE[ptype]:<10} {cat:<26} {r['n']:>4} "
                f"{r['rho']:>+6.3f} {p_str:>7} {mw_str:>7} "
                f"{str(r['avg_high'] or ''):>8} {str(r['avg_low'] or ''):>10}{sig_m}"
            )

    # Saisonale Pollen-Übersicht
    if pollen:
        lines.append("\n### Saisonale Pollen-Übersicht (Monatsmittel)\n")
        by_month: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for d, vals in pollen.items():
            m = d[:7]
            for typ in POLLEN_COLS:
                if vals.get(typ) is not None:
                    by_month[m][typ].append(vals[typ])
        header2 = f"{'Monat':<9}" + "".join(f"{POLLEN_DE[t]:>9}" for t in POLLEN_COLS)
        lines.append(header2)
        lines.append("-" * len(header2))
        for m in sorted(by_month):
            row = f"  {m:<9}"
            for typ in POLLEN_COLS:
                vals = by_month[m][typ]
                avg = sum(vals) / len(vals) if vals else 0
                row += f"{avg:>9.1f}"
            lines.append(row)

    return "\n".join(lines)


def _plot(pollen: dict, symptome: dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    dates = sorted(set(pollen) & set(symptome))
    if len(dates) < 3:
        print(t("Zu wenig Daten für Plot.", "Not enough data for plot."))
        return

    dts = [datetime.fromisoformat(d) for d in dates]
    grass  = [pollen[d].get("grass")  or 0 for d in dates]
    birch  = [pollen[d].get("birch")  or 0 for d in dates]
    auge   = [symptome[d].get("Auge") for d in dates]
    erkalt = [symptome[d].get("Erkältung") for d in dates]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), facecolor="#1e1e2e", sharex=True)
    fig.suptitle("Pollen × Symptome", color="#E0E0E0", fontsize=13)

    for ax in (ax1, ax2):
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    ax1.fill_between(dts, grass, alpha=0.5, color="#7bed9f", label="Gräser")
    ax1.fill_between(dts, birch, alpha=0.4, color="#ffd32a", label="Birke")
    ax1.set_ylabel("Pollen (Max/Tag)", color="#ccc", fontsize=8)
    ax1.legend(fontsize=8, facecolor="#333", labelcolor="#ccc")

    ax2.plot(dts, [v or 0 for v in auge],   "o-", color="#ff6b81", lw=1.5, label="Auge",      ms=4)
    ax2.plot(dts, [v or 0 for v in erkalt], "s-", color="#74b9ff", lw=1.5, label="Erkältung", ms=4)
    ax2.set_ylabel("Symptom-Score (Ø)", color="#ccc", fontsize=8)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax2.legend(fontsize=8, facecolor="#333", labelcolor="#ccc")

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"pollen_symptoms_{ts}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Plot: {out}")
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
    out = OUT_DIR / f"pollen_symptoms_{ts}.md"
    content = f"# Pollen × Symptom-Korrelation\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(
        description=t("Pollen × Symptom-Korrelation", "Pollen × symptom correlation")
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

    conn = open_db()
    mconn = open_medicine_db()
    pollen   = load_pollen(conn, args.date_from, args.date_to)
    symptome = load_symptom_days(conn, args.date_from, args.date_to, args.person, medicine_conn=mconn)
    conn.close()
    mconn.close()

    print(t(
        f"Pollen-Tage: {len(pollen)} | Symptom-Tage: {len(symptome)} | "
        f"Überlappung: {len(set(pollen) & set(symptome))} Tage",
        f"Pollen days: {len(pollen)} | Symptom days: {len(symptome)} | "
        f"Overlap: {len(set(pollen) & set(symptome))} days"
    ))

    corr = {lag: correlate(pollen, symptome, lag) for lag in [0, -1, -2]}

    report = build_report(pollen, symptome, corr)
    print("\n" + report)

    if args.plot:
        _plot(pollen, symptome)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
