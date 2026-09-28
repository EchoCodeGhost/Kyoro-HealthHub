#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Polar H10 Langzeit-Analyse (5-days-Monitoring)

valueet die importierten PPI-Daten aus einem mehrtägigen H10-Brustgurt-Tragen aus.
berechnet:
  - Stündliche RMSSD (HRV-Verlauf über day and Night)
  - Tägliche HRV-Summary (Sleep vs. day)
  - Post-Exertions-Reaktionen (Workout → HRV Folgestanden)
  - Arrhythmia-Hinweise (CV-RR > 0.15)
  - Comparison with historischer Baseline (aus polar_nightly_hrv)

Usage:
  python analyse_ecg_longterm.py --from YYYY-MM-DD --to YYYY-MM-DD
  python analyse_ecg_longterm.py --from YYYY-MM-DD --to YYYY-MM-DD --plot

@tier        heuristic
@purpose.de  Wertet mehrtägige Polar-H10-Daueraufnahmen aus: stündliche RMSSD, tägliche
             HRV-Summary (Schlaf vs. Tag), Post-Exertions-Reaktionen und Arrhythmie-Hinweise.
@purpose.en  Evaluates multi-day Polar H10 continuous recordings: hourly RMSSD, daily HRV
             summary (sleep vs. day), post-exertion reactions and arrhythmia indicators.
@method.de   Stündliche Aggregation von ppi_raw; RMSSD und CV-RR je Stunde;
             Post-Workout-HRV-Verlauf der Folgestunden. CV > 0,15 als Arrhythmie-Fenster
             (heuristisch). Vergleich mit polar_nightly_hrv als historischer Baseline.
@method.en   Hourly aggregation of ppi_raw; RMSSD and CV-RR per hour; post-workout HRV
             trend in subsequent hours. CV > 0.15 as arrhythmia window (heuristic).
             Comparison with polar_nightly_hrv as historical baseline.
@scoring     Arrhythmie-Fenster: CV-RR > 0,15 je Stunde (heuristisch)
             Tagesklassifikation: arrhythmia_stunden > 2 = Auffälligkeit (heuristisch)
             RMSSD-Methode: Task Force ESC/NASPE 1996 (doi:10.1161/01.CIR.93.5.1043)
             Basis: CV-Schwelle und Stunden-Grenze projektintern, kein publizierter Schwellenwert
@limits.de   Heuristische Methode: CV-Schwelle 0,15 ist heuristisch, kein aus klinischen Studien abgeleiteter Wert.
             Arrhythmie-Stunden-Grenze (>2 h) ist heuristisch.
             RMSSD-Berechnung: validiert per Task Force ESC/NASPE 1996
             (doi:10.1161/01.CIR.93.5.1043). Mehrtägiges Tragen des H10 ist praktisch
             eingeschränkt (Komfort, Akkuleistung). Kein klinisches Holter-EKG.
             n=1, Consumer-Sensorik.
@limits.en   Heuristic method: CV threshold 0.15 is heuristic, not derived from clinical studies.
             Arrhythmia-hours threshold (>2 h) is heuristic.
             RMSSD computation: validated per Task Force ESC/NASPE 1996
             (doi:10.1161/01.CIR.93.5.1043). Multi-day wearing of H10 is practically
             limited (comfort, battery). Not a clinical Holter ECG. n=1, consumer sensors.
@refs        Task Force of the ESC and NASPE (1996). Heart rate variability.
             Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart Rate Variability. Circulation, 93(5):1043-1065. doi:10.1161/01.CIR.93.5.1043

