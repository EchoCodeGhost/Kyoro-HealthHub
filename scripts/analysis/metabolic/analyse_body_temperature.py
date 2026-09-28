#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Body temperature-Verlauf & Entzündungs-Analyse

Analysiert Langzeit-Skin temperature aus Polar (SL_DISTAL),
nächtliche Handgelenktemperatur aus Apple Watch (wrist_temp_sleep)
and Oura-Abweichungen. Detects subfebrile Phasen,
circadiane Muster and Correlationen with HRV/Symptomsn.

Usage:
  python analyse_body_temperature.py --plot
  python analyse_body_temperature.py --from YYYY-MM-DD --plot
  python analyse_body_temperature.py --plot --no-llm

@tier        heuristic
@purpose.de  Analysiert Langzeit-Hauttemperatur aus Polar (distal, SL_DISTAL), nächtliche
             Handgelenktemperatur aus Apple Watch und Oura-Abweichungen; detektiert subfebrile
             Phasen und zirkadiane Muster.
@purpose.en  Analyses long-term skin temperature from Polar (distal), nightly wrist temperature
             from Apple Watch and Oura deviations; detects subfebrile phases and circadian patterns.
@method.de   Heuristische Schwellen: Oura-Abweichung > 0,8 °C = erhöht; Haut-Distal > 36 °C =
             ungewöhnlich hoch. Pearson-Korrelation Temperatur × HRV/Symptome. Kein klinisch
             validierter Fieber-Algorithmus.
@method.en   Heuristic thresholds: Oura deviation > 0.8 °C = elevated; distal skin > 36 °C =
             unusually high. Pearson correlation temperature × HRV/symptoms. No clinically
             validated fever algorithm.
@limits.de   Heuristische Methode: Hauttemperatur (distal) ist kein Maß für Körperkerntemperatur. Oura-Abweichung
             ist relativ zur persönlichen Baseline, nicht absolut. Consumer-Sensorik, n=1.
@limits.en   Heuristic method: Skin temperature (distal) does not reflect core body temperature. Oura deviation
             is relative to personal baseline, not absolute. Consumer sensors, n=1.
@refs        Mackowiak PA, Wasserman SS, Levine MM (1992). A critical appraisal of 98.6°F, the upper limit of the normal body temperature, and other legacies of Carl Reinhold August Wunderlich. JAMA, 268(12), 1578-1580. doi:10.1001/jama.1992.03490120092034
             Pho GN, Thigpen N, Patel S, Tily H (2023). Feasibility of measuring physiological responses to breakthrough infections and COVID-19 vaccine using a wearable ring sensor. Digital Biomarkers, 1-6. doi:10.1159/000528874 (Ring-Temperaturabweichung als Infektions-Frühwarnsignal)
             Smarr BL, Aschbacher K, Fisher SM, et al. (2020). Feasibility of continuous fever monitoring using wearable devices. Scientific Reports, 10(1):21640. doi:10.1038/s41598-020-78355-6 (peer-reviewt, n=50; periphere Hauttemperatur via Wearable korreliert mit selbstberichtetem Fieber — direkte methodische Stuetze fuer die hier durchgefuehrte Hauttemperatur-Langzeitanalyse)

@relevance.de  Ermöglicht die Stoffwechselanalyse, essentiell für die metabolische Gesundheit
@relevance.en  Enables metabolic analysis, essential for metabolic health
@scoring
    Temperature thresholds: Oura deviation >0.8°C elevated | Polar distal >36°C unusually high
    Subfebrile phase: persistent elevation above baseline
    Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
@reads       measurements (skin_temperature, wrist_temp_sleep), oura_temperature_raw,
             daily_stress, symptoms
