#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Blood glucose-Analyse (Glukometer)

Analysiert Blood glucose-Messungen: Tageszeit-Profile, Verteilung, In-Range-Quote,
Marker-Evaluation (nüchtern/nach Mahlzeit) and Trend über Zeit.

Usage:
  python analyse_blood_glucose.py --plot
  python analyse_blood_glucose.py --from YYYY-MM-DD --plot
  python analyse_blood_glucose.py --plot --no-llm

@tier        validated
@purpose.de  Analysiert Blutzucker-Selbstmessungen aus dem Glukometer: Tageszeit-Profile,
             Werteverteilung, Time-in-Range-Quote, Nüchtern-/Postprandial-Marker und Trend.
@purpose.en  Analyses blood glucose self-measurements from glucometer: time-of-day profiles,
             value distribution, time-in-range fraction, fasting/post-prandial markers and trend.
@method.de   Klassifikation nach IDF/ADA-Grenzwerten: Nüchtern <100 mg/dL normal,
             100–125 prädiabetisch, ≥126 diabetisch; 2h postprandial <140 / 140–199 / ≥200 mg/dL.
             Zielbereich 70–140 mg/dL für Time-in-Range-Berechnung.
@method.en   Classification per IDF/ADA thresholds: fasting <100 mg/dL normal,
             100–125 pre-diabetic, ≥126 diabetic; 2h post-prandial <140 / 140–199 / ≥200 mg/dL.
             Target range 70–140 mg/dL for time-in-range calculation.
@refs        American Diabetes Association Standards 2024, Diabetes Care,
             American Diabetes Association Professional Practice Committee (2024). 5. Facilitating Positive Health Behaviors and Well-being to Improve Health Outcomes: Standards of Care in Diabetes—2024. Diabetes Care, 47(Supplement_1):S77-S110. doi:10.2337/dc24-S005

@relevance.de  Ermöglicht die Stoffwechselanalyse, essentiell für die metabolische Gesundheit
@relevance.en  Enables metabolic analysis, essential for metabolic health
@limits.de   Glukometer-Punktmessungen erfassen keine kontinuierlichen Schwankungen.
             Messfrequenz und Zeitpunkte sind nicht standardisiert (keine Studie-OGTT-Bedingungen).
@limits.en   Glucometer spot measurements do not capture continuous glucose fluctuations.
             Measurement frequency and timing are not standardised (not OGTT conditions).
