#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Interrupted Time Series (ITS) Analysis

Compares HRV (RMSSD), Resting heart rate and sleep quality before/after a configurable
event cut-off date via segmented linear regression.

Modell: Y = β₀ + β₁·t + β₂·D + β₃·(t−t_c)·D
  β₁ = Vor-Trend (ms/day)
  β₂ = Niveau-Sprung am Cutoff
  β₃ = Trend-Änderung nach Cutoff

@tier        heuristic
@purpose.de  Vergleicht HRV (RMSSD), Ruhepuls und Schlafqualität vor und nach einem konfigurierbaren Ereignis-Datum mittels segmentierter linearer Regression (Interrupted Time Series).
@purpose.en  Compares HRV (RMSSD), resting heart rate and sleep quality before and after a configurable cut-off date using segmented linear regression (interrupted time series).
@method.de   Segmentierte lineare Regression Y = β₀ + β₁·t + β₂·D + β₃·(t−t_c)·D; OLS in Pure-Python. Cohen's d für Effektgröße. Keine Konfounderkontrolle.
@method.en   Segmented linear regression Y = β₀ + β₁·t + β₂·D + β₃·(t−t_c)·D; OLS in Pure-Python. Cohen's d for effect size. No confounder adjustment.
@limits.de   Heuristische Methode: Kein Kausalitätsnachweis; Konfoundfaktoren (Saisonalität, Geräteänderungen) nicht kontrolliert. Mindestdatenbedarf: ≥30 Tage je Segment empfohlen.
@limits.en   Heuristic method: No causal inference; confounders (seasonality, device changes) not controlled. Minimum data requirement: ≥30 days per segment recommended.
@scoring
    Model: Y = β₀ + β₁·t + β₂·D + β₃·(t−t_c)·D where D=1 if t>=t_c (cutoff date)
    Effect size: Cohen's d 0.2 small | 0.5 medium | 0.8 large
    Segment trend: β₁ pre-interruption | β₃ post-interruption change
