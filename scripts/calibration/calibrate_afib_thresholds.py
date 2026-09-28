#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
"""
AFib Level-1 Schwellenwert-Kalibrierung

@tier        calibrated
@purpose.de  Kalibriert Schwellenwerte für AFib-Erkennung mit MIT-BIH AFDB-Datenbank
@purpose.en  Calibrates thresholds for AFib detection using MIT-BIH AFDB database
@method.de   Kalibriert AFib Level-1 Schwellenwerte unter Verwendung der MIT-BIH Atrial Fibrillation Database.
             25 Aufnahmen à ~10h, 250 Hz, mit Rhythmus-Annotationen.
             Berechnet optimale Schwellenwerte für 5 HRV-Metriken.
@method.en   Calibrates AFib Level-1 thresholds using MIT-BIH Atrial Fibrillation Database.
             25 records × ~10h each, 250 Hz, with rhythm annotations.
             Computes optimal thresholds for 5 HRV metrics.
@reads       MIT-BIH AFDB-Datenbank aus data/calibration/afdb/
@writes      data/calibration/afdb_thresholds.json, data/calibration/afdb_calibration.csv, data/calibration/afdb_roc.png
@refs        Moody GB, Mark RG (2001). The impact of the MIT-BIH Arrhythmia Database. IEEE Engineering in Medicine and Biology Magazine, 20(3):45-50. doi:10.1109/51.932724
             Goldberger AL, Amaral LAN, Glass L et al. (2000). PhysioBank, PhysioToolkit, and PhysioNet. Circulation, 101(23). doi:10.1161/01.CIR.101.23.e215

@relevance.de  Ermöglicht die Kalibrierung von Algorithmen und Schwellenwerten, essentiell für die Datenqualität
@relevance.en  Enables calibration of algorithms and thresholds, essential for data quality
@limits.de   Kalibrierung basiert auf AFDB-Daten. Validität für andere Datensätze nicht garantiert.
@limits.en   Calibration based on AFDB data. Validity for other datasets not guaranteed.
@usage
    cd ~/Kyoro-HealthHub/scripts
    python3 calibration/calibrate_afib_thresholds.py
"""

import json
import math
import sys
from pathlib import Path
from typing import Optional

import wfdb

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.rr_interval_algorithms import turning_point_ratio, sample_entropy as _sampen_impl

AFDB_DIR   = Path(__file__).parent.parent.parent / "data" / "calibration" / "afdb"
OUT_DIR    = Path(__file__).parent.parent.parent / "data" / "calibration"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FS         = 250          # Hz
WINDOW_S   = 300          # 5-minute windows
MIN_BEATS  = 30           # minimum RR intervals per window


# ── RR-Metric helpers (same logic as import_ecg_logger._afib_level1) ─────────

def poincare_sd1_sd2(rr: list[float]) -> tuple[float, float]:
    n = len(rr)
    diffs = [rr[i+1] - rr[i] for i in range(n - 1)]
    sd1 = math.sqrt(sum(d**2 for d in diffs) / (2 * len(diffs)))
    mean_rr = sum(rr) / n
    variance = sum((r - mean_rr) ** 2 for r in rr) / n
    sd2 = math.sqrt(max(0.0, 2 * variance - sd1**2))
    return sd1, sd2


def _count_fast(templates: list[list[float]], m: int, r: float) -> int:
    count = 0
    for i in range(len(templates)):
        for j in range(len(templates)):
            if i == j:
                continue
            if max(abs(templates[i][k] - templates[j][k]) for k in range(m)) <= r:
                count += 1
    return count


def sample_entropy(rr: list[float], m: int = 2, r_factor: float = 0.2) -> float:
    result = _sampen_impl(rr, m=m, r_factor=r_factor)
    return result if result is not None else float("nan")


def cv_drr(rr: list[float]) -> float:
    diffs = [abs(rr[i+1] - rr[i]) for i in range(len(rr) - 1)]
    if not diffs:
        return float("nan")
    mean_d = sum(diffs) / len(diffs)
    if mean_d <= 0:
        return float("nan")
    std_d = math.sqrt(sum((d - mean_d) ** 2 for d in diffs) / len(diffs))
    return std_d / mean_d


def cv_rr(rr: list[float]) -> float:
    n = len(rr)
    mean = sum(rr) / n
    if mean <= 0:
        return float("nan")
    std = math.sqrt(sum((r - mean) ** 2 for r in rr) / n)
    return std / mean


def compute_metrics(rr: list[float]) -> dict:
    if len(rr) < MIN_BEATS:
        return {}
    sd1, sd2 = poincare_sd1_sd2(rr)
    ratio = (sd1 / sd2) if sd2 > 0 else 1.0
    return {
        "poincare_ratio":   round(ratio, 4),
        "sampen":           round(sample_entropy(rr) or float("nan"), 4),
        "turning_pt_ratio": round(turning_point_ratio(rr), 4),
        "cv_drr":           round(cv_drr(rr), 4),
        "cv_rr":            round(cv_rr(rr), 4),
    }


