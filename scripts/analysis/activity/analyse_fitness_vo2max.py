#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Fitness & VO2max-Trend

Analysiert die aerobe Kapazität über Zeit aus Polar (Own Index) und zwei
unabhängigen Garmin-Schätzverfahren (aktivitätsbasiert / biometrisch) sowie
Oura. VO2max ist einer der stärksten objektiven Marker für körperliche
Konditionsveränderungen.

Usage:
  python analyse_fitness_vo2max.py --plot
  python analyse_fitness_vo2max.py --from YYYY-MM-DD --plot
  python analyse_fitness_vo2max.py --plot --no-llm

@tier        heuristic
@purpose.de  Analysiert die aerobe Kapazität (VO2max) über Zeit aus Polar Own Index,
             zwei unabhängigen Garmin-Schätzverfahren (aktivitätsbasiert und
             biometrisch) und Oura als Marker für Konditionsveränderungen.
@purpose.en  Analyses aerobic capacity (VO2max) over time from Polar Own Index, two
             independent Garmin estimation methods (activity-based and biometric)
             and Oura as a marker for fitness changes.
@method.de   Sammelt gerätespezifische VO2max-Schätzungen (Polar Orthostatik-Testprotokoll,
             Garmin get_training_status().mostRecentVO2Max.generic [aktivitätsbasiert,
             source_app=garmin_connect] und Garmin fitnessAgeData.biometricVo2Max
             [biometrisch, source_app=garmin_gdpr], Oura-Modell) ohne Kreuzvalidierung
             zwischen Geräten oder Verfahren; die beiden Garmin-Schätzungen liegen im
             selben Zeitraum ~10 Punkte auseinander und werden nie gemittelt, sondern
             getrennt berichtet. Bei garmin_connect zählt nur ein Wertwechsel als
             Messung, da wiederholte Abrufe denselben Wert mit neuem Datum re-schreiben
             konnten. ACSM-Referenzwerte für Klassifikation (>45 / 38–45 / 30–38 /
             23–30 / <23 ml/min/kg).
@method.en   Collects device-specific VO2max estimates (Polar orthostatic test, Garmin
             get_training_status().mostRecentVO2Max.generic [activity-based,
             source_app=garmin_connect] and Garmin fitnessAgeData.biometricVo2Max
             [biometric, source_app=garmin_gdpr], Oura model) without cross-device or
             cross-method validation; the two Garmin estimates diverge by ~10 points
             over the same period and are never averaged, always reported separately.
             For garmin_connect, only a value change counts as a measurement, since
             repeated fetches could re-write the same value under a new date. ACSM
             reference values for classification (>45 / 38–45 / 30–38 / 23–30 / <23
             ml/min/kg).
@limits.de   Heuristische Methode: VO2max-Schätzungen aus Consumer-Geräten haben Messungenauigkeiten von ±10–20 %.
             Polar Own Index und die beiden Garmin-Verfahren nutzen unterschiedliche
             Algorithmen und sind, wie die Divergenz zwischen den beiden Garmin-
             Schätzungen desselben Geräts zeigt, nur begrenzt belastbar.
             Keine Spiroergometrie-Referenz. n=1. Die Referenzlinien im Plot (25 / 35
             ml/min/kg) sind generische Orientierungswerte — ACSM-Normwerte sind
             alters- und geschlechtsspezifisch (z.B. sehr gut: >42 ml/min/kg für Personen 20–29 J).
@limits.en   Heuristic method: VO2max estimates from consumer devices have measurement uncertainties of ±10–20 %.
             Polar Own Index and the two Garmin methods use different algorithms and,
             as shown by the divergence between the two Garmin estimates of the same
             device, have limited reliability. No spiroergometry
             reference. n=1. Plot reference lines (25 / 35 ml/min/kg) are generic
             orientation values — ACSM norms are time period- and sex-specific.
@scoring
    VO2max classes (ACSM): >45 excellent | 38-45 very good | 30-38 good | 23-30 fair | <23 poor
    Polar Own Index: EXCELLENT | VERY_GOOD | GOOD | ACCEPTABLE | NEEDS_IMPROVEMENT
@refs        ACSM Guidelines for Exercise Testing and Prescription, 11th ed. 2022
             Myers J, Prakash M, Froelicher V, Do D, Partington S, Atwood JE (2002). Exercise Capacity and Mortality among Men Referred for Exercise Testing. New England Journal of Medicine, 346(11):793-801. doi:10.1056/NEJMoa011858
             Tanaka H, Monahan KD, Seals DR (2001). Age-predicted maximal heart rate revisited. Journal of the American College of Cardiology, 37(1):153-156. doi:10.1016/S0735-1097(00)01054-8
             Gulati M, Black HR, Shaw LJ, et al. (2005). The Prognostic Value of a Nomogram for Exercise Capacity in Women. New England Journal of Medicine, 353(5):468-475. doi:10.1056/nejmoa044154

