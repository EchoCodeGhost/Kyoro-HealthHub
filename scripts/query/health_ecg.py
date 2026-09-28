#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
health_ecg.py — EKG-Analyse fuer Apple Watch ECG CSVs

@tier        infrastructure
@purpose.de  Analysiert Apple Watch EKG-Aufzeichnungen: R-Peak-Detektion, Herzfrequenz, RR-Intervall-Variabilitaet, Rhythmus-Unregelmaessigkeiten
@purpose.en  Analyzes Apple Watch ECG recordings: R-peak detection, heart rate from ECG, RR interval variability, rhythm irregularities
@method.de   Laedt EKG-CSV-Dateien aus dem Apple ECG-Verzeichnis und fuehrt algorithmische Analysen durch:
             - Bandpassfilter (5-25 Hz) zur Baseline-Korrektur
             - R-Peak-Detektion mit dynamischer Schwelle (0.5 SD)
             - Validierung: RR-Intervalle 300-1800ms (33-200 bpm)
             - HRV-Metriken: RMSSD, SDNN, pNN50, Variationskoeffizient
             - Unregelmaessigkeits-Metriken: CV_RR, Irregularity Index
             Optional: Plots (EKG-Signal + RR-Tachogramm) und detaillierte Metriken (experimentell)
             Zeigt Zusammenfassung mit Klassifizierungen und PEM-Warnungen an.
@method.en   Loads ECG CSV files from Apple ECG directory and performs algorithmic analysis:
             - Bandpass filter (5-25 Hz) for baseline correction
             - R-peak detection with dynamic threshold (0.5 SD)
             - Validation: RR intervals 300-1800ms (33-200 bpm)
             - HRV metrics: RMSSD, SDNN, pNN50, coefficient of variation
             - Irregularity metrics: CV_RR, irregularity index
             Optional: plots (ECG signal + RR tachogram) and detailed metrics (experimental)
             Shows summary with classifications and PEM warnings.
@reads       Apple Watch EKG-CSV Dateien aus data/ecg/ oder health_config.apple_xml.parent/electrocardiograms/
@writes      analyses/ekg/ Verzeichnis (Plots als PNG-Dateien)
@limits.de   Experimentelle algorithmische Analyse. Resultate mit Vorsicht interpretieren.
             Abhaengig von Apple Watch EKG-Datenverfuegbarkeit.

@relevance.de  Ermöglicht EKG-spezifische Abfragen, essentiell für die kardiologische Analyse
@relevance.en  Enables ECG-specific queries, essential for cardiological analysis
@limits.en   Experimental algorithmic analysis. Results should be interpreted with caution.
             Depends on Apple Watch ECG data availability.
@usage
    python health_ecg.py
    python health_ecg.py --plot
    python health_ecg.py --full
