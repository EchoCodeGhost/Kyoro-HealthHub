# R-Peak-Erkennung aus EKG-Rohdaten beliebiger Quelle (Pan-Tompkins).

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_ecg_rpeaks.py`

**Evidence tier:** research (peer-reviewed literature basis, but no formal clinical validation study with endpoints)

## Purpose

Detects R-peaks in ECG raw signals from any source using the Pan-Tompkins algorithm. Writes detected peaks to ecg_rpeaks and derived RR intervals to ppi_raw — source label derived device- agnostically from ecg_sessions.source (e.g. 'apple_health' → 'ecg_apple'), so that compute_arrhythmia and compute_ppi_dfa can process ECG sessions from any source that delivers raw signals into ecg_sessions/ecg_samples like any other RR data stream. Additionally: PR/QRS delineation (see modules/ecg_waveform_algorithms.py) for sources that do not compute these values themselves (Apple Watch, ECG Logger/H10) — Withings BPM Core already reports PR/QRS/QT/QTc via its own certified on-device algorithm (import_withings.py) and is skipped here to avoid two competing values under the same metric name. ECG Logger sessions (separate table schema ecg_logger_sessions/ecg_logger_ecg, see import_ecg_logger.py) are additionally read for delineation — previously entirely unused for anything beyond the app's own RR computation, which already lands directly in ppi_raw.

## Relevance

Enables ECG data analysis, essential for cardiological diagnostics

## Method

R-peaks: Pan-Tompkins 1985 (bandpass filter 5-15 Hz → 5-point derivative → squaring → 150ms moving window integration → peak search with 200ms refractory period). Excluded: poor_recording sessions. PR/QRS delineation: see modules/ ecg_waveform_algorithms.py for method/limits (neurokit2, DWT delineation) — per session, the MEDIAN across all successfully delineated beats is written (one value per recording, mirroring Withings' own one-value-per-recording pattern), not one value per individual beat.

## Thresholds

| Value | Meaning |
|---|---|
| `ok` | Detected HR 30–200 bpm; RR plausibility window 300–2000 ms |
| `suspicious` | poor_recording sessions are skipped |

## Data flow

- **Reads:** `ecg_sessions`, `ecg_samples`, `ecg_logger_sessions`, `ecg_logger_ecg`
- **Writes:**

  ```
  ecg_rpeaks: R-Peak-Indizes pro ECG-Session
  ppi_raw: RR-Intervalle (source device-agnostisch abgeleitet, s. @purpose)
  measurements: ecg_pr_duration_ms, ecg_qrs_duration_ms (Median je Session,
  source_app='ecg_delineation_<quelle>' bzw. 'ecg_delineation_ecg_logger')
  ```

## Limitations

Adaptive threshold simplified: 0.25 × 98th percentile of MWI (robust against outlier artifacts). The original Pan-Tompkins uses an adaptive learning algorithm with running signal/noise peak estimates; this simplification is practical for 30-s segments but may deviate for heavily noisy or artefact-laden signals. 30-second windows (≈30–38 beats) too short for DFA alpha1 (needs ≥100 beats). Tateno-Glass and arrhythmia detection work from n≥3 beats. Not a replacement for clinical ECG; the device's own ECG classification (ecg_sessions.classification, computed per device) remains the primary source for AFES direct evidence. PR/QRS delineation: see modules/ecg_waveform_algorithms.py @limits for the full scope (among others, QT/QTc deliberately not computed — T-wave detection empirically unstable, see there).

## References

- Pan J, Tompkins WJ (1985). A Real-Time QRS Detection Algorithm. IEEE Transactions on Biomedical Engineering, BME-32(3):230-236. doi:10.1109/TBME.1985.325532
- Martinez JP, Almeida R, Olmos S, Rocha AP, Laguna P (2004). A wavelet-based ECG delineator: evaluation on standard databases. IEEE Transactions on Biomedical Engineering, 51(4):570-581. doi:10.1109/TBME.2003.821031
- Makowski D, Pham T, Lau ZJ et al. (2021). NeuroKit2: A Python toolbox for neurophysiological signal processing. Behavior Research Methods, 53(4):1689-1696. doi:10.3758/s13428-020-01516-y

## Usage

```bash
python compute_ecg_rpeaks.py
python compute_ecg_rpeaks.py --recompute
```
