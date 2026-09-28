#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Gangbild & Neurologie (Apple Watch)

Analysiert Apple Watch Gangparameter als Langzeit-Neurofunktionsmarker:
Walking Steadiness (Gleichgewicht), Asymmetry (Seitenunterschied),
Speed (Gehgeschwindigkeit) and Step Length (Schrittlänge).

Apple Walking Steadiness: ≥75% = OK, 60–75% = Niedrig, <60% = Sehr niedrig.

Usage:
  python analyse_gait.py --plot
  python analyse_gait.py --from YYYY-MM-DD --plot
  python analyse_gait.py --plot --no-llm

@tier        heuristic
@purpose.de  Analysiert Apple Watch Gangparameter (Walking Steadiness, Asymmetry, Speed,
             Step Length) als Langzeit-Neurofunktionsmarker mit Korrelation zu HRV
             und Energie.
@purpose.en  Analyses Apple Watch gait parameters (walking steadiness, asymmetry, speed,
             step length) as long-term neurofunction markers with correlation to HRV and energy.
@method.de   Tagesdurchschnitt der Apple-Health-Metriken; Spearman-Korrelation mit
             HRV/Symptomen. Referenzwerte: Steadiness ≥ 75 % = OK (Apple-eigene Definition),
             Speed > 1,2 m/s = normal (Literatur-Referenz). Keine unabhängige Laborvalidierung.