# ── AFDB loading ──────────────────────────────────────────────────────────────

def load_record(rec: str) -> Optional[tuple[list[float], list[bool]]]:
    """
    Returns (rr_ms_list, is_afib_list) — one entry per inter-beat interval.
    AFDB format: .atr = rhythm-change markers only (all '+'), .qrs = beat positions.
    """
    rec_path = str(AFDB_DIR / rec)

    # Rhythm changes from .atr (all symbols are '+', aux_note has '(AFIB', '(N', ...)
    try:
        atr = wfdb.rdann(rec_path, "atr")
    except Exception as e:
        print(f"  [WARN] {rec}: cannot read .atr — {e}", file=sys.stderr)
        return None

    # Beat positions from .qrs
    try:
        qrs = wfdb.rdann(rec_path, "qrs")
    except Exception as e:
        print(f"  [WARN] {rec}: cannot read .qrs — {e}", file=sys.stderr)
        return None

    # Build rhythm change list: (sample, "AFIB"|"N")
    rhythm_changes: list[tuple[int, str]] = []
    for samp, aux in zip(atr.sample, atr.aux_note):
        stripped = (aux or "").strip().rstrip("\x00").upper()
        if stripped.startswith("("):
            is_afib_label = stripped in {"(AFIB", "(AFL"}
            rhythm_changes.append((samp, "AFIB" if is_afib_label else "N"))

    beat_samples = list(qrs.sample)

    if len(beat_samples) < 2:
        return None

    # Assign rhythm to each beat interval
    # Start assumption: sinus (N)
    current_rhythm = "N"
    rc_idx = 0

    rr_intervals: list[float] = []
    is_afib_flags: list[bool] = []

    for i in range(len(beat_samples) - 1):
        s = beat_samples[i]
        # Advance rhythm pointer
        while rc_idx < len(rhythm_changes) and rhythm_changes[rc_idx][0] <= s:
            current_rhythm = rhythm_changes[rc_idx][1]
            rc_idx += 1
        rr_ms = (beat_samples[i + 1] - s) / FS * 1000.0
        if 200 <= rr_ms <= 3000:  # physiologically plausible
            rr_intervals.append(rr_ms)
            is_afib_flags.append(current_rhythm == "AFIB")

    return rr_intervals, is_afib_flags


# ── Windowed feature extraction ───────────────────────────────────────────────

def extract_windows(
    rr_ms: list[float],
    is_afib: list[bool],
    window_beats: int = 150,
    step_beats: int = 75,
) -> list[dict]:
    """Sliding window over RR series. Window size ~150 beats ≈ 2–3 min."""
    rows = []
    for start in range(0, len(rr_ms) - window_beats, step_beats):
        chunk_rr    = rr_ms[start : start + window_beats]
        chunk_afib  = is_afib[start : start + window_beats]
        afib_frac   = sum(chunk_afib) / len(chunk_afib)
        label_afib  = afib_frac >= 0.9  # >90% beats in AFIB → AFib window
        label_mixed = 0.1 < afib_frac < 0.9

        if label_mixed:
            continue  # skip ambiguous windows

        metrics = compute_metrics(chunk_rr)
        if not metrics:
            continue

        row = {"label": int(label_afib)}
        row.update(metrics)
        rows.append(row)
    return rows


# ── ROC / threshold finding ───────────────────────────────────────────────────

METRICS = ["poincare_ratio", "sampen", "turning_pt_ratio", "cv_drr", "cv_rr"]
# Direction: for all 5 metrics, higher value → more likely AFib
HIGHER_IS_AFIB = {
    "poincare_ratio":   True,
    "sampen":           True,
    "turning_pt_ratio": True,
    "cv_drr":           True,
    "cv_rr":            True,
}


