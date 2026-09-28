#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Histamin-Trigger-Analyse

Wertet das Histamin-Trigger-Tagebuch aus:
  - Tägliche Histaminlast (Kategorie-Score)
  - Top-Trigger-Lebensmittel nach Reaktionshäufigkeit
  - Reaktionszeitfenster (Sofort- vs. Spätreaktion)
  - Korrelation Histaminlast ↔ Symptome
  - Liberatoren vs. echtes Histamin
  - Wochentags-/Mahlzeitmuster

Histaminlast-Scoring (pro Portion):
  high=3  medium=2  low=0  liberator=2  blocker=1 (kumulativer Effekt)

Wissenschaftliche Grundlage:
  - Schnedl & Enko 2021: Histamine intolerance originates in the gut
  - Maintz & Novak 2007: Histamine and histamine intolerance (AJCN)
  - Afrin et al. 2021: Diagnosis of mast cell activation syndrome (global consensus-2)

@tier        heuristic
@purpose.de  Wertet ein Histamin-Trigger-Tagebuch auf Muster für Histaminintoleranz aus: Tageslasten, Top-Trigger, Reaktionszeitfenster und Symptomkorrelation.
@purpose.en  Analyses a histamine trigger diary for patterns of histamine intolerance: daily loads, top triggers, reaction time windows and symptom correlations.
@method.de   Kategorie-basiertes Histaminlast-Scoring (high=3, medium=2, low=0, liberator=2); Korrelation mit Symptomen aus der symptoms-Tabelle.
@method.en   Category-based histamine load scoring (high=3, medium=2, low=0, liberator=2); correlation with symptoms from the symptoms table.
@refs        Schnedl WJ, Enko D (2021). Histamine intolerance originates in the gut. Nutrients, 13(4), 1262. doi:10.3390/nu13041262
             Maintz L, Novak N (2007). Histamine and histamine intolerance. American Journal of Clinical Nutrition, 85(5), 1185-1196. doi:10.1093/ajcn/85.5.1185
             Afrin LB, Ackerley MB, Bluestein LS, et al. (2021). Diagnosis of mast cell activation syndrome: a global "consensus-2". Diagnosis, 8(2), 137-152. doi:10.1515/dx-2020-0005

@relevance.de  Unterstützt die Abklärung und das Management von Mastzellaktivierungssyndromen und Histamin-Intoleranz durch systematische Analyse von Symptommustern und Auslösern
@relevance.en  Supports the clinical work-up and management of mast cell activation syndromes and histamine intolerance through systematic analysis of symptom patterns and triggers
@scoring     Histaminlast-Score (kumuliert je Tag):
               high × 3  +  liberator × 2  +  medium × 2  +  blocker × 1  +  low × 0
             Reaktionsrate: Einträge mit reaction_h-Angabe / Einträge gesamt (je Lebensmittel)
             Basis: projektintern; Kategorie-Werte nicht aus einer Validierungsstudie abgeleitet.
             Orientierung: Maintz & Novak 2007 Klassifikation histaminreicher Lebensmittel
             (doi:10.1093/ajcn/85.5.1185). Kein Schwellenwert für klinische Bewertung.
@limits.de   Heuristische Methode: Histaminlast-Scoring ist ein vereinfachtes Kategorie-Modell ohne individuelle Portionsmengen-Kalibrierung; kein validiertes Instrument; fehlende Laborwerte (DAO, Histamin, Tryptase) können nicht ersetzt werden.
@limits.en   Heuristic method: Histamine load scoring is a simplified category model without individual portion-size calibration; not a validated instrument; missing lab values (DAO, histamine, tryptase) cannot be substituted.
@reads       food_triggers, symptoms
@writes      analyses/immunology/histamine_triggers_*.{md,png}

Usage:
  python3 analyse_histamine_triggers.py
  python3 analyse_histamine_triggers.py --plot
  python3 analyse_histamine_triggers.py --days 30 --plot --no-llm

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_histamine_triggers.py
    python analyse_histamine_triggers.py --help
    python analyse_histamine_triggers.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg
from modules.db import open_db, DB_OPERATIONAL_ERRORS
from modules.i18n import t, add_lang_arg, apply_lang_from_args
_cfg = _Cfg()

OUT_DIR = _cfg.analyses_dir / "immunology"

