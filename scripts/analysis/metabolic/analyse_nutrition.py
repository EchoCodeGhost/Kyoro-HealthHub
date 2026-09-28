#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Nutritions-Analyse (FDDB)

Analysiert Nutritionsdaten aus FDDB: Makronährstoff-Verteilung,
Kalorientrend, Mahlzeiten-Timing and Correlation with HRV / Energie /
Symptomsn am Folgetag.

@tier        heuristic
@purpose.de  Analysiert FDDB-Nutritionsdaten auf Makronährstoff-Verteilung, Kalorientrend und Mahlzeiten-Timing sowie Spearman-Korrelation mit Folgetag-HRV und Energie.
@purpose.en  Analyses FDDB nutrition data for macronutrient distribution, calorie trend and meal timing, as well as Spearman correlation with next-day HRV and energy.
@method.de   Tagesaggregat aus nutrition_daily; Spearman-Rangkorrelation (Pure-Python) zwischen Ernährungsvariablen und HRV/Energie am Folgetag; eigenes Kalorienziel (KCAL_ZIEL=2000 kcal) als Referenz.
@method.en   Daily aggregate from nutrition_daily; Spearman rank correlation (pure Python) between nutrition variables and next-day HRV/energy; own calorie target (KCAL_ZIEL=2000 kcal) as reference.
@scoring     Kalorie-Klassifikation (heuristisch, projektintern):
               <1500 kcal = Unterversorgung, 1500–2500 kcal = Normal, >2500 kcal = Erhöht
               Referenz: KCAL_ZIEL = 2000 kcal (eigener Zielwert, nicht DGE-kalibriert)
               Späte Mahlzeiten: Stunden-Stempel ≥21:00 Uhr = "spät" (heuristisch)
               Basis: projektintern; DGE/EFSA-Referenzwerte für Makronährstoffe existieren, aber im Skript nicht umgesetzt.
@limits.de   Heuristische Methode: Eigenes Kalorienziel (2000 kcal) nicht individuell kalibriert; Kalorie-Bänder (1500/2500 kcal) heuristisch ohne DGE/WHO-Referenzwert-Abgleich; Späte-Mahlzeiten-Schwelle 21:00 Uhr ohne publizierte Validierung; FDDB-Daten abhängig von manuellem Logging; Lag-Korrelation explorativ ohne Multiple-Testing-Korrektur.
@limits.en   Heuristic method: Own calorie target (2000 kcal) not individually calibrated; calorie bands (1500/2500 kcal) heuristic without DGE/WHO reference value comparison; late meal threshold 21:00 without published validation; FDDB data dependent on manual logging; lag correlation exploratory without multiple testing correction.
@refs        FAO/WHO/UNU 2001, Energy requirements — Human energy requirements; ISBN:92-5-105212-5
             Almoosawi S, Vingeliene S, Karagounis LG, Pot GK (2016). Chrono-nutrition: a review of current evidence from observational studies on global trends in time-of-day of energy intake and its association with obesity. Proceedings of the Nutrition Society, 75(4):487-500. doi:10.1017/S0029665116000306

@relevance.de  Ermöglicht die Stoffwechselanalyse, essentiell für die metabolische Gesundheit
@relevance.en  Enables metabolic analysis, essential for metabolic health
@reads       nutrition_daily, measurements, symptoms
@writes      analyses/metabolic/nutrition_*.{md,png}

Usage:
  python analyse_nutrition.py --plot
  python analyse_nutrition.py --from YYYY-MM-DD --plot
  python analyse_nutrition.py --plot --no-llm

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_nutrition.py
    python analyse_nutrition.py --help
    python analyse_nutrition.py --from 2024-01-01 --to 2024-12-31
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
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "metabolic"

from modules.prompts.analysis_metabolic import (
    SYSTEM_PROMPT_ANALYSE_NUTRITION_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_NUTRITION_EN as SYSTEM_PROMPT_EN,
)

KCAL_ZIEL = 2000


