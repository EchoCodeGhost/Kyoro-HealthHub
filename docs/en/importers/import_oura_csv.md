# Oura Ring CSV-Export → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_oura_csv.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports data from Oura Ring CSV exports (data.zip) as a supplement to the API. Provides more granular raw data and additional metrics not available through the official API.

## Relevance

Enables import of sleep and recovery data from Oura rings, essential for sleep analysis

## Method

Reads the data.zip file from imports/oura/ or an explicit path. Imports: cycle data (phases, fertility), day tags, raw data (temperature, daytime stress, sleep model), metrics (VO2max, workouts, contraception, OMSS score), and location stays. Workouts are additionally mirrored (filtered by activity type, see mirror_workouts_to_sessions) into sessions/session_metrics so they can feed training-load-based triggers (compute_pem.py) the same way Polar trainings do — oura_workouts itself remains the complete, unfiltered raw record.

## Data flow

- **Reads:** `{imports/oura/}/data.zip`, `(Oura`, `CSV`, `Export)`
- **Writes:**

  ```
  health.db (oura_cycle_insights, oura_period_starts,
  oura_cycle_predictions, oura_tags, oura_temperature_raw,
  oura_daytime_stress, oura_sleep_model, oura_vo2max, oura_workouts,
  oura_contraception, oura_survey, location_stays, sessions,
  session_metrics, ...)
  ```

## Limitations

Supplements API data, does not replace it. Some tables are only created if data is present. No medical interpretation. training_load for mirrored Oura workouts is a rough calorie-based approximation (see OURA_TRAINING_LOAD_CAL_FACTOR), not heart-rate-based like Polar's/Garmin's — usable as a trigger signal only, not as an exactly comparable training load. Oura has the lowest priority tier of all sources (see TRAINING_LOAD_SOURCE_PRIORITY, modules/base.py) — on overlap with Polar or Garmin, Oura loses its training_load regardless of import order, even if the other source is imported later.

## Usage

```bash
python import_oura_csv.py                        # neueste data.zip in imports/oura/
python import_oura_csv.py --file /pfad/data.zip  # expliziter Path
python import_oura_csv.py --rebuild              # Tables leeren + neu aufbauen
```