# Projektinternes Kategorie-Scoring — kein publiziertes Validierungsmodell.
# Orientierung: Maintz & Novak 2007 (doi:10.1093/ajcn/85.5.1185) Klassifikation histaminreicher Lebensmittel.
HIST_SCORE = {"high": 3, "medium": 2, "low": 0, "liberator": 2, "blocker": 1, "unknown": 1}

from modules.prompts.analysis_immunology import (
    SYSTEM_PROMPT_ANALYSE_HISTAMINE_TRIGGERS_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_HISTAMINE_TRIGGERS_EN as SYSTEM_PROMPT_EN,
)


def _load_triggers(conn, d_from, d_to, person):
    try:
        return conn.execute("""
            SELECT date, time_str, food_name, portion_g, histamine_cat,
                   reaction_h, symptoms, severity, meal_type
            FROM food_triggers
            WHERE date >= ? AND date <= ? AND person=?
            ORDER BY date, time_str
        """, (d_from, d_to, person)).fetchall()
    except DB_OPERATIONAL_ERRORS:
        return []


def _load_histamine_symptoms(conn, d_from, d_to):
    """Histamin-relevante Symptome: Flush, Urtikaria, Juckreiz, Kopfschmerzen, GI"""
    HISTAMINE_SYMPTOMS = (
        "Flush", "Urtikaria", "Juckreiz", "Kopfschmerzen", "Migräne",
        "Bauchschmerzen", "Durchfall", "Übelkeit", "Herzrasen", "Atemot",
        "Augenrötung", "Schwellung", "Angst",
        # blue-ME-Rohfeldnamen (import_blue_me.py, unveraendert uebernommen)
        "kopfschmerzen", "durchfall", "uebelkeit", "angst",
    )
    try:
        placeholders = ",".join("?" * len(HISTAMINE_SYMPTOMS))
        rows = conn.execute(f"""
            SELECT date, AVG(COALESCE(value_num, 0)) as avg_severity
            FROM symptoms
            WHERE symptom IN ({placeholders})
              AND date >= ? AND date <= ?
            GROUP BY date
            ORDER BY date
        """, (*HISTAMINE_SYMPTOMS, d_from, d_to)).fetchall()
        return {r[0]: r[1] for r in rows}
    except DB_OPERATIONAL_ERRORS:
        return {}


def _daily_load(triggers):
    """Berechnet tägliche Histaminlast als Score."""
    daily = defaultdict(float)
    for row in triggers:
        date = row[0]
        cat  = row[4] or "unknown"
        daily[date] += HIST_SCORE.get(cat, 1)
    return dict(daily)


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