"""

import argparse
import csv
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))
from health_config import Config as _Cfg
_cfg = _Cfg()

import numpy as np
from modules.i18n import add_lang_arg, apply_lang_from_args

ECG_DIR = _cfg.apple_xml.parent / "electrocardiograms"
OUT_DIR = _cfg.analyses_dir / "ekg"
SAMPLE_RATE = 512  # Hz


def load_ecg(csv_path: Path) -> tuple[dict, np.ndarray]:
    """Loads Apple Watch EKG-CSV. Gibt (Metadaten, Signal-Array in µV) zurück.

    Format: Metadaten-Header, then Datenzeilen with [Qualitätswert, µV-Spannungswert].
    Only die Spannungsspalte wird als sequentielle 512-Hz-Samples gelesen.
    """
    meta = {}
    values = []
    in_data = False
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip(): continue
            key = row[0].strip()
            val = row[1].strip() if len(row) > 1 else ""
            if not in_data:
                if key in ("Name","Geburtsdatum","Aufzeichnungsdatum","Klassifizierung",
                           "Symptome","Gerät","Messrate","Softwareversion"):
                    meta[key] = val
                if key == "Einheit":
                    in_data = True
            else:
                # Datenzeilen: [Qualitätswert, µV] — only µV (column 2) verwenden
                try:
                    if len(row) >= 2:
                        values.append(float(row[1]))
                except (ValueError, IndexError):
                    pass
    return meta, np.array(values)


def detect_r_peaks(signal: np.ndarray, sr: int = 512) -> np.ndarray:
    """R-Peak-Detektion for Apple Watch Lead-I EKG (512 Hz, µV).

    Apple Watch ECGs sind 30s lang, quantisiert auf ~1-999 µV.
    R-Peaks sind die dominanten positiven Ausschläge.
    """
    from scipy.signal import butter, filtfilt, find_peaks

    # 1. Bandpassfilter 5–25 Hz — entfernt Baseline-Wander and Hochfrequenzrauschen
    nyq = sr / 2
    b, a = butter(2, [5/nyq, 25/nyq], btype='band')
    filtered = filtfilt(b, a, signal)

    # 2. Normierung (Z-Score for robuste Schwelle)
    filtered_norm = (filtered - np.mean(filtered)) / (np.std(filtered) + 1e-8)

    # 3. R-Peak-Suche: Peaks müssen > 0.5 Standard deviationen sein
    #    Mindestabstand: 300ms (= 200 bpm Maximum)
    min_dist  = int(0.30 * sr)   # 300ms
    threshold = 0.5              # in Standardabweichungen
    peaks, props = find_peaks(filtered_norm, height=threshold, distance=min_dist)

    # 4. Only Peaks behalten die zu physiologisch validen RR-Intervalln führen
    if len(peaks) > 1:
        rr_ms = np.diff(peaks) / sr * 1000
        valid = (rr_ms >= 300) & (rr_ms <= 1800)  # 33–200 bpm
        keep  = set()
        for i, v in enumerate(valid):
            if v:
                keep.add(i)
                keep.add(i + 1)
        if keep:
            peaks = peaks[sorted(keep)]

    return peaks


def analyse_ecg(signal: np.ndarray, peaks: np.ndarray, sr: int = 512) -> dict:
    """berechnet HR and HRV-Metriken aus R-Peaks (only physiologisch valide Intervall)."""
    if len(peaks) < 3:
        return {"error": "Zu wenige R-Peaks erkannt"}

    rr_ms_all = np.diff(peaks) / sr * 1000
    # Only physiologisch plausible RR-Intervall
    valid     = rr_ms_all[(rr_ms_all >= 300) & (rr_ms_all <= 1800)]
    if len(valid) < 3:
        return {"error": "Zu wenige valide RR-Intervalle"}

    hr_mean = 60000 / np.mean(valid)
    hr_min  = 60000 / valid.max()
    hr_max  = 60000 / valid.min()

    # RMSSD: aufeinanderfolgende Differenzen
    rr_diffs = np.diff(valid)
    rmssd    = np.sqrt(np.mean(rr_diffs ** 2))
    # SDNN per HRV-Konvention (Task Force 1996): Stichproben-SD, ddof=1
    sdnn     = np.std(valid, ddof=1)
    pnn50    = np.sum(np.abs(rr_diffs) > 50) / len(rr_diffs) * 100

    # Atrial fibrillation-Metrik: Variationskoeffizient der RR-Intervall
    # AF typisch: CV > 0.15 (Irregularity Index)
    cv_rr    = np.std(valid, ddof=1) / np.mean(valid)

    # Unregelmäßigkeit: % der RR-Intervall die >15% from Median abweichen
    median_rr = np.median(valid)
    irr_pct   = np.sum(np.abs(valid - median_rr) > 0.15 * median_rr) / len(valid) * 100

    return {
        "hr_mean":    round(hr_mean, 1),
        "hr_min":     round(hr_min, 1),
        "hr_max":     round(hr_max, 1),
        "rmssd":      round(rmssd, 1),
        "sdnn":       round(sdnn, 1),
        "pnn50":      round(pnn50, 1),
        "cv_rr":      round(cv_rr, 3),
        "irr_pct":    round(irr_pct, 1),
        "n_beats":    len(peaks),
        "n_valid_rr": len(valid),
        "duration_s": round(len(signal) / sr, 1),
    }


def plot_ecg(signal: np.ndarray, peaks: np.ndarray, meta: dict, out_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), facecolor="#1A1A2E")
    time_axis = np.arange(len(signal)) / SAMPLE_RATE

    # EKG-Rohsignal (erste 10 seconds)
    n = min(len(signal), 10 * SAMPLE_RATE)
    ax1.set_facecolor("#16213E")
    ax1.plot(time_axis[:n], signal[:n], color="#2E86AB", linewidth=0.8)
    peaks_in = peaks[peaks < n]
    ax1.scatter(time_axis[peaks_in], signal[peaks_in], color="#E84855", s=20, zorder=5, label="R-Peaks")
    ax1.set_xlabel("Zeit (s)", color="#E0E0E0", fontsize=8)
    ax1.set_ylabel("µV", color="#E0E0E0", fontsize=8)
    ax1.set_title(f"EKG — {meta.get('Aufzeichnungsdatum','')[:16]} | {meta.get('Klassifizierung','')}",
                  color="#E0E0E0", fontsize=10)
    ax1.tick_params(colors="#E0E0E0", labelsize=7)
    ax1.spines[['top','right']].set_visible(False)
    for s in ax1.spines.values(): s.set_color("#8B8B8B")
    ax1.legend(fontsize=7, labelcolor="#E0E0E0", facecolor="#16213E")

    # RR-Tachogramm
    if len(peaks) > 2:
        rr = np.diff(peaks) / SAMPLE_RATE * 1000
        ax2.set_facecolor("#16213E")
        ax2.plot(rr, "o-", color="#57A773", linewidth=1, markersize=3)
        ax2.axhline(np.mean(rr), color="#F4A261", linestyle="--", linewidth=1, label=f"∅ {np.mean(rr):.0f}ms")
        ax2.set_xlabel("Herzschlag #", color="#E0E0E0", fontsize=8)
        ax2.set_ylabel("RR-Intervall (ms)", color="#E0E0E0", fontsize=8)
        ax2.set_title("RR-Tachogramm (HRV-Rohdaten)", color="#E0E0E0", fontsize=10)
        ax2.tick_params(colors="#E0E0E0", labelsize=7)
        ax2.spines[['top','right']].set_visible(False)
        for s in ax2.spines.values(): s.set_color("#8B8B8B")
        ax2.legend(fontsize=7, labelcolor="#E0E0E0", facecolor="#16213E")

    fig.tight_layout()
    fig.savefig(str(out_path), dpi=120, bbox_inches="tight", facecolor="#1A1A2E")
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plot", action="store_true", help="EKG-Plots erstellen")
    parser.add_argument("--full", action="store_true", help="Algorithmische HRV-Metriken (experimentell)")
    add_lang_arg(parser)

    args = parser.parse_args()
    apply_lang_from_args(args)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ecg_files = sorted(ECG_DIR.glob("ecg_*.csv"))
    print(f"{len(ecg_files)} EKG-Dateien gefunden.\n")

    results = []
    from collections import Counter

    for f in ecg_files:
        try:
            meta, signal = load_ecg(f)
            if len(signal) < 100:
                continue

            klassifizierung = meta.get("Klassifizierung", "?")
            datum           = meta.get("Aufzeichnungsdatum", "")[:16]
            symptome        = meta.get("Symptome", "").strip()

            flag = ""
            if "Vorhofflimmern" in klassifizierung:      flag = " 🔴"
            elif "Hohe Herzfrequenz" in klassifizierung: flag = " ⚠️"
            elif "Uneindeutig" in klassifizierung:       flag = " ⚡"
            elif "Schlechte" in klassifizierung:         flag = " 📶"

            results.append({"file": f.name, "meta": meta, "signal_len": len(signal)})

            print(f"── {datum}{flag} ──")
            print(f"   Klassifizierung: {klassifizierung}{flag}")
            print(f"   Dauer: {len(signal)/SAMPLE_RATE:.0f}s | Samples: {len(signal)}")
            if symptome:
                print(f"   Symptome: {symptome}")

            # Optionale algorithmische Analyse (experimentell — Resultse with Vorsicht interpretieren)
            if args.full:
                try:
                    peaks   = detect_r_peaks(signal)
                    metrics = analyse_ecg(signal, peaks)
                    if "error" not in metrics:
                        print(f"   [Algo] HR≈{metrics['hr_mean']:.0f} bpm | "
                              f"RMSSD≈{metrics['rmssd']:.0f}ms | CV={metrics['cv_rr']:.3f} | "
                              f"valide RR={metrics['n_valid_rr']}")
                    else:
                        print(f"   [Algo] {metrics['error']}")
                except Exception as e:
                    print(f"   [Algo] Fehler: {e}")

            if args.plot:
                try:
                    peaks    = detect_r_peaks(signal)
                    plot_out = OUT_DIR / f"{f.stem}_analysis.png"
                    plot_ecg(signal, peaks, meta, plot_out)
                    print(f"   Plot: {plot_out}")
                except Exception as e:
                    print(f"   Plot-Fehler: {e}")
            print()

        except Exception as e:
            print(f"  {f.name}: Fehler — {e}")

    # Summary
    if results:
        print("=" * 55)
        print("ZUSAMMENFASSUNG")
        print("=" * 55)
        klassifizierungen = [r['meta'].get('Klassifizierung','?') for r in results]
        for k, n in Counter(klassifizierungen).most_common():
            flag = " 🔴 → Kardiologische Abklärung" if "Vorhofflimmern" in k else \
                   (" ⚠️" if "Hohe Herzfrequenz" in k else "")
            print(f"  {k}: {n}x{flag}")

        af_list = [(r['meta'].get('Aufzeichnungsdatum','')[:16], r['meta'].get('Symptome',''))
                   for r in results if "Vorhofflimmern" in r['meta'].get('Klassifizierung','')]
        if af_list:
            print(f"\n🔴 VORHOFFLIMMERN-EREIGNISSE ({len(af_list)}):")
            for dt, sym in af_list:
                print(f"  {dt}" + (f" | Symptome: {sym}" if sym else ""))
            print("\n  → Empfehlung: Kardiologische Vorstellung, ggf. Langzeit-EKG")

        print(f"\nEKG-Plots (mit --plot): {OUT_DIR}")


if __name__ == "__main__":
    main()
