#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Flüssigkeitsaufnahme × Orthostatische Intoleranz

Analysiert ob ausreichende Flüssigkeits- und Salzaufnahme die
orthostatische Toleranz verbessert:
  - Tägliche Flüssigkeitsbilanz vs. Ziele (2,5 L + 3 g Na)
  - Korrelation Flüssigkeit am Vortag ↔ orthostatische HR-Reaktion
  - Koffein-Timing (DAO-Hemmung, vaskuläre Effekte)
  - Natrium-Aufnahme vs. Symptomstärke
  - Tageszeit-Verteilung (Konzentration früh = OI-Prävention)

Wissenschaftliche Grundlage:
  - Dysautonomia International: Fluid and salt management
  - Arnold et al. 2018: Dietary sodium and orthostatic intolerance
  - Raj 2013: Postural orthostatic tachycardia

Usage:
  python3 analyse_fluid_orthostatic.py
  python3 analyse_fluid_orthostatic.py --plot
  python3 analyse_fluid_orthostatic.py --days 30 --plot --no-llm

@tier        heuristic
@purpose.de  Analysiert ob ausreichende Flüssigkeits- und Salzaufnahme die orthostatische
             Toleranz verbessert: Tagesziele, Vortagskorrelation, Natrium-Wirkung und
             Koffein-Timing.
@purpose.en  Analyses whether adequate fluid and salt intake improves orthostatic tolerance:
             daily targets, previous-day correlation, sodium effect and caffeine timing.
@method.de   Flüssigkeitsziel 2.500 ml/Tag + 3.000 mg Natrium (Raj 2013);
             Pearson-Korrelation Vortags-Flüssigkeit × HR-Delta orthostatisch. Keine
             klinisch randomisierten Datenpunkte.
@method.en   Fluid target 2,500 ml/day + 3,000 mg sodium (Raj 2013);
             Pearson correlation previous-day fluid × orthostatic HR delta. No clinically
             randomised data points.
@refs        Raj SR (2013). Postural Tachycardia Syndrome (POTS). Circulation, 127(23):2336-2342. doi:10.1161/CIRCULATIONAHA.112.144501
             Arnold et al. 2018, Heart Rhythm (DOI ausstehend)
             Sheldon RS, Grubb BP, Olshansky B et al. (2015). 2015 Heart Rhythm Society Expert Consensus Statement on the Diagnosis and Treatment of Postural Tachycardia Syndrome, Inappropriate Sinus Tachycardia, and Vasovagal Syncope. Heart Rhythm, 12(6):e41-e63. doi:10.1016/j.hrthm.2015.03.029

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@limits.de   Heuristische Methode: Validierte Komponenten: Flüssigkeitsziel 2.500 ml + 3.000 mg Na (Raj 2013,
             doi:10.1161/CIRCULATIONAHA.112.144501), orthostatisches Kriterium >=30 bpm (Sheldon 2015,
             doi:10.1016/j.hrthm.2015.03.029). Heuristisch: Pearson-Korrelation Vortag ×
             HR-Delta, Grenzwert 20 bpm. Flüssigkeits-Logging ist manuell und lückenhaft.
             Orthostase-HR-Delta aus Consumer-Messgerät ohne standardisiertes Protokoll.
             Keine Kontrollgruppe. n=1.
@limits.en   Heuristic method: Validated components: fluid target 2,500 ml + 3,000 mg Na (Raj 2013,
             doi:10.1161/CIRCULATIONAHA.112.144501), orthostatic criterion >=30 bpm (Sheldon 2015,
             doi:10.1016/j.hrthm.2015.03.029). Heuristic: Pearson correlation previous-day
             fluid × HR delta, borderline threshold at 20 bpm. Fluid logging is manual and
             incomplete. Orthostatic HR delta from consumer device without standardised
             protocol. No control group. n=1.
