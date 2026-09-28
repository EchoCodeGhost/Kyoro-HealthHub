#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
Polar H7 — 24h-Analyse

valueet einen 24h-Aufnahmezeitraum aus der polar_ppi-Table aus.
Der H7 überträgt live via Bluetooth — Aufnahme per Polar Beat App,
after Sync zu Polar Flow, then `import_all.py --update`.

Vorbereitung:
  1. Polar Beat App öffnen → H7 koppeln → Workout starten ("Freies Workout")
  2. 24h tragen (Handy in Bluetooth-Reichweite lassen, App aktiv)
  3. Workout beenden → automatisch zu Polar Flow sync
  4. Daten importieren: python3 import_all.py --update
  5. Diese Evaluation: python3 scripts/analysis/analyse_ecg_24h.py --from YYYY-MM-DD --to YYYY-MM-DD

Usage:
  python analyse_ecg_24h.py --from YYYY-MM-DD --to YYYY-MM-DD
  python analyse_ecg_24h.py --from YYYY-MM-DD --to YYYY-MM-DD --plot
  python analyse_ecg_24h.py --from YYYY-MM-DD --to YYYY-MM-DD --no-llm

@tier        heuristic
@purpose.de  Wertet 24-Stunden-Aufnahmen des Polar H7 Brustgurts aus: stündliche RMSSD,
             CV-RR, Herzfrequenz-Profil, Arrhythmie-Fenster und Vergleich mit historischer
             Baseline.
@purpose.en  Evaluates 24-hour recordings from the Polar H7 chest strap: hourly RMSSD,
             CV-RR, heart rate profile, arrhythmia windows and comparison with historical
             baseline.
@method.de   Stündliche Aggregation von ppi_raw; RMSSD und CV-RR je Stunde berechnet.
             Arrhythmie-Fenster: CV > 0,15 (heuristische Schwelle, nicht validiert).
             Vergleich mit polar_nightly_hrv als Baseline. Die Tages-Min/Max-HF
             (60000/max bzw. 60000/min der Puls-Abstaende ueber den ganzen Tag)
             wird vor der Berechnung durch modules/rr_interval_algorithms.filter_beat_artifacts
             lokal-median-gefiltert — gefunden bei der Entwicklung von
             compute_orthostatic_detection.py: ein einzelner isolierter, sehr
             kurzer Puls-Abstand (Geraete-/Import-Bodenwert-Artefakt) wuerde sonst
             als Tages-Max-HF durchschlagen, unabhaengig von echter Physiologie.
@method.en   Hourly aggregation of ppi_raw; RMSSD and CV-RR computed per hour.
             Arrhythmia windows: CV > 0.15 (heuristic threshold, not validated).
             Comparison with polar_nightly_hrv as baseline. The daily min/max HR
             (60000/max resp. 60000/min of the pulse intervals across the whole
             day) is local-median-filtered via
             modules/rr_interval_algorithms.filter_beat_artifacts before computation —
             found while developing compute_orthostatic_detection.py: a single
             isolated, very short pulse interval (a device/import floor-value
             artifact) would otherwise show up as the daily max HR, regardless of
             genuine physiology.
@scoring     Arrhythmie-Fenster: CV-RR > 0,15 je Stunde (heuristisch)
             RMSSD-Methode: Task Force ESC/NASPE 1996 (doi:10.1161/01.CIR.93.5.1043)
             Basis: CV-Schwelle projektintern, kein publizierter Schwellenwert
@limits.de   Heuristische Methode: CV-Schwelle 0,15 ist heuristisch, nicht aus klinischen Studien abgeleitet.
             Polar H7 PPI kann Bewegungsartefakte enthalten. Kein klinisches Holter-EKG.
             n=1, Consumer-Sensorik, Einzelaufnahme.
             RMSSD-Berechnung: validiert per Task Force ESC/NASPE 1996
             (doi:10.1161/01.CIR.93.5.1043).
@limits.en   Heuristic method: CV threshold 0.15 is heuristic, not derived from clinical studies.
             Polar H7 PPI may contain motion artefacts. Not a clinical Holter ECG.
             n=1, consumer sensors, single recording.
             RMSSD computation: validated per Task Force ESC/NASPE 1996
             (doi:10.1161/01.CIR.93.5.1043).
