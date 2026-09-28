# CGM-Glukose-Analyse — Freestyle Libre 3 Continuous Glucose Monitor

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/metabolic/analyse_cgm_glucose.py`

**Evidence tier:** validated (clinical validation study exists: sensitivity/specificity or endpoints prospectively established)

## Purpose

Analyses continuous glucose monitoring data (Freestyle Libre 3): time in range, glucose variability, daily rhythm and associations with activity and HRV.

## Relevance

Enables metabolic analysis, essential for metabolic health

## Method

TIR/TAR/TBR per ATTD consensus 2019: target range 3.9–10.0 mmol/L; CV target < 36 % (stable glucose). Pre-diabetes thresholds: fasting 5.6 mmol/L, post-prandial 7.8 mmol/L.

## Data flow

- **Reads:** `cgm_readings`, `blood_glucose`, `sessions`, `measurements`, `(hrv_rmssd/rmssd_ms)`
- **Writes:** `analyses/metabolic/*.{md,png} (kein DB-Write)`

## Limitations

CGM sensors have a measurement uncertainty of ±10–15 %. Calibration and sensor warm-up periods are not separately filtered. n=1, no RCT design.

## References

- Battelino T, Danne T, Bergenstal RM et al. (2019). Clinical Targets for Continuous Glucose Monitoring Data Interpretation: Recommendations From the International Consensus on Time in Range. Diabetes Care, 42(8):1593-1603. doi:10.2337/dci19-0028

## Usage

```bash
python analyse_cgm_glucose.py
python analyse_cgm_glucose.py --help
python analyse_cgm_glucose.py --from 2024-01-01 --to 2024-12-31
```