def _bericht(triggers, histamine_symptoms, d_from, d_to):
    if not triggers:
        return t(
            "Keine Trigger-Daten.\nEingabe: python3 importers/import_histamine_diary.py --manual",
            "No trigger data.\nEntry: python3 importers/import_histamine_diary.py --manual",
        )

    n = len(triggers)
    daily_load = _daily_load(triggers)

    # Trigger-Häufigkeit nach Lebensmittel
    food_reactions = defaultdict(lambda: {"count": 0, "with_reaction": 0, "max_severity": 0, "cats": []})
    for _, _, food, portion, cat, react_h, symptoms, severity, meal_type in triggers:
        fr = food_reactions[food]
        fr["count"] += 1
        fr["cats"].append(cat or "unknown")
        if react_h is not None:
            fr["with_reaction"] += 1
        if severity and (severity > fr["max_severity"]):
            fr["max_severity"] = severity

    # Symptom-Analyse
    all_symptoms = defaultdict(int)
    reaction_times = []
    for row in triggers:
        react_h = row[5]
        syms = row[6]
        if syms:
            for s in syms.split(","):
                all_symptoms[s.strip()] += 1
        if react_h is not None:
            reaction_times.append(react_h)

    avg_load = sum(daily_load.values()) / len(daily_load) if daily_load else 0

    # Kategorie-Verteilung
    cat_counts = defaultdict(int)
    for r in triggers:
        cat_counts[r[4] or "unknown"] += 1

    lines = [
        t(f"## Histamin-Trigger-Analyse — {d_from} bis {d_to}",
          f"## Histamine trigger analysis — {d_from} to {d_to}"),
        t(f"Einträge: {n}  |  Tage mit Protokoll: {len(daily_load)}  |  "
          f"Tgl. Histaminlast Ø: {avg_load:.1f}",
          f"Entries: {n}  |  days with log: {len(daily_load)}  |  "
          f"Avg daily histamine load: {avg_load:.1f}"),
        "",
        t("### Kategorie-Verteilung", "### Category distribution"),
    ]
    for cat in ["high", "liberator", "medium", "blocker", "low", "unknown"]:
        cnt = cat_counts.get(cat, 0)
        if cnt:
            lines.append(f"  {cat:12} {cnt:4}x  ({cnt/n*100:.0f}%)")
    lines.append("")

    # Top-Trigger
    lines.append(t("### Top-Trigger (mit Reaktion)", "### Top triggers (with reaction)"))
    sorted_foods = sorted(
        food_reactions.items(),
        key=lambda x: (x[1]["with_reaction"], x[1]["max_severity"]),
        reverse=True
    )[:15]
    for food, stats in sorted_foods:
        if stats["with_reaction"] == 0 and stats["max_severity"] == 0:
            continue
        cat = max(set(stats["cats"]), key=stats["cats"].count)
        lines.append(t(
            f"  {food:30} [{cat:9}]  Reaktion: {stats['with_reaction']}/{stats['count']}x  "
            f"max. Schwere: {stats['max_severity']}",
            f"  {food:30} [{cat:9}]  reactions: {stats['with_reaction']}/{stats['count']}x  "
            f"max severity: {stats['max_severity']}",
        ))
    lines.append("")

    # Reaktionszeitfenster
    if reaction_times:
        sofort  = sum(1 for h in reaction_times if h < 1.0)
        kurz    = sum(1 for h in reaction_times if 1.0 <= h < 4.0)
        spaet   = sum(1 for h in reaction_times if h >= 4.0)
        avg_h   = sum(reaction_times) / len(reaction_times)
        lines += [
            t("### Reaktionszeitfenster", "### Reaction time windows"),
            t(f"  Sofort (<1h): {sofort}x  |  Kurz (1–4h): {kurz}x  |  Spät (≥4h): {spaet}x",
              f"  Immediate (<1h): {sofort}x  |  Short (1–4h): {kurz}x  |  Late (≥4h): {spaet}x"),
            t(f"  Durchschnitt: {avg_h:.1f}h", f"  Average: {avg_h:.1f}h"),
            "",
        ]

    # Top-Symptome
    if all_symptoms:
        lines.append(t("### Häufigste Symptome", "### Most common symptoms"))
        for sym, cnt in sorted(all_symptoms.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"  {sym:30} {cnt}x")
        lines.append("")

    # Korrelation mit Symptomen
    if histamine_symptoms and daily_load:
        pairs = [(daily_load[d], histamine_symptoms[d])
                 for d in daily_load if d in histamine_symptoms]
        if len(pairs) >= 5:
            xs, ys = zip(*pairs)
            r, n_p = _pearson(list(xs), list(ys))
            if r is not None:
                interp = (
                    t("stark", "strong") if abs(r) > 0.5 else
                    t("mäßig", "moderate") if abs(r) > 0.3 else
                    t("schwach", "weak")
                )
                lines += [
                    t("### Histaminlast ↔ Symptome",
                      "### Histamine load ↔ symptoms"),
                    t(f"  Pearson r = {r:.2f}  (n={n_p}, {interp}er Zusammenhang)",
                      f"  Pearson r = {r:.2f}  (n={n_p}, {interp} association)"),
                    "",
                ]

    # Mahlzeit-Muster
    meal_stats = defaultdict(lambda: {"count": 0, "reactions": 0})
    for r in triggers:
        meal = r[8] or "unknown"
        meal_stats[meal]["count"] += 1
        if r[5] is not None:
            meal_stats[meal]["reactions"] += 1
    if len(meal_stats) > 1:
        lines.append(t("### Mahlzeit-Muster", "### Meal pattern"))
        for meal, stats in sorted(meal_stats.items()):
            pct = stats["reactions"] / stats["count"] * 100 if stats["count"] else 0
            lines.append(t(
                f"  {meal:12} {stats['count']:3} Einträge  Reaktionsrate {pct:.0f}%",
                f"  {meal:12} {stats['count']:3} entries   reaction rate {pct:.0f}%",
            ))

    return "\n".join(lines)