@refs        Task Force of the ESC and NASPE (1996). Heart rate variability.
             Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart Rate Variability. Circulation, 93(5):1043-1065. doi:10.1161/01.CIR.93.5.1043

@relevance.de  Ermöglicht die kardiovaskuläre Analyse, essentiell für die Herz-Kreislauf-Diagnostik
@relevance.en  Enables cardiovascular analysis, essential for cardiac diagnostics
@reads       ppi_raw, air_quality, pollen, indoor_environment
@writes      analyses/cardiovascular/*.{md,png} (kein DB-Write)

@usage
    python analyse_ecg_24h.py
    python analyse_ecg_24h.py --help
    python analyse_ecg_24h.py --from 2024-01-01 --to 2024-12-31
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
from modules.rr_interval_algorithms import filter_beat_artifacts

DB_PATH = _cfg.db_path
OUT_DIR = _cfg.analyses_dir / "cardiovascular"

SYSTEM_H7 = """Du bist ein Kardiologe und Sportmediziner mit Expertise in
Herzfrequenzvariabilität.

Du analysierst 24h kontinuierliche Beat-to-beat HRV-Daten vom Polar H7 Brustgurt.

Analysiere auf Deutsch:
1. **Tagesverlauf der HRV**: Wann ist die HRV am höchsten/niedrigsten?
   Zirkadianes Muster erkennbar? (Typisch: HRV nachts am höchsten)
2. **Schlafphase**: Wie verändert sich HRV und HR im Schlaf?
3. **Aktivitätsphasen**: Wie reagiert HRV auf Bewegung/Aktivität?
4. **Arrhythmie-Fenster**: Perioden mit CV-RR > 0.15
5. **Ruhepuls-Profil**: Tiefstwert (Schlaf) vs. Tagesdurchschnitt
6. **Vergleich mit historischer Baseline**: Wie verhält sich der Tag im Langzeitvergleich?
7. **Klinische Einordnung**: Was sagen die 24h über Erholung und autonome Regulation?"""

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
    sd   = (sum((x - mean)**2 for x in ppis) / (len(ppis) - 1))**0.5
    return round(sd / mean, 4)


def load_ppi(conn, start: str, end: str) -> list:
    rows = conn.execute("""
        SELECT datetime, pulse_ms FROM ppi_raw
        WHERE datetime >= ? AND datetime <= ?
          AND pulse_ms BETWEEN 300 AND 1800
        ORDER BY datetime
    """, (start, end)).fetchall()
    return [(datetime.fromisoformat(r[0][:19]), r[1]) for r in rows]


def analyse_hourly(daten: list) -> dict:
    standen = defaultdict(list)
    for dt, ppi in daten:
        standen[dt.replace(minute=0, second=0, microsecond=0)].append(ppi)

    ergebnis = {}
    for stande, ppis in sorted(standen.items()):
        rmssd = compute_rmssd(ppis)
        cv    = compute_cv(ppis)
        hr    = round(60000 / (sum(ppis) / len(ppis)), 1) if ppis else None
        ergebnis[stande] = {
            "rmssd": rmssd, "cv": cv, "hr": hr, "n": len(ppis),
            "arrhythmie": cv is not None and cv > 0.15
        }
    return ergebnis


def load_baseline(conn) -> float | None:
    r = conn.execute("""
        SELECT ROUND(AVG(rmssd_ms), 1) FROM polar_nightly_hrv
        WHERE rmssd_ms > 0
    """).fetchone()
    return r[0] if r else None


def _fmt_hr(v: float | None) -> str:
    """Formatiert einen Herzfrequenz-Wert oder 'n. a.' bei fehlender Messung.

    hr_min/hr_max werden aus filter_beat_artifacts(all_ppis) berechnet und sind
    None, wenn dabei keine Beats uebrig bleiben — ohne Behandlung erscheint dann
    das Python-Literal "None" im Bericht statt eines Leerwerts.
    """
    return f"{v}" if v is not None else "n. a."


def build_report(stuendlich: dict, daten: list, baseline: float | None,
                     datum: str, pollen_dict=None, air_quality=None,
                     indoor_air=None) -> str:
    lines = []
    lines.append(f"## H7 24h-Analyse — {datum}")
    if baseline:
        lines.append(f"Historische Baseline: {baseline}ms RMSSD\n")

    # Gesamtstatistik
    all_ppis  = [p for _, p in daten]
    all_rmssd = [w["rmssd"] for w in stuendlich.values() if w["rmssd"]]
    if all_ppis:
        hr_mean = round(60000 / (sum(all_ppis) / len(all_ppis)), 1)
        # min()/max() ueber EINZELNE Beats sind anfaellig fuer einen bekannten
        # Geraete-/Import-Bodenwert bei sehr kurzen pulse_ms-Werten (s.
        # modules/rr_interval_algorithms.filter_beat_artifacts fuer die Herkunft dieses
        # Fundes) — ohne Filterung wuerde ein einzelner isolierter ~301ms-Beat
        # irgendwo im ganzen Tag als "Max HR" ~199bpm anzeigen, unabhaengig von
        # echter Physiologie. Nur fuer hr_min/hr_max gefiltert, nicht fuer den
        # Mittelwert oder RMSSD — ein einzelner Ausreisser verschiebt einen
        # Mittelwert ueber tausende Beats kaum, ein Minimum/Maximum aber direkt.
        ppis_f  = filter_beat_artifacts(all_ppis)
        hr_min  = round(60000 / max(ppis_f), 1) if ppis_f else None
        hr_max  = round(60000 / min(ppis_f), 1) if ppis_f else None
        lines.append(f"### Gesamtübersicht ({len(daten):,} Herzschläge)")
        lines.append(f"  HR: ∅{hr_mean} bpm | Min {_fmt_hr(hr_min)} | Max {_fmt_hr(hr_max)} bpm")
    if all_rmssd:
        avg_rmssd = round(sum(all_rmssd) / len(all_rmssd), 1)
        lines.append(f"  RMSSD: ∅{avg_rmssd}ms | Min {min(all_rmssd)}ms | Max {max(all_rmssd)}ms")
        if baseline:
            delta = round(avg_rmssd - baseline, 1)
            lines.append(f"  vs. Baseline: {delta:+.1f}ms ({delta/baseline*100:+.0f}%)")

    # Stündlicher Verlauf
    lines.append("\n### Stündlicher Verlauf")
    for stande, werte in sorted(stuendlich.items()):
        if not werte["rmssd"]:
            continue
        h    = stande.hour
        bar  = "█" * int((werte["rmssd"] or 0) / 3)
        flag = ""
        if werte["arrhythmie"]:  flag = " ⚠️ Arrhythmia-Verdacht"
        elif 22 <= h or h < 6:  flag = " 🌙 Night"
        elif 6 <= h < 9:        flag = " ☀️ Morning"
        lines.append(
            f"  {stande.strftime('%H:%M')}: "
            f"RMSSD {werte['rmssd']:>5}ms | HR {werte['hr']:>4}bpm | "
            f"n={werte['n']:>4}  {bar}{flag}"
        )

    # Sleep vs. day
    # Night: 22–06 Uhr (Kernschlaf), day: 09–21 Uhr (Aktivphase).
    # 06–09 and 21–22 sind bewusst ausgeklammert — Aufwach- and Einschlafphase
    # verfälschen beide Kategorien and sind als Puffer sinnvoller unklassifiziert.
    schlaf_rmssd = [w["rmssd"] for dt, w in stuendlich.items()
                    if w["rmssd"] and (dt.hour < 6 or dt.hour >= 22)]
    tag_rmssd    = [w["rmssd"] for dt, w in stuendlich.items()
                    if w["rmssd"] and 9 <= dt.hour < 21]
    if schlaf_rmssd and tag_rmssd:
        lines.append("\n### Sleep vs. day")
        lines.append(f"  Night (22–06 Uhr): ∅{sum(schlaf_rmssd)/len(schlaf_rmssd):.1f}ms")
        lines.append(f"  day   (09–21 Uhr): ∅{sum(tag_rmssd)/len(tag_rmssd):.1f}ms")
        diff = sum(schlaf_rmssd)/len(schlaf_rmssd) - sum(tag_rmssd)/len(tag_rmssd)
        lines.append(f"  Night-Boost: {diff:+.1f}ms "
                     f"({'✅ normal' if diff > 5 else '⚠️ gering — autonome Dysfunktion?'})")

    # Arrhythmia
    arr = [(dt, w) for dt, w in stuendlich.items() if w["arrhythmie"]]
    if arr:
        # "auffällig" statt "notable" — reiner Deutschtext im uebrigen Bericht.
        lines.append(f"\n### Arrhythmia-Fenster ({len(arr)}h auffällig)")
        for dt, w in arr:
            lines.append(f"  {dt.strftime('%H:%M')}: CV={w['cv']:.3f} | RMSSD={w['rmssd']}ms")
    else:
        # War "no notableen Perioden" — Rest einer fehlerhaften Wortersetzung
        # ("auffälligen" -> "notable" mitten im deutschen Satz eingesetzt).
        lines.append("\n### Arrhythmia-Fenster: keine auffälligen Perioden")

    # Umgebungskontext für den Messtag
    pollen_dict = pollen_dict or {}
    air_quality = air_quality or {}
    indoor_air  = indoor_air  or {}
    if pollen_dict or air_quality or indoor_air:
        lines.append("\n### Umgebungskontext am Messtag")
    if pollen_dict:
        day = datum[:10]
        p = pollen_dict.get(day, {})
        if p:
            parts = [f"{l} {p[k]:.0f}" for k, l in [("birch","Birke"), ("grass","Gräser"),
                     ("alder","Erle"), ("mugwort","Beifuß")] if p.get(k)]
            # p.get('total','—') direkt mit :.0f formatiert wuerde bei fehlendem
            # 'total'-Schluessel ValueError werfen ("Unknown format code 'f' for
            # object of type 'str'") — Format-Spezifikation kann nicht auf den
            # String-Platzhalter '—' angewendet werden, nur auf echte Zahlen.
            total = p.get("total")
            total_str = f"{total:.0f} g/m³" if total is not None else "n. a."
            lines.append(f"  Pollen: {', '.join(parts) if parts else '—'}  |  Gesamt: {total_str}")
    if air_quality:
        day = datum[:10]
        a = air_quality.get(day, {})
        if a:
            lines.append(f"  AQI EU: {a.get('aqi_eu_mean','—')}  |  PM2.5: {a.get('pm25_mean','—')} µg/m³"
                         f"  |  Staub: {a.get('dust_mean','—')} µg/m³")
    if indoor_air:
        day = datum[:10]
        i = indoor_air.get(day, {})
        if i:
            parts = [f"{k} {v}" for k, v in sorted(i.items())
                     if k in ("aqi","pm25","pm10","humidity","voc","temperature")]
            lines.append(f"  Indoor: {', '.join(parts)}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=t("Polar H7 — 24h-Analyse", "Polar H7 — 24 h analysis"))
    parser.add_argument("--from", dest="date_from", default=None,
                        help="Datum YYYY-MM-DD (Aufzeichnungstag der H7-Messung). "
                             "Default: letzter Tag mit PPI-Daten in der DB.")
    parser.add_argument("--to",   dest="date_to",   default=None,
                        help="Ende-Datum (Default: gleich wie --from)")
    parser.add_argument("--person", default=OWN_PERSON_ID,
                        help=t("Person (Standard: selbst)", "Person (default: self)"))
    parser.add_argument("--plot",   action="store_true", help="Plots erstellen")
    parser.add_argument("--no-llm", action="store_true", help="Only Rohdaten")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    conn    = open_db()

    if not args.date_from:
        row = conn.execute(
            "SELECT substr(MAX(datetime),1,10) FROM ppi_raw"
        ).fetchone()
        if not row or not row[0]:
            print(t("Keine PPI-Daten in der DB — H7-24h-Analyse übersprungen.",
                    "No PPI data in DB — H7 24 h analysis skipped."))
            return
        args.date_from = row[0]
        print(t(f"Kein --from angegeben — nutze letzten verfügbaren Tag: {args.date_from}",
                f"No --from given — using latest available day: {args.date_from}"))

    date_to = args.date_to or args.date_from

    print(t(f"Lade PPI-Daten {args.date_from} ...",
            f"Loading PPI data {args.date_from} ..."))
    daten = load_ppi(conn, args.date_from + "T00:00", date_to + "T23:59")

    if not daten:
        print(t("Keine PPI-Daten für diesen Zeitbereich.",
                "No PPI data for this time range."))
        print(t("Tipp: Erst Polar Beat App beenden, dann:",
                "Tip: First close the Polar Beat App, then:"))
        print("  python3 import_all.py --update")
        return

    print(t(f"  {len(daten):,} Herzschläge geladen",
            f"  {len(daten):,} heartbeats loaded"))

    stuendlich = analyse_hourly(daten)
    baseline   = load_baseline(conn)
    pollen     = load_pollen(conn, args.date_from, args.date_to or args.date_from)
    aq         = load_air_quality(conn, args.date_from, args.date_to or args.date_from)
    indoor     = load_indoor_air(conn, args.date_from, args.date_to or args.date_from)
    conn.close()

    report = build_report(stuendlich, daten, baseline, args.date_from,
                          pollen_dict=pollen, air_quality=aq, indoor_air=indoor)
    print("\n" + report)

    if args.plot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            OUT_DIR.mkdir(parents=True, exist_ok=True)
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8),
                                            facecolor="#1A1A2E")
            fig.suptitle(f"H7 24h-Analyse — {args.date_from}",
                        color="#E0E0E0", fontsize=12)

            xs  = [dt for dt, w in sorted(stuendlich.items()) if w["rmssd"]]
            ys  = [w["rmssd"] for _, w in sorted(stuendlich.items()) if w["rmssd"]]
            hrs = [w["hr"] for _, w in sorted(stuendlich.items()) if w["rmssd"]]
            colors = ["#E84855" if w["arrhythmie"] else "#2E86AB"
                     for _, w in sorted(stuendlich.items()) if w["rmssd"]]

            ax1.set_facecolor("#16213E")
            ax1.bar(range(len(xs)), ys, color=colors, alpha=0.8)
            ax1.set_xticks(range(len(xs)))
            ax1.set_xticklabels([x.strftime("%H") for x in xs],
                               fontsize=7, color="#E0E0E0")
            if baseline:
                ax1.axhline(baseline, color="#F4A261", linestyle="--",
                           alpha=0.6, label=f"Baseline {baseline}ms")
            ax1.set_ylabel("RMSSD (ms)", color="#E0E0E0", fontsize=9)
            ax1.set_title("Stündliche RMSSD (rot=Arrhythmia-Verdacht)",
                         color="#E0E0E0")
            ax1.tick_params(colors="#E0E0E0", labelsize=7)
            ax1.legend(fontsize=8, labelcolor="#E0E0E0", facecolor="#16213E")
            for s in ax1.spines.values(): s.set_color("#8B8B8B")

            ax2.set_facecolor("#16213E")
            ax2.plot(range(len(xs)), hrs, color="#57A773", linewidth=1.5)
            ax2.fill_between(range(len(xs)), hrs, alpha=0.2, color="#57A773")
            ax2.set_xticks(range(len(xs)))
            ax2.set_xticklabels([x.strftime("%H:%M") for x in xs],
                               fontsize=6, color="#E0E0E0", rotation=45)
            ax2.set_ylabel("HR (bpm)", color="#E0E0E0", fontsize=9)
            ax2.set_title("Stündliche Heart rate", color="#E0E0E0")
            ax2.tick_params(colors="#E0E0E0", labelsize=7)
            for s in ax2.spines.values(): s.set_color("#8B8B8B")

            fig.tight_layout()
            plot_path = OUT_DIR / f"h7_24h_{args.date_from}.png"
            fig.savefig(str(plot_path), dpi=130, bbox_inches="tight",
                       facecolor="#1A1A2E")
            plt.close()
            print(t(f"\nPlot gespeichert: {plot_path}", f"\nPlot saved: {plot_path}"))
        except Exception as e:
            print(t(f"Plot fehlgeschlagen: {e}", f"Plot failed: {e}"))

    if not args.no_llm:
        try:
            from modules.llm import call_llm
            print(t("\nLLM analysiert 24h-HRV ...", "\nLLM analysing 24 h HRV ..."))
            answer = call_llm(report, system=SYSTEM_H7 + DEUTSCH, max_tokens=5000)
        except Exception as e:
            print(t(f"LLM nicht verfügbar: {e}", f"LLM not available: {e}"))
            answer = ""

        print("\n" + "="*60)
        print(answer)
        print("="*60)

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = OUT_DIR / f"h7_analysis_{args.date_from}_{ts}.md"
        out.write_text(
            f"# H7 24h-HRV-Analyse — {args.date_from}\n\n"
            f"## Rohdaten\n```\n{report}\n```\n\n"
            f"## Clinical Analyse\n{answer}\n",
            encoding="utf-8"
        )
        print(t(f"\nBericht: {out}", f"\nReport: {out}"))


if __name__ == "__main__":
    main()