@writes      analyses/metabolic/*.{md,png} (kein DB-Write)

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_body_temperature.py
    python analyse_body_temperature.py --help
    python analyse_body_temperature.py --from 2024-01-01 --to 2024-12-31
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
OUT_DIR = _cfg.analyses_dir / "metabolic"

from modules.prompts.analysis_metabolic import (
    SYSTEM_PROMPT_ANALYSE_BODY_TEMPERATURE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_BODY_TEMPERATURE_EN as SYSTEM_PROMPT_EN,
)

# Skin temperature-Thresholde (distal/Handgelenk)
SUBFEBRIL_DISTAL = 36.0  # über diesem Wert als distal ungewöhnlich hoch markiert
OURA_ERHOEHUNG   = 0.8   # °C über Baseline gilt als erhöht


def load_data(conn, d_from, d_to):
    # Polar: dayss-Aggregat (hours-Withtel for circadianes Profiles)
    polar_daily = conn.execute("""
        SELECT date,
               AVG(value) AS avg_temp,
               MIN(value) AS min_temp,
               MAX(value) AS max_temp
        FROM measurements
        WHERE metric = 'skin_temperature'
          AND source_app IN ('polar_connect', 'polar_flow')
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    # hours-Profiles for circadianen Rhythmus
    polar_hourly = conn.execute("""
        SELECT CAST(SUBSTR(ts, 12, 2) AS INTEGER) AS stunde,
               AVG(value) AS avg_temp
        FROM measurements
        WHERE metric = 'skin_temperature'
          AND source_app IN ('polar_connect', 'polar_flow')
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY stunde
        ORDER BY stunde
    """, (d_from, d_to)).fetchall()

    # Oura: nächtliche Abweichungen (falls Tabelle vorhanden)
    try:
        oura_daily = conn.execute("""
            SELECT DATE(timestamp) AS date, AVG(skin_temp) AS avg_temp
            FROM oura_temperature_raw
            WHERE DATE(timestamp) >= ? AND DATE(timestamp) <= ?
            GROUP BY DATE(timestamp)
            ORDER BY date
        """, (d_from, d_to)).fetchall()
    except Exception:
        oura_daily = []

    # Apple Watch: Handgelenktemperatur im Sleep
    apple_temp = conn.execute("""
        SELECT date, AVG(value) AS avg_temp
        FROM measurements
        WHERE metric = 'wrist_temp_sleep'
          AND source_app = 'apple_health'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    # Klinisches Thermometer (Beurer FT95 u.a.): metric='body_temperature'.
    # Das ist Koerpertemperatur, nicht Haut- oder Handgelenkstemperatur -- deshalb
    # eigene Quelle statt Vermischung mit den Wearable-Werten. Wurde bisher von
    # KEINER Analyse gelesen, obwohl import_beurer.py die Werte schreibt.
    # Plausibilitaetsfilter MUSS auf den Rohwerten greifen, nicht auf dem Tagesmittel:
    # eine unplausible Einzelmessung verschwindet sonst im Durchschnitt des Tages
    # (36.7 + 36.5 + 34.2 -> 35.8) und faelscht ihn still, statt ausgeschlossen zu
    # werden. Unter 35 °C misst kein waches Subjekt -- solche Werte stammen aus
    # abgebrochener oder falsch platzierter Messung.
    clinical_temp = conn.execute("""
        SELECT date, AVG(value) AS avg_temp, MIN(value), MAX(value), COUNT(*)
        FROM measurements
        WHERE metric = 'body_temperature'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
          AND value >= 35.0
        GROUP BY date
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    clinical_implausible = conn.execute("""
        SELECT date, value FROM measurements
        WHERE metric = 'body_temperature'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL AND value < 35.0
        ORDER BY date
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
    elif "symptoms" in tables:
        for d, wert in conn.execute("""
            SELECT date, AVG(value_num) FROM symptoms
            WHERE date >= ? AND date <= ? AND category='Ressourcen' AND value_num IS NOT NULL
            GROUP BY date
        """, (d_from, d_to)):
            symptome[d] = wert

    return polar_daily, polar_hourly, oura_daily, apple_temp, clinical_temp, clinical_implausible, stress, symptome


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


def build_report(polar_daily, polar_hourly, oura_daily, apple_temp, clinical_temp, clinical_implausible, stress, symptome, d_from, d_to):
    if not polar_daily and not oura_daily and not apple_temp and not clinical_temp:
        return "No Temperaturdaten im angefragten Time range."

    def avg(lst): return round(sum(lst) / len(lst), 2) if lst else None

    lines = [f"## Body temperature-Analyse — {d_from} bis {d_to}\n"]

    # Polar Statistiken
    if polar_daily:
        n = len(polar_daily)
        avg_temps = [r[1] for r in polar_daily if r[1]]
        min_temps = [r[2] for r in polar_daily if r[2]]
        max_temps = [r[3] for r in polar_daily if r[3]]
        overall_avg = avg(avg_temps)
        n_hoch = sum(1 for v in avg_temps if v > SUBFEBRIL_DISTAL)

        lines += [
            f"### Polar Skin temperature (distal, n={n} days)\n",
            f"  Ø: **{overall_avg} °C**  |  "
            f"Min: {min(min_temps):.1f}  |  Max: {max(max_temps):.1f}",
            f"  days with erhöhter Temp. (>{SUBFEBRIL_DISTAL}°C): "
            f"{n_hoch} ({round(n_hoch/n*100,1)}%)",
        ]

        # Trend
        if n >= 10:
            q = n // 4
            early = avg(avg_temps[:q])
            late  = avg(avg_temps[-q:])
            if early and late:
                delta = round(late - early, 2)
                lines.append(f"  Trend: {delta:+.2f} °C (früh: {early} → spät: {late})")

    # Circadiana
    if polar_hourly:
        lines.append("\n### Circadianes Temperaturprofil (Polar, hours-Ø)\n")
        peak_h = max(polar_hourly, key=lambda x: x[1])
        tief_h = min(polar_hourly, key=lambda x: x[1])
        for h, t in polar_hourly:
            marker = " ← Max" if h == peak_h[0] else (" ← Min" if h == tief_h[0] else "")
            lines.append(f"  {h:02d}:00  {t:.2f} °C{marker}")

    # Oura
    if oura_daily:
        oura_temps = [r[1] for r in oura_daily if r[1] is not None]
        if oura_temps:
            baseline = avg(oura_temps)
            erhoehen = [v for v in oura_temps if v - baseline > OURA_ERHOEHUNG]
            absinken = [v for v in oura_temps if v - baseline < -OURA_ERHOEHUNG]
            lines += [
                f"\n### Oura Skin temperature (n={len(oura_daily)} Nights)\n",
                f"  Ø: {round(baseline, 2)} °C",
                f"  Nights erhöht (>{OURA_ERHOEHUNG}°C über Ø): {len(erhoehen)}",
                f"  Nights erniedrigt (>{OURA_ERHOEHUNG}°C unter Ø): {len(absinken)}",
            ]

    # Apple Watch
    if clinical_temp:
        ct_vals  = [r[1] for r in clinical_temp if r[1] is not None]
        lines += [f"\n### Klinisches Thermometer — Körpertemperatur (n={len(ct_vals)} Messtage)\n"]
        if ct_vals:
            n_feb = sum(1 for v in ct_vals if v >= 38.0)
            n_sub = sum(1 for v in ct_vals if 37.5 <= v < 38.0)
            lines += [
                f"  Ø: **{avg(ct_vals)} °C**  |  Min: {round(min(ct_vals),1)}  |  Max: {round(max(ct_vals),1)}",
                f"  Fieber (≥38.0 °C): {n_feb}  |  Subfebril (37.5–37.9 °C): {n_sub}",
            ]
        if clinical_implausible:
            lines += [
                f"  ⚠ {len(clinical_implausible)} Einzelmessung(en) unter 35 °C ausgeschlossen: "
                + ", ".join(f"{d} {v:.1f} °C" for d, v in clinical_implausible)
                + " — physiologisch unplausibel, vermutlich Messfehler.",
            ]

    if apple_temp:
        aw_vals = [r[1] for r in apple_temp if r[1] is not None]
        if aw_vals:
            aw_avg  = avg(aw_vals)
            aw_min  = round(min(aw_vals), 2)
            aw_max  = round(max(aw_vals), 2)
            n_hoch_aw = sum(1 for v in aw_vals if v > 37.0)
            lines += [
                f"\n### Apple Watch Handgelenktemperatur im Sleep (n={len(apple_temp)} Nights)\n",
                f"  Ø: **{aw_avg} °C**  |  Min: {aw_min}  |  Max: {aw_max}",
                f"  Nights >37.0 °C: {n_hoch_aw} ({round(n_hoch_aw/len(aw_vals)*100,1)}%)",
            ]
            # Trend
            if len(aw_vals) >= 10:
                q = len(aw_vals) // 4
                early = avg(aw_vals[:q])
                late  = avg(aw_vals[-q:])
                if early and late:
                    delta = round(late - early, 2)
                    lines.append(f"  Trend: {delta:+.2f} °C (früh: {early} → spät: {late})")

    # Correlationen
    if polar_daily:
        dates_p = [r[0] for r in polar_daily]
        temp_vals = [r[1] for r in polar_daily]
        hrv_v  = [stress[d]["hrv"]   if d in stress else None for d in dates_p]
        sym_v  = [symptome.get(d) for d in dates_p]
        r_t_hrv = spearman_r(temp_vals, hrv_v)
        r_t_sym = spearman_r(temp_vals, sym_v)
        if any(r is not None for r in [r_t_hrv, r_t_sym]):
            lines += [
                "\n### Correlation Temperatur × Wohlbefinden (Spearman r)\n",
                f"  Ø Temp × HRV:      {r_t_hrv if r_t_hrv else 'n.a.'}",
                f"  Ø Temp × Energie:  {r_t_sym if r_t_sym else 'n.a.'}",
            ]

    return "\n".join(lines)


def _plot(polar_daily, polar_hourly, oura_daily, apple_temp, stress, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), facecolor="#1e1e2e")
    fig.suptitle(f"Body temperature {d_from}–{d_to}", color="#E0E0E0", fontsize=13)
    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    # Polar-Verlauf
    if polar_daily:
        dts  = [datetime.fromisoformat(r[0]) for r in polar_daily if r[1]]
        vals = [r[1] for r in polar_daily if r[1]]
        axes[0].plot(dts, vals, color="#fdcb6e", lw=1.0, alpha=0.8)
        axes[0].axhline(SUBFEBRIL_DISTAL, color="#e17055", lw=0.8, ls="--", alpha=0.6,
                        label=f"Schwelle {SUBFEBRIL_DISTAL}°C")
        axes[0].set_ylabel("Hauttemp. Ø (°C)", color="#ccc", fontsize=9)
        axes[0].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Circadianes Profiles
    if polar_hourly:
        hours = [r[0] for r in polar_hourly]
        temps = [r[1] for r in polar_hourly]
        axes[1].plot(hours, temps, color="#e17055", lw=1.5, marker="o", ms=4)
        axes[1].set_xticks(range(0, 24))
        axes[1].set_xticklabels([f"{h}" for h in range(0, 24)], fontsize=7, color="#aaa")
        axes[1].set_ylabel("Ø Temp. (°C)", color="#ccc", fontsize=9)
        axes[1].set_xlabel("Uhrzeit", color="#ccc", fontsize=9)

    # Apple Watch + Oura Comparison
    if apple_temp:
        aw_dts  = [datetime.fromisoformat(r[0]) for r in apple_temp if r[1] is not None]
        aw_vals = [r[1] for r in apple_temp if r[1] is not None]
        if aw_dts:
            axes[2].plot(aw_dts, aw_vals, color="#2ecc71", lw=1.2, alpha=0.9,
                         label="Apple Watch (Sleep)")
            axes[2].axhline(37.0, color="#e17055", lw=0.7, ls="--", alpha=0.5)
    if oura_daily:
        oura_temps = [r[1] for r in oura_daily if r[1] is not None]
        if oura_temps:
            o_dts = [datetime.fromisoformat(r[0]) for r in oura_daily if r[1] is not None]
            axes[2].plot(o_dts, oura_temps, color="#a29bfe", lw=1.0, alpha=0.8,
                         label="Oura (Night)")
    if apple_temp or oura_daily:
        axes[2].set_ylabel("Handgelenktemp. (°C)", color="#ccc", fontsize=9)
        axes[2].legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
        axes[2].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"body_temperature_{ts}.png"
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
    out = OUT_DIR / f"body_temperature_{ts}.md"
    content = f"# Body temperature-Analyse\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


def main():
    parser = argparse.ArgumentParser(description=t("Body temperature-Verlauf", "Body temperature trend"))
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
    polar_daily, polar_hourly, oura_daily, apple_temp, clinical_temp, clinical_implausible, stress, symptome = \
        load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not polar_daily and not oura_daily and not apple_temp and not clinical_temp:
        print(t("Keine Temperaturdaten. Zuerst: python3 importers/import_polar.py "
                "und/oder import_apple_health.py",
                "No temperature data. Run first: python3 importers/import_polar.py "
                "and/or import_apple_health.py"))
        return

    print(t(f"Polar-Tage: {len(polar_daily)}  |  Oura-Nächte: {len(oura_daily)}  |  "
            f"Apple Watch-Nächte: {len(apple_temp)}",
            f"Polar days: {len(polar_daily)}  |  Oura nights: {len(oura_daily)}  |  "
            f"Apple Watch nights: {len(apple_temp)}"))

    report = build_report(polar_daily, polar_hourly, oura_daily, apple_temp, clinical_temp, clinical_implausible,
                               stress, symptome, args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(polar_daily, polar_hourly, oura_daily, apple_temp,
              stress, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
