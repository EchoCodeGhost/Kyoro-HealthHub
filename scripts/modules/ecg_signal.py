# SPDX-License-Identifier: GPL-3.0-or-later
"""
ecg_signal.py — ECG-Signalverarbeitung

@tier        infrastructure
@purpose.de  Bietet Funktionen für die Verarbeitung von Roh-EKG-Signalen:
             Bandpass-Filter und Pan-Tompkins QRS-Detektion.
@purpose.en  Provides functions for raw ECG signal processing:
             bandpass filter and Pan-Tompkins QRS detection.
@method.de   Implementiert Bandpass-Filter (Butterworth oder Diff-basierte Näherung)
             und Pan-Tompkins-Algorithmus für Echtzeit-QRS-Detektion.
             Referenz: J. Pan & W.J. Tompkins, 1985, IEEE Trans. Biomed. Eng.
@method.en   Implements bandpass filter (Butterworth or diff-based approximation)
             and Pan-Tompkins algorithm for real-time QRS detection.
             Reference: J. Pan & W.J. Tompkins, 1985, IEEE Trans. Biomed. Eng.
@refs        Pan J, Tompkins WJ (1985). A Real-Time QRS Detection Algorithm. IEEE Transactions on Biomedical Engineering, BME-32(3):230-236. doi:10.1109/TBME.1985.325532

@relevance.de  Bietet EKG-Signalverarbeitungsfunktionen, essentiell für die kardiologische Analyse
@relevance.en  Provides ECG signal processing functions, essential for cardiological analysis
@reads       Keine Tabellen (verarbeitet Rohdaten)
@writes      Keine Tabellen (gibt verarbeitete Daten zurück)
@limits.de   Filter-Parameter sind empirisch. Nicht fuer klinische Diagnose geeignet.
@limits.en   Filter parameters are empirical. Not suitable for clinical diagnosis.
@usage
    from modules.ecg_signal import pan_tompkins
    peaks = pan_tompkins(samples_uv, fs_hz=300)
    rr_ms = [(peaks[i+1] - peaks[i]) / fs_hz * 1000 for i in range(len(peaks)-1)]
"""



def bandpass_filter(signal, fs: float, low: float = 5.0, high: float = 15.0):
    """
    Butterworth bandpass filter for ECG preprocessing (scipy) or
    diff-based approximation fallback.
    """
    import numpy as np
    arr = np.asarray(signal, dtype=float)
    try:
        from scipy.signal import butter, filtfilt
        nyq = fs / 2.0
        b, a = butter(1, [low / nyq, high / nyq], btype="band")
        return filtfilt(b, a, arr)
    except Exception:
        # Fallback: high-pass via diff + low-pass via running mean
        hp = np.diff(arr, prepend=arr[0])
        win = max(1, int(fs / high))
        lp = np.convolve(hp, np.ones(win) / win, mode="same")
        return lp


def pan_tompkins(samples_uv, fs_hz: float) -> list[int]:
    """
    Pan-Tompkins QRS detection on raw ECG samples.

    Args:
        samples_uv: raw ECG amplitudes in µV (list or ndarray)
        fs_hz:      sampling frequency in Hz

    Returns:
        Sorted list of R-peak sample indices (in original signal time).
        Empty list if signal is too short or no peaks found.
    """
    import numpy as np

    sig = np.asarray(samples_uv, dtype=float)
    n = len(sig)

    if n < int(0.5 * fs_hz):
        return []

    # ── Step 1: Bandpass filter ───────────────────────────────────────────
    filtered = bandpass_filter(sig, fs_hz)

    # ── Step 2: 5-point derivative ────────────────────────────────────────
    deriv = np.zeros(n)
    deriv[2:-2] = (
        2 * filtered[4:]
        + filtered[3:-1]
        - filtered[1:-3]
        - 2 * filtered[:-4]
    ) * fs_hz / 8.0

    # ── Step 3: Squaring ──────────────────────────────────────────────────
    squared = deriv ** 2

    # ── Step 4: Moving window integration (~150 ms) ───────────────────────
    win = max(1, int(0.150 * fs_hz))
    integrated = np.convolve(squared, np.ones(win) / win, mode="same")

    # ── Step 5: Candidate peaks (refractory 200 ms) ───────────────────────
    refractory = int(0.200 * fs_hz)

    try:
        from scipy.signal import find_peaks as _find_peaks
        candidates, _ = _find_peaks(integrated, distance=refractory)
    except ImportError:
        # Pure-numpy local maxima
        diff_sign = np.sign(np.diff(integrated))
        candidates = np.where((diff_sign[:-1] > 0) & (diff_sign[1:] <= 0))[0] + 1

    if len(candidates) == 0:
        return []

    # ── Step 6: Adaptive threshold (Pan-Tompkins learning) ────────────────
    init_win = min(int(2 * fs_hz), n)
    spki = float(np.mean(integrated[:init_win]))   # signal peak estimate
    npki = 0.5 * spki                              # noise peak estimate
    last_qrs = -refractory
    qrs_indices: list[int] = []

    for idx in candidates:
        if idx - last_qrs < refractory:
            continue
        peak_val = float(integrated[idx])
        threshold = npki + 0.25 * (spki - npki)

        if peak_val >= threshold:
            qrs_indices.append(int(idx))
            last_qrs = idx
            spki = 0.125 * peak_val + 0.875 * spki
        else:
            npki = 0.125 * peak_val + 0.875 * npki

    if not qrs_indices:
        return []

    # ── Step 7: Back-search for true R-peak in filtered signal ────────────
    # Integrated signal lags by ~win/2 samples; search ±75 ms around estimate.
    lag = win // 2
    search_half = int(0.075 * fs_hz)
    r_peaks: list[int] = []

    for qrs_idx in qrs_indices:
        start = max(0, qrs_idx - lag - search_half)
        end   = min(n, qrs_idx - lag + search_half)
        if start >= end:
            r_peaks.append(qrs_idx)
        else:
            local_max = start + int(np.argmax(np.abs(filtered[start:end])))
            r_peaks.append(local_max)

    return sorted(set(r_peaks))