@refs        Penfold RB, Zhang F (2013). Use of Interrupted Time Series Analysis in Evaluating Health Care Quality Improvements. Academic Pediatrics, 13(6 Suppl):S38-S44. doi:10.1016/j.acap.2013.08.002 (ITS-Methode)
             Cohen J (1988). Statistical Power Analysis for the Behavioral Sciences (2nd ed.). Lawrence Erlbaum Associates. (Cohen's d: 0.2 small, 0.5 medium, 0.8 large)
@relevance.de Unterstützt die infektionsbezogene Datenanalyse und Entscheidungsfindung durch systematische Aufbereitung von Wearable- und Symptomdaten
@relevance.en Supports infection-related data analysis and decision-making through systematic processing of wearable and symptom data
@reads       polar_nightly_hrv, measurements, sessions, session_metrics
@writes      analyses/infectious/*.{md,png}

Usage:
  python analyse_postinfectious_its.py --plot
  python analyse_postinfectious_its.py --cutoff 2023-06-01 --plot
  python analyse_postinfectious_its.py --from 2022-01-01 --to YYYY-MM-DD --plot --no-llm

@usage
    python analyse_postinfectious_its.py
    python analyse_postinfectious_its.py --help
    python analyse_postinfectious_its.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import math
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "infectious"

SYSTEM_PROMPT = """Du bist ein Internist mit Expertise in Herzfrequenzvariabilität und
Zeitreihenanalyse. Du analysierst eine Interrupted-Time-Series-Analyse (ITS) der HRV
vor und nach einem definierten Ereignis-Cutoff.

Analysiere auf Deutsch:
1. **ITS-Ergebnis**: Gibt es einen statistisch messbaren Einbruch der HRV nach dem Cutoff?
2. **Effektgröße**: Was bedeutet der berechnete Effekt (Cohen's d, ΔRMSSD)?
3. **Verlauf**: Hat sich die HRV nach dem Einbruch erholt, stabilisiert oder verschlechtert?
4. **Ruhepuls**: Bestätigt er den HRV-Befund?
5. **Empfehlung**: Konsequenzen für Aktivitätsmanagement und ärztliche Abklärung?"""


def load_hrv(conn, d_from, d_to):
    """Nacht-RMSSD, geraeteagnostisch.

    Las vorher ausschliesslich polar_nightly_hrv — in v2 ein leerer Stub, sobald
    kein Polar-Geraet im Einsatz ist. Diese Analyse (ITS auf die HRV rund um ein
    Infektionsdatum) meldete deshalb dauerhaft "Keine HRV-Daten", obwohl die
    Metrik in measurements vorliegt. Polar bleibt bevorzugt, weil Brustgurt-RMSSD
    weniger artefaktbehaftet ist als optische Handgelenkmessung; fehlt sie, wird
    measurements.hrv_rmssd genutzt.
    """
    polar = conn.execute(
        "SELECT date, rmssd_ms FROM polar_nightly_hrv "
        "WHERE date >= ? AND date <= ? AND rmssd_ms > 0 ORDER BY date",
        (d_from, d_to)
    ).fetchall()
    if polar:
        return polar

    return conn.execute("""
        SELECT date, AVG(value) AS rmssd_ms
        FROM measurements
        WHERE metric = 'hrv_rmssd'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL AND value > 0
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()


_SOURCE_APP_LABELS = {
    "garmin_connect": "Garmin",
    "garmin_gdpr": "Garmin GDPR",
    "apple_health": "Apple Health",
    "oura_app": "Oura",
    "polar_connect": "Polar",
}


def _device_label(sources: set[str]) -> str:
    """Anzeigename aus den tatsaechlich vorhandenen source_app-Werten ableiten.

    Frueher hart auf 'Garmin' bzw. 'Polar' verdrahtet, unabhaengig davon, was in
    der DB stand (Schlaf-Score war z.B. als 'Polar' beschriftet, obwohl in dieser
    DB ausschliesslich garmin_connect/garmin_gdpr Schlaf-Scores liefern). Label
    wird jetzt aus den Daten abgeleitet statt angenommen.
    """
    if not sources:
        return "unbekannte Quelle"
    return ", ".join(sorted(_SOURCE_APP_LABELS.get(s, s) for s in sources))


def load_rhr(conn, d_from, d_to):
    # resting_hr liegt in measurements (v2 — garmin_daily existiert nicht mehr).
    # Geraeteagnostisch: keine source_app-Einschraenkung, sonst fallen z.B.
    # garmin_gdpr-Zeilen still unter den Tisch (siehe _device_label()/CLAUDE.md
    # Hard Rule 7 — Garmin liefert Ruhepuls ueber zwei getrennte Pipelines).
    rows = conn.execute("""
        SELECT date, AVG(value) AS resting_hr
        FROM measurements
        WHERE metric = 'resting_hr'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    return {r[0]: r[1] for r in rows}


def rhr_sources(conn, d_from, d_to) -> set[str]:
    rows = conn.execute("""
        SELECT DISTINCT source_app FROM measurements
        WHERE metric = 'resting_hr' AND date >= ? AND date <= ?
          AND source_app IS NOT NULL
    """, (d_from, d_to)).fetchall()
    return {r[0] for r in rows}


def load_sleep(conn, d_from, d_to):
    # sleep_score liegt in session_metrics (v2 — polar_sleep_score existiert
    # nicht mehr). Geraeteagnostisch ueber alle source_app hinweg gelesen (in
    # dieser DB ausschliesslich Garmin, s. _device_label()); Beschriftung im
    # Bericht wird aus den tatsaechlichen Quellen abgeleitet, nie hartcodiert.
    rows = conn.execute("""
        SELECT s.date, MAX(sm.value) AS sleep_score
        FROM sessions s
        JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'sleep'
          AND sm.metric = 'sleep_score'
          AND s.date >= ? AND s.date <= ?
          AND sm.value IS NOT NULL
        GROUP BY s.date
        ORDER BY s.date
    """, (d_from, d_to)).fetchall()
    return {r[0]: r[1] for r in rows}


def sleep_sources(conn, d_from, d_to) -> set[str]:
    rows = conn.execute("""
        SELECT DISTINCT s.source_app
        FROM sessions s
        JOIN session_metrics sm ON sm.session_id = s.id
        WHERE s.type = 'sleep' AND sm.metric = 'sleep_score'
          AND s.date >= ? AND s.date <= ? AND s.source_app IS NOT NULL
    """, (d_from, d_to)).fetchall()
    return {r[0] for r in rows}


def rolling_avg(vals, w=28):
    return [sum(vals[max(0, i - w + 1):i + 1]) / len(vals[max(0, i - w + 1):i + 1])
            for i in range(len(vals))]


def cohens_d(a, b):
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return 0.0
    m1, m2 = sum(a) / n1, sum(b) / n2
    v1 = sum((x - m1) ** 2 for x in a) / (n1 - 1)
    v2 = sum((x - m2) ** 2 for x in b) / (n2 - 1)
    sd = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2))
    return (m2 - m1) / sd if sd > 0 else 0.0


def its_regression(dates, vals, cutoff):
    try:
        import numpy as np
        import statsmodels.api as sm
    except ImportError:
        return None

    t0 = datetime.strptime(dates[0], "%Y-%m-%d")
    tc = (datetime.strptime(cutoff, "%Y-%m-%d") - t0).days
    t = np.array([(datetime.strptime(d, "%Y-%m-%d") - t0).days for d in dates])
    y = np.array(vals)

    D = (t >= tc).astype(float)
    Dt = D * (t - tc)  # post-slope variable (0 before cutoff)
    X = sm.add_constant(np.column_stack([t, D, Dt]))

    model = sm.OLS(y, X).fit()
    pred = model.get_prediction(X).summary_frame(alpha=0.05)

    return {
        "beta": model.params,
        "pvalues": model.pvalues,
        "r2": model.rsquared,
        "y_pred": pred["mean"].values,
        "ci_lower": pred["obs_ci_lower"].values,
        "ci_upper": pred["obs_ci_upper"].values,
        "n_pre": int(sum(D == 0)),
        "n_post": int(sum(D == 1)),
    }


def build_report(hrv_data, cutoff, rhr_dict, schlaf_dict,
                 rhr_label="unbekannte Quelle", sleep_label="unbekannte Quelle"):
    from scipy import stats

    dates = [r[0] for r in hrv_data]
    vals = [r[1] for r in hrv_data]
    pre = [v for d, v in zip(dates, vals) if d < cutoff]
    post = [v for d, v in zip(dates, vals) if d >= cutoff]

    lines = ["## ITS-Analyse (Interrupted Time Series)\n",
             f"Cutoff: {cutoff} | Zeitraum: {dates[0]} – {dates[-1]}",
             f"Datenpunkte: {len(vals)} gesamt | {len(pre)} vor Cutoff | {len(post)} nach Cutoff\n"]

    if len(pre) < 30:
        lines.append(f"⚠️  Nur {len(pre)} Datenpunkte vor dem Cutoff (min. 30 empfohlen).\n")
    if len(post) < 30:
        lines.append(f"⚠️  Nur {len(post)} Datenpunkte nach dem Cutoff (min. 30 empfohlen).\n")

    if pre and post:
        m_pre = round(sum(pre) / len(pre), 1)
        m_post = round(sum(post) / len(post), 1)
        delta = round(m_post - m_pre, 1)
        d = round(cohens_d(pre, post), 2)
        t_stat, p = stats.ttest_ind(pre, post, equal_var=False)
        d_str = "groß" if abs(d) >= 0.8 else "mittel" if abs(d) >= 0.5 else "klein"

        lines.append("### HRV (RMSSD)")
        lines.append(f"  Vor Cutoff:  ∅{m_pre}ms  (n={len(pre)})")
        lines.append(f"  Nach Cutoff: ∅{m_post}ms  (n={len(post)})")
        lines.append(f"  Δ RMSSD:    {delta:+.1f}ms  ({delta/m_pre*100:+.0f}%)")
        lines.append(f"  Cohen's d:  {d:+.2f}  ({d_str})")
        lines.append(f"  t-Test:     t={t_stat:.2f}, p={p:.4f} "
                     f"{'✅ signifikant' if p < 0.05 else '(nicht signifikant)'}\n")

        res = its_regression(dates, vals, cutoff)
        if res:
            b, pv = res["beta"], res["pvalues"]
            lines.append("### Segmentierte Regression")
            lines.append(f"  Vor-Trend:          {b[1]*365:+.1f}ms/Jahr  (p={pv[1]:.4f})")
            lines.append(f"  Niveau-Sprung (β₂): {b[2]:+.1f}ms           (p={pv[2]:.4f})")
            lines.append(f"  Nach-Trend:         {(b[1]+b[3])*365:+.1f}ms/Jahr")
            lines.append(f"  Trend-Änderung (β₃):{b[3]:+.4f}ms/Tag   (p={pv[3]:.4f})")
            lines.append(f"  R²: {res['r2']:.3f}\n")

    rhr_pre  = [rhr_dict[d] for d in dates if d < cutoff  and d in rhr_dict]
    rhr_post = [rhr_dict[d] for d in dates if d >= cutoff and d in rhr_dict]
    if rhr_pre and rhr_post:
        lines.append(f"### Ruhepuls ({rhr_label})")
        lines.append(f"  Vor: ∅{sum(rhr_pre)/len(rhr_pre):.1f} bpm  |  "
                     f"Nach: ∅{sum(rhr_post)/len(rhr_post):.1f} bpm  |  "
                     f"Δ: {sum(rhr_post)/len(rhr_post) - sum(rhr_pre)/len(rhr_pre):+.1f} bpm\n")

    schl_pre  = [schlaf_dict[d] for d in dates if d < cutoff  and d in schlaf_dict]
    schl_post = [schlaf_dict[d] for d in dates if d >= cutoff and d in schlaf_dict]
    if schl_pre and schl_post:
        lines.append(f"### Schlaf-Score ({sleep_label})")
        lines.append(f"  Vor: ∅{sum(schl_pre)/len(schl_pre):.1f}  |  "
                     f"Nach: ∅{sum(schl_post)/len(schl_post):.1f}  |  "
                     f"Δ: {sum(schl_post)/len(schl_post) - sum(schl_pre)/len(schl_pre):+.1f}\n")

    return "\n".join(lines)


def _plot(hrv_data, cutoff, rhr_dict, rhr_label="unbekannte Quelle"):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        dates = [r[0] for r in hrv_data]
        vals  = [r[1] for r in hrv_data]
        xs    = [datetime.strptime(d, "%Y-%m-%d") for d in dates]
        cutoff_dt = datetime.strptime(cutoff, "%Y-%m-%d")
        ra = rolling_avg(vals, 28)

        fig_rows = 2 if rhr_dict else 1
        fig, axes = plt.subplots(fig_rows, 1, figsize=(14, 5 * fig_rows),
                                  facecolor="#1A1A2E", sharex=True)
        if fig_rows == 1:
            axes = [axes]
        fig.suptitle(f"ITS — Cutoff: {cutoff}", color="#E0E0E0", fontsize=12)

        ax = axes[0]
        ax.set_facecolor("#16213E")
        dot_colors = ["#4A90D9" if d < cutoff else "#E84855" for d in dates]
        ax.scatter(xs, vals, c=dot_colors, s=8, alpha=0.35, zorder=2)
        ax.plot(xs, ra, color="#F4A261", linewidth=1.5, label="28d-Mittelwert", zorder=3)

        pre_vals  = [v for d, v in zip(dates, vals) if d < cutoff]
        post_vals = [v for d, v in zip(dates, vals) if d >= cutoff]
        pre_xs    = [x for x, d in zip(xs, dates) if d < cutoff]
        post_xs   = [x for x, d in zip(xs, dates) if d >= cutoff]
        if pre_vals:
            m = sum(pre_vals) / len(pre_vals)
            ax.hlines(m, pre_xs[0], pre_xs[-1], colors="#4A90D9",
                      linewidth=1.5, linestyle="--", alpha=0.7, label=f"∅ vor {m:.1f}ms")
        if post_vals:
            m = sum(post_vals) / len(post_vals)
            ax.hlines(m, post_xs[0], post_xs[-1], colors="#E84855",
                      linewidth=1.5, linestyle="--", alpha=0.7, label=f"∅ nach {m:.1f}ms")

        res = its_regression(dates, vals, cutoff)
        if res:
            ax.plot(xs, res["y_pred"], color="#57A773", linewidth=1.5,
                    label="ITS-Regression", zorder=4)
            ax.fill_between(xs, res["ci_lower"], res["ci_upper"],
                            color="#57A773", alpha=0.07)

        ax.axvline(cutoff_dt, color="#FFD700", linewidth=1.5, linestyle=":",
                   label=f"Cutoff {cutoff}")
        ax.set_ylabel("RMSSD (ms)", color="#E0E0E0", fontsize=9)
        ax.set_title("HRV Nacht-RMSSD (blau=vor, rot=nach Cutoff)", color="#E0E0E0")
        ax.tick_params(colors="#E0E0E0", labelsize=7)
        ax.legend(fontsize=7, labelcolor="#E0E0E0", facecolor="#16213E")
        for s in ax.spines.values():
            s.set_color("#8B8B8B")

        if len(axes) > 1 and rhr_dict:
            ax2 = axes[1]
            ax2.set_facecolor("#16213E")
            rd = sorted(rhr_dict)
            rxs = [datetime.strptime(d, "%Y-%m-%d") for d in rd]
            rvs = [rhr_dict[d] for d in rd]
            rc = ["#4A90D9" if d < cutoff else "#E84855" for d in rd]
            ax2.scatter(rxs, rvs, c=rc, s=8, alpha=0.4)
            ax2.plot(rxs, rolling_avg(rvs, 28), color="#F4A261", linewidth=1.5,
                     label="28d-Mittelwert")
            ax2.axvline(cutoff_dt, color="#FFD700", linewidth=1.5, linestyle=":")
            ax2.set_ylabel("Ruhepuls (bpm)", color="#E0E0E0", fontsize=9)
            ax2.set_title(f"Ruhepuls — {rhr_label}", color="#E0E0E0")
            ax2.tick_params(colors="#E0E0E0", labelsize=7)
            ax2.legend(fontsize=7, labelcolor="#E0E0E0", facecolor="#16213E")
            for s in ax2.spines.values():
                s.set_color("#8B8B8B")

        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        fig.autofmt_xdate(rotation=45)
        fig.tight_layout()
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = OUT_DIR / f"postinfectious_its_{ts}.png"
        fig.savefig(str(path), dpi=130, bbox_inches="tight", facecolor="#1A1A2E")
        plt.close()
        print(f"Plot: {path}")
    except Exception as e:
        print(f"Plot fehlgeschlagen: {e}")


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=SYSTEM_PROMPT, max_tokens=3000)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""

def run_its(cutoff: str, d_from: str | None = None,
            d_to: str | None = None) -> str:
    """ITS-Analyse für einen Cutoff; gibt Markdown-Textblock zurück.

    Öffnet eigene DB-Verbindung. Gibt '' zurück wenn < 30 Datenpunkte
    je Segment vorhanden sind.
    """
    from modules.db import open_db
    conn = open_db()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        d_from = d_from or cutoff
        d_to   = d_to   or today

        hrv_data = load_hrv(conn, d_from, d_to)
        if not hrv_data:
            return ""
        
        rhr_dict = load_rhr(conn, d_from, d_to)
        schlaf_dict = load_sleep(conn, d_from, d_to)
        rhr_label = _device_label(rhr_sources(conn, d_from, d_to))
        sleep_label = _device_label(sleep_sources(conn, d_from, d_to))
        conn.close()

        # Mindest-Datenpunkt-Schwelle
        dates = [r[0] for r in hrv_data]
        vals = [r[1] for r in hrv_data]
        pre = [v for d, v in zip(dates, vals) if d < cutoff]
        post = [v for d, v in zip(dates, vals) if d >= cutoff]

        if len(pre) < 30 or len(post) < 30:
            return ""

        return build_report(hrv_data, cutoff, rhr_dict, schlaf_dict,
                            rhr_label=rhr_label, sleep_label=sleep_label)
    except Exception:
        return ""
    finally:
        if 'conn' in locals() and not conn.closed:
            conn.close()


def _save(report, cutoff, llm_text=""):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT_DIR / f"postinfectious_its_{ts}.md"
    content = f"# ITS-Analyse — Cutoff {cutoff}\n\n{report}\n"
    if llm_text:
        content += f"\n## Klinische Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(f"Bericht: {out}")


def main():
    parser = argparse.ArgumentParser(description=t("ITS-Analyse (Interrupted Time Series)", "ITS Analysis (Interrupted Time Series)"))
    parser.add_argument("--from",   dest="date_from",
                        default=_cfg.data_start or "1900-01-01")
    parser.add_argument("--to",     dest="date_to",
                        default=str(datetime.today().date()))
    parser.add_argument("--cutoff", default=_cfg.infection_date,
                        help="Event cut-off date YYYY-MM-DD "
                             "(default: clinical.infection_date from config)")
    parser.add_argument("--plot",   action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    if not args.cutoff:
        parser.error(t(
            "--cutoff erforderlich (oder clinical.infection_date in health_config.json setzen)",
            "--cutoff required (or set clinical.infection_date in health_config.json)"))

    conn = open_db()
    hrv_data = load_hrv(conn, args.date_from, args.date_to)
    if not hrv_data:
        print("Keine HRV-Daten im angegebenen Zeitraum.")
        conn.close()
        return

    print(f"HRV: {len(hrv_data)} Einträge ({hrv_data[0][0]} – {hrv_data[-1][0]})")
    rhr_dict    = load_rhr(conn, args.date_from, args.date_to)
    schlaf_dict = load_sleep(conn, args.date_from, args.date_to)
    rhr_label   = _device_label(rhr_sources(conn, args.date_from, args.date_to))
    sleep_label = _device_label(sleep_sources(conn, args.date_from, args.date_to))
    conn.close()

    report = build_report(hrv_data, args.cutoff, rhr_dict, schlaf_dict,
                          rhr_label=rhr_label, sleep_label=sleep_label)
    print("\n" + report)

    if args.plot:
        _plot(hrv_data, args.cutoff, rhr_dict, rhr_label=rhr_label)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, args.cutoff, llm_text)


if __name__ == "__main__":
    main()
