#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Respiration rate im Sleep — Analyse

Analysiert nächtliche Respiration rate aus Garmin und Apple Watch
(respiratory_rate):
Trends, Ausreißer als Indikator, Korrelation mit Schlafqualität, HRV und Symptomen.

Normwert Ruheatmung: 12–20 Atemzüge/min. Nights oft 10–16.
Erhöhte nächtliche Respiration rate (>18) deutet auf schlechte Recovery hin.

@tier        heuristic
@purpose.de  Analysiert nächtliche Atemfrequenztrends aus Garmin- und Apple-Watch-Daten auf Ausreißer, Trends und Korrelationen mit Schlafqualität und HRV.
@purpose.en  Analyses nightly respiratory rate trends from Garmin and Apple Watch data for outliers, trends and correlations with sleep quality and HRV.
@method.de   Tagesaggregat (AVG, MIN, MAX) aus measurements; Ausreißerdetektion mit eigenen Schwellen (>18/min Warnung, <10/min Warnung); gleitender Durchschnitt.
@method.en   Daily aggregate (AVG, MIN, MAX) from measurements; outlier detection with custom thresholds (>18/min warning, <10/min warning); moving average.
@limits.de   Heuristische Methode: Grenzwert 18/min ist literaturbasiert (Normwert 12–20/min), aber scriptspezifisch gewählt; Garmin-Atemfrequenz nur während des Schlafs erfasst. Keine Validierung als Detektor.
@limits.en   Heuristic method: Threshold 18/min is literature-based (normal 12–20/min) but script-specific; Garmin respiratory rate is captured during sleep only. Not validated as a detector.
@refs        Cretikos MA, Bellomo R, Hillman K, Chen J, Finfer S, Flabouris A (2008). Respiratory rate: the neglected vital sign. Medical Journal of Australia, 188(11):657-659. doi:10.5694/j.1326-5377.2008.tb01825.x
             Massaroni C, Nicolò A, Schena E, Sacchetti M (2020). Remote Respiratory Monitoring in the Time of COVID-19. Frontiers in Physiology, 11:635. doi:10.3389/fphys.2020.00635

