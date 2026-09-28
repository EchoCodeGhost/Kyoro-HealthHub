# bp_norms.py — Einheitliche Blutdruck-Einstufung nach ESC/ESH

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/bp_norms.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides ONE shared, cited classification of office/home blood pressure and prevents a severity grade from being derived from too few or non-standardised measurements.

## Relevance

A blood-pressure classification is a consequential statement. Producing it from a single reading or with shifted thresholds creates either false worry or false reassurance.

## Method

Pure lookup logic, no computation. Thresholds per ESC/ESH (office measurement): optimal <120, normal 120-129, high-normal 130-139, grade 1 140-159, grade 2 160-179, grade 3 from 180 systolic; a diastolic value from 90 also raises to grade 1. For home self-measurement the lower threshold 135/85 applies. In addition a minimum count: below it NO grade is assigned, the value is reported as a single finding instead. Two scripts in this project previously carried thresholds shifted against each other (one classified from 140 as "grade 2") and assigned a grade even for a single reading.

## Data flow

- **Reads:** `keine`
- **Writes:** `keine`

## Limitations

The classification does not replace a medical assessment — it assumes standardised conditions (rest, no caffeine/nicotine beforehand, correct cuff, mean of several readings on several days). This module does not know whether those conditions were met — callers should also report documented confounders from the data source.

## References

- Williams B, Mancia G, Spiering W et al. (2018). 2018 ESC/ESH Guidelines for the management of arterial hypertension. European Heart Journal 39(33):3021-3104. doi:10.1093/eurheartj/ehy339

## Usage

```bash
from modules.bp_norms import classify, MIN_READINGS_FOR_GRADE
classify(142.0, 89.0, n_readings=1)
# -> ("Einzelmessung, keine Einstufung", False)
classify(142.0, 89.0, n_readings=12)
# -> ("Grad 1 Hypertonie", True)
```
