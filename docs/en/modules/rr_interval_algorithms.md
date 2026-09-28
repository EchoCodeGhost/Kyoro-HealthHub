# rr_interval_algorithms.py — Gemeinsame RR-Intervall-Algorithmen (HRV-Metriken

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/rr_interval_algorithms.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides pure mathematical algorithms on RR/pulse-interval sequences without DB access or config — both classic HRV dispersion metrics (TPR, SampEn, Shannon entropy) and beat-level rhythm classification (bigeminy-run detection, single-PVC detection), which are not variability metrics themselves but share the same input type (interval sequence) and the same DB-/config-free architecture. Importable from various analysis scripts.

## Relevance

Provides RR-interval algorithms (HRV + rhythm classification), essential for autonomic health monitoring

## Method

HRV metrics: turning_point_ratio (local extrema ratio, TPR / Tateno & Glass), sample_entropy (SampEn per Kubios standard), shannon_entropy_rr (normalized Shannon entropy). AFib detection: detect_tateno_glass (ECG/chest strap), detect_sampentropy (optical sensors), detect_dash2009 (PPG). Helper: filter_beat_artifacts (local-median outlier filtering for individual pulse intervals — see the function's own docstring for provenance: originally developed in compute_orthostatic_detection.py, moved here after the same boundary-clipping artifact [a device/import floor value affecting very short pulse_ms values] was also found in analyse_ecg_24h.py). Beat-level rhythm classification (not an HRV dispersion metric, but classification of individual beat transitions/beats): classify_beat_pattern (per-beat-transition short/normal/long classification via instantaneous heart-rate difference, 5-BPM zero-quadrant threshold per Han et al. 2020), detect_bigeminy_runs (detects sustained short-long alternation as the RR correlate of bigeminy — published thresholds: min. 5 S-L pairs, vector-angle standard deviation <= 10 degrees), compute_prematurity_features/ detect_premature_beats_cuesta (per-beat prematurity/compensatory pause and classification per Cuesta et al. 2014 — detects isolated premature beats, complementary to detect_bigeminy_runs, see the functions' own docstrings and @limits below for the exact scope of replication).

## Data flow

- **Reads:** `Keine`, `Tabellen`, `(reine`, `Mathematik)`
- **Writes:** `Keine Tabellen (gibt Berechnungsergebnisse zurück)`

## Limitations

Pure mathematics without clinical validation. No diagnostic function. detect_bigeminy_runs/classify_beat_pattern: the three published numeric thresholds from Han et al. 2020 (5-BPM zero-quadrant, min. 5 S-L pairs, vector-angle SD <= 10 degrees) are replicated — NOT replicated is their full 9-quadrant Poincare grid (only full-text access available, not the original figure with the exact quadrant numbering), their AF/NSR pre-classification step (in Han et al. the method is only applied to segments already classified as AF or NSR), or their accelerometer-based motion- artifact rejection. The original method was validated on smartwatch PPG (Samsung Simband/Gear S3) and MIMIC-III pulse- oximetry PPG — not on Polar H10/H7 chest-strap ECG-derived RR, which is additionally used here; extrapolating to ECG-quality RR is plausible (RR precision there is higher than PPG) but not itself separately validated. detect_premature_beats_cuesta/compute_prematurity_features: the feature formulas (prematurity/compensatory pause, 10-beat window) are replicated exactly per Cuesta et al. 2014 (section 2.2.1). NOT replicated is the actually trained LDA decision boundary — the paper only publishes the empirical class means (normal: -0.048/-0.027, PVC: 0.265/0.203), not the LDA coefficients or covariance matrix. The nearest-class-centroid classification used here is the correct reduction of an LDA under the assumption of equal/isotropic covariance between classes — a documented approximation using the only actually published numbers, not the byte-exact original decision boundary. The original also averages over the 10 preceding beats already ANNOTATED as normal (ground truth available in MIT-BIH); here the 10 immediately preceding beats are averaged regardless of their classification, since no ground-truth labels are available online. The authors themselves state the method fails for sustained patterns such as bigeminy couplets — it is complementary to detect_bigeminy_runs (single-beat vs. run detection), not a replacement for it.

## References

- Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439
- Han D, Bashar SK, Mohagheghian F et al. (2020). Premature Atrial and Ventricular Contraction Detection using Photoplethysmographic Data from a Smartwatch. Sensors (Basel), 20(19):5683. doi:10.3390/s20195683
- Cuesta P, Lado MJ, Vila XA, Alonso R (2014). Detection of premature ventricular contractions using the RR-interval signal: a simple algorithm for mobile devices. Technology and Health Care, 22(4):651-656. doi:10.3233/THC-140818

## Usage

```bash
from modules.rr_interval_algorithms import turning_point_ratio, detect_bigeminy_runs
from modules.rr_interval_algorithms import detect_premature_beats_cuesta
```