def _plot(triggers, histamine_symptoms, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    if not triggers:
        return

    daily_load = _daily_load(triggers)
    dates_dl   = sorted(daily_load.keys())
    loads      = [daily_load[d] for d in dates_dl]
    dt_dl      = [datetime.strptime(d, "%Y-%m-%d") for d in dates_dl]

    n_plots = 2 + (1 if histamine_symptoms else 0)
    fig, axes = plt.subplots(n_plots, 1, figsize=(14, 4 * n_plots), facecolor="#1e1e2e")
    if n_plots == 1:
        axes = [axes]

    # Histaminlast
    ax = axes[0]
    ax.set_facecolor("#2d2d44")
    ax.bar(dt_dl, loads, color="#fd79a8", alpha=0.7, width=0.8)
    ax.set_ylabel(t("Histaminlast (Score)", "Histamine load (score)"),
                  color="white", fontsize=9)
    ax.tick_params(colors="white", labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
    ax.grid(True, alpha=0.15, axis="y")
    for s in ax.spines.values():
        s.set_visible(False)

    # Trigger-Kategorien
    ax = axes[1]
    ax.set_facecolor("#2d2d44")
    cat_colors = {"high": "#d63031", "liberator": "#e17055", "medium": "#fdcb6e",
                  "low": "#00b894", "blocker": "#74b9ff", "unknown": "#636e72"}
    cat_by_date = defaultdict(lambda: defaultdict(float))
    for row in triggers:
        cat_by_date[row[0]][row[4] or "unknown"] += HIST_SCORE.get(row[4] or "unknown", 1)
    all_dates = sorted(cat_by_date.keys())
    all_dt    = [datetime.strptime(d, "%Y-%m-%d") for d in all_dates]
    bottom    = [0.0] * len(all_dates)
    for cat in ["high", "liberator", "medium", "blocker", "low"]:
        vals = [cat_by_date[d].get(cat, 0) for d in all_dates]
        ax.bar(all_dt, vals, bottom=bottom, color=cat_colors.get(cat, "#636e72"),
               alpha=0.8, width=0.8, label=cat)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_ylabel(t("Last nach Kategorie", "Load by category"), color="white", fontsize=9)
    ax.legend(fontsize=7, labelcolor="white", framealpha=0.3)
    ax.tick_params(colors="white", labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
    ax.grid(True, alpha=0.15, axis="y")
    for s in ax.spines.values():
        s.set_visible(False)

    # Histamin-Symptome
    if histamine_symptoms and len(axes) > 2:
        ax = axes[2]
        ax.set_facecolor("#2d2d44")
        sym_dates = sorted(histamine_symptoms.keys())
        sym_vals  = [histamine_symptoms[d] for d in sym_dates]
        sym_dt    = [datetime.strptime(d, "%Y-%m-%d") for d in sym_dates]
        ax.plot(sym_dt, sym_vals, color="#a29bfe", lw=1.5, marker=".", markersize=5)
        ax.set_ylabel(t("Symptome Ø", "Symptoms avg"), color="white", fontsize=9)
        ax.tick_params(colors="white", labelsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
        ax.grid(True, alpha=0.15)
        for s in ax.spines.values():
            s.set_visible(False)

    fig.patch.set_facecolor("#1e1e2e")
    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"histamine_trigger_{ts}.png"
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
    out = OUT_DIR / f"histamine_trigger_{ts}.md"
    content = report
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"  Bericht: {out}", f"  Report: {out}"))


def main():
    parser = argparse.ArgumentParser(
        description=t("Histamin-Trigger analysieren", "Analyse histamine triggers"))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--days",   type=int, default=90,
                        help=t("Analysezeitraum in Tagen", "Analysis period in days"))
    parser.add_argument("--from",   dest="date_from", type=str, default=None)
    parser.add_argument("--to",     dest="date_to",   type=str, default=None)
    parser.add_argument("--person", type=str, default=None)
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    from health_config import OWN_PERSON_ID
    person = args.person or OWN_PERSON_ID
    d_to   = args.date_to   or datetime.now().strftime("%Y-%m-%d")
    d_from = args.date_from or (
        datetime.strptime(d_to, "%Y-%m-%d") - timedelta(days=args.days)
    ).strftime("%Y-%m-%d")

    conn         = open_db()
    triggers     = _load_triggers(conn, d_from, d_to, person)
    histamine_sym     = _load_histamine_symptoms(conn, d_from, d_to)
    conn.close()

    if not triggers:
        print(t("Keine Trigger-Daten — zuerst import_histamine_diary.py ausführen.",
                "No trigger data — run import_histamine_diary.py first."))
        return

    report = _bericht(triggers, histamine_sym, d_from, d_to)
    print(report)

    if args.plot:
        _plot(triggers, histamine_sym, d_from, d_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
