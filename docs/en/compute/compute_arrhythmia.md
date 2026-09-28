# Arrhythmia detection from all available sources.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_arrhythmia.py`

**Evidence tier:** research (peer-reviewed literature basis, but no formal clinical validation study with endpoints)

## Purpose

Detects arrhythmia episodes from multiple sources, annotating each with a confidence level reflecting the quality of the source data.

## Relevance

Enables detection of cardiac arrhythmias, essential for cardiological monitoring

## Method

Source-dependent confidence hierarchy. Devices measure different things: Apple 30 s snapshot ECG (triggered), ECG Logger long-term (1 h+), Polar H10 chest-strap RR (5-min windows), optical PPG (systematically less accurate under arrhythmia). ppi_raw → 5-min windows → ppi_windows → episode aggregation. Additionally: bigeminy detection via RR-interval alternation (short-long-short-long, the timing correlate of a premature beat + compensatory pause) — streamed per device over ppi_raw, segmented on recording gaps, at least 3 consecutive S-L cycles count as an episode (distinguishes sustained bigeminy from isolated extrasystoles). Motivation: a smartphone PPG heart- rhythm scan (FibriCheck, s. import_fibricheck.py) flagged a possible extrasystole/bigeminy episode during sleep — the same pattern recognition now runs continuously over the person's own wearable raw data instead of only at one-off spot checks. FibriCheck reports themselves are additionally ingested as their own expert-panel-reviewed episode source (fibricheck_sessions).

## Thresholds

| Value | Meaning |
|---|---|
| `high` | Apple ECG (FDA, Perez 2019) / ECG Logger (TPR+SampEn single-lead) / FibriCheck with physician review |
| `moderate` | Polar H10/H7 via ppi_raw, TPR AFDB-calibrated (threshold 0.5743, AUC 0.882); bigeminy alternation heuristic on ECG-quality data; FibriCheck without physician review |
| `moderate` | Optical PPG via Dash 2009 (Shannon entropy+CV), not AFDB-validated |
| `low` | Unknown sources (CV heuristic fallback, not validated); bigeminy alternation heuristic on optical PPG |

## Data flow

- **Reads:** `ppi_raw`, `ecg_sessions`, `ecg_logger_sessions`, `fibricheck_sessions`, `devices`, `sessions`, `data/calibration/afdb_thresholds.json`, `(tateno_glass/sampentropy)`, `data/calibration/dash2009_thresholds.json`, `(öffentlicher`, `Datensatz`, `s.`, `calibrate_dash2009_public.py)`, `data/calibration/dash2009_self_thresholds.json`, `(Geräte-Überlappung`, `s.`, `calibrate_dash2009_overlap.py)`
- **Writes:**

  ```
  ppi_windows: 5-min statistics from ppi_raw; column sensor_mode
  ('ecg' | a device_registry sensor_type | NULL) is the effective
  measurement mode used for algorithm routing below, resolved via
  modules/ppi_provenance.py (data-derived, not device-derived — a
  device can have more than one measurement mode, e.g. a watch's
  continuous optical PPG vs. its own occasional ECG lead, both
  landing in ppi_raw under the same device_id)
  arrhythmie_episoden: contiguous abnormal periods; columns
  confidence ('high'|'moderate'|'low'), source (raw-data origin);
  detection_method 'bigeminy_rr_alternation' for the RR-alternation
  episodes, 'premature_beat_rr' for single/clustered premature-beat
  episodes (n_fenster reused as cluster size: 1=isolated, 2=couplet,
  3=triplet, >=3=run — no separate label column), 'fibricheck_
  <result_code>_<version>' for ingested FibriCheck reports
  ```

## Limitations