def roc_analysis(labels: list[int], scores: list[float], higher_is_afib: bool = True):
    """Returns (thresholds, tpr_list, fpr_list, auc, best_threshold, best_f1)."""
    pairs = [(s, lb) for s, lb in zip(scores, labels) if not math.isnan(s)]
    if not pairs:
        return None

    pairs.sort(key=lambda x: x[0], reverse=higher_is_afib)
    n_pos = sum(lb for _, lb in pairs)
    n_neg = len(pairs) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None

    thresholds, tprs, fprs = [], [], []
    tp = fp = 0
    prev_s = None
    for score, label in pairs:
        if score != prev_s and prev_s is not None:
            thresholds.append(prev_s)
            tprs.append(tp / n_pos)
            fprs.append(fp / n_neg)
        if label == 1:
            tp += 1
        else:
            fp += 1
        prev_s = score
    thresholds.append(prev_s)
    tprs.append(tp / n_pos)
    fprs.append(fp / n_neg)

    auc = 0.0
    for i in range(1, len(tprs)):
        auc += (fprs[i] - fprs[i-1]) * (tprs[i] + tprs[i-1]) / 2

    best_f1, best_thresh = 0.0, thresholds[0]
    for thresh, tpr, fpr in zip(thresholds, tprs, fprs):
        prec_denom = tpr * n_pos + fpr * n_neg
        if prec_denom == 0:
            continue
        prec = tpr * n_pos / prec_denom
        rec  = tpr
        if prec + rec == 0:
            continue
        f1 = 2 * prec * rec / (prec + rec)
        if f1 > best_f1:
            best_f1    = f1
            best_thresh = thresh

    return {
        "thresholds": thresholds,
        "tprs": tprs,
        "fprs": fprs,
        "auc": round(auc, 4),
        "best_threshold": round(best_thresh, 4),
        "best_f1": round(best_f1, 4),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import csv

    records = sorted(p.stem for p in AFDB_DIR.glob("*.hea"))
    if not records:
        print(f"Keine Records in {AFDB_DIR}. Bitte zuerst download_afdb.py ausführen.")
        sys.exit(1)

    print(f"MIT-BIH AFDB Kalibrierung: {len(records)} Records")
    print(f"  AFDB-Verzeichnis: {AFDB_DIR}")
    print()

    all_windows: list[dict] = []

    for i, rec in enumerate(records, 1):
        print(f"  [{i:>2}/{len(records)}] {rec} ...", end="", flush=True)
        result = load_record(rec)
        if result is None:
            print(" übersprungen")
            continue
        rr_ms, is_afib = result
        n_afib = sum(is_afib)
        print(f" {len(rr_ms):>6} RR,  {n_afib:>6} AFIB-Intervalle ({100*n_afib/max(1,len(rr_ms)):.0f}%)")

        windows = extract_windows(rr_ms, is_afib)
        all_windows.extend(windows)

    if not all_windows:
        print("Keine auswertbaren Fenster gefunden.", file=sys.stderr)
        sys.exit(1)

    n_afib_win = sum(w["label"] for w in all_windows)
    n_sr_win   = len(all_windows) - n_afib_win
    print(f"\nGesamt: {len(all_windows)} Fenster — {n_afib_win} AFib, {n_sr_win} SR")

    # Save CSV
    csv_path = OUT_DIR / "afdb_calibration.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["label"] + METRICS)
        writer.writeheader()
        writer.writerows(all_windows)
    print(f"  → {csv_path}")

    # ROC per metric
    labels = [w["label"] for w in all_windows]
    results = {}
    print()
    print(f"{'Metrik':<20} {'AUC':>6}  {'Best-Threshold':>15}  {'Best-F1':>8}")
    print("-" * 58)
    for metric in METRICS:
        scores = [w.get(metric, float("nan")) for w in all_windows]
        roc = roc_analysis(labels, scores, higher_is_afib=HIGHER_IS_AFIB[metric])
        if roc is None:
            print(f"  {metric:<20} — kein Ergebnis")
            continue
        results[metric] = roc
        print(f"  {metric:<20} {roc['auc']:>6.4f}  {roc['best_threshold']:>15.4f}  {roc['best_f1']:>8.4f}")

    # Save thresholds JSON
    thresholds = {
        m: {
            "threshold":       results[m]["best_threshold"],
            "higher_is_afib":  HIGHER_IS_AFIB[m],
            "auc":             results[m]["auc"],
            "best_f1":         results[m]["best_f1"],
        }
        for m in METRICS if m in results
    }
    json_path = OUT_DIR / "afdb_thresholds.json"
    with open(json_path, "w") as f:
        json.dump(thresholds, f, indent=2)
    print(f"\n  → Thresholds: {json_path}")

    # ROC plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 6))
        colors = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00"]
        for metric, color in zip(METRICS, colors):
            if metric not in results:
                continue
            r = results[metric]
            ax.plot(r["fprs"], r["tprs"],
                    label=f"{metric} (AUC={r['auc']:.3f})", color=color, lw=1.8)
            ax.axvline(x=0, color="grey", lw=0.5)

        ax.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.5)
        ax.set_xlabel("False Positive Rate (1 – Specificity)")
        ax.set_ylabel("True Positive Rate (Sensitivity)")
        ax.set_title(f"ROC — AFib Level-1 Metriken\n(MIT-BIH AFDB, {len(records)} Records, {len(all_windows)} Fenster)")
        ax.legend(loc="lower right", fontsize=9)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        roc_path = OUT_DIR / "afdb_roc.png"
        fig.savefig(roc_path, dpi=150)
        plt.close(fig)
        print(f"  → ROC-Plot: {roc_path}")
    except ImportError:
        print("  (matplotlib nicht verfügbar, kein Plot)")

    print("\nKalibrierung abgeschlossen.")
    print("\nEmpfohlene Thresholds für import_ecg_logger._afib_level1():")
    for m, v in thresholds.items():
        direction = ">" if v["higher_is_afib"] else "<"
        print(f"  {m:<22} {direction} {v['threshold']:.4f}  (AUC={v['auc']:.3f}, F1={v['best_f1']:.3f})")


if __name__ == "__main__":
    main()
