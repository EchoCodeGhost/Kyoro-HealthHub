#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Cyclephase × Sleepqualität × Body temperature

Untersucht, wie Cyclephase with Sleep and Body temperature zusammenhängt.

Datenquellen:
  - oura_cycle_insights: Phasenzuordnung (aktuell)
  - womanlog_cycles: historische Cyclestarts → Phasenschätzung
  - sleep_cycle_full: Sleepqualität, Body temperature-Abweichung
  - oura_sleep: Sleepdauer, Effizienz, Temperatur-Abweichung (aktuell)
  - oura_readiness: Body temperature

Methode:
  - 4 Phasen: Menstruation (T1-5), Follikel (T6-13), Ovulation (T14), Luteal (T15-28)
  - Kruskal-Wallis-Test (nicht-parametrisch)

Usage:
  python analyse_cycle_sleep.py --plot
  python analyse_cycle_sleep.py --zyklus-laenge 28 --plot

@tier        heuristic
@refs        Shechter A, Boivin DB (2010). Sleep, Hormones, and Circadian Rhythms throughout the Menstrual Cycle in Healthy Women and Women with Premenstrual Dysphoric Disorder. International Journal of Endocrinology, 2010:259345. doi:10.1155/2010/259345
             de Zambotti M, Baker FC, Colrain IM (2015). Validation of Sleep-Tracking Technology Compared with Polysomnography in Adolescents. Sleep, 38(9):1461-1468. doi:10.5665/sleep.4990

@relevance.de  Untersucht den Einfluss des Menstruationszyklus auf Schlafqualität und zirkadiane Rhythmen, essentiell für die Erkennung zyklusbedingter Schlafstörungen und die Optimierung der Schlafhygiene
@relevance.en  Examines the influence of the menstrual cycle on sleep quality and circadian rhythms, essential for identifying cycle-related sleep disorders and optimizing sleep hygiene
@purpose.de  Untersucht den Zusammenhang zwischen Zyklusphase, Schlafqualität und
             Körpertemperatur mittels Kruskal-Wallis-Test und Gruppenvergleich
             über 4 Zyklusphasen.
@purpose.en  Investigates the association between cycle phase, sleep quality and body
             temperature using Kruskal-Wallis test and group comparison across 4 cycle phases.
@method.de   Phasenzuordnung aus oura_cycle_insights (bevorzugt) oder WomanLog-Schätzung
             (feste Taggrenzen). Kruskal-Wallis-Test (nicht-parametrisch) für Gruppenunterschiede.
             Keine klinisch validierten Schwellen für phasenbezogene Schlafunterschiede.
@method.en   Phase assignment from oura_cycle_insights (preferred) or WomanLog estimation
             (fixed day boundaries). Kruskal-Wallis test (non-parametric) for group differences.
             No clinically validated thresholds for phase-specific sleep differences.
@limits.de   Heuristische Methode: Phasenzuordnung aus Wearable ist approximativ. Schlafquelle variiert je
             Datenverfügbarkeit. Keine Hormonmessungen zur Phasenbestätigung. n=1.
@limits.en   Heuristic method: Phase assignment from wearable is approximate. Sleep source varies by data
             availability. No hormone measurements to confirm phases. n=1.
@scoring
    Phase assignment: menstruation day 1-5 | follicular day 6-13 | ovulation day 14 | luteal day 15-28
    Statistical test: Kruskal-Wallis (non-parametric group comparison)
@reads       oura_cycle_insights, womanlog_cycles, sleep_cycle_full, oura_sleep,
             oura_readiness