TPR assumes stationary HR. Training windows (±15 min buffer) are stored with arrhythmie_flag=0 because physical exertion systematically produces false positives. Optical sources are unreliable under arrhythmia; the fallback heuristic is not validated. RMSSD confirmation guard (rmssd >= RMSSD_CONFIRM) is a local addition not present in the original Tateno & Glass 2001 paper — the original uses the TPR threshold alone. This addition increases specificity at the cost of sensitivity; RMSSD_CONFIRM is a heuristic configuration parameter without published validation. External comparison (Mannhart et al. 2023, BASEL Wearable Study): even well-funded, FDA-cleared consumer devices (Apple Watch 6, Samsung Galaxy Watch 3) reach only 85%/75% sensitivity/specificity against a 12-lead ECG reference, with ~25% of recordings inconclusive — the AUC gap between this pipeline's moderate-confidence sources and the tateno_glass chest-strap reference (0.657-0.713 vs. 0.882) is consistent with that general order of magnitude for PPG-based detection, not a pipeline-specific failure. Bigeminy detection: the thresholds (BIGEMINY_ZERO_BAND_BPM, BIGEMINY_MIN_PAIRS, BIGEMINY_ANGLE_SD_MAX_DEG) are the published values from Han et al. 2020 (Sensors 20(19):5683, PPG bigeminy/ trigeminy detection, validated on smartwatch + MIMIC-III pulse- oximetry data, Sp 97%/PPV 81%/NPV 94%/accuracy 92%) — see modules/rr_interval_algorithms.py detect_bigeminy_runs() for the exact scope of replication (the three numeric thresholds yes, the full 9-quadrant Poincare grid and accelerometer-based motion-artifact rejection no). Because Han et al. 2020 validated exclusively on PPG, applying the method to chest-strap ECG RR (also used here, since the method itself is interval-based and device-agnostic) is not separately validated — more precise raw data than PPG, but an unconfirmed, if plausible, transfer. Hence 'moderate', not 'high' confidence for every source modality (see BIGEMINY_CONFIDENCE_BY_MODE), and no physician review of this implementation. Segmenting on gaps >30s can artificially split a genuine alternation run that spans midnight or a brief sensor dropout into two episodes. Single-beat PVC detection (premature_beat_rr): implements Cuesta et al. 2014 (Technology and Health Care 22(4):651-656, doi: 10.3233/THC-140818, prematurity + compensatory pause, MIT-BIH- validated, Se 90.13%/Sp 82.52%, AUC 0.928) — see modules/rr_interval_algorithms.py detect_premature_beats_cuesta() for the exact scope of replication (feature formulas exact, classification via nearest-class-centroid instead of the unpublished LDA coefficients). Complementary to detect_bigeminy_runs — detects single beats/short clusters (couplet/triplet/run), not sustained alternation; the authors themselves name bigeminy couplets as a failure case of their method. Clusters are formed only from immediately consecutive beat indices, not temporal proximity — two isolated PVCs that happen to occur close together in time remain deliberately separate episodes. Only 'ecg'/'chest_strap' sources are run through the detector at all (device-class routing like SENSOR_TYPE_ROUTING, not just a confidence downgrade) — an initial test run against real data showed optical/PPG sources produce a false-positive explosion (>99% of all findings came from 3 optical devices, chest-strap ECG produced a plausible order of magnitude). A synthetic test confirms the cause: classification turns measurably false- positive above roughly 50ms of beat-to-beat noise (SD) — PPG raw data routinely exceeds that under real-world conditions, chest-strap ECG practically never does. Consistent with Cuesta et al.'s own validation scope (MIT-BIH/ECG only). FibriCheck episodes: assumes a fixed 60-s duration (no beat-level statistics available in the report), result_code mapping only covers previously seen phrasings (s. import_fibricheck.py @limits).

## References

- Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439
- Dash S, Chon KH, Lu S, Raeder EA (2009). Automatic Real Time Detection of Atrial Fibrillation. Annals of Biomedical Engineering, 37(9):1701-1709. doi:10.1007/s10439-009-9740-z
- Perez MV, Mahaffey KW, Hedlin H et al. (2019). Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation. New England Journal of Medicine, 381(20):1909-1917. doi:10.1056/NEJMoa1901183
- Mannhart D, Lischer M, Knecht S et al. (2023). Clinical Validation of 5 Direct-to-Consumer Wearable Smart Devices to Detect Atrial Fibrillation: BASEL Wearable Study. JACC Clinical Electrophysiology, 9(2):232-242. doi:10.1016/j.jacep.2022.09.011
- Cuesta P, Lado MJ, Vila XA, Alonso R (2014). Detection of premature ventricular contractions using the RR-interval signal: a simple algorithm for mobile devices. Technology and Health Care, 22(4):651-656. doi:10.3233/THC-140818
- Han D, Bashar SK, Mohagheghian F et al. (2020). Premature Atrial and Ventricular Contraction Detection using Photoplethysmographic Data from a Smartwatch. Sensors (Basel), 20(19):5683. doi:10.3390/s20195683

## Usage

```bash
python compute_arrhythmia.py
python compute_arrhythmia.py --person PER-XXXXXXXX
```
