# fix_resting_hr_mislabeled_metrics.py — Renames two mislabeled resting-HR

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/fix_resting_hr_mislabeled_metrics.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Two importers wrote values under generic/incorrect metric names that are not, in fact, a daily-measured resting heart rate: (1) import_oura.py imported Oura's readiness.contributors.resting_heart_rate -- a 0-100-scale score, not a bpm value -- mislabeled with unit 'bpm' as 'readiness_hr_resting'; (2) import_polar.py imported Polar's physicalInformation.restingHeartRate -- a rarely-updated profile field for Polar's own HR-zone calculation, not a daily measurement -- under the generic name 'resting_hr', identical to genuine daily measurements from other devices (e.g. Garmin). Both importers are already fixed (new metric names for future imports); this migration brings already-imported databases in line so compute_canonical.build_resting_hr() stops feeding incorrect values into health_canonical.resting_heart_rate.

## Relevance

Prevents two mislabeled wearable fields from continuing to feed into derived tables as genuine resting heart rate -- data quality, not a feature.

## Method

Two targeted UPDATE statements on measurements: (1) metric='readiness_hr_resting' AND source_app='oura_app' -> metric='readiness_contrib_resting_hr', unit=NULL; (2) metric='resting_hr' AND source_app='polar_connect' -> metric='polar_profile_resting_hr' (unit stays 'bpm', it is a genuine bpm value, just not a daily measurement). Garmin's 'resting_hr' rows (source_app='garmin_gdpr') are left untouched -- those are genuine daily measurements. Idempotent: checks row count first, re-running is a no-op.

## Data flow

- **Reads:** `health.db`, `(measurements)`
- **Writes:**

  ```
  health.db (measurements.metric, measurements.unit only --
  no values changed)
  ```

## Limitations

After running, compute_canonical.py and compute_daily_context.py must be re-run so the derived tables reflect the fix -- this migration only changes measurements.

## Usage

```bash
python3 scripts/migrations/fix_resting_hr_mislabeled_metrics.py --dry-run
python3 scripts/migrations/fix_resting_hr_mislabeled_metrics.py
python3 scripts/compute/compute_canonical.py
python3 scripts/compute/compute_daily_context.py
```