@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@reads       ppi_raw, polar_nightly_hrv, air_quality, pollen, indoor_environment
@writes      analyses/cardiovascular/*.{md,png} (kein DB-Write)

@usage
    python analyse_ecg_longterm.py
    python analyse_ecg_longterm.py --help
    python analyse_ecg_longterm.py --from 2024-01-01 --to 2024-12-31
"""

import argparse
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from health_config import Config as _Cfg, OWN_PERSON_ID
from modules.db import open_db
_cfg = _Cfg()

from modules.i18n import t, add_lang_arg, apply_lang_from_args
from modules.arrhythmia_utils import load_pollen, load_air_quality, load_indoor_air

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "cardiovascular"

SYSTEM_H10 = """Du bist ein Kardiologe und Sportmediziner mit Expertise in Herzfrequenzvariabilität.

Du analysierst 5 Tage kontinuierliche Beat-to-beat HRV-Daten vom Polar H10 Brustgurt.

Analysiere auf Deutsch:
1. **HRV-Tagesverlauf**: Wann ist die HRV am höchsten/niedrigsten? Zirkadianes Muster?
2. **Schlaf vs. Tag**: Vergleich nächtlicher vs. tagsüber HRV
3. **Post-Exertions-Reaktion**: Wie reagiert die HRV in den Stunden nach Aktivität?
4. **Arrhythmie-Fenster**: Perioden mit auffällig hohem CV-RR (>0.15)
5. **Tages-zu-Tages-Variabilität**: Welche Tage waren Erholungstage, welche Belastungstage?
6. **Vergleich mit Baseline**: Wie verhält sich die 5-Tage-HRV vs. historischem Mittel?
7. **Klinische Einordnung**: Was bedeuten die Muster für autonome Regulation und Erholung?
8. **Empfehlungen**: Was sagen die Daten für Aktivitätsplanung und Erholung?"""

DEUTSCH = "\n\nWICHTIG: Antworte ausschließlich auf Deutsch."


def compute_rmssd(ppis: list) -> float | None:
    if len(ppis) < 5:
        return None
    diffs = [(ppis[i+1] - ppis[i])**2 for i in range(len(ppis)-1)]
    return round(math.sqrt(sum(diffs) / len(diffs)), 1)


def compute_cv(ppis: list) -> float | None:
    if len(ppis) < 5:
        return None
    mean = sum(ppis) / len(ppis)
    return round((sum((x - mean)**2 for x in ppis) / (len(ppis) - 1))**0.5 / mean, 4)


def load_ppi_data(conn, start: str, end: str) -> list:
    rows = conn.execute("""
        SELECT datetime, pulse_ms FROM ppi_raw
        WHERE datetime >= ? AND datetime <= ?
          AND pulse_ms BETWEEN 300 AND 1800
        ORDER BY datetime
    """, (start, end)).fetchall()
    return [(datetime.fromisoformat(r[0][:19]), r[1]) for r in rows]


def analyse_hourly(daten: list) -> dict:
    """Gruppiert PPI-Daten in hours and berechnet RMSSD + CV."""
    stunden = defaultdict(list)
    for dt, ppi in daten:
        key = dt.replace(minute=0, second=0, microsecond=0)
        stunden[key].append(ppi)

    ergebnis = {}
    for stunde, ppis in sorted(stunden.items()):
        rmssd = compute_rmssd(ppis)
        cv    = compute_cv(ppis)
        hr    = round(60000 / (sum(ppis) / len(ppis)), 1) if ppis else None
        ergebnis[stunde] = {
            "rmssd": rmssd, "cv": cv, "hr": hr, "n": len(ppis),
            "arrhythmie": cv is not None and cv > 0.15
        }
    return ergebnis


def analyse_daily(stuendlich: dict) -> dict:
    tage = defaultdict(lambda: {"rmssd_all": [], "rmssd_schlaf": [], "rmssd_tag": [],
                                 "arrhythmia_h": 0, "n_stunden": 0})
    for stunde, werte in stuendlich.items():
        if werte["rmssd"] is None:
            continue
        tag = stunde.strftime("%Y-%m-%d")
        h   = stunde.hour
        tage[tag]["rmssd_all"].append(werte["rmssd"])
        tage[tag]["n_stunden"] += 1
        if werte["arrhythmie"]:
            tage[tag]["arrhythmia_h"] += 1
        # Night: 22–06 Uhr, day: 09–21 Uhr. 06–09 and 21–22 sind bewusst
        # ausgeklammert (Aufwach-/Einschlafpuffer, würden beide Kategorien verfälschen).
        if 0 <= h < 6 or h >= 22:
            tage[tag]["rmssd_schlaf"].append(werte["rmssd"])
        elif 9 <= h < 21:
            tage[tag]["rmssd_tag"].append(werte["rmssd"])

    zusammenfassung = {}
    for tag, d in sorted(tage.items()):
        def avg(lst): return round(sum(lst)/len(lst), 1) if lst else None
        zusammenfassung[tag] = {
            "rmssd_gesamt": avg(d["rmssd_all"]),
            "rmssd_schlaf": avg(d["rmssd_schlaf"]),
            "rmssd_tag":    avg(d["rmssd_tag"]),
            "arrhythmia_stunden": d["arrhythmia_h"],
            "n_stunden":    d["n_stunden"],
        }
    return zusammenfassung


def load_baseline(conn) -> float | None:
    r = conn.execute("""
        SELECT ROUND(AVG(rmssd_ms), 1) FROM polar_nightly_hrv
        WHERE rmssd_ms > 0
    """).fetchone()
    return r[0] if r else None


def _fmt_ms(v: float | None) -> str:
    """Formatiert einen Millisekunden-Wert oder 'n. a.' bei fehlender Messung.

    Ohne diese Behandlung erzeugt die direkte String-Verkettung f"{v}ms" bei
    v=None die Ausgabe "Nonems" (Python rendert None als Text "None", direkt
    gefolgt von der Einheit "ms" ohne Trennzeichen) — z.B. wenn ein Tag zu
    wenige PPI-Werte fuer eine RMSSD-Berechnung hat (compute_rmssd() gibt bei
    <5 Intervallen None zurueck) oder keine historische Baseline in
    polar_nightly_hrv existiert.
    """
    return f"{v}ms" if v is not None else "n. a."


def build_report(stuendlich, taeglich, baseline, zeitraum,
                 pollen_dict=None, air_quality=None, indoor_air=None) -> str:
    lines = []
    lines.append(f"## H10 Langzeit-Analyse {zeitraum[0]} – {zeitraum[1]}")
    lines.append(f"Historische Baseline: {_fmt_ms(baseline)}\n")

    lines.append("### Tägliche Overview")
    for tag, d in taeglich.items():
        # "auffällig" statt "notable" — reiner Deutschtext im uebrigen Bericht,
        # "notable" war Rest einer fehlerhaften Wortersetzung (siehe auch
        # "notableen" weiter unten).
        arrhythmie = f" ⚠️ {d['arrhythmia_stunden']}h auffällig" if d['arrhythmia_stunden'] > 2 else ""
        lines.append(
            f"  {tag}: RMSSD∅ {_fmt_ms(d['rmssd_gesamt'])} | "
            f"Sleep {_fmt_ms(d['rmssd_schlaf'])} | day {_fmt_ms(d['rmssd_tag'])} | "
            f"{d['n_stunden']}h Daten{arrhythmie}"
        )

    lines.append("\n### Stündlicher HRV-Verlauf (days kombiniert)")
    standen_withtel = defaultdict(list)
    for stande, werte in stuendlich.items():
        if werte["rmssd"]:
            standen_withtel[stande.hour].append(werte["rmssd"])
    for h in range(24):
        vals = standen_withtel[h]
        if vals:
            avg = round(sum(vals)/len(vals), 1)
            bar = "█" * int(avg / 3)
            flag = " ←Night" if 0 <= h < 6 else (" ←day" if 9 <= h < 20 else "")
            lines.append(f"  {h:02d}:00 — ∅{avg:>5}ms  {bar}{flag}")

    lines.append("\n### Arrhythmia-Fenster (CV-RR > 0.15)")
    arrhythmie_fenster = [(dt, w) for dt, w in stuendlich.items() if w["arrhythmie"]]
    if arrhythmie_fenster:
        for dt, w in arrhythmie_fenster[:20]:
            lines.append(f"  {dt.strftime('%Y-%m-%d %H:%M')}: CV={w['cv']:.3f} | RMSSD={w['rmssd']}ms | HR={w['hr']}bpm")
        if len(arrhythmie_fenster) > 20:
            lines.append(f"  ... and {len(arrhythmie_fenster)-20} weitere")
    else:
        # War "No notableen Fenster." — Rest einer fehlerhaften Wortersetzung
        # ("auffälligen" -> "notable" mitten im deutschen Satz eingesetzt).
        lines.append("  Keine auffälligen Fenster.")

    lines.append("\n### Gesamtstatistik")
    all_rmssd = [w["rmssd"] for w in stuendlich.values() if w["rmssd"]]
    if all_rmssd:
        lines.append(f"  RMSSD: ∅{sum(all_rmssd)/len(all_rmssd):.1f}ms | Min {min(all_rmssd)}ms | Max {max(all_rmssd)}ms")
        if baseline:
            delta = round(sum(all_rmssd)/len(all_rmssd) - baseline, 1)
            lines.append(f"  vs. historische Baseline ({baseline}ms): {delta:+.1f}ms ({delta/baseline*100:+.0f}%)")

    # Umgebungskontext für den Aufnahmezeitraum
    pollen_dict = pollen_dict or {}
    air_quality = air_quality or {}
    indoor_air  = indoor_air  or {}
    if pollen_dict or air_quality or indoor_air:
        lines.append("\n### Umgebungskontext im Aufnahmezeitraum")
    if pollen_dict:
        lines.append("  Pollen (grains/m³, Tagesmittel):")
        for key, label in [("birch","Birke"), ("alder","Erle"), ("grass","Gräser"),
                           ("mugwort","Beifuß"), ("ragweed","Ragweed"), ("total","Gesamt")]:
            vals = [pollen_dict[d][key] for d in pollen_dict if pollen_dict[d].get(key) is not None]
            if vals:
                lines.append(f"    {label:<10} Ø {round(sum(vals)/len(vals),1):>6}  Max {max(vals):.0f}")
    if air_quality:
        lines.append("  Luftqualität (Tagesmittel):")
        for key, label in [("aqi_eu_mean","AQI EU"), ("pm25_mean","PM2.5 µg/m³"),
                           ("dust_mean","Staub µg/m³")]:
            vals = [air_quality[d][key] for d in air_quality if air_quality[d].get(key) is not None]
            if vals:
                lines.append(f"    {label:<15} Ø {round(sum(vals)/len(vals),1):>6}  Max {max(vals):.1f}")
    if indoor_air:
        lines.append(f"  Indoor-Luft ({len(indoor_air)} Tage):")
        all_stypes = sorted({st for day in indoor_air.values() for st in day})
        for stype in all_stypes:
            vals = [indoor_air[d][stype] for d in indoor_air if stype in indoor_air[d]]
            if vals:
                lines.append(f"    {stype:<20} Ø {round(sum(vals)/len(vals),2)}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=t("H10 Langzeit-Analyse", "H10 long-term analysis"))
    parser.add_argument("--from", dest="date_from", default=_cfg.data_start or "2000-01-01", help="Start YYYY-MM-DD")
    parser.add_argument("--to",   dest="date_to",   default=datetime.now().strftime("%Y-%m-%d"), help="Ende YYYY-MM-DD")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    parser.add_argument("--plot", action="store_true", help="Plots erstellen")
    parser.add_argument("--no-llm", action="store_true", help="Only Rohdaten, no LLM")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn = open_db()

    # Daten laden
    print(t(f"Lade PPI-Daten {args.date_from} → {args.date_to} ...",
            f"Loading PPI data {args.date_from} → {args.date_to} ..."))
    daten = load_ppi_data(conn, args.date_from + "T00:00", args.date_to + "T23:59")
    print(t(f"  {len(daten):,} RR-Intervalle", f"  {len(daten):,} RR intervals"))

    if not daten:
        print(t("Keine Daten für diesen Zeitbereich.", "No data for this time range."))
        return

    # Analyse
    print(t("Berechne stündliche HRV ...", "Computing hourly HRV ..."))
    stuendlich = analyse_hourly(daten)
    taeglich   = analyse_daily(stuendlich)
    baseline   = load_baseline(conn)
    pollen     = load_pollen(conn, args.date_from, args.date_to)
    aq         = load_air_quality(conn, args.date_from, args.date_to)
    indoor     = load_indoor_air(conn, args.date_from, args.date_to)
    conn.close()

    # Bericht
    report = build_report(stuendlich, taeglich, baseline, (args.date_from, args.date_to),
                          pollen_dict=pollen, air_quality=aq, indoor_air=indoor)
    print("\n" + report)

    # Optional: Plots
    if args.plot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            OUT_DIR.mkdir(parents=True, exist_ok=True)
            fig, axes = plt.subplots(2, 1, figsize=(16, 10),
                                     facecolor="#1A1A2E")
            fig.suptitle(f"H10 Langzeit-HRV {args.date_from} – {args.date_to}",
                        color="#E0E0E0", fontsize=13)

            # Stündliche RMSSD über all days
            ax1 = axes[0]
            ax1.set_facecolor("#16213E")
            xs  = [dt for dt, w in sorted(stuendlich.items()) if w["rmssd"]]
            ys  = [w["rmssd"] for dt, w in sorted(stuendlich.items()) if w["rmssd"]]
            colors = ["#E84855" if w["arrhythmie"] else "#2E86AB"
                     for dt, w in sorted(stuendlich.items()) if w["rmssd"]]
            ax1.scatter(xs, ys, c=colors, s=8, alpha=0.7)
            if baseline:
                ax1.axhline(baseline, color="#F4A261", linestyle="--", alpha=0.5,
                           label=f"Historische Baseline {baseline}ms")
            ax1.set_ylabel("RMSSD (ms)", color="#E0E0E0", fontsize=9)
            ax1.set_title("Stündliche RMSSD (rot=Arrhythmia-Verdacht)", color="#E0E0E0")
            ax1.tick_params(colors="#E0E0E0", labelsize=7)
            ax1.legend(fontsize=8, labelcolor="#E0E0E0", facecolor="#16213E")
            for s in ax1.spines.values(): s.set_color("#8B8B8B")

            # Täglicher Comparison Sleep vs. day
            ax2 = axes[1]
            ax2.set_facecolor("#16213E")
            tage_list = list(taeglich.keys())
            x = range(len(tage_list))
            schlaf = [taeglich[t]["rmssd_schlaf"] or 0 for t in tage_list]
            tag    = [taeglich[t]["rmssd_tag"] or 0 for t in tage_list]
            ax2.bar([i-0.2 for i in x], schlaf, 0.4, label="Sleep", color="#2E86AB", alpha=0.8)
            ax2.bar([i+0.2 for i in x], tag,    0.4, label="day",    color="#57A773", alpha=0.8)
            ax2.set_xticks(list(x))
            ax2.set_xticklabels(tage_list, color="#E0E0E0", fontsize=8)
            ax2.set_ylabel("RMSSD (ms)", color="#E0E0E0", fontsize=9)
            ax2.set_title("Sleep- vs. dayss-HRV pro day", color="#E0E0E0")
            ax2.tick_params(colors="#E0E0E0", labelsize=8)
            ax2.legend(fontsize=8, labelcolor="#E0E0E0", facecolor="#16213E")
            for s in ax2.spines.values(): s.set_color("#8B8B8B")

            fig.tight_layout()
            plot_path = OUT_DIR / f"h10_longterm_{args.date_from}_{args.date_to}.png"
            fig.savefig(str(plot_path), dpi=130, bbox_inches="tight", facecolor="#1A1A2E")
            plt.close()
            print(t(f"\nPlot gespeichert: {plot_path}", f"\nPlot saved: {plot_path}"))
        except Exception as e:
            print(t(f"Plot fehlgeschlagen: {e}", f"Plot failed: {e}"))

    # LLM-Analyse
    if not args.no_llm:
        try:
            from modules.llm import call_llm
            print(t("\nLLM analysiert 5-Tage-HRV ...", "\nLLM analysing 5-day HRV ..."))
            answer = call_llm(report, system=SYSTEM_H10 + DEUTSCH, max_tokens=5000)
        except Exception as e:
            print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
            answer = ""

        print("\n" + "="*60)
        print(answer)
        print("="*60)

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = OUT_DIR / f"h10_analysis_{args.date_from}_{ts}.md"
        out.write_text(
            f"# H10 Langzeit-HRV-Analyse\n\n"
            f"*{args.date_from} – {args.date_to}*\n\n"
            f"## Rohdaten\n```\n{report}\n```\n\n"
            f"## Clinical Analyse\n{answer}\n",
            encoding="utf-8"
        )
        print(t(f"\nBericht: {out}", f"\nReport: {out}"))


if __name__ == "__main__":
    main()
