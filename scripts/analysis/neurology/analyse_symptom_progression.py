#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Symptomverlauf & Correlationen

Analysiert das Symptom diary über Zeit: Trends pro Kategorie,
Gut-/Schlechttag-Profile and Correlation with objektiven Messdaten.

Methode:
  - 30/90-days gleitende Averagee pro Symptom-Kategorie
  - Gut-/Schlechttag-Profiles (oberstes vs. unterstes Quartil nach Energie-Budget)
  - Spearman-Rangkorrelation: Symptoms × HRV / Sleep / Stress

@tier        heuristic
@purpose.de  Analysiert Symptomverlauf über Zeit: Trends je Kategorie, Gut-/Schlechttag-Profile und Korrelation mit objektiven Biomarkern (HRV, Schlaf, Stress).
@purpose.en  Analyses symptom progression over time: trends per category, good/bad-day profiles and correlation with objective biomarkers (HRV, sleep, stress).
@method.de   30/90-Tage gleitende Mittelwerte je Symptomkategorie; Gut-/Schlechttag-Trennung nach Quartil des Energie-Budgets; Spearman-Rangkorrelation mit HRV/Schlaf/Stress.
@method.en   30/90-day moving averages per symptom category; good/bad-day split by energy budget quartile; Spearman rank correlation with HRV/sleep/stress.
@limits.de   Heuristische Methode: Subjektive Symptomskalierung; keine klinisch validierten Symptomscores; Vollständigkeit des Tagebuchs bestimmt die Aussagekraft. Keine Adjustierung für saisonale Einflüsse.
@limits.en   Heuristic method: Subjective symptom scaling; no clinically validated symptom scores; diary completeness determines interpretability. No adjustment for seasonal influences.
@refs        Fukuda K, Straus SE, Hickie I, Sharpe MC, Dobbins JG, Komaroff A (1994). The Chronic Fatigue Syndrome: A Comprehensive Approach to Its Definition and Study. Annals of Internal Medicine, 121(12):953-959. doi:10.7326/0003-4819-121-12-199412150-00009
             Carruthers BM, van de Sande MI, De Meirleir KL et al. (2011). Myalgic encephalomyelitis: International Consensus Criteria. Journal of Internal Medicine, 270(4):327-338. doi:10.1111/j.1365-2796.2011.02428.x

