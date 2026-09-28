# Dash 2009 Selbst-Kalibrierung aus Geräte-Überlappungsfenstern

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/calibration/calibrate_dash2009_overlap.py`

**Evidence tier:** calibrated (literature-based + parameters tuned to personal baselines, no external validation)

## Purpose

Calibrates the Dash 2009 thresholds (Shannon entropy, CV_RR) from time windows where a validated source (Polar H10/H7 chest strap, tateno_glass algorithm) AND an optical wrist source (Vantage V3/ Loop Gen 2/Ignite 2) both delivered data simultaneously — a person-specific alternative/addition to the public-dataset calibration (calibrate_dash2009_public.py).

## Relevance

Enables calibration of algorithms and thresholds, essential for data quality

## Method

Finds 5-min windows with ppi_raw data from both device groups simultaneously (genuine parallel wear). Devices are classified via modules/device_registry.sensor_type(device_id) (chest_strap vs. optical_wrist_gps) — NOT by comparing the raw device column against a fixed set of semantic names like "polar_vantage" (ppi_raw.device holds the pseudonymized device_id, e.g. "DEV-394bbcad", never a semantic string; an earlier set-comparison therefore NEVER matched, regardless of actual parallel wear time present — 0 windows was a bug, not missing data, see @limits). Uses the validated source's tateno_glass flag as pseudo-ground-truth (NOT a clinical diagnosis!) and searches via ROC/Youden's J for the Dash 2009 threshold that best agrees with this reference.

## Data flow

- **Reads:** `ppi_raw`
- **Writes:** `data/calibration/dash2009_self_thresholds.json`

## Limitations

Pseudo-ground-truth, not a clinical diagnosis — tateno_glass itself is only AFDB-calibrated, not perfect. n=1 (single person), sample size depends on actual parallel wear time and may be small/zero. Without real AFib episodes in the overlap windows, this script essentially only calibrates the false-positive rate on normal rhythm, not sensitivity to genuine atrial fibrillation. Device classification via sensor_type comes from the registry configuration — a device without a (correct) sensor_type entry silently contributes to neither bucket (validated or optical) rather than raising an error.

## References

- Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439
- Dash S, Chon KH, Lu S, Raeder EA (2009). Automatic Real Time Detection of Atrial Fibrillation. Annals of Biomedical Engineering, 37(9):1701-1709. doi:10.1007/s10439-009-9740-z

## Usage

```bash
python3 scripts/calibration/calibrate_dash2009_overlap.py
python3 scripts/calibration/calibrate_dash2009_overlap.py --person max
```
