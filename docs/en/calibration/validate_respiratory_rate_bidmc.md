# Atemfrequenz-Schätzer-Validierung gegen BIDMC-Ground-Truth

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/calibration/validate_respiratory_rate_bidmc.py`

**Evidence tier:** calibrated (literature-based + parameters tuned to personal baselines, no external validation)

## Purpose

Validates the RSA-based respiratory rate estimation logic from mobile/KyoroPolarApp/.../RespiratoryRateEstimator.kt (reimplemented in Python here) against real respiratory rate ground truth from the BIDMC dataset (BACK-26, local feature backlog).

## Relevance

Enables algorithm validation, essential for quality assurance

## Method

Downloads bidmc_XX_Signals.csv (PLETH waveform, 125 Hz) and bidmc_XX_Numerics.csv (RESP ground truth in breaths/min, 1 Hz) in CSV format (not the binary WFDB .breath annotation format — much simpler to parse, and the README explicitly recommends CSV for direct use). Peak detection on PLETH yields pulse-to-pulse intervals (substitute for a real PPI stream). The same detrend+ smoothing+peak-counting logic as RespiratoryRateEstimator.kt is reimplemented here in Python and compared against the real RESP column over 30-second windows (MAE).

## Data flow

- **Reads:** `PhysioNet`, `bidmc_csv/`, `files`, `(online`, `cached`, `in`, `data/calibration/bidmc_csv/`, `after`, `first`, `run)`
- **Writes:** `data/calibration/bidmc_csv/ (raw CSVs), stdout summary`

## Limitations

Pulse-to-pulse intervals here come from PPG peak detection on a clean ICU monitor recording (125 Hz, low noise) — on a real wrist-worn PPG (Polar Loop Gen 2/Polar 360, ~22-100 Hz, motion artifacts) accuracy is likely worse than measured here. This validation shows an upper bound, not a guarantee for the Kotlin implementation in everyday use.

## References

- Pimentel MAF, Johnson AEW, Charlton PH et al. (2017). Toward a Robust Estimation of Respiratory Rate From Pulse Oximeters. IEEE Transactions on Biomedical Engineering, 64(8):1914-1923. doi:10.1109/TBME.2016.2613124

## Usage

```bash
python3 scripts/calibration/validate_respiratory_rate_bidmc.py
python3 scripts/calibration/validate_respiratory_rate_bidmc.py --records bidmc01,bidmc02
python3 scripts/calibration/validate_respiratory_rate_bidmc.py --limit 10
```