def load_data(conn, d_from, d_to):
    daily = conn.execute("""
        SELECT date, kcal, fat_g, carbs_g, protein_g, meal_count, last_meal
        FROM nutrition_daily
        WHERE date >= ? AND date <= ?
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    stress = {}
    if "daily_stress" in tables:
        for d, rmssd, stress_s, sleep_h in conn.execute("""
            SELECT date, rmssd_ms, stress_score, sleep_hours
            FROM daily_stress WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            stress[d] = {"hrv": rmssd, "stress": stress_s, "sleep_h": sleep_h}

    symptome = {}
    if "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num)
            FROM symptoms
            WHERE date >= ? AND date <= ?
              AND category = 'Ressourcen'
              AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert
    elif "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num)
            FROM symptoms
            WHERE date >= ? AND date <= ?
              AND category = 'Ressourcen'
              AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert

    return daily, stress, symptome


def letzte_mahlzeit_stunden(lm_str):
    """Gibt Stande der letzten Mahlzeit zurück (float) or None."""
    if not lm_str:
        return None
    try:
        parts = lm_str.strip().split(":")
        return int(parts[0]) + int(parts[1]) / 60
    except Exception:
        return None


def spearman_r(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
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
    return round(rs, 3)


def build_report(daily, stress, symptome, d_from, d_to):
    if not daily:
        return "Keine Ernährungsdaten im angefragten Zeitraum."

    n = len(daily)
    kcal_vals   = [r[1] for r in daily if r[1]]
    fett_vals   = [r[2] for r in daily if r[2]]
    kh_vals     = [r[3] for r in daily if r[3]]
    prot_vals   = [r[4] for r in daily if r[4]]
    mahlz_vals  = [r[5] for r in daily if r[5]]
    lm_vals     = [letzte_mahlzeit_stunden(r[6]) for r in daily]

    avg_kcal  = round(sum(kcal_vals) / len(kcal_vals), 0) if kcal_vals else None
    avg_fett  = round(sum(fett_vals) / len(fett_vals), 1) if fett_vals else None
    avg_kh    = round(sum(kh_vals)   / len(kh_vals),   1) if kh_vals   else None
    avg_prot  = round(sum(prot_vals) / len(prot_vals),  1) if prot_vals else None
    avg_malz  = round(sum(mahlz_vals)/ len(mahlz_vals), 1) if mahlz_vals else None
    lm_valid  = [v for v in lm_vals if v is not None]
    avg_lm    = round(sum(lm_valid) / len(lm_valid), 1) if lm_valid else None

    # Makro-Prozente
    if avg_fett and avg_kh and avg_prot:
        kcal_fett = avg_fett * 9
        kcal_kh   = avg_kh   * 4
        kcal_prot = avg_prot * 4
        total     = kcal_fett + kcal_kh + kcal_prot
        pct_f = round(kcal_fett / total * 100, 1)
        pct_k = round(kcal_kh   / total * 100, 1)
        pct_p = round(kcal_prot / total * 100, 1)
        makro_str = f"KH {pct_k}% / Fett {pct_f}% / Protein {pct_p}%"
    else:
        makro_str = "nicht berechenbar"

    # Kalorienverteilung
    n_unter = sum(1 for v in kcal_vals if v < 1500)
    n_norm  = sum(1 for v in kcal_vals if 1500 <= v <= 2500)
    n_ueber = sum(1 for v in kcal_vals if v > 2500)

    # Späte Mahlzeiten (nach 21 Uhr)
    n_spaet = sum(1 for v in lm_valid if v >= 21)

    lines = [
        f"## Ernährungs-Analyse — {d_from} bis {d_to}\n",
        f"Tage mit Einträgen: **{n}**  |  Zeitraum: {daily[0][0]} – {daily[-1][0]}",
    ]

    if avg_kcal:
        lines.append(f"Ø Kalorien: **{avg_kcal:.0f} kcal/Tag**  "
                     f"({'–' if avg_kcal < 1500 else '+' if avg_kcal > 2500 else '✓'})")
    if avg_fett:
        lines.append(f"Ø Fett: {avg_fett} g  |  Ø Kohlenhydrate: {avg_kh} g  |  "
                     f"Ø Protein: {avg_prot} g")
    lines.append(f"Makro-Verteilung: {makro_str}")
    if avg_malz:
        lines.append(f"Ø Mahlzeiten/Tag: {avg_malz}")
    if avg_lm:
        lines.append(f"Ø letzte Mahlzeit: {int(avg_lm)}:{int((avg_lm % 1)*60):02d} Uhr  |  "
                     f"Späte Mahlzeiten (≥21:00): {n_spaet}/{len(lm_valid)} "
                     f"({round(n_spaet/len(lm_valid)*100,1) if lm_valid else 0}%)\n")

    lines += [
        "### Kalorienverteilung\n",
        f"  <1500 kcal (Unterversorgung): {n_unter} Tage ({round(n_unter/len(kcal_vals)*100,1) if kcal_vals else 0}%)",
        f"  1500–2500 kcal (normal):       {n_norm} Tage ({round(n_norm/len(kcal_vals)*100,1) if kcal_vals else 0}%)",
        f"  >2500 kcal (erhöht):           {n_ueber} Tage ({round(n_ueber/len(kcal_vals)*100,1) if kcal_vals else 0}%)",
    ]

    # weekstag-Muster
    dow_kcal = defaultdict(list)
    for r in daily:
        if r[1]:
            try:
                dow = datetime.fromisoformat(r[0]).strftime("%a")
                dow_kcal[dow].append(r[1])
            except ValueError:
                pass
    if dow_kcal:
        lines.append("\n### Kcal nach Wochentag\n")
        dow_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        lines.append(f"  {'Tag':<5} {'Ø kcal':>8} {'n':>4}")
        lines.append("  " + "-" * 20)
        for dow in dow_order:
            if dow in dow_kcal:
                avg = round(sum(dow_kcal[dow]) / len(dow_kcal[dow]))
                lines.append(f"  {dow:<5} {avg:>8.0f} {len(dow_kcal[dow]):>4}")

    # Folgetag-Correlationen
    daily_by_date = {r[0]: r for r in daily}
    dates_sorted  = sorted(daily_by_date.keys())

    kcal_x, hrv_y, stress_y, sym_y, lm_x, hrv_lm = [], [], [], [], [], []
    for d in dates_sorted:
        r = daily_by_date[d]
        try:
            next_d = (datetime.fromisoformat(d) + timedelta(days=1)).strftime("%Y-%m-%d")
        except ValueError:
            continue
        if next_d in stress:
            hrv_next = stress[next_d].get("hrv")
            st_next  = stress[next_d].get("stress")
            if r[1]:
                kcal_x.append(r[1])
                hrv_y.append(hrv_next)
                stress_y.append(st_next)
            lm_h = letzte_mahlzeit_stunden(r[6])
            if lm_h is not None and hrv_next is not None:
                lm_x.append(lm_h)
                hrv_lm.append(hrv_next)
        if next_d in symptome and r[1]:
            sym_y.append(symptome[next_d])
            if len(kcal_x) > len(sym_y):
                kcal_x = kcal_x[:len(sym_y)]

    if any(v is not None for v in [spearman_r(kcal_x, hrv_y),
                                    spearman_r(kcal_x, stress_y)]):
        lines.append("\n### Korrelation Ernährung → Folgetag-Werte (Spearman r)\n")
        lines.append(f"  {'Variable':<30} {'× HRV':>7} {'× Stress':>9}")
        lines.append("  " + "-" * 50)

        r_kcal_hrv    = spearman_r(kcal_x, hrv_y)
        r_kcal_stress = spearman_r(kcal_x, stress_y)
        lines.append(f"  {'Kalorien':<30} "
                     f"{str(r_kcal_hrv) if r_kcal_hrv else 'n.a.':>7} "
                     f"{str(r_kcal_stress) if r_kcal_stress else 'n.a.':>9}")

        # Protein
        prot_x = [daily_by_date[d][4] for d in dates_sorted
                  if daily_by_date[d][4] and
                  (datetime.fromisoformat(d) + timedelta(days=1)).strftime("%Y-%m-%d") in stress]
        hrv_prot = [stress[(datetime.fromisoformat(d) + timedelta(days=1)).strftime("%Y-%m-%d")].get("hrv")
                    for d in dates_sorted
                    if daily_by_date[d][4] and
                    (datetime.fromisoformat(d) + timedelta(days=1)).strftime("%Y-%m-%d") in stress]
        r_prot_hrv = spearman_r(prot_x, hrv_prot)
        lines.append(f"  {'Protein (g)':<30} "
                     f"{str(r_prot_hrv) if r_prot_hrv else 'n.a.':>7} {'n.a.':>9}")

        if lm_x:
            r_lm_hrv = spearman_r(lm_x, hrv_lm)
            lines.append(f"  {'Letzte Mahlzeit (Uhrzeit)':<30} "
                         f"{str(r_lm_hrv) if r_lm_hrv else 'n.a.':>7} {'n.a.':>9}")

    return "\n".join(lines)


def _plot(daily, stress, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), facecolor="#1e1e2e")
    fig.suptitle(f"Ernährungs-Verlauf {d_from}–{d_to}", color="#E0E0E0", fontsize=13)

    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    dts_all   = []
    kcal_all  = []
    fett_all  = []
    kh_all    = []
    prot_all  = []

    for r in daily:
        try:
            dt = datetime.fromisoformat(r[0])
        except ValueError:
            continue
        if r[1]:
            dts_all.append(dt)
            kcal_all.append(r[1])
            fett_all.append(r[2] or 0)
            kh_all.append(r[3] or 0)
            prot_all.append(r[4] or 0)

    # Kalorienverlauf with 7-days-Schnitt
    if dts_all:
        axes[0].bar(dts_all, kcal_all, color="#74b9ff", alpha=0.5, width=0.8)
        # 7-days-Glättung
        if len(kcal_all) >= 7:
            ma7 = []
            for i in range(len(kcal_all)):
                start = max(0, i - 6)
                chunk = kcal_all[start:i + 1]
                ma7.append(sum(chunk) / len(chunk))
            axes[0].plot(dts_all, ma7, color="#0984e3", lw=1.5, label="7-Tage-Ø")
        axes[0].axhline(KCAL_ZIEL, color="#fdcb6e", lw=0.8, ls="--", alpha=0.6,
                        label=f"Ziel {KCAL_ZIEL} kcal")
        axes[0].set_ylabel("kcal", color="#ccc", fontsize=9)
        axes[0].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Makronährstoffe gestapelt (als Kalorienanteil)
    if dts_all:
        kh_kcal   = [v * 4 for v in kh_all]
        prot_kcal = [v * 4 for v in prot_all]
        fett_kcal = [v * 9 for v in fett_all]
        axes[1].stackplot(dts_all, kh_kcal, prot_kcal, fett_kcal,
                          labels=["Kohlenhydrate", "Protein", "Fett"],
                          colors=["#fdcb6e", "#2ecc71", "#e17055"], alpha=0.85)
        axes[1].set_ylabel("kcal (Makros)", color="#ccc", fontsize=9)
        axes[1].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white", loc="upper left")
        axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # HRV-Verlauf (optional overlay)
    if stress:
        stress_dates = sorted(stress.keys())
        hrv_dts  = [datetime.fromisoformat(d) for d in stress_dates if stress[d].get("hrv")]
        hrv_vals = [stress[d]["hrv"] for d in stress_dates if stress[d].get("hrv")]
        if hrv_dts:
            axes[2].plot(hrv_dts, hrv_vals, color="#a29bfe", lw=1.2, label="HRV RMSSD")
            axes[2].set_ylabel("HRV RMSSD (ms)", color="#ccc", fontsize=9)
            axes[2].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
            axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p  = OUT_DIR / f"nutrition_{ts}.png"
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
    out = OUT_DIR / f"nutrition_{ts}.md"
    content = f"# Ernährungs-Analyse\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("Ernährungs-Analyse", "Nutrition analysis"))
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
    daily, stress, symptome = load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not daily:
        print("Keine Ernährungsdaten. Zuerst: python3 importers/import_fddb.py")
        return

    print(f"Ernährungstage: {len(daily)} ({daily[0][0]} – {daily[-1][0]})")

    report = build_report(daily, stress, symptome, args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(daily, stress, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
