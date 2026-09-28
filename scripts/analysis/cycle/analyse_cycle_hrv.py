#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Cycle- & HRV-Analyse

Analysiert Cyclelängen-Trends (WomanLog), phasenbezogene
HRV / Energie / PEM-Risiko sowie Cyclesymptome.

Phasen (grobe Einteilung aus Cyclestart):
  Menstruation: day 1–5
  Follikulär:   day 6–12
  Ovulation:    day 13–15
  Luteal:       day 16–28+

Usage:
  python analyse_cycle_hrv.py --plot
  python analyse_cycle_hrv.py --from YYYY-MM-DD --plot
  python analyse_cycle_hrv.py --plot --no-llm

@tier        heuristic
@purpose.de  Analysiert Zykluslängen-Trends aus WomanLog, phasenbezogene HRV / Energie /
             PEM-Risiko sowie Zykussymptome und Oura-Cycle-Insights.
@purpose.en  Analyses cycle length trends from WomanLog, phase-specific HRV / energy /
             PEM risk, cycle symptoms and Oura cycle insights.
@method.de   Grobe 4-Phasen-Einteilung aus Zyklusstartdatum (feste Tag-Grenzen);
             Gruppenvergleich HRV/Stress nach Phase. Oura-Cycle-Insights werden
             direkt übernommen ohne Kreuzvalidierung. Keine formal validierten Schwellen.
@method.en   Rough 4-phase assignment from cycle start date (fixed day boundaries);
             group comparison HRV/stress by phase. Oura cycle insights are used
             directly without cross-validation. No formally validated thresholds.
@limits.de   Heuristische Methode: Feste Phasengrenzen (Tag 1–5, 6–12, 13–15, 16+) ignorieren individuelle
             Variabilität. Oura-Phasenzuordnung ist proprietär und nicht publiziert validiert.
             n=1, explorativ.
             Zykluslängen-Grenzen: kurz < 24 Tage / lang > 38 Tage per FIGO 2018
             (Munro et al., Int J Gynaecol Obstet 2018, doi:10.1002/ijgo.12666).
             Alle Phasengrenzen (Tag 1–5, 6–12, 13–15) sind heuristisch, nicht hormonal
             bestätigt.
@limits.en   Heuristic method: Fixed phase boundaries (day 1–5, 6–12, 13–15, 16+) ignore individual
             variability. Oura phase assignment is proprietary and not published-validated.
             n=1, exploratory.
             Cycle length boundaries: short < 24 days / long > 38 days per FIGO 2018
             (Munro et al., Int J Gynaecol Obstet 2018, doi:10.1002/ijgo.12666).
             All phase boundaries (days 1–5, 6–12, 13–15) are heuristic, not
             hormonally confirmed.
@scoring
    Cycle length: short <24 days | normal 21-35 days | long >38 days (FIGO 2018)
    Phase assignment: menstruation day 1-5 | follicular day 6-12 | ovulation day 13-15 | luteal day 16+
@refs        Munro MG et al. (2018). FIGO classification system for causes of abnormal
             Munro MG, Critchley HOD, Fraser IS (2018). The two FIGO systems for normal and abnormal uterine bleeding symptoms and classification of causes of abnormal uterine bleeding in the reproductive years: 2018 revisions. International Journal of Gynecology & Obstetrics, 143(3):393-408. doi:10.1002/ijgo.12666

