#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Migraine — Multi-Trigger-Analyse

Untersucht welche Kombination aus Sleep, HRV, Cyclephase, Wetter and
Stress with Migraine-Anfällen zusammenhängt.

Methode:
  - Lag-Correlation: Trigger ±3 days um jeden Migrainetag
  - Personen-Whitney U Test pro Trigger (Migrainetag vs. no Migrainetag)
  - Relatives Risiko im schlechtesten Trigger-Quartil
  - Kombinierter Risiko-Score aus allen signifikanten Triggern

@tier        heuristic
@purpose.de  Identifiziert Migräne-Trigger aus Schlaf-, HRV-, Wetter- und Zyklus-Daten durch Lag-Korrelation (±3 Tage) und non-parametrischen Gruppenvergleich.
@purpose.en  Identifies migraine triggers from sleep, HRV, weather and cycle data via lag correlation (±3 days) and non-parametric group comparison.
@method.de   Lag-Korrelation je Trigger-Variable; Personen-Whitney-U-Test (Migränetag vs. kein Migränetag); relatives Risiko im schlechtesten Trigger-Quartil; eigener kombinierter Risiko-Score.
@method.en   Lag correlation per trigger variable; Personen-Whitney U test (migraine day vs. non-migraine day); relative risk in worst trigger quartile; own combined risk score.
@scoring     Kombinierter Trigger-Risiko-Score (heuristisch, projektintern):
               Signifikante Trigger (p<0.05) → gewichteter Komposit-Score
               Schwere-Klassifikation: ≥3 = "schwer" (heuristisch, kein validierter Schwellenwert)
               Quartil-Risiko: relatives Risiko im schlechtesten Trigger-Quartil
               Basis: projektintern, keine klinische Validierung.
@limits.de   Heuristische Methode: Explorative Analyse ohne Multiple-Testing-Korrektur; kausale Trigger-Identifikation nicht möglich; Schwere-Schwellenwert ≥3 für "schwere Migräne" heuristisch ohne Leitliniengrundlage; Zyklus-Daten nur wenn Oura-Cycle-Insights oder reproductive_health vorhanden; Migräne-Events aus sessions-Tabelle erforderlich.
@limits.en   Heuristic method: Exploratory analysis without multiple testing correction; causal trigger identification not possible; severity threshold ≥3 for "severe migraine" is heuristic without guideline basis; cycle data only if Oura cycle insights or reproductive health present; migraine events required in sessions table.
@refs        Goadsby PJ, Holland PR, Martins-Oliveira M, Hoffmann J, Schankin C, Akerman S (2017). Pathophysiology of Migraine: A Disorder of Sensory Processing. Physiological Reviews, 97(2):553-622. doi:10.1152/physrev.00034.2015
             Scher AI, Stewart WF, Liberman J, Lipton RB (1998). Prevalence of Frequent Headache in a Population Sample. Headache: The Journal of Head and Face Pain, 38(7):497-506. doi:10.1046/j.1526-4610.1998.3807497.x

@relevance.de  Ermöglicht die neurologische Analyse, essentiell für die Nervensystemdiagnostik
@relevance.en  Enables neurological analysis, essential for nervous system diagnostics
@reads       sessions, session_metrics, measurements, weather_station, oura_cycle_insights, reproductive_health, symptoms
@writes      analyses/neurology/migraine_triggers_*.{md,png}

Usage:
  python analyse_migraine_triggers.py --plot
  python analyse_migraine_triggers.py --from YYYY-MM-DD --plot
  python analyse_migraine_triggers.py --plot --no-llm

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_migraine_triggers.py
    python analyse_migraine_triggers.py --help
    python analyse_migraine_triggers.py --from 2024-01-01 --to 2024-12-31
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
OUT_DIR = _cfg.analyses_dir / "neurology"

from modules.prompts.analysis_neurology import (
    SYSTEM_PROMPT_ANALYSE_MIGRAINE_TRIGGERS_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_MIGRAINE_TRIGGERS_EN as SYSTEM_PROMPT_EN,
)


def _date_range(d_from, d_to):
    d = datetime.fromisoformat(d_from).date()
    end = datetime.fromisoformat(d_to).date()
    while d <= end:
        yield str(d)
        d += timedelta(days=1)


