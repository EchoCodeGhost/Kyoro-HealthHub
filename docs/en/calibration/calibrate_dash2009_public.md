# Dash 2009 Schwellenwert-Kalibrierung gegen öffentlichen Wrist-PPG-AFib-Datensatz

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/calibration/calibrate_dash2009_public.py`

**Evidence tier:** calibrated (literature-based + parameters tuned to personal baselines, no external validation)

## Purpose

Calibrates the Dash 2009 thresholds (Shannon entropy, CV_RR) for optical wrist-PPG sources (Polar Vantage V3/Loop Gen 2/Ignite 2) against a real, clinically annotated wrist-PPG AFib dataset — unlike MIT-BIH AFDB (ECG only, no PPG, see calibrate_afib_thresholds.py) this is signal-type appropriate for Dash 2009.

## Relevance

Enables calibration of algorithms and thresholds, essential for data quality

## Method

Reads MAT v7.3/HDF5 files from data/calibration/zenodo_afib_ppg/extracted/ (see download_ppg_afib_zenodo.py) via h5py — scipy.io.loadmat doesn't support v7.3 (verified via --inspect). Per subject (01–08) there is ONE continuous ECG reference recording (<subject>_ECG_01.mat: 500Hz raw signal, beat-indexed QRSindex + rr + AF_annotation) and several shorter, time-shifted wrist PPG recordings (<subject>_PPG_NN.mat: 100Hz PPG_GREEN, its OWN recording_starttime/-startday, NO AFib annotation of its own). AFib labeling for PPG beats therefore does NOT come from the PPG file itself but via time alignment: PPG segment start time minus ECG reference start time (from recording_starttime, ASCII "HH:MM:SS", plus day-of-month from recording_startday — no full date in the source, see @limits) gives an offset in seconds relative to ECG start; each PPG-detected beat time is projected onto the ECG timeline via that offset and labeled with the AF_annotation value of the nearest preceding QRSindex beat (searchsorted). PPG peaks are extracted from PPG_GREEN via a bandpass (0.5–5Hz pulse-wave band) plus peak detection with a BLOCK-WISE (30s) adaptive prominence threshold — a single global threshold fails because wrist PPG shows massive local amplitude swings from motion artifact (empirically: blocks within the same file ranged from SD~4000 to SD~285000 ADC units). Additionally, a motion gate: the same files also carry Accelerometer_X/Y/Z — blocks whose acceleration- magnitude SD falls in the most motion-heavy ACCEL_QUANTILE_CUT (75th percentile) of THAT file are excluded from peak search entirely instead of still yielding noisy peaks. RR intervals that would bridge an excluded gap are dropped (block-index continuity check). The remaining RR sequence then also passes through the local-median outlier filter from modules/rr_interval_algorithms.filter_beat_artifacts (the same function originally built for compute_orthostatic_detection.py) — catches individual mis-detected peaks that occur even within an otherwise "good" block. RR intervals → 5-min windows → Shannon entropy (shannon_entropy_rr) + CV_RR per window → ROC/Youden's J. Same sliding-window and ROC pattern as calibrate_afib_thresholds.py.

## Data flow

- **Reads:** `data/calibration/zenodo_afib_ppg/extracted/*.mat`
- **Writes:**

  ```
  data/calibration/dash2009_thresholds.json,
  data/calibration/dash2009_public_calibration.csv
  ```

## Limitations

Time alignment between PPG segment and ECG reference relies on day-of-month WITHOUT month/year (source files carry no full date) — a month rollover within a subject's recording span is detected heuristically (day difference >20 → assumed wraparound) but can be off by ±1 day; affects only subjects whose recording starts very close to a month boundary. PPG peak detection is an own, not clinically validated bandpass+prominence heuristic, not a reference algorithm — wrist PPG is inherently more motion-artifact-prone than chest-strap ECG, some detected "beats" are likely artifacts (only a coarse RR-range plausibility filter, 200–3000ms, plus the motion gate + local outlier filter, see @method, is applied). The resulting AUC therefore reflects both the quality of the Dash 2009 thresholds AND the quality of this own peak detection — the two cannot be evaluated separately. The motion gate excludes the most motion-heavy portions of each file entirely — if this person's AFib episodes systematically occur during rest OR systematically during activity (unknown, not checked), the gate could introduce a class selection bias rather than only removing noise; not quantified. Dataset license: "Other (Non-Commercial)" — non-commercial calibration use only, raw data stays untracked (.gitignore).

## References

- Dash S, Chon KH, Lu S, Raeder EA (2009). Automatic Real Time Detection of Atrial Fibrillation. Annals of Biomedical Engineering, 37(9):1701-1709. doi:10.1007/s10439-009-9740-z
- Bacevičius J, Abramikas Ž, Badaras I et al. (2022). Long-term electrocardiogram and wrist-based photoplethysmogram recordings with annotated atrial fibrillation episodes [Data set]. Zenodo. doi:10.5281/zenodo.5815074 (dataset: 8 subjects, one continuous multi-day ECG reference + several wrist-PPG segments per subject, beat-to-beat AFib annotation on the ECG)

## Usage

```bash
python3 scripts/calibration/download_ppg_afib_zenodo.py   # once, ~7 GB
python3 scripts/calibration/calibrate_dash2009_public.py --inspect <file.mat>
python3 scripts/calibration/calibrate_dash2009_public.py
```
