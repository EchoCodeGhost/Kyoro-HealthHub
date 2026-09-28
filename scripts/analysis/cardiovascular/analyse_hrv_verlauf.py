#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
HRV-Verlauf (RMSSD) mit Ereignismarkern — Arzttermin-Export

@tier        heuristic
@refs        Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
             Shaffer F, Ginsberg JP (2017). An overview of heart rate variability metrics and norms. Frontiers in Public Health, 5:258. doi:10.3389/fpubh.2017.00258

@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@purpose.de  Erstellt monatliches RMSSD-Verlaufsdiagramm mit konfigurierten Ereignismarkern
             fuer Kardiologen- oder andere Arzttermine.
@purpose.en  Creates monthly RMSSD trend chart with configured event markers
             for cardiology or other medical appointments.
@method.de   Liest monatliche RMSSD-Mittelwerte aus measurements (mind. 5 Messtage/Monat).
             Zeichnet Ereignislinien aus clinical.events (Typ: infection, reinfection).
             Berechnet Pre/Post-Baseline relativ zum ersten bzw. letzten Ereignis.
             Gibt prozentualen Gesamtrueckgang aus. Speichert als PDF in analyses/<datum>/.
@method.en   Reads monthly RMSSD averages from measurements (min. 5 measurement days/month).
             Draws event lines from clinical.events (type: infection, reinfection).
             Calculates pre/post baseline relative to first/last event.
             Reports total percentage decline. Saves as PDF to analyses/<date>/.
@reads       measurements (metric=hrv_rmssd)
@writes      analyses/cardiovascular/<YYYY-MM-DD>/hrv_cardiology_<datum>.{pdf,md}
@scoring     Prozentualer Rueckgang: (baseline_pre − baseline_post) / baseline_pre × 100;
             kein klinischer Grenzwert, projektintern zur Verlaufsorientierung.
@limits.de   Heuristische Visualisierung. Kein klinisches Diagnosewerkzeug.
             Monatsgranularitaet: Tagesausreisser werden gemittelt.
             Mindestens 5 Messtage pro Monat erforderlich.
@limits.en   Heuristic visualization. Not a clinical diagnostic tool.
             Monthly granularity: daily outliers are averaged out.
             Minimum 5 measurement days per month required.
@usage
    python3 scripts/analysis/cardiovascular/analyse_hrv_verlauf.py
    python3 scripts/analysis/cardiovascular/analyse_hrv_verlauf.py --from 2023-01-01
    python3 scripts/analysis/cardiovascular/analyse_hrv_verlauf.py --out /tmp/hrv.pdf