@reads       blood_glucose
@writes      analyses/metabolic/*.{md,png} (kein DB-Write)

@prompt-classification  LLM:Analysis
@prompt.de             SYSTEM_PROMPT (de_only)
@prompt.en             -

@usage
    python analyse_blood_glucose.py
    python analyse_blood_glucose.py --help
    python analyse_blood_glucose.py --from 2024-01-01 --to 2024-12-31
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
OUT_DIR = _cfg.analyses_dir / "metabolic"

from modules.prompts.analysis_metabolic import (
    SYSTEM_PROMPT_ANALYSE_BLOOD_GLUCOSE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_BLOOD_GLUCOSE_EN as SYSTEM_PROMPT_EN,
)

ZIELBEREICH_MIN = 70
ZIELBEREICH_MAX = 140


def load_data(conn, d_from, d_to, person):
    """Spot-Blutzucker der auswertenden Person.

    Filtert zwingend nach `person`: ein Blutzuckermessgeraet wird typischerweise
    von mehreren Personen benutzt, und `blood_glucose` fuehrt die Messwerte aller
    Nutzer derselben Hardware. Ohne den Filter erscheinen fremde Werte im Bericht.
    """
    rows = conn.execute("""
        SELECT ts, date, glucose_mgdl, glucose_mmol, meal_context, hba1c
        FROM blood_glucose
        WHERE date >= ? AND date <= ? AND person = ?
          AND glucose_mgdl IS NOT NULL
        ORDER BY ts
    """, (d_from, d_to, person)).fetchall()
    return rows


# Tageszeit-Buckets als (Obergrenze in Stunden, DE-Label, EN-Label). Eine
# gemeinsame Quelle für tageszeit_gruppe() (Zuordnung) und build_report()
# (Ausgabereihenfolge), damit beide nie auseinanderlaufen. Das 7–10-Uhr-
# Fenster heisst bewusst "nüchtern"/"fasting" statt neutral "Vormittags",
# weil es den Nüchtern-Glukose-Marker abbildet (siehe @method oben).
# t() wird hier bei jedem Aufruf neu ausgewertet (nicht als Modul-Konstante
# vorberechnet), damit --lang/apply_lang_from_args() aus main() greift, auch
# wenn das erst nach dem Import passiert.
_TAGESZEIT_BUCKETS = [
    (7,  "Nachts (0–7)",             "Night (0–7)"),
    (10, "Morgens, nüchtern (7–10)", "Morning, fasting (7–10)"),
    (14, "Mittags (10–14)",          "Midday (10–14)"),
    (18, "Nachmittags (14–18)",      "Afternoon (14–18)"),
    (24, "Abends (18–24)",           "Evening (18–24)"),
]


def _tageszeit_labels() -> list[str]:
    """Bucket-Labels in fester Reihenfolge, sprachabhängig via t()."""
    return [t(de, en) for _, de, en in _TAGESZEIT_BUCKETS]


def tageszeit_gruppe(dt_str):
    h = int(dt_str[11:13]) if len(dt_str) >= 13 else 12
    for upper, de, en in _TAGESZEIT_BUCKETS:
        if h < upper:
            return t(de, en)
    return t(_TAGESZEIT_BUCKETS[-1][1], _TAGESZEIT_BUCKETS[-1][2])


def build_report(rows, d_from, d_to):
    if not rows:
        return "No Blood glucose-Daten im angefragten Time range."

    n = len(rows)
    vals_mg  = [r[2] for r in rows]
    avg_mg   = round(sum(vals_mg) / n, 1)
    min_mg   = min(vals_mg)
    max_mg   = max(vals_mg)
    std_mg   = round((sum((v - avg_mg)**2 for v in vals_mg) / n) ** 0.5, 1)

    n_low    = sum(1 for v in vals_mg if v < ZIELBEREICH_MIN)
    n_high   = sum(1 for v in vals_mg if v > ZIELBEREICH_MAX)
    n_range  = n - n_low - n_high
    tir_pct  = round(n_range / n * 100, 1)

    hba1c_vals = [r[5] for r in rows if r[5]]
    hba1c_str  = f"{round(sum(hba1c_vals)/len(hba1c_vals),1)}% ({len(hba1c_vals)} Messungen)" \
                 if hba1c_vals else "nicht vorhanden"

    # Marker-Analyse (meal_context)
    marker_dist = defaultdict(list)
    for r in rows:
        m = (r[4] or "unbekannt").strip() or "unbekannt"
        marker_dist[m].append(r[2])

    # Tageszeit-Profile
    tz_vals = defaultdict(list)
    for r in rows:
        tz_vals[tageszeit_gruppe(r[0])].append(r[2])

    # Trend
    dates_ord = [(datetime.fromisoformat(r[1]).toordinal(), r[2]) for r in rows]
    if len(dates_ord) >= 10:
        n_r = len(dates_ord)
        xs = [x for x, _ in dates_ord]
        ys = [y for _, y in dates_ord]
        mx, my = sum(xs)/n_r, sum(ys)/n_r
        cov = sum((xs[i]-mx)*(ys[i]-my) for i in range(n_r))
        var = sum((xs[i]-mx)**2 for i in range(n_r))
        slope_yr = round(cov / var * 365, 1) if var > 0 else 0
        trend_str = f"{slope_yr:+.1f} mg/dL/Jahr"
    else:
        trend_str = "zu wenig Daten"

    lines = [
        f"## Blood glucose-Analyse — {d_from} bis {d_to}\n",
        f"Messungen: **{n}**  |  Time range: {rows[0][1]} – {rows[-1][1]}",
        f"Ø BZ: **{avg_mg} mg/dL** ({round(avg_mg/18.0, 1)} mmol/L)  |  "
        f"SD: {std_mg}  |  Min: {min_mg}  |  Max: {max_mg}",
        f"Time in Range ({ZIELBEREICH_MIN}–{ZIELBEREICH_MAX} mg/dL): **{tir_pct}%** "
        f"({n_range}/{n})",
        f"Hypo (<{ZIELBEREICH_MIN}): {n_low} ({round(n_low/n*100,1)}%)  |  "
        f"Hyper (>{ZIELBEREICH_MAX}): {n_high} ({round(n_high/n*100,1)}%)",
        f"HbA1c: {hba1c_str}",
        f"Trend: {trend_str}\n",
        t("### Tageszeit-Profil\n", "### Time-of-day profile\n"),
        "  {:<24} {:>8} {:>6} {:>6} {:>5}".format(
            t("Tageszeit", "Time of day"), t("Ø mg/dL", "Avg mg/dL"),
            t("Min", "Min"), t("Max", "Max"), t("n", "n"),
        ),
        "  " + "-" * 52,
    ]
    for g in _tageszeit_labels():
        if g in tz_vals:
            v = tz_vals[g]
            avg = round(sum(v)/len(v), 1)
            flag = " ⚠" if avg > 140 else (" ↓" if avg < 70 else "")
            lines.append(f"  {g:<24} {avg:>8.1f} {min(v):>6.0f} {max(v):>6.0f} {len(v):>5}{flag}")

    if len(marker_dist) > 1:
        lines += ["\n### Nach Messzeitpunkt (Marker)\n",
                  f"  {'Marker':<24} {'Ø mg/dL':>8} {'n':>5}"]
        lines.append("  " + "-" * 40)
        for m, v in sorted(marker_dist.items(), key=lambda x: -len(x[1])):
            avg = round(sum(v)/len(v), 1)
            flag = " ⚠" if avg > 140 else ""
            lines.append(f"  {m:<24} {avg:>8.1f} {len(v):>5}{flag}")

    return "\n".join(lines)


def _plot(rows, d_from, d_to):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), facecolor="#1e1e2e")
    fig.suptitle(f"Blood glucose-Verlauf {d_from}–{d_to}", color="#E0E0E0", fontsize=13)

    for ax in axes:
        ax.set_facecolor("#2a2a3e")
        ax.tick_params(colors="#aaa", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")

    dts  = [datetime.fromisoformat(r[0]) for r in rows]
    vals = [r[2] for r in rows]

    colors = ["#2ecc71" if ZIELBEREICH_MIN <= v <= ZIELBEREICH_MAX
              else ("#ff6b6b" if v > ZIELBEREICH_MAX else "#74b9ff")
              for v in vals]
    axes[0].scatter(dts, vals, c=colors, s=20, alpha=0.8)
    axes[0].axhline(ZIELBEREICH_MAX, color="#ff6b6b", lw=0.8, ls="--", alpha=0.6)
    axes[0].axhline(ZIELBEREICH_MIN, color="#74b9ff", lw=0.8, ls="--", alpha=0.6)
    axes[0].axhline(100, color="#fdcb6e", lw=0.5, ls=":", alpha=0.5)
    axes[0].set_ylabel("Blood glucose (mg/dL)", color="#ccc", fontsize=9)
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

    # Histogramm
    axes[1].hist(vals, bins=30, color="#4ecdc4", alpha=0.8, edgecolor="#2a2a3e")
    axes[1].axvline(ZIELBEREICH_MIN, color="#74b9ff", lw=1, ls="--")
    axes[1].axvline(ZIELBEREICH_MAX, color="#ff6b6b", lw=1, ls="--")
    axes[1].axvline(126, color="#d63031", lw=1, ls=":")
    axes[1].set_xlabel("mg/dL", color="#ccc", fontsize=9)
    axes[1].set_ylabel("Häufigkeit", color="#ccc", fontsize=9)

    plt.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    p  = OUT_DIR / f"blood_glucose_{ts}.png"
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
    out = OUT_DIR / f"blood_glucose_{ts}.md"
    content = f"# Blood glucose-Analyse\n\n{report}\n"
    if llm_text:
        content += f"\n## Clinical Interpretation\n\n{llm_text}\n"
    out.write_text(content, encoding="utf-8")
    print(t(f"Bericht: {out}", f"Report: {out}"))


def main():
    parser = argparse.ArgumentParser(description=t("Blood glucose-Analyse", "Blood glucose analysis"))
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
    rows = load_data(conn, args.date_from, args.date_to, args.person)
    conn.close()

    if not rows:
        print(t("Keine Blutzucker-Daten. Zuerst: python3 importers/import_beurer.py",
                "No blood glucose data. Run first: python3 importers/import_beurer.py"))
        return

    print(t(f"Blutzucker-Messungen: {len(rows)} ({rows[0][1]} – {rows[-1][1]})",
            f"Blood glucose readings: {len(rows)} ({rows[0][1]} – {rows[-1][1]})"))

    report = build_report(rows, args.date_from, args.date_to)
    print("\n" + report)

    if args.plot:
        _plot(rows, args.date_from, args.date_to)

    llm_text = "" if args.no_llm else _run_llm(report)
    _save(report, llm_text)


if __name__ == "__main__":
    main()