@scoring
    Fluid target: >=2500 ml/day + >=3000 mg Na/day
    Orthostatic tolerance: HR delta <20 bpm acceptable | 20-30 bpm borderline | >=30 bpm orthostatic intolerance
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
@reads       fluid_intake, sessions, session_metrics
@writes      analyses/cardiovascular/*.{md,png} (kein DB-Write)

@usage
    python analyse_fluid_orthostatic.py
    python analyse_fluid_orthostatic.py --help
    python analyse_fluid_orthostatic.py --from 2024-01-01 --to 2024-12-31
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
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_FLUID_ORTHOSTATIC_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_FLUID_ORTHOSTATIC_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

OUT_DIR = _cfg.analyses_dir / "cardiovascular"

FLUID_TARGET_ML  = 2500   # Raj 2013 Empfehlung: 2-3 L/Tag; doi:10.1161/CIRCULATIONAHA.112.144501
SODIUM_TARGET_MG = 3000   # ~7.5 g NaCl/Tag; Raj 2013 (3-5 g Na/Tag); doi:10.1161/CIRCULATIONAHA.112.144501

def _load_fluid(conn, d_from, d_to, person):
    try:
        return conn.execute("""
            SELECT date, time_str, beverage, volume_ml, caffeine_mg, sodium_mg
            FROM fluid_intake
            WHERE date >= ? AND date <= ? AND person=?
            ORDER BY date, time_str
        """, (d_from, d_to, person)).fetchall()
    except DB_OPERATIONAL_ERRORS:
        return []


def _load_orthostatic(conn, d_from, d_to, person):
    """hr_delta aus session_metrics der Orthostase-Sessions."""
    try:
        rows = conn.execute("""
            SELECT s.date, sm.value as hr_delta
            FROM sessions s
            JOIN session_metrics sm ON sm.session_id = s.id
            WHERE s.type = 'orthostatic'
              AND sm.metric = 'hr_delta'
              AND s.date >= ? AND s.date <= ?
              AND s.person = ?
            ORDER BY s.date
        """, (d_from, d_to, person)).fetchall()
        return {r[0]: r[1] for r in rows}
    except DB_OPERATIONAL_ERRORS:
        return {}


def _daily_fluid(fluid_rows):
    daily = defaultdict(lambda: {"volume": 0.0, "caffeine": 0.0, "sodium": 0.0, "alcohol": 0.0})
    for date, time_str, beverage, vol, caf, na in fluid_rows:
        d = daily[date]
        d["volume"]   += vol or 0
        d["caffeine"] += caf or 0
        d["sodium"]   += na  or 0
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


def _bericht(fluid_rows, daily, orthostatic, d_from, d_to):
    if not fluid_rows:
        return t(
            "Keine Flüssigkeitsdaten.\nEingabe: python3 importers/import_fluid_intake.py --manual",
            "No fluid intake data.\nEntry: python3 importers/import_fluid_intake.py --manual",
        )

    n_days   = len(daily)
    avg_vol  = sum(d["volume"] for d in daily.values()) / n_days if n_days else 0
    avg_na   = sum(d["sodium"] for d in daily.values()) / n_days if n_days else 0
    avg_caf  = sum(d["caffeine"] for d in daily.values()) / n_days if n_days else 0

    days_ok_vol = sum(1 for d in daily.values() if d["volume"] >= FLUID_TARGET_ML)
    days_ok_na  = sum(1 for d in daily.values() if d["sodium"] >= SODIUM_TARGET_MG)

    vol_flag = "✓" if avg_vol >= FLUID_TARGET_ML else "△"
    na_flag  = "✓" if avg_na  >= SODIUM_TARGET_MG else "△"

    lines = [
        t(f"## Flüssigkeitsaufnahme × OI — {d_from} bis {d_to}",
          f"## Fluid intake × OI — {d_from} to {d_to}"),
        t(f"Tage: {n_days}  |  Einträge: {len(fluid_rows)}",
          f"Days: {n_days}  |  entries: {len(fluid_rows)}"),
        "",
        t("### Tagesübersicht (Durchschnitt)", "### Daily average"),
        t(f"  {vol_flag} Flüssigkeit: {avg_vol:.0f} ml  (Ziel: {FLUID_TARGET_ML} ml)  "
          f"Ziel erreicht: {days_ok_vol}/{n_days} Tagen",
          f"  {vol_flag} Fluid: {avg_vol:.0f} ml  (target: {FLUID_TARGET_ML} ml)  "
          f"target met: {days_ok_vol}/{n_days} days"),
        t(f"  {na_flag} Natrium: {avg_na:.0f} mg  (Ziel: {SODIUM_TARGET_MG} mg)  "
          f"Ziel erreicht: {days_ok_na}/{n_days} Tagen",
          f"  {na_flag} Sodium: {avg_na:.0f} mg  (target: {SODIUM_TARGET_MG} mg)  "
          f"target met: {days_ok_na}/{n_days} days"),
        t(f"    Koffein: {avg_caf:.0f} mg/Tag",
          f"    Caffeine: {avg_caf:.0f} mg/day"),
        "",
    ]

    # Getränke-Aufschlüsselung
    bev_totals = defaultdict(lambda: {"vol": 0.0, "days": set()})
    for date, time_str, bev, vol, caf, na in fluid_rows:
        bev_totals[bev]["vol"]  += vol or 0
        bev_totals[bev]["days"].add(date)
    lines.append(t("### Getränke-Verteilung (Gesamt)", "### Beverage breakdown (total)"))
    for bev, stats in sorted(bev_totals.items(), key=lambda x: -x[1]["vol"])[:8]:
        lines.append(t(
            f"  {bev:20} {stats['vol']:.0f} ml  ({len(stats['days'])} Tage)",
            f"  {bev:20} {stats['vol']:.0f} ml  ({len(stats['days'])} days)",
        ))
    lines.append("")

    # Tageszeit-Verteilung
    hour_vol = defaultdict(float)
    for _, time_str, _, vol, _, _ in fluid_rows:
        if time_str and ":" in time_str:
            try:
                h = int(time_str.split(":")[0])
                hour_vol[h] += vol or 0
            except (ValueError, IndexError):
                pass
    if hour_vol:
        morning = sum(v for h, v in hour_vol.items() if 6 <= h < 12)
        afternoon = sum(v for h, v in hour_vol.items() if 12 <= h < 18)
        evening = sum(v for h, v in hour_vol.items() if h >= 18)
        total_h = morning + afternoon + evening or 1
        lines += [
            t("### Tageszeit-Verteilung", "### Time-of-day distribution"),
            t(f"  Morgens 6–12h:   {morning:.0f} ml ({morning/total_h*100:.0f}%)",
              f"  Morning 6–12h:   {morning:.0f} ml ({morning/total_h*100:.0f}%)"),
            t(f"  Nachmittag 12–18h: {afternoon:.0f} ml ({afternoon/total_h*100:.0f}%)",
              f"  Afternoon 12–18h: {afternoon:.0f} ml ({afternoon/total_h*100:.0f}%)"),
            t(f"  Abend 18+h:      {evening:.0f} ml ({evening/total_h*100:.0f}%)",
              f"  Evening 18+h:    {evening:.0f} ml ({evening/total_h*100:.0f}%)"),
            "",
        ]

    # Flüssigkeit ↔ Orthostatik (Vortag → Orthostase)
    if orthostatic:
        fluid_dates = sorted(daily.keys())
        pairs_vol, pairs_na = [], []
        for d in fluid_dates:
            next_d = (datetime.strptime(d, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            if next_d in orthostatic:
                oi_val = orthostatic[next_d]
                pairs_vol.append((daily[d]["volume"], oi_val))
                pairs_na.append((daily[d]["sodium"], oi_val))
            elif d in orthostatic:
                oi_val = orthostatic[d]
                pairs_vol.append((daily[d]["volume"], oi_val))
                pairs_na.append((daily[d]["sodium"], oi_val))

        lines.append(t("### Flüssigkeit ↔ Orthostatik", "### Fluid ↔ orthostatic"))
        if len(pairs_vol) >= 5:
            xs, ys = zip(*pairs_vol)
            r, n   = _pearson(list(xs), list(ys))
            if r is not None:
                lines.append(t(
                    f"  Flüssigkeit ↔ ΔHR: r = {r:.2f}  (n={n})",
                    f"  Fluid ↔ ΔHR: r = {r:.2f}  (n={n})",
                ))
        if len(pairs_na) >= 5:
            xs, ys = zip(*pairs_na)
            r, n   = _pearson(list(xs), list(ys))
            if r is not None:
                lines.append(t(
                    f"  Natrium ↔ ΔHR: r = {r:.2f}  (n={n})",
                    f"  Sodium ↔ ΔHR: r = {r:.2f}  (n={n})",
                ))
        if not pairs_vol:
            lines.append(t(
                "  Kein Überlapp mit Orthostase-Messungen.",
                "  No overlap with orthostatic measurements.",
            ))
        lines.append("")

    # OI-Score: schlechte Tage
    bad_days = [d for d, v in daily.items()
                if v["volume"] < FLUID_TARGET_ML * 0.7 or v["sodium"] < SODIUM_TARGET_MG * 0.5]
    if bad_days:
        lines += [
            t(f"### Unterversorgung ({len(bad_days)} Tage <70% Flüssigkeit oder <50% Natrium)",
              f"### Underhydration ({len(bad_days)} days <70% fluid or <50% sodium)"),
        ]
        for d in sorted(bad_days)[-5:]:
            v = daily[d]
            lines.append(t(
                f"  {d}  {v['volume']:.0f} ml  Na: {v['sodium']:.0f} mg",
                f"  {d}  {v['volume']:.0f} ml  Na: {v['sodium']:.0f} mg",
            ))

    return "\n".join(lines)


def _plot(fluid_rows, daily, orthostatic, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    if not daily:
        return

    dates_sorted = sorted(daily.keys())
    dt_list = [datetime.strptime(d, "%Y-%m-%d") for d in dates_sorted]
    vols    = [daily[d]["volume"] for d in dates_sorted]
    nas     = [daily[d]["sodium"] for d in dates_sorted]
    cafs    = [daily[d]["caffeine"] for d in dates_sorted]

    n_plots = 2 + (1 if orthostatic else 0)
    fig, axes = plt.subplots(n_plots, 1, figsize=(14, 4 * n_plots), facecolor="#1e1e2e")
    if n_plots == 1:
        axes = [axes]

    # Flüssigkeit
    ax = axes[0]
    ax.set_facecolor("#2d2d44")
    colors = ["#74b9ff" if v >= FLUID_TARGET_ML else "#fd79a8" for v in vols]
    ax.bar(dt_list, vols, color=colors, alpha=0.8, width=0.8)
    ax.axhline(FLUID_TARGET_ML, color="#55efc4", lw=1.5, ls="--", alpha=0.7,
               label=t(f"Ziel {FLUID_TARGET_ML} ml", f"Target {FLUID_TARGET_ML} ml"))
    ax.set_ylabel(t("Flüssigkeit (ml)", "Fluid (ml)"), color="white", fontsize=9)
    ax.legend(fontsize=8, labelcolor="white", framealpha=0.3)
    ax.tick_params(colors="white", labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
    ax.grid(True, alpha=0.15, axis="y")
    for s in ax.spines.values():
        s.set_visible(False)

    # Natrium + Koffein
    ax = axes[1]
    ax.set_facecolor("#2d2d44")
    na_colors = ["#a29bfe" if v >= SODIUM_TARGET_MG else "#e17055" for v in nas]
    ax.bar(dt_list, nas, color=na_colors, alpha=0.8, width=0.8,
           label=t("Natrium (mg)", "Sodium (mg)"))
    ax.axhline(SODIUM_TARGET_MG, color="#55efc4", lw=1.5, ls="--", alpha=0.7,
               label=t(f"Ziel {SODIUM_TARGET_MG} mg", f"Target {SODIUM_TARGET_MG} mg"))
    ax2 = ax.twinx()
    ax2.plot(dt_list, cafs, color="#fdcb6e", lw=1.5, marker=".", markersize=4, alpha=0.8)
    ax2.set_ylabel(t("Koffein (mg)", "Caffeine (mg)"), color="#fdcb6e", fontsize=8)
    ax2.tick_params(colors="#fdcb6e", labelsize=7)
    ax.set_ylabel(t("Natrium (mg)", "Sodium (mg)"), color="white", fontsize=9)
    ax.legend(fontsize=8, labelcolor="white", framealpha=0.3)
    ax.tick_params(colors="white", labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
    ax.grid(True, alpha=0.15, axis="y")
    for s in ax.spines.values():
        s.set_visible(False)

    # Orthostatik
    if orthostatic and len(axes) > 2:
        ax = axes[2]
        ax.set_facecolor("#2d2d44")
        oi_dates = sorted(orthostatic.keys())
        oi_vals  = [orthostatic[d] for d in oi_dates]
        oi_dt    = [datetime.strptime(d, "%Y-%m-%d") for d in oi_dates]
        oi_colors = ["#d63031" if v >= 30 else "#e17055" if v >= 20 else "#55efc4"
                     for v in oi_vals]
        ax.bar(oi_dt, oi_vals, color=oi_colors, alpha=0.8, width=0.8)
        ax.axhline(30, color="#d63031", lw=1, ls="--", alpha=0.5, label="30 bpm")  # Sheldon 2015, doi:10.1016/j.hrthm.2015.03.029
        ax.axhline(20, color="#e17055", lw=1, ls=":", alpha=0.5, label="Grenzwertig 20 bpm")  # heuristisch / projektintern
        ax.set_ylabel("ΔHR Orthostase (bpm)", color="white", fontsize=9)
        ax.legend(fontsize=8, labelcolor="white", framealpha=0.3)
        ax.tick_params(colors="white", labelsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%y"))
        ax.grid(True, alpha=0.15, axis="y")
        for s in ax.spines.values():
            s.set_visible(False)

    fig.patch.set_facecolor("#1e1e2e")
    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"fluid_oi_{ts}.png"
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
    out = OUT_DIR / f"fluid_oi_{ts}.md"
    content = report
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"  Bericht: {out}", f"  Report: {out}"))


def main():
    parser = argparse.ArgumentParser(
        description=t("Flüssigkeitsaufnahme × OI analysieren",
                      "Analyse fluid intake × orthostatic intolerance"))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--days",   type=int, default=60)
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
    fluid_rows   = _load_fluid(conn, d_from, d_to, person)
    orthostatic  = _load_orthostatic(conn, d_from, d_to, person)
    conn.close()

    if not fluid_rows:
        print(t("Keine Flüssigkeitsdaten — zuerst import_fluid_intake.py ausführen.",
                "No fluid data — run import_fluid_intake.py first."))
        return

    daily   = _daily_fluid(fluid_rows)
    report = _bericht(fluid_rows, daily, orthostatic, d_from, d_to)
    print(report)

    if args.plot:
        _plot(fluid_rows, daily, orthostatic, d_from, d_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