@writes      analyses/cycle/*.{md,png} (kein DB-Write)

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_cycle_sleep.py
    python analyse_cycle_sleep.py --help
    python analyse_cycle_sleep.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime, timedelta
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
    SYSTEM_PROMPT_ANALYSE_CYCLE_SLEEP_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_CYCLE_SLEEP_EN as SYSTEM_PROMPT_EN,
)


def phasen_label(tag_im_zyklus, zyklus_laenge=28):
    """Cyclephase aus day im Cycle schätzen."""
    if tag_im_zyklus <= 0:
        return None
    if tag_im_zyklus <= 5:
        return "Menstruation"
    if tag_im_zyklus <= 13:
        return "Follikelphase"
    ovulation_day = round(zyklus_laenge * 14 / 28)
    if tag_im_zyklus == ovulation_day:
        return "Ovulation"
    if tag_im_zyklus <= zyklus_laenge:
        return "Lutealphase"
    return None


def load_oura_phases(conn):
    """Direkte Phasendaten aus oura_cycle_insights."""
    rows = conn.execute("""
        SELECT day, cycle_phase, day_of_cycle
        FROM oura_cycle_insights
        WHERE cycle_phase IS NOT NULL AND cycle_phase != ''
        ORDER BY day
    """).fetchall()
    mapping = {}
    for d, phase, doc in rows:
        if phase:
            mapping[d] = OURA_PHASE_MAP.get(phase.lower(), phase)
    return mapping


def load_womanlog_phases(conn, zyklus_laenge):
    """Cyclestart-Daten → Phasenschätzung for all Folgetage."""
    rows = conn.execute(
        "SELECT date, duration_days FROM womanlog_cycles ORDER BY date"
    ).fetchall()

    mapping = {}
    for i, (start_str, dur) in enumerate(rows):
        start = datetime.strptime(start_str, "%Y-%m-%d")
        length = dur if dur else zyklus_laenge
        # Fülle jeden day dieses Cycle with der geschätzten Phase
        for tag in range(1, length + 1):
            d = (start + timedelta(days=tag - 1)).strftime("%Y-%m-%d")
            mapping[d] = phasen_label(tag, length)
    return mapping


def load_sleep_data(conn, d_from, d_to):
    """Sleep Cycle Daten."""
    rows = conn.execute("""
        SELECT date, quality_pct, body_temp_dev, time_asleep_s
        FROM sleep_cycle_full
        WHERE date >= ? AND date <= ?
          AND quality_pct IS NOT NULL
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    return {r[0]: {"quality": r[1], "temp_dev": r[2], "sleep_s": r[3]} for r in rows}


def load_oura_sleep(conn, d_from, d_to):
    """Oura Schlafdaten (if vorhanden and nicht vollständig NULL)."""
    rows = conn.execute("""
        SELECT date, efficiency_pct, sleep_duration_s, temp_deviation
        FROM oura_sleep
        WHERE date >= ? AND date <= ?
          AND (efficiency_pct IS NOT NULL
               OR sleep_duration_s IS NOT NULL
               OR temp_deviation IS NOT NULL)
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    return {r[0]: {"efficiency": r[1], "sleep_s": r[2], "temp_dev": r[3]} for r in rows}


def _kruskal_wallis(gruppen):
    """Kruskal-Wallis-Test über scipy."""
    try:
        from scipy.stats import kruskal
        nicht_leer = [g for g in gruppen if len(g) >= 3]
        if len(nicht_leer) < 2:
            return None, None
        stat, p = kruskal(*nicht_leer)
        return round(stat, 2), round(p, 4)
    except Exception:
        return None, None


PHASEN_ORDER = ["Menstruation", "Follikelphase", "Ovulation", "Lutealphase"]

OURA_PHASE_MAP = {
    "menstrual":  "Menstruation",
    "follicular": "Follikelphase",
    "ovulation":  "Ovulation",
    "luteal":     "Lutealphase",
}


def build_report(phase_dict, schlaf_dict, oura_schlaf_dict, zyklus_laenge):
    # Kombiniere all Sourcen: Phasen + Schlafdaten
    phase_schlaf = {}
    for d, phase in phase_dict.items():
        if phase not in PHASEN_ORDER:
            continue
        if d in schlaf_dict:
            phase_schlaf.setdefault(phase, []).append(
                (schlaf_dict[d]["quality"],
                 schlaf_dict[d]["temp_dev"],
                 schlaf_dict[d]["sleep_s"])
            )
        elif d in oura_schlaf_dict:
            o = oura_schlaf_dict[d]
            phase_schlaf.setdefault(phase, []).append(
                (o["efficiency"], o["temp_dev"], o["sleep_s"])
            )

    n_total = sum(len(v) for v in phase_schlaf.values())

    lines = [
        "## Zyklusphase × Schlaf × Körpertemperatur\n",
        f"Datenpunkte: {n_total} Nächte mit Phasenzuordnung",
        f"Zykluslänge (Schätzung): {zyklus_laenge} Tage\n",
    ]

    if n_total < 20:
        lines.append(f"⚠️  Nur {n_total} Nächte mit Phasenzuordnung.")
        lines.append("    Mehr Daten durch Oura Ring über Zeit — Analyse wird valider.\n")

    # Pro Phase: Meane + N
    lines.append("### Schlafqualität pro Phase")
    quality_by_phase = []
    for phase in PHASEN_ORDER:
        vals = phase_schlaf.get(phase, [])
        qualities = [v[0] for v in vals if v[0] is not None]
        quality_by_phase.append(qualities)
        if qualities:
            m = sum(qualities) / len(qualities)
            bar = "█" * int(m / 5)
            lines.append(f"  {phase:<16} n={len(qualities):>3}  ∅{m:4.0f}%  {bar}")
        else:
            lines.append(f"  {phase:<16} n=  0  (keine Daten)")

    kw_stat, kw_p = _kruskal_wallis(quality_by_phase)
    if kw_stat is not None:
        lines.append(f"  Kruskal-Wallis: H={kw_stat}, p={kw_p} "
                     f"{'✅ signifikant' if kw_p < 0.05 else '(nicht signifikant)'}")
    lines.append("")

    lines.append("### Schlafdauer pro Phase")
    sleep_by_phase = []
    for phase in PHASEN_ORDER:
        vals = phase_schlaf.get(phase, [])
        sleeps = [v[2] / 3600 for v in vals if v[2] is not None and v[2] > 0]
        sleep_by_phase.append(sleeps)
        if sleeps:
            m = sum(sleeps) / len(sleeps)
            lines.append(f"  {phase:<16} ∅{m:.1f}h")
        else:
            lines.append(f"  {phase:<16} (keine Daten)")

    kw_stat2, kw_p2 = _kruskal_wallis(sleep_by_phase)
    if kw_stat2 is not None:
        lines.append(f"  Kruskal-Wallis: H={kw_stat2}, p={kw_p2} "
                     f"{'✅ signifikant' if kw_p2 < 0.05 else '(nicht signifikant)'}")
    lines.append("")

    lines.append("### Körpertemperatur-Abweichung pro Phase")
    temp_by_phase = []
    for phase in PHASEN_ORDER:
        vals = phase_schlaf.get(phase, [])
        temps = [v[1] for v in vals if v[1] is not None]
        temp_by_phase.append(temps)
        if temps:
            m = sum(temps) / len(temps)
            direction = "↑ erhöht" if m > 0.1 else "↓ erniedrigt" if m < -0.1 else "neutral"
            lines.append(f"  {phase:<16} ∅{m:+.2f}°C  {direction}")
        else:
            lines.append(f"  {phase:<16} (keine Daten)")

    kw_stat3, kw_p3 = _kruskal_wallis(temp_by_phase)
    if kw_stat3 is not None:
        lines.append(f"  Kruskal-Wallis: H={kw_stat3}, p={kw_p3} "
                     f"{'✅ signifikant' if kw_p3 < 0.05 else '(nicht signifikant)'}")
    lines.append("")

    return "\n".join(lines)


def _plot(phase_dict, schlaf_dict, oura_schlaf_dict):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Sammle Daten pro Phase
        phase_data = {p: {"quality": [], "temp": [], "sleep_h": []}
                      for p in PHASEN_ORDER}
        for d, phase in phase_dict.items():
            if phase not in PHASEN_ORDER:
                continue
            src = schlaf_dict.get(d) or oura_schlaf_dict.get(d)
            if src:
                q = src.get("quality") or src.get("efficiency")
                t = src.get("temp_dev")
                s = src.get("sleep_s")
                if q:  phase_data[phase]["quality"].append(q)
                if t:  phase_data[phase]["temp"].append(t)
                if s:  phase_data[phase]["sleep_h"].append(s / 3600)

        phase_colors = {
            "Menstruation":  "#E84855",
            "Follikelphase": "#4A90D9",
            "Ovulation":     "#57A773",
            "Lutealphase":   "#F4A261",
        }

        fig, axes = plt.subplots(1, 3, figsize=(15, 6), facecolor="#1A1A2E")
        fig.suptitle("Zyklusphase × Schlaf × Körpertemperatur", color="#E0E0E0", fontsize=12)

        metrics = [
            ("quality", "Schlafqualität (%)", "Schlafqualität"),
            ("sleep_h", "Schlafdauer (h)", "Schlafdauer"),
            ("temp", "Temperatur-Abweichung (°C)", "Körpertemperatur"),
        ]

        for idx, (key, ylabel, title) in enumerate(metrics):
            ax = axes[idx]
            ax.set_facecolor("#16213E")

            positions = []
            labels = []
            has_data = False
            for i, phase in enumerate(PHASEN_ORDER):
                vals = phase_data[phase][key]
                if vals:
                    ax.boxplot(vals, positions=[i], widths=0.6,
                                    patch_artist=True, notch=False,
                                    boxprops=dict(facecolor=phase_colors[phase], alpha=0.7),
                                    medianprops=dict(color="#E0E0E0", linewidth=2),
                                    whiskerprops=dict(color="#8B8B8B"),
                                    capprops=dict(color="#8B8B8B"),
                                    flierprops=dict(marker=".", color="#8B8B8B", alpha=0.5))
                    has_data = True
                positions.append(i)
                labels.append(phase[:6])

            if not has_data:
                ax.text(0.5, 0.5, "Keine\nDaten", transform=ax.transAxes,
                        ha="center", va="center", color="#E0E0E0", fontsize=10)

            ax.set_xticks(range(len(PHASEN_ORDER)))
            ax.set_xticklabels([p[:6] for p in PHASEN_ORDER], color="#E0E0E0", fontsize=7)
            ax.set_ylabel(ylabel, color="#E0E0E0", fontsize=8)
            ax.set_title(title, color="#E0E0E0", fontsize=9)
            ax.tick_params(colors="#E0E0E0", labelsize=7)
            for s in ax.spines.values():
                s.set_color("#8B8B8B")

            if key == "temp":
                ax.axhline(0, color="#8B8B8B", linewidth=0.8, linestyle="--", alpha=0.5)

        fig.tight_layout()
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUT_DIR / f"cycle_sleep_{ts}.png"
        fig.savefig(str(path), dpi=130, bbox_inches="tight", facecolor="#1A1A2E")
        plt.close()
        print(f"Plot: {path}")
    except Exception as e:
        print(f"Plot fehlgeschlagen: {e}")


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=2000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text=""):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"cycle_sleep_{ts}.md"
    content = f"# Zyklusphase × Schlaf × Körpertemperatur\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("Zyklusphase × Schlaf × Temperatur", "Cycle phase × sleep × temperature"))
    parser.add_argument("--from",           dest="date_from",     default=(datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d"))
    parser.add_argument("--to",             dest="date_to",       default=str(datetime.today().date()))
    parser.add_argument("--all",            dest="all_data",      action="store_true",
                        help=t("Alle verfügbaren Daten (überschreibt --from/--to)",
                               "All available data (overrides --from/--to)"))
    parser.add_argument("--zyklus-laenge",  dest="zyklus_laenge", type=int, default=28,
                        help="Typische Zykluslänge in Tagen (Default: 28)")
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)
    if args.all_data:
        args.date_from = _cfg.data_start or "1900-01-01"
        args.date_to   = datetime.today().strftime("%Y-%m-%d")

    conn = open_db()

    # Phasenzuordnung: Oura hat Vorrang, then womanlog-Schätzung
    oura_phasen    = load_oura_phases(conn)
    womanlog_phasen = load_womanlog_phases(conn, args.zyklus_laenge)
    schlaf_dict    = load_sleep_data(conn, args.date_from, args.date_to)
    oura_schlaf    = load_oura_sleep(conn, args.date_from, args.date_to)
    conn.close()

    # Kombiniere: Oura überschreibt womanlog-Schätzung
    phase_dict = {**womanlog_phasen, **oura_phasen}

    n_phasen = sum(1 for d, p in phase_dict.items()
                   if p in PHASEN_ORDER and (d in schlaf_dict or d in oura_schlaf))
    print(f"Phasenzuordnungen total: {len(phase_dict)}")
    print(f"  davon mit Schlafdaten: {n_phasen}")
    print(f"  Oura-Phasen (direkt):  {len(oura_phasen)}")
    print(f"  WomanLog (geschätzt):  {len(womanlog_phasen)}")

    report = build_report(phase_dict, schlaf_dict, oura_schlaf, args.zyklus_laenge)
    print("\n" + report)

    if args.plot:
        _plot(phase_dict, schlaf_dict, oura_schlaf)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