@relevance.de  Ermöglicht die Analyse von Aktivitätsdaten, essentiell für die Bewegungs- und Fitnessanalyse
@relevance.en  Enables activity data analysis, essential for movement and fitness analysis
@reads       assessments, measurements, oura_vo2max, daily_stress
@writes      analyses/activity/*.{md,png} (kein DB-Write)

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_fitness_vo2max.py
    python analyse_fitness_vo2max.py --help
    python analyse_fitness_vo2max.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_activity import (
    SYSTEM_PROMPT_ANALYSE_FITNESS_VO2MAX_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_FITNESS_VO2MAX_EN as SYSTEM_PROMPT_EN,
)
_cfg = _Cfg()

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "activity"

# VO2max Fitness-Klassen (Polar)
FITNESS_KLASSEN = {
    "EXCELLENT": "Ausgezeichnet",
    "VERY_GOOD": "Sehr gut",
    "GOOD":      "Gut",
    "MODERATE":  "Durchschnittlich",
    "FAIR":      "Unterdurchschnittlich",
    "POOR":      "Niedrig",
}


def load_data(conn, d_from, d_to):
    polar = conn.execute("""
        SELECT a.date,
               a.score AS own_index,
               COALESCE(
                   JSON_EXTRACT(a.details, '$.fitness_class'),
                   JSON_EXTRACT(a.details, '$.class')
               ) AS fitness_class
        FROM assessments a
        WHERE a.instrument = 'polar_fitness_test'
          AND a.date >= ? AND a.date <= ?
        ORDER BY a.date
    """, (d_from, d_to)).fetchall()

    # VO2max: Garmin liefert ZWEI unabhaengige, nicht vergleichbare Schaetzungen
    # (siehe Docstring @limits) — niemals gemischt/gemittelt ueber source_app
    # hinweg lesen, sonst entsteht ein bedeutungsloser Mittelwert zwischen zwei
    # ~10 Punkte auseinanderliegenden Verfahren. Getrennt geladen:
    #   vo2_activity   = garmin_connect (aktivitaetsbasiert, get_training_status()
    #                     .mostRecentVO2Max.generic, ganzzahlig)
    #   vo2_biometric  = garmin_gdpr (biometrisch, fitnessAgeData.biometricVo2Max,
    #                     mit Nachkommastellen)
    vo2_activity = conn.execute("""
        SELECT date, value AS vo2
        FROM measurements
        WHERE metric = 'vo2max' AND source_app = 'garmin_connect'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        ORDER BY date
    """, (d_from, d_to)).fetchall()
    vo2_activity = _collapse_unchanged(vo2_activity)

    vo2_biometric = conn.execute("""
        SELECT date, value AS vo2
        FROM measurements
        WHERE metric = 'vo2max' AND source_app = 'garmin_gdpr'
          AND date >= ? AND date <= ?
          AND value IS NOT NULL
        ORDER BY date
    """, (d_from, d_to)).fetchall()

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    oura_vo2 = []
    if "oura_vo2max" in tables:
        oura_vo2 = conn.execute("""
            SELECT day, vo2_max FROM oura_vo2max
            WHERE day >= ? AND day <= ? ORDER BY day
        """, (d_from, d_to)).fetchall()

    stress = {}
    if "daily_stress" in tables:
        for d, rmssd, *_ in conn.execute("""
            SELECT date, rmssd_ms FROM daily_stress
            WHERE date >= ? AND date <= ?
        """, (d_from, d_to)):
            stress[d] = rmssd

    return polar, vo2_activity, vo2_biometric, oura_vo2, stress


def _collapse_unchanged(rows):
    """Nur echte Wertwechsel behalten (erste Zeile je neuem Wert).

    garmin_connect (aktivitaetsbasiertes VO2max) schrieb den zuletzt bekannten
    Wert frueher bei jedem Abruf erneut mit dem Abrufdatum weg — die zeitliche
    Dichte war dadurch artifiziell, nur ein Wertwechsel ist ein echtes Update.
    Kollabiert aufeinanderfolgende identische Werte auf die jeweils erste
    Zeile, damit Trend/Zaehlung nicht Abrufhaeufigkeit statt Fitnessaenderung
    misst.
    """
    out = []
    last = None
    for date, val in rows:
        if val != last:
            out.append((date, val))
            last = val
    return out


def _spearman(pairs):
    n = len(pairs)
    if n < 5:
        return None
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


def build_report(polar, vo2_activity, vo2_biometric, oura_vo2, stress, d_from, d_to):
    if not polar and not vo2_activity and not vo2_biometric and not oura_vo2:
        return "No VO2max-Daten im angefragten Time range."

    def avg(lst): return round(sum(lst) / len(lst), 1) if lst else None

    lines = [f"## Fitness & VO2max-Trend — {d_from} bis {d_to}\n"]

    if polar:
        oi_vals = [r[1] for r in polar if r[1]]
        classes = [r[2] for r in polar if r[2]]
        lines += [
            "### Polar Own Index\n",
            f"  Messungen: {len(polar)}  |  Time range: {polar[0][0]} – {polar[-1][0]}",
            f"  Ø: **{avg(oi_vals)}**  |  Min: {min(oi_vals):.0f}  |  Max: {max(oi_vals):.0f}",
        ]
        if classes:
            last_class = FITNESS_KLASSEN.get(polar[-1][2], polar[-1][2])
            lines.append(f"  Letzte Fitness-Klasse: {last_class}")
        if len(oi_vals) >= 4:
            delta = round(oi_vals[-1] - oi_vals[0], 1)
            lines.append(f"  Trend: {delta:+.1f} (erste: {oi_vals[0]} → letzte: {oi_vals[-1]})")
        lines.append("\n  All Messungen:")
        for r in polar:
            kl = FITNESS_KLASSEN.get(r[2], r[2] or "")
            lines.append(f"  {r[0]}  Own Index: {r[1]}  ({kl})")

    # Zwei Garmin-Schaetzverfahren — getrennt berichtet, nie gemittelt (s. load_data).
    if vo2_activity:
        vo2_vals = [r[1] for r in vo2_activity if r[1]]
        lines += [
            "\n### Garmin VO2max — aktivitätsbasiert (garmin_connect)\n",
            f"  Wertwechsel: {len(vo2_activity)}  |  Ø: **{avg(vo2_vals)} ml/min/kg**",
            f"  Min: {min(vo2_vals):.0f}  |  Max: {max(vo2_vals):.0f}",
        ]
        if len(vo2_vals) >= 4:
            delta = round(vo2_vals[-1] - vo2_vals[0], 1)
            lines.append(f"  Trend: {delta:+.1f} (erster Wechsel: {vo2_vals[0]:.0f} → letzter: {vo2_vals[-1]:.0f})")
        lines.append("\n  Verlauf (nur Wertwechsel):")
        for r in vo2_activity:
            lines.append(f"  {r[0]}  {r[1]:.0f} ml/min/kg")

    if vo2_biometric:
        vo2_vals = [r[1] for r in vo2_biometric if r[1]]
        lines += [
            "\n### Garmin VO2max — biometrisch (garmin_gdpr)\n",
            f"  Messungen: {len(vo2_biometric)}  |  Ø: **{avg(vo2_vals)} ml/min/kg**",
            f"  Min: {min(vo2_vals):.1f}  |  Max: {max(vo2_vals):.1f}",
        ]
        if len(vo2_vals) >= 4:
            delta = round(vo2_vals[-1] - vo2_vals[0], 1)
            lines.append(f"  Trend: {delta:+.1f} (erste: {vo2_vals[0]:.1f} → letzte: {vo2_vals[-1]:.1f})")
        lines.append("\n  Verlauf (Auszug, letzte 20 Tage):")
        for r in vo2_biometric[-20:]:
            lines.append(f"  {r[0]}  {r[1]:.1f} ml/min/kg")

    if vo2_activity and vo2_biometric:
        common = sorted(set(d for d, _ in vo2_activity) & set(d for d, _ in vo2_biometric))
        if common:
            act = dict(vo2_activity)
            bio = dict(vo2_biometric)
            diffs = [act[d] - bio[d] for d in common]
            mean_diff = sum(diffs) / len(diffs)
            lines.append(
                f"\n⚠️ Beide Garmin-Schätzverfahren divergieren: an {len(common)} gemeinsamen "
                f"Tagen im Mittel {mean_diff:+.1f} ml/min/kg (aktivitätsbasiert − biometrisch). "
                "Zwei Schätzungen desselben Geräts, die deutlich auseinanderliegen — geringe "
                "Belastbarkeit für Absolutwerte, nie als eine Zeitreihe mischen."
            )

    if oura_vo2:
        lines += ["\n### Oura VO2max\n"]
        for r in oura_vo2:
            lines.append(f"  {r[0]}  {r[1]:.1f} ml/min/kg")

    # Correlation VO2max × HRV — je Garmin-Verfahren getrennt (s.o.: nicht mischen)
    for label, series in [
        ("aktivitätsbasiert", vo2_activity),
        ("biometrisch", vo2_biometric),
    ]:
        vo2_pts = [(r[0], r[1]) for r in (series or []) if r[1]]
        if len(vo2_pts) >= 5:
            pairs = [(v, stress[d]) for d, v in vo2_pts if stress.get(d)]
            rs = _spearman(pairs)
            if rs is not None:
                lines.append(f"\nCorrelation VO2max ({label}) × HRV RMSSD (Spearman r): {rs}")

    return "\n".join(lines)


def _plot(polar, vo2_activity, vo2_biometric, oura_vo2, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, ax = plt.subplots(figsize=(14, 5), facecolor="#1e1e2e")
    ax.set_facecolor("#2a2a3e")
    ax.tick_params(colors="#aaa", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    fig.suptitle(f"VO2max & Fitness-Kapazität {d_from}–{d_to}",
                 color="#E0E0E0", fontsize=13)

    if polar:
        dts  = [datetime.fromisoformat(r[0]) for r in polar if r[1]]
        vals = [r[1] for r in polar if r[1]]
        ax.plot(dts, vals, "o-", color="#2ecc71", ms=8, lw=1.5, label="Polar Own Index")

    if vo2_activity:
        dts  = [datetime.fromisoformat(r[0]) for r in vo2_activity if r[1]]
        vals = [r[1] for r in vo2_activity if r[1]]
        ax.plot(dts, vals, "s-", color="#74b9ff", ms=6, lw=1.2, alpha=0.9,
                label="Garmin VO2max (aktivitätsbasiert)")

    if vo2_biometric:
        dts  = [datetime.fromisoformat(r[0]) for r in vo2_biometric if r[1]]
        vals = [r[1] for r in vo2_biometric if r[1]]
        ax.plot(dts, vals, "-", color="#fd79a8", lw=0.9, alpha=0.7,
                label="Garmin VO2max (biometrisch)")

    if oura_vo2:
        dts  = [datetime.fromisoformat(r[0]) for r in oura_vo2 if r[1]]
        vals = [r[1] for r in oura_vo2 if r[1]]
        ax.plot(dts, vals, "^", color="#a29bfe", ms=8, label="Oura VO2max")

    # Referenzlinien (generische Orientierungswerte — ACSM-Normwerte sind alters-/geschlechtsspezifisch)
    ax.axhline(25, color="#e17055", lw=0.8, ls="--", alpha=0.5, label="Niedrig (<25)")  # ACSM 2022: generischer Orientierungswert; nicht alters-/geschlechtsspezifisch
    ax.axhline(30, color="#fdcb6e", lw=0.6, ls=":", alpha=0.5)
    ax.axhline(35, color="#2ecc71", lw=0.6, ls=":", alpha=0.4, label="Average (35)")  # ACSM 2022: Myers et al. 2002 N Engl J Med, doi:10.1056/NEJMoa011858
    ax.set_ylabel("VO2max / Own Index (ml/min/kg)", color="#ccc", fontsize=9)
    ax.legend(fontsize=8, facecolor="#2a2a3e", labelcolor="white")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p = OUT_DIR / f"fitness_vo2max_{ts}.png"
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
    out = OUT_DIR / f"fitness_vo2max_{ts}.md"
    content = f"# Fitness & VO2max-Trend\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


def main():
    parser = argparse.ArgumentParser(description=t("Fitness & VO2max-Trend", "Fitness & VO2max trend"))
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
    polar, vo2_activity, vo2_biometric, oura_vo2, stress = load_data(conn, args.date_from, args.date_to)
    conn.close()

    if not polar and not vo2_activity and not vo2_biometric and not oura_vo2:
        print(t("Keine VO2max-Daten. Zuerst Polar/Garmin/Oura importieren.",
                "No VO2max data. Import Polar/Garmin/Oura first."))
        return

    print(t(f"Polar: {len(polar)}  |  Garmin aktivitätsbasiert: {len(vo2_activity)}  |  "
            f"Garmin biometrisch: {len(vo2_biometric)}  |  Oura: {len(oura_vo2)}",
            f"Polar: {len(polar)}  |  Garmin activity-based: {len(vo2_activity)}  |  "
            f"Garmin biometric: {len(vo2_biometric)}  |  Oura: {len(oura_vo2)}"))
    report = build_report(polar, vo2_activity, vo2_biometric, oura_vo2, stress,
                               args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(polar, vo2_activity, vo2_biometric, oura_vo2, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
