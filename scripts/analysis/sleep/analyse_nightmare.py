# SPDX-License-Identifier: GPL-3.0-or-later
"""
analyse_nightmare.py — Alptraum-Alarm-Analyse (Kyoro SleepGuard)

@tier        experimental
@purpose.de  Analysiert Alptraum-Alarme der Kyoro-SleepGuard-Uhr-App: Häufigkeit, Uhrzeitverteilung, HR-Delta und klinisches RBD-Screening-Flag.
@purpose.en  Analyses nightmare alarms from the Kyoro SleepGuard watch app: frequency, time-of-night distribution, HR delta, and clinical RBD screening flag.
@method.de   Liest nightmare_hr / nightmare_baseline aus measurements; aggregiert pro Nacht; erkennt aufeinanderfolgende Nächte (≥3 = RBD-Flag); vergleicht HRV am Folgemorgen zwischen Alarm- und ruhigen Nächten.
@method.en   Reads nightmare_hr / nightmare_baseline from measurements; aggregates per night; detects consecutive nights (≥3 = RBD flag); compares next-morning HRV between alarm and quiet nights.
@refs        Schenck CH, Boeve BF, Mahowald MW (2013). Delayed emergence of a parkinsonian disorder or dementia in 81% of older men initially diagnosed with idiopathic rapid eye movement sleep behavior disorder: a 16-year update on a previously reported series. Sleep Medicine, 14(8):744-748. doi:10.1016/j.sleep.2012.10.009
             Postuma RB, Gagnon JF, Vendette M, Fantini ML, Massicotte-Marquez J, Montplaisir J (2009). Quantifying the risk of neurodegenerative disease in idiopathic REM sleep behavior disorder. Neurology, 72(15):1296-1300. doi:10.1212/WNL.0b013e3181a52fbe

@relevance.de  Ermöglicht die Schlafanalyse, essentiell für die Schlafforschung und Gesundheitsüberwachung
@relevance.en  Enables sleep analysis, essential for sleep research and health monitoring
@limits.de   HR-basierte Alptraum-Erkennung ist heuristisch; Erhöhungen können auch durch normale Schlaf-Tachykardie entstehen. Wearable-HR weist PPG-Artefakte auf. Kein Ersatz für Polysomnographie.
@limits.en   HR-based nightmare detection is heuristic; elevations can also arise from normal sleep tachycardia. Wearable HR has PPG artefacts. Not a substitute for polysomnography.
@reads       measurements (nightmare_hr, nightmare_baseline, rmssd, hrv_rmssd)
@writes      analyses/sleep/nightmare_report.txt, analyses/sleep/nightmare_analysis.png
@usage
    python3 scripts/analysis/sleep/analyse_nightmare.py
    python3 scripts/analysis/sleep/analyse_nightmare.py --lang en
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from health_config import Config, OWN_PERSON_ID
from modules.base import resolve_person, resolve_timezone
from modules.db import open_db
from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.prompts.analysis_sleep import (
    SYSTEM_PROMPT_ANALYSE_NIGHTMARE_DE as SYSTEM_PROMPT_DE,
    SYSTEM_PROMPT_ANALYSE_NIGHTMARE_EN as SYSTEM_PROMPT_EN,
)


def _run_llm(report: str) -> str:
    try:
        from modules.llm import call_llm
        print(t("\nLLM analysiert ...", "\nLLM analysing ..."))
        return call_llm(report, system=t(SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN), max_tokens=800)
    except Exception as e:
        print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
        return ""

RBD_CONSECUTIVE_THRESHOLD = 3  # Nächte in Folge → klinisches Flag


def run(conn, *, lang="de", person=None, output_dir=None, llm=False):
    cfg = Config()
    person = resolve_person(person)
    out = Path(output_dir or cfg.analyses_dir) / "sleep"
    out.mkdir(parents=True, exist_ok=True)

    events = _load_events(conn, person)
    lines = []

    if not events:
        msg = t(
            "Keine Alptraum-Ereignisse in der Datenbank.\n"
            "Import: python3 scripts/importers/import_nightmare_log.py <csv>",
            "No nightmare events in database.\n"
            "Import: python3 scripts/importers/import_nightmare_log.py <csv>",
        )
        print(msg)
        return {"status": "no_data"}

    # ── Pro-Nacht aggregieren ──────────────────────────────────────────────
    by_night = defaultdict(list)
    for ev in events:
        by_night[ev["date"]].append(ev)

    nights = sorted(by_night.keys())
    counts = [len(by_night[d]) for d in nights]
    deltas = [ev["hr"] - ev["base"] for d in nights for ev in by_night[d]]
    hours  = [ev["ts"].hour for d in nights for ev in by_night[d]]

    # ── Aufeinanderfolgende Nächte ─────────────────────────────────────────
    max_consec, cur_consec = 0, 1
    consec_runs = []
    for i in range(1, len(nights)):
        d0 = datetime.strptime(nights[i - 1], "%Y-%m-%d").date()
        d1 = datetime.strptime(nights[i],     "%Y-%m-%d").date()
        if (d1 - d0).days == 1:
            cur_consec += 1
        else:
            if cur_consec >= RBD_CONSECUTIVE_THRESHOLD:
                consec_runs.append((nights[i - cur_consec], nights[i - 1], cur_consec))
            max_consec = max(max_consec, cur_consec)
            cur_consec = 1
    if cur_consec >= RBD_CONSECUTIVE_THRESHOLD:
        consec_runs.append((nights[-cur_consec], nights[-1], cur_consec))
    max_consec = max(max_consec, cur_consec)

    rbd_flag = max_consec >= RBD_CONSECUTIVE_THRESHOLD

    # ── HRV-Korrelation (nächster Morgen) ─────────────────────────────────
    hrv_by_date = _load_hrv(conn, person)
    nights_with_alarm = set(nights)
    nights_hrv    = [(d, hrv_by_date[d]) for d in hrv_by_date if d in nights_with_alarm]
    no_alarm_hrv  = [(d, hrv_by_date[d]) for d in hrv_by_date if d not in nights_with_alarm]

    # ── Text-Report ────────────────────────────────────────────────────────
    lines.append(t("# Alptraum-Analyse (Kyoro SleepGuard)", "# Nightmare Analysis (Kyoro SleepGuard)"))
    lines.append(t(
        f"Analysiert: {len(events)} Ereignisse über {len(nights)} Nächte",
        f"Analyzed: {len(events)} events across {len(nights)} nights",
    ))
    lines.append(t(
        f"Ø Ereignisse/Nacht: {np.mean(counts):.1f}  (Max: {max(counts)})",
        f"Avg events/night: {np.mean(counts):.1f}  (Max: {max(counts)})",
    ))
    lines.append(t(
        f"Ø HR-Delta (Alarm − Baseline): +{np.mean(deltas):.1f} bpm  (Max: +{max(deltas):.0f} bpm)",
        f"Avg HR delta (alarm − baseline): +{np.mean(deltas):.1f} bpm  (Max: +{max(deltas):.0f} bpm)",
    ))
    lines.append(t(
        f"Häufigste Uhrzeit: {_mode_hour(hours)}:xx Uhr",
        f"Most common hour: {_mode_hour(hours)}:xx",
    ))
    lines.append(t(
        f"Max. aufeinanderfolgende Nächte mit Alarm: {max_consec}",
        f"Max. consecutive nights with alarm: {max_consec}",
    ))

    if rbd_flag:
        lines.append("")
        lines.append(t(
            f"⚠️  KLINISCHES FLAG: {max_consec} aufeinanderfolgende Nächte mit Alarmen "
            f"(Schwelle: {RBD_CONSECUTIVE_THRESHOLD}). "
            "RBD-Screening (Neurologie / Schlaflabor) empfohlen.",
            f"⚠️  CLINICAL FLAG: {max_consec} consecutive nights with alarms "
            f"(threshold: {RBD_CONSECUTIVE_THRESHOLD}). "
            "RBD screening (neurology / sleep lab) recommended.",
        ))
        for start, end, n in consec_runs:
            lines.append(f"   {start} – {end}: {n} Nächte")

    if nights_hrv and no_alarm_hrv:
        hrv_alarm   = np.mean([v for _, v in nights_hrv]) if nights_hrv else None
        hrv_no      = np.mean([v for _, v in no_alarm_hrv])
        if hrv_alarm is not None:
            lines.append(t(
                f"\nHRV am Folgetag: {hrv_alarm:.1f} ms (Alarmnacht) vs. {hrv_no:.1f} ms (ruhige Nacht)",
                f"\nHRV next morning: {hrv_alarm:.1f} ms (alarm night) vs. {hrv_no:.1f} ms (quiet night)",
            ))

    for line in lines:
        print(line)

    report_text = "\n".join(lines)
    llm_text = _run_llm(report_text) if llm else ""
    content = report_text
    if llm_text:
        content += t("\n\n## Klinische Interpretation\n\n", "\n\n## Clinical Interpretation\n\n") + llm_text + "\n"
    report_path = out / "nightmare_report.txt"
    report_path.write_text(content, encoding="utf-8")

    # ── Plots ──────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle(t("Alptraum-Monitoring – Kyoro SleepGuard", "Nightmare Monitoring – Kyoro SleepGuard"),
                 fontsize=13, fontweight="bold")

    # 1) Timeline Ereignisse/Nacht
    ax = axes[0, 0]
    night_dts = [datetime.strptime(d, "%Y-%m-%d") for d in nights]
    ax.bar(night_dts, counts, color="#e05050", width=0.6)
    if rbd_flag:
        for start, end, n in consec_runs:
            ax.axvspan(
                datetime.strptime(start, "%Y-%m-%d") - timedelta(hours=12),
                datetime.strptime(end,   "%Y-%m-%d") + timedelta(hours=12),
                alpha=0.15, color="orange",
                label=t(f"RBD-Verdacht ({n}N)", f"RBD suspect ({n}N)"),
            )
        ax.legend(fontsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=7)
    ax.set_ylabel(t("Alarme/Nacht", "Alarms/night"))
    ax.set_title(t("Ereignisse pro Nacht", "Events per night"))
    ax.yaxis.get_major_locator().set_params(integer=True)

    # 2) Uhrzeitverteilung
    ax = axes[0, 1]
    ax.hist(hours, bins=range(0, 25), color="#5080e0", edgecolor="white", rwidth=0.8)
    ax.set_xlabel(t("Uhrzeit (h)", "Hour of night"))
    ax.set_ylabel(t("Häufigkeit", "Count"))
    ax.set_title(t("Verteilung Alarmzeit", "Alarm time distribution"))
    ax.set_xticks(range(0, 24, 2))

    # 3) HR-Delta Histogramm
    ax = axes[1, 0]
    ax.hist(deltas, bins=10, color="#e08030", edgecolor="white")
    ax.axvline(np.mean(deltas), color="red", linestyle="--",
               label=f"Ø +{np.mean(deltas):.0f} bpm")
    ax.set_xlabel(t("HR-Delta (bpm über Baseline)", "HR delta (bpm above baseline)"))
    ax.set_ylabel(t("Häufigkeit", "Count"))
    ax.set_title(t("HR-Anstieg beim Alarm", "HR rise at alarm"))
    ax.legend(fontsize=8)

    # 4) HRV Folgetag: Alarm vs. ruhig
    ax = axes[1, 1]
    if nights_hrv and no_alarm_hrv:
        hrv_vals_alarm = [v for _, v in nights_hrv]
        hrv_vals_quiet = [v for _, v in no_alarm_hrv]
        ax.boxplot([hrv_vals_quiet, hrv_vals_alarm],
                   labels=[t("Ruhige Nacht", "Quiet night"),
                           t("Alarmnacht", "Alarm night")],
                   patch_artist=True,
                   boxprops=dict(facecolor="#c0d8ff"),
                   medianprops=dict(color="navy", linewidth=2))
        ax.set_ylabel("RMSSD (ms)")
        ax.set_title(t("HRV am Folgetag", "HRV next morning"))
    else:
        ax.text(0.5, 0.5, t("Keine HRV-Daten", "No HRV data"),
                ha="center", va="center", transform=ax.transAxes, color="gray")
        ax.set_title(t("HRV am Folgetag", "HRV next morning"))

    plt.tight_layout()
    plot_path = out / "nightmare_analysis.png"
    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(t(f"\nPlot: {plot_path}", f"\nPlot: {plot_path}"))

    return {
        "status": "ok",
        "n_events": len(events),
        "n_nights": len(nights),
        "rbd_flag": rbd_flag,
        "max_consecutive": max_consec,
        "mean_delta_bpm": float(np.mean(deltas)),
    }


def _load_events(conn, person):
    rows = conn.execute(
        """SELECT m.ts, m.value AS hr, b.value AS base
           FROM measurements m
           LEFT JOIN measurements b
             ON b.ts = m.ts AND b.metric = 'nightmare_baseline' AND b.person = m.person
           WHERE m.metric = 'nightmare_hr' AND m.person = ?
           ORDER BY m.ts""",
        (person,),
    ).fetchall()

    events = []
    for ts_str, hr, base in rows:
        try:
            dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            events.append({
                "ts":   dt,
                "date": dt.strftime("%Y-%m-%d"),
                "hr":   float(hr),
                "base": float(base) if base is not None else float(hr) - 20,
            })
        except Exception:
            continue
    return events


def _load_hrv(conn, person):
    rows = conn.execute(
        """SELECT date, AVG(value) FROM measurements
           WHERE metric IN ('rmssd', 'hrv_rmssd') AND person = ?
           GROUP BY date""",
        (person,),
    ).fetchall()
    return {r[0]: r[1] for r in rows if r[1] is not None}


def _mode_hour(hours):
    if not hours:
        return "?"
    counts = defaultdict(int)
    for h in hours:
        counts[h] += 1
    return max(counts, key=counts.get)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description=t("Alptraum-Alarm-Analyse (Kyoro SleepGuard)",
                      "Nightmare alarm analysis (Kyoro SleepGuard)"))
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    # Von analyse_all.py durchgereichte Standardflags, die dieses Skript
    # (noch) nicht auswertet — nur zur Kompatibilität mit dem Master-Runner.
    parser.add_argument("--from", dest="date_from", default=None)
    parser.add_argument("--to",   dest="date_to",   default=None)
    parser.add_argument("--date", dest="single_date", default=None)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--plot", action="store_true")
    add_lang_arg(parser)
    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()
    try:
        run(conn, person=args.person, llm=not args.no_llm)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
