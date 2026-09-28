#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Sitzverhalten & Bewegungsunterbrechungen

Analysiert das tägliche Steh- and Bewegungsverhalten aus Apple Watch-Daten
(Stand-hours pro day, Stehzeit in minutes) sowie Polar-Aktivitätslevel.
Langes Sitzen ist ein unabhängiger kardiovaskulärer Risikofaktor; das Verhältnis
von Ruhe und Aktivität ist für Personen mit eingeschränkter Belastungstoleranz besonders relevant.

@tier        heuristic
@refs        Biswas A, Oh PI, Faulkner GE et al. (2015). Sedentary Time and Its Association With Risk for Disease Incidence, Mortality, and Hospitalization in Adults. Annals of Internal Medicine, 162(2):123-132. doi:10.7326/M14-1651
             Healy GN, Dunstan DW, Salmon J, Cerin E, Shaw JE, Zimmet PZ, Owen N (2008). Breaks in Sedentary Time: Beneficial Associations With Metabolic Risk. Diabetes Care, 31(4):661-666. doi:10.2337/dc07-2046

@relevance.de  Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse
@relevance.en  Enables activity data analysis, essential for movement and fitness analysis
@purpose.de  Analysiert tägliches Steh- und Sitzverhalten aus Apple Watch (Stand-Stunden, Stehzeit) und Polar-Aktivitätslevel sowie deren Korrelation mit Folgetag-HRV.
@purpose.en  Analyses daily standing and sitting behaviour from Apple Watch (stand hours, standing time) and Polar activity levels and their correlation with next-day HRV.
@method.de   Aggregation von stand_hour (Apple Health) und stand_time_min; Spearman-Rangkorrelation mit HRV; eigener Zielwert: ≥12 Stand-Stunden/Tag (Apple Watch Kriterium).
@method.en   Aggregation of stand_hour (Apple Health) and stand_time_min; Spearman rank correlation with HRV; custom target: ≥12 stand hours/day (Apple Watch criterion).
@limits.de   Heuristische Methode: Schwellenwert 12 Stand-Stunden basiert auf Apple Watch Produktdefinition, nicht auf klinischen Studien. Keine adjustierten Zielwerte für Personen mit Belastungsintoleranz.
@limits.en   Heuristic method: Threshold of 12 stand hours follows Apple Watch product definition, not clinical studies. No adjusted targets for persons with exercise intolerance.
@scoring
    Stand goal: >=12 stand-hours/day (Apple Watch criterion). Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