"""
import sys
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from health_config import Config, OWN_PERSON_ID
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_cardiovascular import (
    SYSTEM_PROMPT_ANALYSE_HRV_VERLAUF_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_HRV_VERLAUF_EN as SYSTEM_PROMPT_EN,
)


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

_cfg = Config()

_inf_events = _cfg.events_of_type("infection", "reinfection")
OUT_DIR     = Path(_cfg.analyses_dir) / "cardiovascular" / datetime.today().strftime("%Y-%m-%d")

# Farbreihe für N Infektionsereignisse (beliebig viele Erreger)
_EVENT_COLORS = ["#e17055", "#d63031", "#6c5ce7", "#0984e3", "#00b894", "#fdcb6e"]


def main():
    ap = argparse.ArgumentParser(
        description=t("HRV-Verlauf für Kardiologen", "HRV course for cardiologist"))
    ap.add_argument("--from", dest="date_from", default=_cfg.data_start or "2000-01-01")
    ap.add_argument("--to",   dest="date_to",   default=datetime.today().strftime("%Y-%m-%d"))
    ap.add_argument("--out",  default=None,
                    help=t("Ausgabepfad (PDF/PNG)", "Output path (PDF/PNG)"))
    ap.add_argument("--plot",   action="store_true",
                    help=t("Plots speichern", "Save plots"))
    ap.add_argument("--no-llm", action="store_true",
                    help=t("KI-Kommentare deaktivieren", "Disable AI commentary"))
    ap.add_argument("--person", default=OWN_PERSON_ID,
                    help=t("Person (Standard: selbst)", "Person (default: self)"))
    add_lang_arg(ap)
    args = ap.parse_args()
    apply_lang_from_args(args)

    conn = open_db()

    # ── Monatliche RMSSD ────────────────────────────────────────────────────
    # Erst je Datum EINEN Nachtwert bilden (AVG je Tag), dann darueber
    # monatlich aggregieren. Ab dem Tag, an dem Garmin von einem nächtlichen
    # Einzelwert auf ~75-90 5-Minuten-Einzelmessungen pro Nacht wechselt,
    # wuerde ein direktes avg/min/max ueber measurements.value die vielen
    # Einzelreadings (inkl. einstelliger Ausreisser-Minima) mit den
    # Nachtmitteln fruehrer Monate vermischen und Min/Max verzerren.
    # Aggregation je Datum in der Subquery macht beide Regimes vergleichbar.
    rows = conn.execute("""
        SELECT strftime('%Y-%m-01', night.date) as mo,
               avg(night.night_val)  as avg,
               min(night.night_val)  as lo,
               max(night.night_val)  as hi,
               count(*)              as days
        FROM (
            SELECT date, AVG(value) AS night_val
            FROM measurements
            WHERE metric='hrv_rmssd' AND person=?
              AND date BETWEEN ? AND ?
            GROUP BY date
        ) night
        GROUP BY mo
        HAVING days >= 5
        ORDER BY mo
    """, (args.person, args.date_from, args.date_to)).fetchall()

    if not rows:
        print(t("Keine HRV-Daten im Zeitraum.", "No HRV data in the selected period."))
        return

    dates = [datetime.strptime(r[0], "%Y-%m-%d") for r in rows]
    avgs  = [r[1] for r in rows]
    los   = [r[2] for r in rows]
    his   = [r[3] for r in rows]

    # Erstes Datum mit >1 Messwert/Nacht = Methodenwechsel (Nachtmittel → 5-Min-Serie)
    switch_row = conn.execute("""
        SELECT MIN(date) FROM (
            SELECT date, COUNT(*) c FROM measurements
            WHERE metric='hrv_rmssd' AND person=?
            GROUP BY date HAVING c > 1
        )
    """, (args.person,)).fetchone()
    method_switch_date = switch_row[0] if switch_row else None

    # Infektionsereignisse als datetime-Objekte (beliebig viele, beliebige Erreger)
    ev_dts = []
    for ev in _inf_events:
        try:
            ev_dts.append((datetime.strptime(ev["date"], "%Y-%m-%d"), ev.get("name", ev["date"])))
        except (KeyError, ValueError):
            pass

    if not ev_dts:
        print(t("Kein Infektionsdatum in health_config.json (clinical.events). Marker werden übersprungen.",
                "No infection date in health_config.json (clinical.events). Markers will be skipped."))

    # Baseline vor erster / nach letzter Infektion
    first_dt = ev_dts[0][0]  if ev_dts else None
    last_dt  = ev_dts[-1][0] if ev_dts else None
    pre  = [a for d, a in zip(dates, avgs) if first_dt is None or d < first_dt]
    post = [a for d, a in zip(dates, avgs) if last_dt  is not None and d >= last_dt]

    baseline_pre  = np.mean(pre)  if pre  else None
    baseline_post = np.mean(post) if post else None

    # ── Plot ────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(13, 5))
    fig.patch.set_facecolor("#fafafa")
    ax.set_facecolor("#fafafa")

    # Bereich min–max (gedämpft)
    ax.fill_between(dates, los, his, alpha=0.12, color="#6c5ce7", label="_nolegend_")

    # Monatliche Durchschnittslinie
    ax.plot(dates, avgs, color="#6c5ce7", lw=2.0, zorder=4,
            label=t("RMSSD ∅ monatlich", "RMSSD avg monthly"))

    # Datenpunkte
    ax.scatter(dates, avgs, color="#6c5ce7", s=28, zorder=5)

    # Infektionslinien — eine pro Ereignis, beliebig viele Erreger
    span = max((dates[-1] - dates[0]).days, 1)
    for i, (ev_dt, ev_name) in enumerate(ev_dts):
        color = _EVENT_COLORS[i % len(_EVENT_COLORS)]
        ax.axvline(ev_dt, color=color, lw=2.0, ls="--", zorder=6,
                   label=f"{ev_name}\n({ev_dt.strftime('%Y-%m-%d')})")

    # Baseline-Horizontalen (vor erster / nach letzter Infektion)
    if baseline_pre is not None and first_dt:
        ax.axhline(baseline_pre, xmax=(first_dt - dates[0]).days / span,
                   color="#00b894", lw=1.2, ls=":", alpha=0.8)
        ax.annotate(t(f"Vor Infektion: ∅ {baseline_pre:.0f} ms",
                      f"Pre-infection: avg {baseline_pre:.0f} ms"),
                    xy=(dates[0], baseline_pre), xytext=(6, 4),
                    textcoords="offset points", fontsize=8.5, color="#00b894")
    if baseline_post is not None and last_dt:
        ax.axhline(baseline_post,
                   xmin=(last_dt - dates[0]).days / span,
                   color="#fdcb6e", lw=1.2, ls=":", alpha=0.8)
        ax.annotate(t(f"Nach letzter Infektion: ∅ {baseline_post:.0f} ms",
                      f"After last infection: avg {baseline_post:.0f} ms"),
                    xy=(last_dt, baseline_post), xytext=(6, -14),
                    textcoords="offset points", fontsize=8.5, color="#b7950b")

    # Prozentualer Gesamtrückgang (vor erster vs. nach letzter Infektion)
    if baseline_pre and baseline_post:
        pct = (baseline_pre - baseline_post) / baseline_pre * 100
        ax.text(0.99, 0.97,
                t(f"Gesamtrückgang: −{pct:.0f}%", f"Total reduction: −{pct:.0f}%"),
                transform=ax.transAxes, ha="right", va="top",
                fontsize=11, fontweight="bold", color="#d63031",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#d63031", alpha=0.85))

    # Achsen
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=35, ha="right", fontsize=8.5)
    ax.set_ylabel("HRV RMSSD (ms)", fontsize=10)
    ax.set_xlabel("")
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.3, ls=":")
    ax.grid(axis="x", alpha=0.15, ls=":")

    if ev_dts:
        ev_labels = " / ".join(name for _, name in ev_dts)
        title = t(f"HRV-Verlauf (RMSSD) — {ev_labels}",
                  f"HRV Course (RMSSD) — {ev_labels}")
    else:
        title = t("HRV-Verlauf (RMSSD)", "HRV Course (RMSSD)")
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.legend(loc="upper right", fontsize=8.5, framealpha=0.9)

    fig.tight_layout()

    # Speichern
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else OUT_DIR / f"hrv_cardiology_{datetime.today().strftime('%Y-%m-%d')}.pdf"
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    print(t(f"Gespeichert: {out_path}", f"Saved: {out_path}"))
    plt.close(fig)

    summary_lines = [t("# HRV-Verlauf (RMSSD)\n", "# HRV course (RMSSD)\n")]
    for d, a, lo, hi in zip(dates, avgs, los, his):
        summary_lines.append(f"- {d.strftime('%Y-%m')}: Ø {a:.0f} ms (min {lo:.0f} / max {hi:.0f})")
    if method_switch_date and args.date_from <= method_switch_date <= args.date_to:
        summary_lines.append(t(
            f"\n⚠️ Methodenwechsel ab {method_switch_date}: vorher ein Garmin-Nachtmittel/Tag, "
            "danach zusaetzlich ~75-90 5-Minuten-Einzelmessungen/Nacht (hier bereits vor der "
            "Monatsaggregation zu einem Tageswert gemittelt, s.o.). Vorher/Nachher-Vergleiche "
            "ueber diesen Zeitpunkt hinweg sind Methodenvergleiche, keine reinen Trendvergleiche.",
            f"\n⚠️ Method change from {method_switch_date}: before, one Garmin nightly average/day; "
            "after, additionally ~75-90 5-minute readings/night (already averaged to one daily "
            "value before monthly aggregation, see above). Before/after comparisons spanning this "
            "date compare methods, not just trend."
        ))
    if ev_dts:
        summary_lines.append(t("\n## Ereignisse", "\n## Events"))
        for ev_dt, ev_name in ev_dts:
            summary_lines.append(f"- {ev_dt.strftime('%Y-%m-%d')}: {ev_name}")
    if baseline_pre is not None:
        summary_lines.append(t(f"\nBaseline vor erster Infektion: Ø {baseline_pre:.0f} ms",
                                f"\nBaseline before first infection: avg {baseline_pre:.0f} ms"))
    if baseline_post is not None:
        summary_lines.append(t(f"Baseline nach letzter Infektion: Ø {baseline_post:.0f} ms",
                                f"Baseline after last infection: avg {baseline_post:.0f} ms"))
    if baseline_pre and baseline_post:
        pct = (baseline_pre - baseline_post) / baseline_pre * 100
        summary_lines.append(t(f"Gesamtrückgang: −{pct:.0f}%", f"Total reduction: −{pct:.0f}%"))
    report = "\n".join(summary_lines)
    llm_text = "" if args.no_llm else _run_llm(report)
    if llm_text:
        report += t("\n\n## Klinische Interpretation\n\n", "\n\n## Clinical Interpretation\n\n") + llm_text + "\n"
    md_path = out_path.with_suffix(".md")
    md_path.write_text(report, encoding="utf-8")
    print(t(f"Bericht gespeichert: {md_path}", f"Report saved: {md_path}"))


if __name__ == "__main__":
    main()
