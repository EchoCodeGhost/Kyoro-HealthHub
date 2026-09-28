# Oura Ring API → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_oura.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports data from Oura Ring 4 via the official API into health.db. Supports sleep, sleep readiness, activity, SpO2, HRV, stress, cardiovascular metrics, continuous heart rate, workouts (incl. auto-detected everyday activity like 'houseWork'), and user tags (symptoms/context).

## Relevance

Enables import of sleep and recovery data from Oura rings, essential for sleep analysis

## Method

Fetches data from the Oura Cloud API. daily_sleep → sessions + session_metrics, sleep → sessions (corrected timestamps) + measurements (HRV RMSSD time series), other daily-* data → measurements. Workout/ enhanced_tag → oura_workouts/oura_tags/user_context — same target tables as import_oura_csv.py (GDPR export), INSERT OR IGNORE deduplicates between both import paths. HRV time series are stored as metric='hrv_rmssd'.

## Data flow

- **Reads:** `Oura`, `Cloud`, `API`, `(https://cloud.ouraring.com)`
- **Writes:**

  ```
  health.db (sessions, session_metrics, measurements, oura_workouts,
  oura_tags, user_context)
  ```

## Limitations

Dependent on the availability of the Oura API and the quality of returned data. No medical interpretation.

## Usage

```bash
python import_oura.py --setup
python import_oura.py             # Vollimport (ab 2024-01-01)
python import_oura.py --update    # Nur neue Daten
python import_oura.py --from 2024-06-01 --to 2024-12-31
python import_oura.py --no-hr     # Ohne kontinuierliche HR
```