@reads       measurements
@writes      analyses/activity/*.{md,png}

Usage:
  python analyse_sedentary.py --plot
  python analyse_sedentary.py --from YYYY-MM-DD --plot
  python analyse_sedentary.py --plot --no-llm

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_sedentary.py
    python analyse_sedentary.py --help
    python analyse_sedentary.py --from 2024-01-01 --to 2024-12-31
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
from modules.prompts.analysis_activity import (
    SYSTEM_PROMPT_ANALYSE_SEDENTARY_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_SEDENTARY_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "activity"

ZIEL_STAND_STUNDEN = 12


def spearman_r(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    n = len(pairs)
    def ranks(vals):
        sv = sorted(range(n), key=lambda i: vals[i])
        r = [0] * n
        for rank, idx in enumerate(sv, 1):
            r[idx] = rank
        return r
    xv, yv = zip(*pairs)
    rx, ry = ranks(list(xv)), ranks(list(yv))
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return round(1 - 6 * d2 / (n * (n ** 2 - 1)), 3)


def load_data(conn, d_from, d_to):
    # Stand-hours pro day (0/1 pro Stunde, SUM = erreichte Stand-hours).
    # Ein Werksreset derselben Apple Watch kann dazu führen, dass sie sich
    # neu koppelt und fortan unter einer anderen device_id-Pseudonym-ID
    # läuft — Apple Health meldet dieselbe Stunde dann kurzzeitig unter
    # zwei device_ids (keine zwei physischen Geräte). Daher zuerst auf
    # einen Wert pro ts kollabieren (MAX, da stand_hour ohnehin 0/1 ist),
    # sonst wird dieselbe Stand-Stunde doppelt gezählt.
    stand_h = conn.execute("""
        SELECT date, SUM(value) AS stand_stunden FROM (
            SELECT date, ts, MAX(value) AS value
            FROM measurements
            WHERE metric = 'stand_hour'
              AND source_app = 'apple_health'
              AND date >= ? AND date <= ?
              AND value IS NOT NULL
            GROUP BY ts
        )
        GROUP BY date ORDER BY date
    """, (d_from, d_to)).fetchall()

    # Stehzeit in minutes pro day — dieselbe Dedupe-Logik wie oben.
    stand_min = conn.execute("""
        SELECT date, SUM(value) AS steh_min FROM (
            SELECT date, ts, MAX(value) AS value
            FROM measurements
            WHERE metric = 'stand_time'
              AND source_app = 'apple_health'
              AND date >= ? AND date <= ?
              AND value IS NOT NULL
            GROUP BY ts
        )
        GROUP BY date ORDER BY date
    """, (d_from, d_to)).fetchall()

    # Stündliches Steh-Profil (Tageszeit)
    stand_hourly = conn.execute("""
        SELECT CAST(SUBSTR(ts, 12, 2) AS INTEGER) AS stunde, AVG(value) FROM (
            SELECT ts, MAX(value) AS value
            FROM measurements
            WHERE metric = 'stand_hour'
              AND source_app = 'apple_health'
              AND date >= ? AND date <= ?
              AND value IS NOT NULL
            GROUP BY ts
        )
        GROUP BY stunde ORDER BY stunde
    """, (d_from, d_to)).fetchall()

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    # Polar Aktivitätslevel — not available in v2; skip gracefully
    polar_activity = []

    # Daily HRV for correlation
    stress = {}
    if "daily_stress" in tables:
        for d, rmssd, *_ in conn.execute("""
            SELECT date, rmssd_ms FROM daily_stress WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            stress[d] = rmssd

    # Symptoms (Energie/Ressourcen)
    symptome = {}
    if "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND category='Ressourcen' AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert
    elif "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND category='Ressourcen' AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert

    return stand_h, stand_min, stand_hourly, polar_activity, stress, symptome


def build_report(stand_h, stand_min, stand_hourly, polar_activity,
                     stress, symptome, d_from, d_to):
    if not stand_h and not polar_activity:
        return "No Sitzverhaltensdaten im angefragten Time range."

    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

    lines = [f"## Sitzverhalten & Bewegungsunterbrechungen — {d_from} bis {d_to}\n"]

    # Apple Watch Stand-hours
    if stand_h:
        steh_vals = [r[1] for r in stand_h if r[1] is not None]
        n = len(stand_h)
        n_ziel    = sum(1 for v in steh_vals if v >= ZIEL_STAND_STUNDEN)
        n_niedrig = sum(1 for v in steh_vals if v < 6)

        lines += [
            f"### Apple Watch Stand-hours (n={n} days)\n",
            f"  Time range: {stand_h[0][0]} – {stand_h[-1][0]}",
            f"  Ø Stand-hours/day: **{avg(steh_vals)}**",
            f"  Ziel ≥{ZIEL_STAND_STUNDEN}h erreicht: {n_ziel} days ({round(n_ziel/n*100,1)}%)",
            f"  Sehr wenig (<6h):    {n_niedrig} days ({round(n_niedrig/n*100,1)}%)",
        ]

        # Monatsmittel
        by_month = defaultdict(list)
        for r in stand_h:
            if r[1] is not None and r[0]:
                by_month[r[0][:7]].append(r[1])
        if len(by_month) >= 2:
            lines.append("\n  Monatsmittel Stand-hours:")
            for ym in sorted(by_month):
                a = avg(by_month[ym])
                bar = "█" * int(a)
                lines.append(f"    {ym}  {a:>5.1f}h  {bar}")

    # Stehzeit in minutes
    if stand_min:
        min_vals = [r[1] for r in stand_min if r[1] is not None]
        lines += [
            f"\n### Stehzeit (n={len(stand_min)} days)\n",
            f"  Ø Stehzeit/day: **{avg(min_vals)} min**",
            f"  Maximum:        {max(min_vals):.0f} min",
            f"  Minimum:        {min(min_vals):.0f} min",
        ]

    # Tageszeit-Profile
    if stand_hourly:
        peak_h = max(stand_hourly, key=lambda x: x[1] or 0)
        low_h  = min(stand_hourly, key=lambda x: x[1] or 1)
        lines += [
            "\n### Tageszeit-Profile (Stand-Wahrscheinlichkeit)\n",
            f"  Aktivste Stande:  {peak_h[0]:02d}:00 Uhr (Ø {peak_h[1]*100:.0f}%)",
            f"  Ruhigste Stande:  {low_h[0]:02d}:00 Uhr (Ø {low_h[1]*100:.0f}%)",
        ]

    # Polar Aktivitätslevel
    if polar_activity:
        n_p = len(polar_activity)
        sed_h  = [r[1] / 3600 for r in polar_activity if r[1]]
        light_h = [r[2] / 3600 for r in polar_activity if r[2]]
        mod_h   = [r[3] / 3600 for r in polar_activity if r[3]]
        vig_h   = [r[4] / 3600 for r in polar_activity if r[4]]
        met_vals = [r[6] for r in polar_activity if r[6]]

        lines += [
            f"\n### Polar Aktivitätslevel (n={n_p} days)\n",
            f"  Time range: {polar_activity[0][0]} – {polar_activity[-1][0]}",
        ]
        if sed_h:
            lines.append(f"  Ø Sitzen/Liegen:   {avg(sed_h)} h/day")
        if light_h:
            lines.append(f"  Ø Leichte Aktivität: {avg(light_h)} h/day")
        if mod_h:
            lines.append(f"  Ø Morate Aktivität: {avg(mod_h)} h/day")
        if vig_h:
            lines.append(f"  Ø Intensive Aktivität: {avg(vig_h)} h/day")
        if met_vals:
            lines.append(f"  Ø MET-minutes:     {avg(met_vals)}")

    # Correlationen
    if stand_h and stress:
        dates_s = [r[0] for r in stand_h]
        steh_x  = [r[1] for r in stand_h]
        hrv_y   = [stress.get(d) for d in dates_s]
        sym_y   = [symptome.get(d) for d in dates_s]
        r_s_hrv = spearman_r(steh_x, hrv_y)
        r_s_sym = spearman_r(steh_x, sym_y)
        if r_s_hrv or r_s_sym:
            lines += [
                "\n### Correlation Stand-hours × (Spearman r)\n",
                f"  × HRV RMSSD:  {r_s_hrv if r_s_hrv else 'n.a.'}",
                f"  × Energie:    {r_s_sym if r_s_sym else 'n.a.'}",
            ]

    return "\n".join(lines)


def _plot(stand_h, stand_min, stand_hourly, polar_activity, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(2, 2, figsize=(14, 8), facecolor="#1e1e2e")
    fig.suptitle(f"Sitzverhalten & Aktivitätslevel {d_from}–{d_to}",
                 color="#E0E0E0", fontsize=13)
    axes_flat = axes.flatten()
    for ax in axes_flat:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # Panel 0: Stand-hours Timeline
    if stand_h:
        dts  = [datetime.fromisoformat(r[0]) for r in stand_h if r[1] is not None]
        vals = [r[1] for r in stand_h if r[1] is not None]
        if dts:
            colors = ["#2ecc71" if v >= ZIEL_STAND_STUNDEN else
                      "#fdcb6e" if v >= 8 else "#e17055" for v in vals]
            axes_flat[0].bar(dts, vals, color=colors, alpha=0.75, width=0.8)
            axes_flat[0].axhline(ZIEL_STAND_STUNDEN, color="#2ecc71", lw=0.8, ls="--",
                                 alpha=0.6, label=f"Ziel {ZIEL_STAND_STUNDEN}h")
            if len(vals) >= 14:
                ma14 = [sum(vals[max(0, i-13):i+1]) / len(vals[max(0, i-13):i+1])
                        for i in range(len(vals))]
                axes_flat[0].plot(dts, ma14, color="#f7b731", lw=1.5, label="14-days-Ø")
            axes_flat[0].set_title("Stand-hours pro day", color="#ccc", fontsize=9)
            axes_flat[0].set_ylabel("hours", color="#ccc", fontsize=9)
            axes_flat[0].legend(fontsize=7, facecolor="#2a2a3e", labelcolor="white")
            axes_flat[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Panel 1: Tageszeit-Profile
    if stand_hourly:
        hours = [r[0] for r in stand_hourly]
        vals  = [r[1] * 100 for r in stand_hourly]
        axes_flat[1].bar(hours, vals, color="#74b9ff", alpha=0.85)
        axes_flat[1].set_title("Stand-Wahrscheinlichkeit (Uhrzeit)", color="#ccc", fontsize=9)
        axes_flat[1].set_ylabel("Ø Stehquote (%)", color="#ccc", fontsize=9)
        axes_flat[1].set_xticks(range(0, 24, 2))
        axes_flat[1].set_xticklabels([f"{h}" for h in range(0, 24, 2)], fontsize=7)
        axes_flat[1].set_ylim(0, 100)

    # Panel 2: Stehzeit in minutes
    if stand_min:
        dts  = [datetime.fromisoformat(r[0]) for r in stand_min if r[1] is not None]
        vals = [r[1] for r in stand_min if r[1] is not None]
        if dts:
            axes_flat[2].plot(dts, vals, color="#a29bfe", lw=1.0, alpha=0.8)
            if len(vals) >= 7:
                ma7 = [sum(vals[max(0, i-6):i+1]) / len(vals[max(0, i-6):i+1])
                       for i in range(len(vals))]
                axes_flat[2].plot(dts, ma7, color="#f7b731", lw=1.5, label="7-days-Ø")
            axes_flat[2].set_title("Stehzeit (minutes/day)", color="#ccc", fontsize=9)
            axes_flat[2].set_ylabel("minutes", color="#ccc", fontsize=9)
            axes_flat[2].legend(fontsize=7, facecolor="#2a2a3e", labelcolor="white")
            axes_flat[2].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Panel 3: Polar Aktivitätslevel gestapelt
    if polar_activity:
        valid = [(r[0], r[1], r[2], r[3], r[4]) for r in polar_activity
                 if r[1] is not None and r[1] > 0]
        if valid:
            dts  = [datetime.fromisoformat(r[0]) for r in valid]
            sed  = [r[1] / 3600 for r in valid]
            light = [r[2] / 3600 for r in valid]
            mod   = [r[3] / 3600 for r in valid]
            vig   = [r[4] / 3600 for r in valid]
            axes_flat[3].stackplot(dts, sed, light, mod, vig,
                                   labels=["Sitzen", "Leicht", "Morat", "Intensiv"],
                                   colors=["#636e72", "#74b9ff", "#fdcb6e", "#e17055"],
                                   alpha=0.7)
            axes_flat[3].set_title("Polar Aktivitätslevel (gestapelt)", color="#ccc", fontsize=9)
            axes_flat[3].set_ylabel("hours", color="#ccc", fontsize=9)
            axes_flat[3].legend(fontsize=6, facecolor="#2a2a3e", labelcolor="white",
                                loc="upper left")
            axes_flat[3].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"sedentary_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(t(f"Plot: {p}", f"Plot: {p}"))
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
    out = OUT_DIR / f"sedentary_{ts}.md"
    content = f"# Sitzverhalten & Bewegungsunterbrechungen\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


def main():
    parser = argparse.ArgumentParser(description=t("Sitzverhalten & Bewegungsunterbrechungen", "Sedentary behaviour & movement breaks"))
    parser.add_argument("--from",   dest="date_from", default=_cfg.data_start or "1900-01-01")
    parser.add_argument("--to",     dest="date_to",   default=str(datetime.today().date()))
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    stand_h, stand_min, stand_hourly, polar_activity, stress, symptome = \
        load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not stand_h and not polar_activity:
        print(t("Keine Sitzverhaltensdaten. Zuerst: python3 importers/import_apple_health.py",
                "No sedentary data. First run: python3 importers/import_apple_health.py"))
        return

    print(t(f"Stand-Stunden-Tage: {len(stand_h)}  |  Polar-Tage: {len(polar_activity)}",
            f"Stand-hours days: {len(stand_h)}  |  Polar days: {len(polar_activity)}"))
    report = build_report(stand_h, stand_min, stand_hourly, polar_activity,
                               stress, symptome, args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(stand_h, stand_min, stand_hourly, polar_activity,
              args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