@prompt-classification LLM:Analysis
@prompt.de SYSTEM_PROMPT
@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@scoring
    Respiratory rate: <10/min warning | 12-20/min normal | >18/min warning (night average)
    Outlier detection: values outside normal range flagged
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
@reads       measurements
@writes      analyses/sleep/*.{md,png}

Usage:
  python analyse_respiration.py --plot
  python analyse_respiration.py --from YYYY-MM-DD --plot
  python analyse_respiration.py --plot --no-llm

@usage
    python analyse_respiration.py
    python analyse_respiration.py --help
    python analyse_respiration.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.baseline import get_baseline, baseline_delta_pct
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_sleep import (
    SYSTEM_PROMPT_ANALYSE_RESPIRATION_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_RESPIRATION_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "sleep"

SCHWELLE_ERHOEHEN = 18.0  # Atemzüge/min als Warngrenze
SCHWELLE_NIEDRIG  = 10.0  # ungewöhnlich niedrig


def load_data(conn, d_from, d_to):
    # dayss-Aggregat (Garmin liefert stündliche Werte während Sleep)
    atem_daily = conn.execute("""
        SELECT date, AVG(value) AS avg_bpm,
               MIN(value) AS min_bpm,
               MAX(value) AS max_bpm,
               COUNT(*) AS n_messwerte
        FROM measurements
        WHERE metric = 'respiration_rate'
          AND source_app = 'garmin_connect'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL AND value > 0
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    # hours-Profiles
    atem_hourly = conn.execute("""
        SELECT CAST(SUBSTR(ts, 12, 2) AS INTEGER) AS stunde,
               AVG(value) AS avg_bpm
        FROM measurements
        WHERE metric = 'respiration_rate'
          AND source_app = 'garmin_connect'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL AND value > 0
        GROUP BY stunde
        ORDER BY stunde
    """, (d_from, d_to)).fetchall()

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}

    schlaf = {}
    if "garmin_sleep" in tables:
        # garmin_sleep hat keine Score-Spalte — Sleep-Score-Korrelation bleibt
        # für Garmin-Daten n.a. (kein Äquivalent in dieser Tabelle)
        for d, dur_s, deep_s, rem_s in conn.execute("""
            SELECT date, total_sleep_s, deep_s, rem_s FROM garmin_sleep
            WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            schlaf[d] = {"score": None, "dur_h": dur_s / 3600 if dur_s else None,
                         "deep_h": deep_s / 3600 if deep_s else None}

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
    elif "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND category='Ressourcen' AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert

    # Apple Watch: Respiration rate (dayss-Aggregat)
    apple_atem = conn.execute("""
        SELECT date, AVG(value) AS avg_bpm
        FROM measurements
        WHERE metric = 'respiratory_rate'
          AND source_app = 'apple_health'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL AND value > 0
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    return atem_daily, atem_hourly, schlaf, stress, symptome, apple_atem


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


def build_report(atem_daily, atem_hourly, schlaf, stress, symptome, apple_atem, d_from, d_to,
                 rr_bl=None):
    if not atem_daily and not apple_atem:
        return "No Respiration rate-Daten im angefragten Time range."

    n = len(atem_daily)
    avg_vals = [r[1] for r in atem_daily if r[1]]
    min_vals = [r[2] for r in atem_daily if r[2]]
    max_vals = [r[3] for r in atem_daily if r[3]]

    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

    overall_avg = avg(avg_vals)
    n_hoch = sum(1 for v in avg_vals if v > SCHWELLE_ERHOEHEN)
    n_niedrig = sum(1 for v in avg_vals if v < SCHWELLE_NIEDRIG)

    lines = [
        f"## Respiration rate-Analyse — {d_from} bis {d_to}\n",
        f"Nights: **{n}**  |  Time range: {atem_daily[0][0]} – {atem_daily[-1][0]}\n",
        "### Basislinie\n",
        f"  Ø nächtliche Respiration rate: **{overall_avg} /min**",
        *([f"  Pers. RR-Baseline ({rr_bl['method']}, n={rr_bl['n_days']} Tage): "
           f"**{rr_bl['value']:.1f} /min** (Bestwerte — niedriger = besser)"
           + (f" | Δ {baseline_delta_pct(overall_avg, rr_bl):+.1f}/min"
              if overall_avg and baseline_delta_pct(overall_avg, rr_bl) is not None else "")]
          if rr_bl else []),
    ]
    if min_vals and max_vals:
        lines.append(f"  Min-Night Ø: {min(avg_vals):.1f}  |  Max-Night Ø: {max(avg_vals):.1f}")
    lines += [
        f"  Erhöhte Nights (>{SCHWELLE_ERHOEHEN:.0f}/min): "
        f"{n_hoch} ({round(n_hoch/n*100,1)}%)",
        f"  Niedrige Nights (<{SCHWELLE_NIEDRIG:.0f}/min): "
        f"{n_niedrig} ({round(n_niedrig/n*100,1)}%)",
    ]

    # Top-5 schlechteste Nights
    top_bad = sorted(atem_daily, key=lambda r: r[1] or 0, reverse=True)[:5]
    if any(r[1] and r[1] > SCHWELLE_ERHOEHEN for r in top_bad):
        lines.append("\n### Auffälligste Nights (höchste Respiration rate)\n")
        for r in top_bad:
            if r[1] and r[1] > SCHWELLE_ERHOEHEN:
                lines.append(f"  {r[0]}:  Ø {r[1]:.1f} /min  (Max: {r[3]:.0f})")

    # Trend
    if n >= 20:
        q = n // 5
        early = avg(avg_vals[:q])
        late  = avg(avg_vals[-q:])
        if early and late:
            delta = round(late - early, 1)
            lines.append(f"\nTrend: {delta:+.1f} /min (früh: {early} → spät: {late})")

    # hours-Profiles
    if atem_hourly:
        lines.append("\n### Stündliches Profiles\n")
        peak = max(atem_hourly, key=lambda x: x[1])
        tief = min(atem_hourly, key=lambda x: x[1])
        for h, bpm in atem_hourly:
            marker = " ← Max" if h == peak[0] else (" ← Min" if h == tief[0] else "")
            lines.append(f"  {h:02d}:00  {bpm:.1f} /min{marker}")

    # Correlationen
    dates = [r[0] for r in atem_daily]
    atem_x = [r[1] for r in atem_daily]
    hrv_y    = [stress[d]["hrv"]       if d in stress else None for d in dates]
    sleep_y  = [schlaf[d]["score"]     if d in schlaf and schlaf[d]["score"] else None for d in dates]
    sym_y    = [symptome.get(d) for d in dates]
    stress_y = [stress[d]["stress"]    if d in stress else None for d in dates]

    r_atem_hrv    = spearman_r(atem_x, hrv_y)
    r_atem_sleep  = spearman_r(atem_x, sleep_y)
    r_atem_sym    = spearman_r(atem_x, sym_y)
    r_atem_stress = spearman_r(atem_x, stress_y)

    if any(r is not None for r in [r_atem_hrv, r_atem_sleep]):
        lines += [
            "\n### Correlation Respiration rate × (Spearman r)\n",
            f"  × HRV RMSSD:      {r_atem_hrv    if r_atem_hrv    else 'n.a.'}",
            f"  × Sleep-Score:   {r_atem_sleep  if r_atem_sleep  else 'n.a.'}",
            f"  × Energie/Ressourcen: {r_atem_sym if r_atem_sym   else 'n.a.'}",
            f"  × Stress-Score:   {r_atem_stress if r_atem_stress else 'n.a.'}",
        ]

    # Apple Watch Comparison
    if apple_atem:
        aw_vals = [r[1] for r in apple_atem if r[1]]
        if aw_vals:
            aw_avg  = avg(aw_vals)
            n_hoch_aw = sum(1 for v in aw_vals if v > SCHWELLE_ERHOEHEN)
            lines += [
                f"\n### Apple Watch Respiration rate (n={len(apple_atem)} days)\n",
                f"  Ø: **{aw_avg} /min**  |  Min: {round(min(aw_vals),1)}  |  Max: {round(max(aw_vals),1)}",
                f"  Erhöhte days (>{SCHWELLE_ERHOEHEN:.0f}/min): "
                f"{n_hoch_aw} ({round(n_hoch_aw/len(aw_vals)*100,1)}%)",
            ]

    # Saison-Aggregat
    by_month = defaultdict(list)
    for r in atem_daily:
        if r[1]:
            by_month[r[0][:7]].append(r[1])
    if len(by_month) >= 6:
        lines.append("\n### Monatswithtel\n")
        for ym in sorted(by_month)[-12:]:
            a = avg(by_month[ym])
            flag = " ⚠" if a and a > SCHWELLE_ERHOEHEN else ""
            lines.append(f"  {ym}  Ø {a} /min{flag}")

    return "\n".join(lines)


def _plot(atem_daily, atem_hourly, stress, apple_atem, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), facecolor="#1e1e2e")
    fig.suptitle(f"Nächtliche Respiration rate {d_from}–{d_to}", color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # Verlauf
    if atem_daily:
        dts  = [datetime.fromisoformat(r[0]) for r in atem_daily if r[1]]
        vals = [r[1] for r in atem_daily if r[1]]
        colors = ["#e17055" if v > SCHWELLE_ERHOEHEN else "#2ecc71" for v in vals]
        axes[0].scatter(dts, vals, c=colors, s=15, alpha=0.7)
        if len(vals) >= 7:
            ma7 = [sum(vals[max(0,i-6):i+1])/len(vals[max(0,i-6):i+1]) for i in range(len(vals))]
            axes[0].plot(dts, ma7, color="#74b9ff", lw=1.5, label="7-days-Ø")
        axes[0].axhline(SCHWELLE_ERHOEHEN, color="#e17055", lw=0.8, ls="--", alpha=0.6,
                        label=f"Schwelle {SCHWELLE_ERHOEHEN:.0f}/min")
        axes[0].set_ylabel("Atemzüge/min", color="#ccc", fontsize=9)
        axes[0].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # hours-Profiles
    if atem_hourly:
        hours = [r[0] for r in atem_hourly]
        bpms  = [r[1] for r in atem_hourly]
        axes[1].plot(hours, bpms, color="#74b9ff", lw=1.8, marker="o", ms=5)
        axes[1].axhline(SCHWELLE_ERHOEHEN, color="#e17055", lw=0.6, ls="--", alpha=0.5)
        axes[1].set_xticks(range(0, 24))
        axes[1].set_xticklabels([f"{h}" for h in range(0, 24)], fontsize=7, color="#aaa")
        axes[1].set_ylabel("Ø Atem /min", color="#ccc", fontsize=9)
        axes[1].set_xlabel("Uhrzeit", color="#ccc", fontsize=9)

    # Verteilung: Garmin + Apple Watch
    garmin_vals = [r[1] for r in atem_daily if r[1]]
    aw_vals     = [r[1] for r in apple_atem if r[1]] if apple_atem else []
    if garmin_vals or aw_vals:
        if garmin_vals:
            axes[2].hist(garmin_vals, bins=20, color="#4ecdc4", alpha=0.7,
                         edgecolor="#2a2a3e", label="Garmin")
        if aw_vals:
            axes[2].hist(aw_vals, bins=20, color="#74b9ff", alpha=0.7,
                         edgecolor="#2a2a3e", label="Apple Watch")
        axes[2].axvline(SCHWELLE_ERHOEHEN, color="#e17055", lw=1.2, ls="--",
                        label=f">{SCHWELLE_ERHOEHEN:.0f} notable")
        axes[2].set_xlabel("Atemzüge/min", color="#ccc", fontsize=9)
        axes[2].set_ylabel("Häufigkeit", color="#ccc", fontsize=9)
        axes[2].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"respiratory_rate_{ts}.png"
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
    out = OUT_DIR / f"respiratory_rate_{ts}.md"
    content = f"# Respiration rate-Analyse\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


def main():
    parser = argparse.ArgumentParser(description=t("Nächtliche Respiration rate-Analyse", "Nocturnal respiration rate analysis"))
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
    atem_daily, atem_hourly, schlaf, stress, symptome, apple_atem = load_data(conn, args.date_from, args.date_to)
    rr_bl = get_baseline(conn, OWN_PERSON_ID, "respiratory_rate")
    conn.close()

    if not atem_daily and not apple_atem:
        print(t("Keine Atemfrequenz-Daten. Zuerst: python3 importers/import_garmin.py "
                "und/oder import_apple_health.py",
                "No respiration rate data. First run: python3 importers/import_garmin.py "
                "and/or import_apple_health.py"))
        return

    print(t(f"Garmin-Nächte: {len(atem_daily)}  |  Apple Watch-Tage: {len(apple_atem)}",
            f"Garmin nights: {len(atem_daily)}  |  Apple Watch days: {len(apple_atem)}"))

    report = build_report(atem_daily, atem_hourly, schlaf, stress, symptome, apple_atem,
                               args.date_from, args.date_to, rr_bl=rr_bl)
    print("\n" + report)

    if args.plot:
        _plot(atem_daily, atem_hourly, stress, apple_atem, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