@method.en   Daily average of Apple Health metrics; Spearman correlation with HRV/symptoms.
             Reference values: steadiness ≥ 75 % = OK (Apple's own definition), speed > 1.2 m/s
             = normal (literature reference). No independent laboratory validation.
@limits.de   Heuristische Methode: Gangparameter aus Consumer-Wearable sind weniger präzise als Ganglabor-Messungen.
             Walking Steadiness-Algorithmus ist proprietär. Konfundierung durch Aktivitätstyp
             (Spaziergang vs. Laufen). n=1.
@limits.en   Heuristic method: Gait parameters from consumer wearable are less precise than laboratory gait
             measurements. Walking steadiness algorithm is proprietary. Confounding by
             activity type (walking vs. running). n=1.
@scoring
    Walking steadiness: >=75% OK | 60-75% low | <60% very low (Apple definition)
    Walking speed: >1.2 m/s normal | 0.8-1.2 m/s borderline | <0.8 m/s community-limited
    Asymmetry: lower = better balance
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
@refs        Fritz S, Lusardi M (2009). White Paper: "Walking Speed: the Sixth Vital Sign". Journal of Geriatric Physical Therapy, 32(2):2-5. doi:10.1519/00139143-200932020-00002
             (walking speed functional limits: <0.8 m/s = community-limited)
             Bohannon RW 1997, Gait Posture 7(2):167-168 (normal comfortable speed ~1.2 m/s)

@relevance.de  Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik
@relevance.en  Enables neurological analysis, essential for nervous system diagnostics
@reads       measurements (walking_steadiness, walking_asymmetry, walking_speed,
             walking_step_length), daily_stress, symptoms
@writes      analyses/neurology/*.{md,png} (kein DB-Write)

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_gait.py
    python analyse_gait.py --help
    python analyse_gait.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
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
    SYSTEM_PROMPT_ANALYSE_GAIT_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_GAIT_EN as SYSTEM_PROMPT_EN,
)

STEADINESS_OK  = 0.75
STEADINESS_LOW = 0.60
# Asymmetrie liegt — wie Steadiness — als Bruch 0..1 vor, obwohl die unit-Spalte '%'
# sagt. Die Schwelle muss deshalb ebenfalls ein Bruch sein; ein Vergleich gegen 10
# konnte nie greifen und meldete dauerhaft null auffällige Tage.
ASYMMETRY_HIGH = 0.10


def load_data(conn, d_from, d_to):
    def apple_daily(record_type):
        # Einheiten normalisieren: Export liefert walking_speed in km/h und
        # walking_step_length in cm — auf m/s bzw. m bringen (sonst Faktor-3.6/100-Fehler).
        return conn.execute("""
            SELECT date,
                   AVG(value*f) AS avg_val, MIN(value*f) AS min_val, MAX(value*f) AS max_val
            FROM (
              SELECT date, value,
                     CASE WHEN unit IN ('km/hr','km/h') THEN 1.0/3.6
                          WHEN unit = 'cm'              THEN 0.01
                          ELSE 1.0 END AS f
              FROM measurements
              WHERE metric = ? AND source_app = 'apple_health'
                AND date >= ? AND date <= ? AND value IS NOT NULL
            )
            GROUP BY date ORDER BY date
        """, (record_type, d_from, d_to)).fetchall()

    steadiness = apple_daily("walking_steadiness")
    asymmetry  = apple_daily("walking_asymmetry")
    speed      = apple_daily("walking_speed")
    step_len   = apple_daily("walking_step_length")

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    stress = {}
    if "daily_stress" in tables:
        for d, rmssd, stress_s, sleep_h in conn.execute("""
            SELECT date, rmssd_ms, stress_score, sleep_hours FROM daily_stress
            WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            stress[d] = {"hrv": rmssd, "stress": stress_s}

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

    return steadiness, asymmetry, speed, step_len, stress, symptome


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


def build_report(steadiness, asymmetry, speed, step_len, stress, symptome, d_from, d_to):
    if not steadiness and not speed:
        return "No Gangbild-Daten im angefragten Time range."

    def avg(lst): return round(sum(lst) / len(lst), 3) if lst else None
    def pct_below(lst, thr): return round(sum(1 for v in lst if v < thr) / len(lst) * 100, 1) if lst else None

    lines = [f"## Gangbild & Neurologie — {d_from} bis {d_to}\n"]

    if steadiness:
        st_vals = [r[1] for r in steadiness if r[1]]
        a = avg(st_vals)
        n_low  = sum(1 for v in st_vals if v < STEADINESS_OK and v >= STEADINESS_LOW)
        n_sehr = sum(1 for v in st_vals if v < STEADINESS_LOW)
        klasse = "Sehr niedrig ⚠⚠" if a and a < STEADINESS_LOW else \
                 "Niedrig ⚠" if a and a < STEADINESS_OK else "OK"
        lines += [
            "### Walking Steadiness (Gleichgewicht)\n",
            f"  Ø: **{round(a*100,1) if a else 'n.a.'}%**  → Klasse: {klasse}",
            f"  Niedrig (<75%): {n_low}  |  Sehr niedrig (<60%): {n_sehr}",
        ]
        # Trend
        if len(st_vals) >= 6:
            q = len(st_vals) // 3
            delta = round((avg(st_vals[-q:]) or 0) - (avg(st_vals[:q]) or 0), 3)
            lines.append(f"  Trend: {delta:+.3f} (früh: {avg(st_vals[:q])} → spät: {avg(st_vals[-q:])})")

    if asymmetry:
        asy_vals = [r[1] for r in asymmetry if r[1] is not None]
        a = avg(asy_vals)
        n_auff = sum(1 for v in asy_vals if v > ASYMMETRY_HIGH)
        lines += [
            "\n### Walking Asymmetry (%)\n",
            f"  Ø: {round(a*100,1) if a else 'n.a.'}%  |  "
            f"Auffällig (>{ASYMMETRY_HIGH*100:.0f}%): {n_auff} days",
        ]

    if speed:
        sp_vals = [r[1] for r in speed if r[1]]
        a = avg(sp_vals)
        n_langsam = sum(1 for v in sp_vals if v < 0.8)  # Fritz & Lusardi 2009: <0.8 m/s = funktionell eingeschränkt, doi:10.1519/00139143-200932020-00002
        lines += [
            "\n### Walking Speed (m/s)\n",
            f"  Ø: {a} m/s  |  Eingeschränkt (<0.8 m/s): {n_langsam} days",
        ]

    if step_len:
        sl_vals = [r[1] for r in step_len if r[1]]
        a = avg(sl_vals)
        lines += [
            "\n### Step Length (m)\n",
            f"  Ø: {a} m",
        ]

    # Correlationen Steadiness × HRV/Energie
    if steadiness:
        dates = [r[0] for r in steadiness]
        st_x  = [r[1] for r in steadiness]
        hrv_y = [stress[d]["hrv"] if d in stress else None for d in dates]
        sym_y = [symptome.get(d) for d in dates]
        r_st_hrv = spearman_r(st_x, hrv_y)
        r_st_sym = spearman_r(st_x, sym_y)
        if any(r is not None for r in [r_st_hrv, r_st_sym]):
            lines += [
                "\n### Correlation Steadiness × (Spearman r)\n",
                f"  × HRV RMSSD: {r_st_hrv if r_st_hrv else 'n.a.'}",
                f"  × Energie:   {r_st_sym if r_st_sym else 'n.a.'}",
            ]

    return "\n".join(lines)


def _plot(steadiness, asymmetry, speed, step_len, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(2, 2, figsize=(14, 8), facecolor="#1e1e2e")
    fig.suptitle(f"Gangbild & Neurologie {d_from}–{d_to}", color="#E0E0E0", fontsize=13)
    axes_flat = axes.flatten()
    for ax in axes_flat:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    def plot_series(ax, rows, label, unit, color, hlines=None):
        dts  = [datetime.fromisoformat(r[0]) for r in rows if r[1] is not None]
        vals = [r[1] for r in rows if r[1] is not None]
        if not dts:
            return
        ax.plot(dts, vals, "o-", color=color, ms=5, lw=1.2, alpha=0.85)
        if hlines:
            for yval, col, ls in hlines:
                ax.axhline(yval, color=col, lw=0.8, ls=ls, alpha=0.6)
        ax.set_ylabel(f"{label} ({unit})", color="#ccc", fontsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    if steadiness:
        plot_series(axes_flat[0], steadiness, "Steadiness", "%", "#2ecc71",
                    [(STEADINESS_OK, "#fdcb6e", "--"), (STEADINESS_LOW, "#e17055", "--")])
        axes_flat[0].set_ylim(0.4, 1.0)

    if asymmetry:
        plot_series(axes_flat[1], asymmetry, "Asymmetry", "%", "#fd79a8",
                    [(0.10, "#fdcb6e", "--")])

    if speed:
        plot_series(axes_flat[2], speed, "Speed", "m/s", "#74b9ff",
                    [(0.8, "#e17055", "--"),   # Fritz & Lusardi 2009: funktionelle Grenze
                     (1.2, "#2ecc71", ":")])   # Bohannon 1997: komfortable Normgeschwindigkeit

    if step_len:
        plot_series(axes_flat[3], step_len, "Step Length", "m", "#a29bfe")

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"gait_{ts}.png"
    plt.savefig(p, dpi=150, bbox_inches="tight")
    print(t(f"Plot: {p}", f"Plot: {p}"))
    plt.close()


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=700)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""


def _save(report, llm_text):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M")
    out = OUT_DIR / f"gait_{ts}.md"
    content = f"# Gangbild & Neurologie\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


def main():
    parser = argparse.ArgumentParser(description=t("Gangbild & Neurologie (Apple Watch)", "Gait & neurology (Apple Watch)"))
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
    steadiness, asymmetry, speed, step_len, stress, symptome = \
        load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not steadiness and not speed:
        print(t("Keine Gangbild-Daten. Apple Watch trägt diese ab watchOS 8+.",
                "No gait data. Apple Watch reports these from watchOS 8+."))
        return

    print(t(f"Steadiness: {len(steadiness)} Wochen  |  Speed: {len(speed)} Tage",
            f"Steadiness: {len(steadiness)} weeks  |  Speed: {len(speed)} days"))
    report = build_report(steadiness, asymmetry, speed, step_len,
                               stress, symptome, args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(steadiness, asymmetry, speed, step_len, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
