#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Atemfrequenz-Schätzer-Validierung gegen BIDMC-Ground-Truth

@tier        calibrated
@purpose.de  Validiert die RSA-basierte Atemfrequenz-Schätzlogik aus
             mobile/KyoroPolarApp/.../RespiratoryRateEstimator.kt (Python-Nachbau
             hier) gegen echte Atemfrequenz-Ground-Truth aus dem BIDMC-Datensatz
             (BACK-26, lokaler Feature-Backlog).
@purpose.en  Validates the RSA-based respiratory rate estimation logic from
             mobile/KyoroPolarApp/.../RespiratoryRateEstimator.kt (reimplemented
             in Python here) against real respiratory rate ground truth from the
             BIDMC dataset (BACK-26, local feature backlog).
@method.de   Lädt bidmc_XX_Signals.csv (PLETH-Wellenform, 125 Hz) und
             bidmc_XX_Numerics.csv (RESP-Ground-Truth in Atemzügen/Min., 1 Hz)
             im CSV-Format (nicht das binäre WFDB-.breath-Annotationsformat —
             deutlich einfacher zu parsen, README empfiehlt CSV explizit für
             direkten Gebrauch). Peak-Detection auf PLETH liefert Puls-zu-Puls-
             Intervalle (Ersatz für einen echten PPI-Stream). Dieselbe Detrend+
             Glättung+Peak-Zählung-Logik wie in RespiratoryRateEstimator.kt wird
             hier in Python nachgebaut und über 30-Sek.-Fenster gegen die echte
             RESP-Spalte verglichen (MAE).
@method.en   Downloads bidmc_XX_Signals.csv (PLETH waveform, 125 Hz) and
             bidmc_XX_Numerics.csv (RESP ground truth in breaths/min, 1 Hz) in
             CSV format (not the binary WFDB .breath annotation format — much
             simpler to parse, and the README explicitly recommends CSV for
             direct use). Peak detection on PLETH yields pulse-to-pulse
             intervals (substitute for a real PPI stream). The same detrend+
             smoothing+peak-counting logic as RespiratoryRateEstimator.kt is
             reimplemented here in Python and compared against the real RESP
             column over 30-second windows (MAE).
@reads       PhysioNet bidmc_csv/ files (online, cached in
             data/calibration/bidmc_csv/ after first run)
@writes      data/calibration/bidmc_csv/ (raw CSVs), stdout summary
@refs        Pimentel MAF, Johnson AEW, Charlton PH et al. (2017). Toward a Robust Estimation of Respiratory Rate From Pulse Oximeters. IEEE Transactions on Biomedical Engineering, 64(8):1914-1923. doi:10.1109/TBME.2016.2613124

@relevance.de  Ermöglicht die Validierung von Algorithmen, essentiell für die Qualitätssicherung
@relevance.en  Enables algorithm validation, essential for quality assurance
@limits.de   Puls-zu-Puls-Intervalle kommen hier aus PPG-Peak-Detection auf
             einer sauberen ICU-Monitor-Aufnahme (125 Hz, wenig Rauschen) — auf
             einem realen Handgelenk-PPG (Polar Loop Gen 2/Polar 360, ~22-100 Hz,
             Bewegungsartefakte) dürfte die Genauigkeit schlechter ausfallen als
             hier gemessen. Diese Validierung zeigt also eine Obergrenze, keine
             Garantie für die Kotlin-Implementierung im Alltag.
@limits.en   Pulse-to-pulse intervals here come from PPG peak detection on a
             clean ICU monitor recording (125 Hz, low noise) — on a real
             wrist-worn PPG (Polar Loop Gen 2/Polar 360, ~22-100 Hz, motion
             artifacts) accuracy is likely worse than measured here. This
             validation shows an upper bound, not a guarantee for the Kotlin
             implementation in everyday use.
@usage
    python3 scripts/calibration/validate_respiratory_rate_bidmc.py
    python3 scripts/calibration/validate_respiratory_rate_bidmc.py --records bidmc01,bidmc02
    python3 scripts/calibration/validate_respiratory_rate_bidmc.py --limit 10
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import requests
from scipy.signal import find_peaks

