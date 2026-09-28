# ecg_signal.py — ECG-Signalverarbeitung

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/ecg_signal.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides functions for raw ECG signal processing: bandpass filter and Pan-Tompkins QRS detection.

## Relevance

Provides ECG signal processing functions, essential for cardiological analysis

## Method

Implements bandpass filter (Butterworth or diff-based approximation) and Pan-Tompkins algorithm for real-time QRS detection. Reference: J. Pan & W.J. Tompkins, 1985, IEEE Trans. Biomed. Eng.

## Data flow

- **Reads:** `Keine`, `Tabellen`, `(verarbeitet`, `Rohdaten)`
- **Writes:** `Keine Tabellen (gibt verarbeitete Daten zurück)`

## Limitations

Filter parameters are empirical. Not suitable for clinical diagnosis.

## References

- Pan J, Tompkins WJ (1985). A Real-Time QRS Detection Algorithm. IEEE Transactions on Biomedical Engineering, BME-32(3):230-236. doi:10.1109/TBME.1985.325532

## Usage

```bash
from modules.ecg_signal import pan_tompkins
peaks = pan_tompkins(samples_uv, fs_hz=300)
rr_ms = [(peaks[i+1] - peaks[i]) / fs_hz * 1000 for i in range(len(peaks)-1)]
```