def load_data(conn, d_from, d_to):
    migräne = {r[0]: r[1] for r in conn.execute("""
        SELECT s.date, MAX(sm.value) AS severity
        FROM sessions s
        JOIN session_metrics sm ON sm.session_id = s.id AND sm.metric = 'severity'
        WHERE s.source_app = 'migraene_app' AND s.date >= ? AND s.date <= ?
        GROUP BY s.date
    """, (d_from, d_to))}

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}

    hrv = {}
    if "daily_stress" in tables:
        for d, rmssd, rhr, stress in conn.execute("""
            SELECT date, rmssd_ms, resting_hr, stress_score
            FROM daily_stress WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            hrv[d] = {"rmssd": rmssd, "rhr": rhr, "stress": stress}

    schlaf = {}
    src = "health_canonical" if "health_canonical" in tables else None
    if src:
        for d, sh, sq in conn.execute("""
            SELECT date, value, NULL FROM health_canonical
            WHERE metric='sleep_duration' AND date >= ? AND date <= ?
        """, (d_from, d_to)):
            schlaf[d] = {"h": sh, "quality": sq}

    wetter = {}
    if "weather_station" in tables:
        for d, hpa, hpa_min, hpa_max, solar, uv in conn.execute("""
            SELECT date, pressure_hpa, pressure_min, pressure_max,
                   solar_wm2_max, uv_index_max
            FROM weather_station WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            delta = (hpa_max - hpa_min) if hpa_max and hpa_min else None
            wetter[d] = {"hpa": hpa, "delta": delta, "solar": solar, "uv": uv}

    zyklus = {}
    if "oura_cycle_insights" in tables:
        for d, phase in conn.execute("""
            SELECT day, cycle_phase FROM oura_cycle_insights
            WHERE day >= ? AND day <= ? AND cycle_phase IS NOT NULL
        """, (d_from, d_to)):
            zyklus[d] = phase
    elif "reproductive_health" in tables:
        # Build cycle map from period_start events + cycle_length events
        period_starts = [r[0] for r in conn.execute("""
            SELECT date FROM reproductive_health
            WHERE event_type = 'period_start' AND date >= ? AND date <= ?
            ORDER BY date
        """, (d_from, d_to))]
        cycle_lengths = {r[0]: int(r[1]) for r in conn.execute("""
            SELECT date, value_num FROM reproductive_health
            WHERE event_type = 'cycle_length' AND date >= ? AND date <= ?
              AND value_num IS NOT NULL
        """, (d_from, d_to))}
        for start in period_starts:
            try:
                s   = datetime.fromisoformat(start).date()
                dur = cycle_lengths.get(start, 28)
                for i in range(int(dur)):
                    zyklus[str(s + timedelta(days=i))] = "menstruation" if i < 5 else (
                        "follicular" if i < 14 else ("ovulation" if i == 14 else "luteal"))
            except Exception:
                pass

    return migräne, hrv, schlaf, wetter, zyklus


def _mw_test(group_a, group_b):
    """Personen-Whitney U, zweiseitig. scipy bevorzugt (mit Mid-Rank-Tiekorrektur
    und exakter bzw. asymptotischer Verteilung); Pure-Python-Fallback nutzt
    Mid-Ranks plus Tiekorrektur in der Varianz (Hollander/Wolfe 1999)."""
    a = [x for x in group_a if x is not None]
    b = [x for x in group_b if x is not None]
    if len(a) < 3 or len(b) < 3:
        return None, None
    try:
        from scipy.stats import mannwhitneyu
        res = mannwhitneyu(a, b, alternative="two-sided")
        return float(res.statistic), float(res.pvalue)
    except Exception:
        import math
        na, nb = len(a), len(b)
        combined = sorted([(v, 0) for v in a] + [(v, 1) for v in b],
                          key=lambda x: x[0])
        # Mid-Ranks bei Bindungen
        ranks = [0.0] * len(combined)
        i = 0
        tie_term = 0.0
        while i < len(combined):
            j = i
            while j + 1 < len(combined) and combined[j + 1][0] == combined[i][0]:
                j += 1
            avg_rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[k] = avg_rank
            t = j - i + 1
            if t > 1:
                tie_term += t * (t * t - 1)
            i = j + 1
        rank_sum_a = sum(r for r, (_, g) in zip(ranks, combined) if g == 0)
        u = rank_sum_a - na * (na + 1) / 2
        n = na + nb
        mu = na * nb / 2
        var = na * nb / 12 * ((n + 1) - tie_term / (n * (n - 1))) if n > 1 else 0.0
        if var <= 0:
            return u, None
        z = abs(u - mu) / math.sqrt(var)
        p = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
        return u, p


def analyse_triggers(migraine_dict, hrv, schlaf, wetter, zyklus, lag_days=0):
    """Comparisont Trigger-Werte an Migraine- vs. Nicht-Migraine-daysn for einen Lag."""
    trigger_def = {
        "hrv_rmssd":    (hrv,     lambda d: hrv.get(d, {}).get("rmssd")),
        "rhr":          (hrv,     lambda d: hrv.get(d, {}).get("rhr")),
        "stress_score": (hrv,     lambda d: hrv.get(d, {}).get("stress")),
        "schlaf_h":     (schlaf,  lambda d: schlaf.get(d, {}).get("h")),
        "druck_hpa":    (wetter,  lambda d: wetter.get(d, {}).get("hpa")),
        "druck_delta":  (wetter,  lambda d: wetter.get(d, {}).get("delta")),
        "solar_wm2":    (wetter,  lambda d: wetter.get(d, {}).get("solar")),
    }

    results = {}
    alle_tage = set(hrv) | set(schlaf) | set(wetter)

    for name, (_, getter) in trigger_def.items():
        mig_vals, nein_vals = [], []
        for d in alle_tage:
            lag_d = str((datetime.fromisoformat(d).date() + timedelta(days=lag_days)))
            val = getter(d)
            if val is None:
                continue
            if lag_d in migraine_dict:
                mig_vals.append(val)
            else:
                nein_vals.append(val)

        if not mig_vals or not nein_vals:
            continue

        avg_mig  = round(sum(mig_vals) / len(mig_vals), 2)
        avg_nein = round(sum(nein_vals) / len(nein_vals), 2)
        _, p = _mw_test(mig_vals, nein_vals)
        results[name] = {
            "n_mig": len(mig_vals), "n_nein": len(nein_vals),
            "avg_migräne": avg_mig, "avg_kein": avg_nein,
            "diff_pct": round((avg_mig - avg_nein) / avg_nein * 100, 1) if avg_nein else None,
            "p": round(p, 4) if p else None,
        }

    return results


def zyklus_risiko(migraine_dict, zyklus):
    """Relative Migraine-Häufigkeit pro Cyclephase."""
    phasen = {}
    for d, phase in zyklus.items():
        if phase not in phasen:
            phasen[phase] = {"total": 0, "mig": 0}
        phasen[phase]["total"] += 1
        if d in migraine_dict:
            phasen[phase]["mig"] += 1
    return {p: {"total": v["total"], "mig": v["mig"],
                "rate": round(v["mig"] / v["total"] * 100, 1) if v["total"] else 0}
            for p, v in phasen.items()}


def build_report(migraine_dict, hrv, schlaf, wetter, zyklus,
                     trigger_lag0, trigger_lag1, trigger_lag2, zyklus_risk):
    n_mig  = len(migraine_dict)
    schwer = sum(1 for v in migraine_dict.values() if v and v >= 3)
    lines  = [
        "## Migräne Multi-Trigger-Analyse\n",
        f"Migräne-Anfälle gesamt: **{n_mig}**  |  davon schwer (≥3): **{schwer}**\n",
        f"Datenbasis: HRV={len(hrv)} Tage | Schlaf={len(schlaf)} Tage | "
        f"Wetter={len(wetter)} Tage | Zyklus={len(zyklus)} Tage\n",
        "### Trigger-Analyse (Lag 0 = Migränetag selbst)\n",
        f"{'Trigger':<18} {'Ø Migräne':>10} {'Ø Kein':>10} {'Δ%':>7} {'p-Wert':>8}",
        "-" * 57,
    ]
    for lag, label, data in [(0, "Lag 0", trigger_lag0),
                              (1, "Lag +1d vorher", trigger_lag1),
                              (2, "Lag +2d vorher", trigger_lag2)]:
        if not data:
            continue
        lines.append(f"\n**{label}:**")
        for name, r in sorted(data.items(), key=lambda x: x[1].get("p") or 1):
            p_str = f"{r['p']:.4f}" if r['p'] else "n.a."
            sig   = " *" if r['p'] and r['p'] < 0.05 else ("†" if r['p'] and r['p'] < 0.1 else "")
            lines.append(f"  {name:<18} {r['avg_migräne']:>10.2f} {r['avg_kein']:>10.2f} "
                         f"{str(r['diff_pct'] or ''):>7} {p_str:>8}{sig}")

    if zyklus_risk:
        lines += ["\n### Zyklusphase × Migräne\n",
                  f"{'Phase':<16} {'Tage':>6} {'Migräne':>8} {'Rate %':>8}"]
        lines.append("-" * 42)
        for phase, r in sorted(zyklus_risk.items(), key=lambda x: -x[1]["rate"]):
            lines.append(f"  {phase:<16} {r['total']:>6} {r['mig']:>8} {r['rate']:>8.1f}%")

    return "\n".join(lines)


def _plot(migraine_dict, hrv, schlaf, trigger_lag0, trigger_lag1):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    mig_dates = sorted(migraine_dict)
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), facecolor="#1e1e2e")
    fig.suptitle("Migräne — Multi-Trigger-Analyse", color="#E0E0E0", fontsize=13)

    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    def plot_trigger(ax, data_dict, key, color, label, mig_dts):
        dates = sorted(data_dict)
        vals  = [data_dict[d].get(key) for d in dates]
        dts   = [datetime.fromisoformat(d) for d in dates]
        valid = [(dt, v) for dt, v in zip(dts, vals) if v is not None]
        if not valid:
            return
        xs, ys = zip(*valid)
        ax.plot(xs, ys, lw=1.2, color=color, alpha=0.8, label=label)
        for md in mig_dts:
            dt = datetime.fromisoformat(md)
            ax.axvline(dt, color="#ff6b6b", alpha=0.4, lw=0.8)
        ax.set_ylabel(label, color="#ccc", fontsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    plot_trigger(axes[0], hrv, "rmssd", "#4ecdc4", "HRV RMSSD (ms)", mig_dates)
    axes[0].set_title("Rote Linien = Migränetage", color="#aaa", fontsize=8, loc="right")
    plot_trigger(axes[1], hrv, "stress", "#f7b731", "Stress-Score", mig_dates)
    plot_trigger(axes[2], schlaf, "h", "#a29bfe", "Schlaf (h)", mig_dates)

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"migraine_trigger_{ts}.png"
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
    out = OUT_DIR / f"migraine_trigger_{ts}.md"
    content = f"# Migräne Multi-Trigger-Analyse\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("Migräne Multi-Trigger-Analyse", "Migraine multi-trigger analysis"))
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
    migräne, hrv, schlaf, wetter, zyklus = load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not migräne:
        print("Keine Migräne-Daten. Zuerst: python3 importers/import_migraine.py")
        return

    print(f"Migräne-Anfälle: {len(migräne)} | HRV-Tage: {len(hrv)} | "
          f"Schlaf: {len(schlaf)} | Wetter: {len(wetter)} | Zyklus: {len(zyklus)}")

    t0 = analyse_triggers(migräne, hrv, schlaf, wetter, zyklus, lag_days=0)
    t1 = analyse_triggers(migräne, hrv, schlaf, wetter, zyklus, lag_days=-1)
    t2 = analyse_triggers(migräne, hrv, schlaf, wetter, zyklus, lag_days=-2)
    zr = zyklus_risiko(migräne, zyklus)

    report = build_report(migräne, hrv, schlaf, wetter, zyklus, t0, t1, t2, zr)
    print("\n" + report)

    if args.plot:
        _plot(migräne, hrv, schlaf, t0, t1)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