CSV_DIR = Path(__file__).parent.parent.parent / "data" / "calibration" / "bidmc_csv"
BASE_URL = "https://physionet.org/files/bidmc/1.0.0/bidmc_csv/"

# Mirrors RespiratoryRateEstimator.kt defaults.
RESAMPLE_HZ = 4.0
DETREND_WINDOW_S = 10.0
SMOOTH_WINDOW_S = 1.5
ESTIMATION_WINDOW_S = 30.0


def ensure_record_csvs(record_num: int) -> tuple[Path, Path]:
    """Downloads (if not already cached) Signals.csv + Numerics.csv for one record."""
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    rec = f"{record_num:02d}"
    signals_path = CSV_DIR / f"bidmc_{rec}_Signals.csv"
    numerics_path = CSV_DIR / f"bidmc_{rec}_Numerics.csv"
    for path, fname in [(signals_path, f"bidmc_{rec}_Signals.csv"),
                         (numerics_path, f"bidmc_{rec}_Numerics.csv")]:
        if path.exists():
            continue
        r = requests.get(BASE_URL + fname, timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
    return signals_path, numerics_path


def load_pleth(signals_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Returns (time_s, pleth) arrays."""
    data = np.genfromtxt(signals_path, delimiter=",", names=True, skip_header=0)
    time_s = data["Time_s"] if "Time_s" in data.dtype.names else data[data.dtype.names[0]]
    pleth = data["PLETH"]
    return time_s, pleth


def load_resp_ground_truth(numerics_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Returns (time_s, resp_breaths_per_min) arrays."""
    data = np.genfromtxt(numerics_path, delimiter=",", names=True, skip_header=0)
    time_s = data[data.dtype.names[0]]
    resp = data["RESP"]
    return time_s, resp


def pleth_to_pulse_intervals(time_s: np.ndarray, pleth: np.ndarray, fs: float = 125.0):
    """Peak-detects the PPG waveform to derive pulse-to-pulse intervals —
    a stand-in for a real device's beat-to-beat PPI stream."""
    min_distance_samples = int(fs * 60 / 200)  # cap at 200 bpm
    peaks, _ = find_peaks(pleth, distance=min_distance_samples, prominence=np.std(pleth) * 0.3)
    peak_times_ms = time_s[peaks] * 1000.0
    ppi_ms = np.diff(peak_times_ms)
    ppi_ts_ms = peak_times_ms[1:]
    return ppi_ts_ms, ppi_ms


def estimate_respiratory_rate_series(ppi_ts_ms: np.ndarray, ppi_ms: np.ndarray) -> list[tuple[float, float]]:
    """Python port of RespiratoryRateEstimator.kt — same detrend/smooth/peak-count
    approach, evaluated at each estimation-window step across the whole recording.
    Returns list of (window_end_time_s, estimated_breaths_per_min)."""
    if len(ppi_ts_ms) < 6:
        return []

    inst_hr = 60_000.0 / ppi_ms
    t_s = ppi_ts_ms / 1000.0

    results = []
    step_s = ESTIMATION_WINDOW_S  # non-overlapping windows, simplest comparison to 30s-avg ground truth
    t_end = t_s[-1]
    window_start = t_s[0] + DETREND_WINDOW_S  # margin so detrending has context
    while window_start + ESTIMATION_WINDOW_S <= t_end:
        window_end = window_start + ESTIMATION_WINDOW_S
        mask = (t_s >= window_start - DETREND_WINDOW_S) & (t_s <= window_end)
        rel_t = t_s[mask]
        rel_hr = inst_hr[mask]
        if len(rel_t) < 6:
            window_start += step_s
            continue

        grid_t = np.arange(rel_t[0], rel_t[-1], 1.0 / RESAMPLE_HZ)
        grid_v = np.interp(grid_t, rel_t, rel_hr)

        detrend_n = max(1, int(DETREND_WINDOW_S * RESAMPLE_HZ))
        smooth_n = max(1, int(SMOOTH_WINDOW_S * RESAMPLE_HZ))
        detrended = grid_v - moving_average(grid_v, detrend_n)
        smoothed = moving_average(detrended, smooth_n)

        est_mask = grid_t >= window_start
        windowed = smoothed[est_mask]
        windowed_t = grid_t[est_mask]
        if len(windowed) < 6:
            window_start += step_s
            continue

        peak_count = count_peaks(windowed)
        duration_min = (windowed_t[-1] - windowed_t[0]) / 60.0
        if duration_min > 0:
            results.append((window_end, peak_count / duration_min))

        window_start += step_s

    return results


def moving_average(values: np.ndarray, window: int) -> np.ndarray:
    """Centered moving average with a shrinking window at the edges — must
    match RespiratoryRateEstimator.kt's movingAverage() exactly (clamped
    half-window on each side), not np.convolve(mode="same")'s implicit
    zero-padding at the boundaries, which biases values near the edges of
    each window toward zero and would make this "Python port" numerically
    diverge from the Kotlin production code precisely where the validation
    is supposed to be checking it."""
    if window <= 1:
        return values.copy()
    n = len(values)
    half = window // 2
    out = np.empty(n)
    for i in range(n):
        lo = max(i - half, 0)
        hi = min(i + half, n - 1)
        out[i] = values[lo:hi + 1].mean()
    return out


def count_peaks(values: np.ndarray) -> int:
    count = 0
    for i in range(1, len(values) - 1):
        if values[i] > values[i - 1] and values[i] >= values[i + 1] and values[i] > 0:
            count += 1
    return count


def validate_record(record_num: int) -> list[float] | None:
    """Returns list of absolute errors (breaths/min) for this record, or None on failure."""
    try:
        signals_path, numerics_path = ensure_record_csvs(record_num)
        time_s, pleth = load_pleth(signals_path)
        resp_time_s, resp_truth = load_resp_ground_truth(numerics_path)
    except Exception as e:
        print(f"  bidmc{record_num:02d}: FEHLER beim Laden — {e}", file=sys.stderr)
        return None

    ppi_ts_ms, ppi_ms = pleth_to_pulse_intervals(time_s, pleth)
    estimates = estimate_respiratory_rate_series(ppi_ts_ms, ppi_ms)
    if not estimates:
        print(f"  bidmc{record_num:02d}: zu wenig Daten für eine Schätzung")
        return None

    errors = []
    for window_end_s, est_rate in estimates:
        # Ground truth is at 1Hz; average over the same 30s window ending here.
        # The clinical monitor itself leaves gaps (NaN) in RESP during signal
        # dropout — nanmean + an all-NaN guard skips those windows instead of
        # silently propagating NaN into the aggregate.
        gt_mask = (resp_time_s >= window_end_s - ESTIMATION_WINDOW_S) & (resp_time_s <= window_end_s)
        if not np.any(gt_mask):
            continue
        window_vals = resp_truth[gt_mask]
        if np.all(np.isnan(window_vals)):
            continue
        gt_rate = np.nanmean(window_vals)
        errors.append(abs(est_rate - gt_rate))

    if errors:
        print(f"  bidmc{record_num:02d}: {len(errors)} Fenster, MAE={np.mean(errors):.2f} bpm")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", default=None, help="Komma-getrennte Record-Nummern, z.B. 1,2,3")
    parser.add_argument("--limit", type=int, default=53, help="Anzahl Records (Default: alle 53)")
    args = parser.parse_args()

    if args.records:
        record_nums = [int(r.strip().replace("bidmc", "")) for r in args.records.split(",")]
    else:
        record_nums = list(range(1, min(args.limit, 53) + 1))

    print(f"Validiere RespiratoryRateEstimator-Logik gegen {len(record_nums)} BIDMC-Aufnahmen...")
    all_errors: list[float] = []
    for n in record_nums:
        errors = validate_record(n)
        if errors:
            all_errors.extend(errors)

    print()
    if all_errors:
        print(f"Gesamt: {len(all_errors)} Fenster über {len(record_nums)} Aufnahmen")
        print(f"MAE:    {np.mean(all_errors):.2f} Atemzüge/Min.")
        print(f"Median: {np.median(all_errors):.2f} Atemzüge/Min.")
        print(f"P90:    {np.percentile(all_errors, 90):.2f} Atemzüge/Min.")
    else:
        print("Keine auswertbaren Fenster — Datenzugriff oder Peak-Detection prüfen.")


if __name__ == "__main__":
    main()
