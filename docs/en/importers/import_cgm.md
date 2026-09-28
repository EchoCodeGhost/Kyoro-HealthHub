# Freestyle Libre 3 (via Apple Health) → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_cgm.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports Continuous Glucose Monitoring (CGM) data from Freestyle Libre 3 (via Apple Health) into health.db. Supports both continuous sensor measurements and manual blood glucose measurements.

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads data from Apple Health export.xml. FLwatch (Freestyle Libre 3) → cgm_readings (5-minute interval), HealthManager Pro (Beurer GL60) → blood_glucose (manual fingerstick measurements). Calibration function shows deviations between CGM and manual measurements within ±15 minutes.

## Data flow

- **Reads:** `{apple_xml}`, `(Apple`, `Health`, `Export)`
- **Writes:** `health.db (cgm_readings, blood_glucose)`

## Limitations

No validation of CGM data quality. Calibration is optional and for analysis only. No medical evaluation from CGM data. Raw data (flwatch_raw) is interstitial Libre readings, systematically lower than fingerstick reference — uncalibrated hypo rates from it are not clinically reliable (own observation: a markedly elevated "hypo" rate on raw data compared to fingerstick reference readings <70 mg/dl in the same period, where not a single reference reading confirmed a hypo). calibrate() only writes a correction function once n≥10 GL60/CGM pairs exist AND the fitted slope is physiologically plausible (0.5–2.0) — at n=3-4 the 2-parameter regression almost always overfits to noise (own observation: a markedly too-flat slope at a small sample size, which would have effectively discarded the raw signal).

## Usage

```bash
python3 import_cgm.py             # vollständiger Import
python3 import_cgm.py --update    # nur neue Einträge ergänzen
python3 import_cgm.py --calibrate # nur Kalibrierungsauswertung (kein Import)
```