@relevance.de  Analysiert zyklusbedingte Veränderungen der Herzfrequenzvariabilität, essentiell für das Verständnis des autonomen Nervensystems und die Identifikation hormoneller Einflüsse auf die kardiovaskuläre Gesundheit
@relevance.en  Analyzes cycle-related changes in heart rate variability, essential for understanding the autonomic nervous system and identifying hormonal influences on cardiovascular health
@reads       reproductive_health, symptoms, oura_cycle_insights, daily_stress
@writes      analyses/cycle/*.{md,png} (kein DB-Write)

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_cycle_hrv.py
    python analyse_cycle_hrv.py --help
    python analyse_cycle_hrv.py --from 2024-01-01 --to 2024-12-31
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
OUT_DIR = _cfg.analyses_dir / "cycle"

from modules.prompts.analysis_cycle import (
    SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_CYCLE_HRV_EN as SYSTEM_PROMPT_EN,
)

PHASEN = [
    (1,  5,  "Menstruation"),
    (6,  12, "Follikulär"),
    (13, 15, "Ovulation"),
    (16, 99, "Luteal"),
]


def zyklusphase(tag):
    for start, ende, name in PHASEN:
        if start <= tag <= ende:
            return name
    return "Luteal"


def load_data(conn, d_from, d_to):
    cycles = conn.execute("""
        SELECT date FROM reproductive_health
        WHERE event_type = 'period_start' AND date >= ? AND date <= ?
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    cycle_starts = [r[0] for r in cycles]

    symptoms_wl = conn.execute("""
        SELECT date, symptom FROM symptoms
        WHERE source = 'womanlog' AND date >= ? AND date <= ?
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    oura_ci = conn.execute("""
        SELECT day, day_of_cycle, cycle_phase, fertile_window, risk
        FROM oura_cycle_insights
        WHERE day >= ? AND day <= ?
        ORDER BY day
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

    from utils.pem_loader import load_pem
    pem = load_pem(conn, d_from, d_to)

    return cycle_starts, symptoms_wl, oura_ci, stress, symptome, pem


def datum_zu_zyklusdaten(cycle_starts, ziel_datum_str):
    """Gibt (Cycletag, Phase) zurück or (None, None)."""
    try:
        ziel = datetime.fromisoformat(ziel_datum_str).date()
    except ValueError:
        return None, None
    best_start = None
    for cs in reversed(cycle_starts):
        try:
            start = datetime.fromisoformat(cs).date()
        except ValueError:
            continue
        if start <= ziel:
            best_start = start
            break
    if best_start is None:
        return None, None
    tag = (ziel - best_start).days + 1
    if tag > 40:
        return None, None
    return tag, zyklusphase(tag)


def build_report(cycle_starts, symptoms_wl, oura_ci, stress, symptome, pem, d_from, d_to):
    if not cycle_starts:
        return "Keine Zyklusdaten im angefragten Zeitraum."

    # Cyclelängen aus aufeinanderfolgenden Starts
    lengths = []
    for i in range(1, len(cycle_starts)):
        try:
            a = datetime.fromisoformat(cycle_starts[i - 1]).date()
            b = datetime.fromisoformat(cycle_starts[i]).date()
            diff = (b - a).days
            if 15 <= diff <= 60:
                lengths.append(diff)
        except ValueError:
            pass

    n_zyklen = len(lengths)
    avg_len  = round(sum(lengths) / n_zyklen, 1) if lengths else None
    min_len  = min(lengths) if lengths else None
    max_len  = max(lengths) if lengths else None
    std_len  = round((sum((v - avg_len) ** 2 for v in lengths) / n_zyklen) ** 0.5, 1) \
               if lengths else None

    n_kurz  = sum(1 for v in lengths if v < 24)   # FIGO 2018: kurz < 24 Tage
    n_lang  = sum(1 for v in lengths if v > 38)   # FIGO 2018: lang > 38 Tage

    # HRV/Energie/PEM nach Phase
    phasen_hrv  = defaultdict(list)
    phasen_sym  = defaultdict(list)
    phasen_pem  = defaultdict(list)
    all_dates = set(list(stress.keys()) + list(symptome.keys()))
    for d in sorted(all_dates):
        tag, phase = datum_zu_zyklusdaten(cycle_starts, d)
        if phase is None:
            continue
        if d in stress and stress[d].get("hrv"):
            phasen_hrv[phase].append(stress[d]["hrv"])
        if d in symptome:
            phasen_sym[phase].append(symptome[d])
        if d in pem:
            phasen_pem[phase].append(pem[d])

    # WomanLog-Symptomhäufigkeit
    sym_count = defaultdict(int)
    for _, sym in symptoms_wl:
        sym_count[sym] += 1

    # Oura risk levels
    oura_risk = defaultdict(int)
    for _, _, _, _, risk in oura_ci:
        if risk:
            oura_risk[risk] += 1

    lines = [
        f"## Zyklus- & HRV-Analyse — {d_from} bis {d_to}\n",
        f"Zyklusstarts: **{len(cycle_starts)}**  |  Auswertbare Längen: {n_zyklen}\n",
    ]

    if lengths:
        lines += [
            "### Zykluslängen\n",
            f"  Ø Länge: **{avg_len} Tage**  |  SD: {std_len}  |  "
            f"Min: {min_len}  |  Max: {max_len}",
            f"  Kurze Zyklen (<24 Tage, FIGO 2018): {n_kurz}  |  Lange Zyklen (>38 Tage, FIGO 2018): {n_lang}",
        ]

        # Trend Cyclelänge (erste vs. letzte 20%)
        q = max(2, n_zyklen // 5)
        avg_early = round(sum(lengths[:q]) / q, 1)
        avg_late  = round(sum(lengths[-q:]) / q, 1)
        delta = round(avg_late - avg_early, 1)
        lines.append(f"  Trend: {delta:+.1f} Tage (frühe Ø {avg_early} → späte Ø {avg_late})")

    lines.append("\n### HRV nach Zyklusphase\n")
    lines.append(f"  {'Phase':<16} {'Ø HRV':>7} {'Ø Energie':>10} {'Ø PEM':>8} {'n':>5}")
    lines.append("  " + "-" * 50)
    for phase in ["Menstruation", "Follikulär", "Ovulation", "Luteal"]:
        hrv_v = phasen_hrv[phase]
        sym_v = phasen_sym[phase]
        pem_v = phasen_pem[phase]
        avg_hrv = round(sum(hrv_v) / len(hrv_v), 1) if hrv_v else None
        avg_sym = round(sum(sym_v) / len(sym_v), 1) if sym_v else None
        avg_pem = round(sum(pem_v) / len(pem_v), 1) if pem_v else None
        lines.append(
            f"  {phase:<16} "
            f"{str(avg_hrv) + ' ms' if avg_hrv else 'n.a.':>7} "
            f"{str(avg_sym) if avg_sym else 'n.a.':>10} "
            f"{str(avg_pem) if avg_pem else 'n.a.':>8} "
            f"{len(hrv_v):>5}"
        )

    if sym_count:
        lines.append("\n### WomanLog-Symptome (häufigste)\n")
        for sym, cnt in sorted(sym_count.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"  {sym:<30} {cnt:>4}×")

    if oura_risk:
        lines.append("\n### Oura Fertilitäts-Risiko\n")
        for risk, cnt in sorted(oura_risk.items(), key=lambda x: -x[1]):
            lines.append(f"  {risk:<12} {cnt:>4} Tage")

    return "\n".join(lines)


def _plot(cycle_starts, stress, symptome, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), facecolor="#1e1e2e")
    fig.suptitle(f"Zyklus & HRV {d_from}–{d_to}", color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # Cyclelängen-Timeline
    lengths, dts_cyc = [], []
    for i in range(1, len(cycle_starts)):
        try:
            a = datetime.fromisoformat(cycle_starts[i - 1]).date()
            b = datetime.fromisoformat(cycle_starts[i]).date()
            diff = (b - a).days
            if 15 <= diff <= 60:
                lengths.append(diff)
                dts_cyc.append(datetime.fromisoformat(cycle_starts[i]))
        except ValueError:
            pass

    if dts_cyc:
        axes[0].scatter(dts_cyc, lengths, color="#fd79a8", s=25, alpha=0.8, zorder=3)
        if len(lengths) >= 5:
            ma = [sum(lengths[max(0,i-4):i+1])/len(lengths[max(0,i-4):i+1]) for i in range(len(lengths))]
            axes[0].plot(dts_cyc, ma, color="#e84393", lw=1.5, label="5-Zyklus-Ø")
        axes[0].axhline(28, color="#fdcb6e", lw=0.8, ls="--", alpha=0.5, label="28 Tage")
        axes[0].set_ylabel("Zykluslänge (Tage)", color="#ccc", fontsize=9)
        axes[0].set_ylim(15, 50)
        axes[0].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    # HRV-Verlauf with Cyclestart-Markierungen
    stress_dates = sorted(stress.keys())
    hrv_dts  = [datetime.fromisoformat(d) for d in stress_dates if stress[d].get("hrv")]
    hrv_vals = [stress[d]["hrv"] for d in stress_dates if stress[d].get("hrv")]
    if hrv_dts:
        axes[1].plot(hrv_dts, hrv_vals, color="#a29bfe", lw=1.0, alpha=0.7)
        for cs in cycle_starts:
            try:
                axes[1].axvline(datetime.fromisoformat(cs), color="#fd79a8",
                                lw=0.5, alpha=0.4)
            except ValueError:
                pass
        axes[1].set_ylabel("HRV RMSSD (ms)", color="#ccc", fontsize=9)
        axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"cycle_hrv_{ts}.png"
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
    out = OUT_DIR / f"cycle_hrv_{ts}.md"
    content = f"# Zyklus- & HRV-Analyse\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("Zyklus- & HRV-Analyse", "Cycle & HRV analysis"))
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
    cycle_starts, symptoms_wl, oura_ci, stress, symptome, pem = \
        load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not cycle_starts:
        print("Keine Zyklusdaten. Zuerst: python3 importers/import_womanlog.py")
        return

    print(f"Zyklusstarts: {len(cycle_starts)}  |  Stress-Tage: {len(stress)}")

    report = build_report(cycle_starts, symptoms_wl, oura_ci,
                               stress, symptome, pem, args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(cycle_starts, stress, symptome, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