@relevance.de  Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik
@relevance.en  Enables neurological analysis, essential for nervous system diagnostics
@scoring
    Trend analysis: 30/90-day moving averages per symptom category
    Good/bad day profiles: top vs bottom quartile by energy budget
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
@reads       symptoms, daily_stress
@writes      analyses/neurology/*.{md,png}

Usage:
  python analyse_symptom_progression.py --plot
  python analyse_symptom_progression.py --from YYYY-MM-DD --plot
  python analyse_symptom_progression.py --plot --no-llm

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_symptom_progression.py
    python analyse_symptom_progression.py --help
    python analyse_symptom_progression.py --from 2024-01-01 --to 2024-12-31
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
OUT_DIR = _cfg.analyses_dir / "neurology"

from modules.prompts.analysis_neurology import (
    SYSTEM_PROMPT_ANALYSE_SYMPTOM_PROGRESSION_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_SYMPTOM_PROGRESSION_EN as SYSTEM_PROMPT_EN,
)

RESSOURCEN_SYMPTOME = {"Energie-Budget Morgens", "Energie-Budget Abends", "Sicherheitsgefühl"}


def load_symptoms(conn, d_from, d_to):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "symptoms" in tables:
        rows = conn.execute("""
            SELECT date, symptom, value_num, category
            FROM symptoms
            WHERE date >= ? AND date <= ? AND value_num IS NOT NULL
            ORDER BY date
        """, (d_from, d_to)).fetchall()
    elif "symptoms" in tables:
        rows = conn.execute("""
            SELECT date, symptom, value_num, category
            FROM symptoms
            WHERE date >= ? AND date <= ? AND value_num IS NOT NULL
            ORDER BY date
        """, (d_from, d_to)).fetchall()
    else:
        rows = []
    return rows


def load_objective(conn, d_from, d_to):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    obj = defaultdict(dict)
    if "daily_stress" in tables:
        for d, rmssd, rhr, stress, sleep_h in conn.execute("""
            SELECT date, rmssd_ms, resting_hr, stress_score, sleep_hours
            FROM daily_stress WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            obj[d].update({"hrv": rmssd, "rhr": rhr, "stress": stress, "sleep_h": sleep_h})
    return dict(obj)


def tagesaggregat(rows):
    """Pro day: Mean pro Kategorie + Energie-Budget."""
    by_day = defaultdict(lambda: defaultdict(list))
    energie = {}
    for date, symptom, wert, kat in rows:
        if kat and kat != "Behandlung":
            is_ressource = (kat == "Ressourcen")
            if is_ressource:
                if wert is not None:
                    by_day[date]["Ressourcen"].append(wert)
                if symptom in ("Energie-Budget Morgens", "Energie-Budget Abends"):
                    energie.setdefault(date, []).append(wert)
            else:
                by_day[date][kat].append(wert)

    result = {}
    for d, kats in by_day.items():
        result[d] = {k: round(sum(v) / len(v), 2) for k, v in kats.items() if v}
        if d in energie:
            result[d]["_energie"] = round(sum(energie[d]) / len(energie[d]), 2)
    return result


def gleitender_mittel(series, window):
    """Gleitender Average über sortierte (date, value)-Liste."""
    result = []
    for i in range(len(series)):
        start = max(0, i - window + 1)
        vals = [v for _, v in series[start:i + 1] if v is not None]
        result.append((series[i][0], round(sum(vals) / len(vals), 2) if vals else None))
    return result


def spearman_r(xs, ys):
    """Spearman-Rangkorrelation without externe Bibliotheken."""
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None, None
    n = len(pairs)

    def ranks(vals):
        sorted_v = sorted(range(n), key=lambda i: vals[i])
        r = [0] * n
        for rank, idx in enumerate(sorted_v, 1):
            r[idx] = rank
        return r

    xv, yv = zip(*pairs)
    rx, ry = ranks(list(xv)), ranks(list(yv))
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    rs = 1 - 6 * d2 / (n * (n ** 2 - 1))
    # t-Approximation for p-value
    import math
    t = rs * math.sqrt((n - 2) / max(1 - rs ** 2, 1e-10))
    p = 2 * (1 - min(0.9999, 0.5 + math.erf(abs(t) / 2 ** 0.5) / 2))
    return round(rs, 3), round(p, 4)


def build_report(tage, obj, d_from, d_to):
    n_tage = len(tage)
    alle_kats = set()
    for v in tage.values():
        alle_kats.update(k for k in v if not k.startswith("_"))

    energie_series = sorted((d, v["_energie"]) for d, v in tage.items() if "_energie" in v)

    # Gut- vs. Schlechttag-Profiles
    gut_tage   = set()
    schlecht_tage = set()
    if energie_series:
        vals = sorted(energie_series, key=lambda x: -x[1])
        q = max(1, len(vals) // 4)
        gut_tage     = {d for d, _ in vals[:q]}
        schlecht_tage = {d for d, _ in vals[-q:]}

    lines = [
        f"## Symptomverlauf — {d_from} bis {d_to}\n",
        f"Tage mit Einträgen: **{n_tage}**  |  Symptom-Kategorien: {', '.join(sorted(alle_kats))}\n",
    ]

    # Kategorie-Overview
    lines.append("### Ø Symptombelastung pro Kategorie (0=keine, 10=max)\n")
    kat_avgs = {}
    for kat in sorted(alle_kats):
        vals = [v[kat] for v in tage.values() if kat in v]
        if vals:
            kat_avgs[kat] = round(sum(vals) / len(vals), 2)
    for kat, avg in sorted(kat_avgs.items(), key=lambda x: -x[1]):
        bar = "█" * int(avg) + "░" * (10 - int(avg))
        lines.append(f"  {kat:<28} {bar} {avg:.1f}")

    # Gut vs. Schlecht
    if gut_tage and schlecht_tage:
        lines.append("\n### Gut- vs. Schlechttag-Profil (nach Energie-Budget)\n")
        lines.append(f"  {'Kategorie':<28} {'Gute Tage':>10} {'Schlechte Tage':>15}")
        lines.append("  " + "-" * 56)
        for kat in sorted(alle_kats):
            g_vals = [tage[d][kat] for d in gut_tage if kat in tage.get(d, {})]
            s_vals = [tage[d][kat] for d in schlecht_tage if kat in tage.get(d, {})]
            if g_vals and s_vals:
                g_avg = round(sum(g_vals) / len(g_vals), 1)
                s_avg = round(sum(s_vals) / len(s_vals), 1)
                lines.append(f"  {kat:<28} {g_avg:>10.1f} {s_avg:>15.1f}")

    # Correlation with objektiven Daten
    if obj:
        lines.append("\n### Korrelation Symptome × Objektive Daten (Spearman r)\n")
        lines.append(f"  {'Symptom-Kat.':<22} {'× HRV':>8} {'× Stress':>9} {'× Schlaf':>9}")
        lines.append("  " + "-" * 52)
        for kat in sorted(alle_kats):
            sym_vals = []
            hrv_vals, stress_vals, sleep_vals = [], [], []
            for d, v in tage.items():
                if kat in v and d in obj:
                    sym_vals.append(v[kat])
                    hrv_vals.append(obj[d].get("hrv"))
                    stress_vals.append(obj[d].get("stress"))
                    sleep_vals.append(obj[d].get("sleep_h"))
            r_hrv,    _ = spearman_r(sym_vals, hrv_vals)
            r_stress, _ = spearman_r(sym_vals, stress_vals)
            r_sleep,  _ = spearman_r(sym_vals, sleep_vals)
            if any(r is not None for r in [r_hrv, r_stress, r_sleep]):
                lines.append(
                    f"  {kat:<22} "
                    f"{str(r_hrv) if r_hrv else 'n.a.':>8} "
                    f"{str(r_stress) if r_stress else 'n.a.':>9} "
                    f"{str(r_sleep) if r_sleep else 'n.a.':>9}")

    return "\n".join(lines)


def _plot(tage, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    COLORS = {"Erschöpfung/Neurologie": "#ff6b6b", "Schmerz": "#f7b731",
              "Ressourcen": "#2ecc71", "Psyche": "#a29bfe",
              "Sensorisch/Neurologie": "#fd79a8", "Bauchraum/GI": "#fdcb6e"}

    alle_kats = set()
    for v in tage.values():
        alle_kats.update(k for k in v if not k.startswith("_"))

    fig, ax = plt.subplots(figsize=(14, 7), facecolor="#1e1e2e")
    ax.set_facecolor("#2a2a3e")
    ax.tick_params(colors="#aaa", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")

    for kat in sorted(alle_kats):
        series = sorted((d, v[kat]) for d, v in tage.items() if kat in v)
        if len(series) < 10:
            continue
        ma = gleitender_mittel(series, 30)
        dts = [datetime.fromisoformat(d) for d, _ in ma]
        vals = [v for _, v in ma]
        color = COLORS.get(kat, "#636e72")
        ax.plot(dts, vals, lw=1.8, color=color, label=kat, alpha=0.85)

    ax.set_title(f"Symptomverlauf {d_from}–{d_to} (30-Tage gleitend)",
                 color="#E0E0E0", fontsize=12)
    ax.set_ylabel("Ø Belastung", color="#ccc")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white", loc="upper left")

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"symptom_progression_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(f"Plot: {p}")
    plt.close()


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=900)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"symptom_progression_{ts}.md"
    content = f"# Symptomverlauf\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("Symptomverlauf & Korrelationen", "Symptom trend & correlations"))
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
    rows  = load_symptoms(conn, args.date_from, args.date_to)
    obj   = load_objective(conn, args.date_from, args.date_to)
    conn.close()

    if not rows:
        print("Keine Symptomtagebuch-Daten. Zuerst: python3 importers/import_symptom_diary.py")
        return

    tage = tagesaggregat(rows)
    print(f"Symptomtage: {len(tage)} | Objektive Tage: {len(obj)}")

    report = build_report(tage, obj, args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(tage, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
