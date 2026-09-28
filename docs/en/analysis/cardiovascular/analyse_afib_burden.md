# AFib-Burden-Analyse — Häufigkeit, Dauer und Trends von Arrhythmie-Episoden

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_afib_burden.py`

**Evidence tier:** calibrated (literature-based + parameters tuned to personal baselines, no external validation)

## Purpose

Analyses frequency, duration and temporal distribution of arrhythmia episodes from Polar PPI data and Apple Watch ECG, plus correlations with barometric pressure, blood pressure, HRV, sleep and stress.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Reads directly from compute-generated arrhythmie_episoden and ecg_sessions; applies CV classification (CV ≥ 10 % = AFib-suspicious, < 10 % = ectopy) from arrhythmia_utils. No independent episode detection in this script.

## Data flow

- **Reads:** `arrhythmie_episoden`, `ecg_sessions`, `biometeo`, `weather_station`, `blood_pressure`, `measurements`, `sessions`, `session_metrics`, `symptoms`
- **Writes:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Limitations

Polar CV detection is not a clinical ECG. CV thresholds are empirical, not formally validated. n=1, no control group, consumer-grade sensors.

## References

- Perez MV, Mahaffey KW, Hedlin H et al. (2019). Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation. New England Journal of Medicine, 381(20):1909-1917. doi:10.1056/NEJMoa1901183
- Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439

## Usage

```bash
python analyse_afib_burden.py
python analyse_afib_burden.py --help
python analyse_afib_burden.py --from 2024-01-01 --to 2024-12-31
```
