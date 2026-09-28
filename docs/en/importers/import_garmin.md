# Garmin Connect → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_garmin.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports data from Garmin Connect into health.db. Supports sleep, heart rate, HRV, stress, body battery, SpO2, respiration, and daily summaries.

## Relevance

Enables import of health and activity data from Garmin devices, essential for comprehensive wearable data analysis

## Method

Reads Garmin data from files created by garmin_download.py. Sleep → sessions + session_metrics, heart rate/HRV/stress → measurements, daily data → measurements, activities (via import_activities) → sessions + session_metrics including training_load (from Garmin's own aerobic/anaerobic Training Effect, heart-rate-based), except for generic 'other' activities or when another source already covers/rejected the same time window (see claim_training_load_slot, modules/base.py). Configuration via ~/.config/kyoro/garmin_config.json (shared with garmin_download.py).

## Data flow

- **Reads:** `Garmin-Exportdateien`, `(JSON/CSV)`
- **Writes:** `health.db (sessions, session_metrics, measurements)`

## Limitations

No validation of Garmin data quality. Dependent on the correctness of the Garmin export. No medical interpretation. training_load for activities is a rough approximation derived from the training effect value (see GARMIN_TRAINING_LOAD_EFFECT_FACTOR), not directly comparable to Polar's training_load, intended only as an equivalent trigger signal.

## Usage

```bash
python3 import_garmin.py               # from 2024-01-01
python3 import_garmin.py --update      # only new data
python3 import_garmin.py --from 2025-01-01 --to 2025-12-31
python3 import_garmin.py --from 2026-05-01 --only sleep,bb,steps
```
