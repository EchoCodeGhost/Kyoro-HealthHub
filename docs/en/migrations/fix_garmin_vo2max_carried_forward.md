# fix_garmin_vo2max_carried_forward.py — Separates carried-forward Garmin

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/fix_garmin_vo2max_carried_forward.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

import_garmin.py wrote mostRecentVO2Max (the most recently determined estimate) daily under the fetch date. Every day without a new estimate therefore looked like a measurement of its own: an unchanged value looked like a dense series, and rows from later fetch days carried a date on which Garmin determined nothing. The importer is fixed (date from calendarDate); this migration brings existing databases in line.

## Relevance

Prevents derived VO2max trends from counting carried-forward values as new measurements — data quality.

## Method

Per person and device, rows with metric='vo2max', source_app='garmin_connect' are sorted by date. The first row of each run of identical values stays 'vo2max' (earliest day the value was visible); all later rows of the same run are renamed to 'vo2max_carried_forward'. No values changed, no rows deleted. Runs once: an existing import_log entry of this migration ends any further run without changes.

## Data flow

- **Reads:** `health.db`, `(measurements)`
- **Writes:** `health.db (measurements.metric only)`

## Limitations

The remaining row's date is an upper bound: Garmin may have determined the value before the first fetch day. A new estimate equal to the previous value cannot be distinguished from a carry-forward and is treated as one. The Garmin data export (garmin_gdpr, biometricVo2Max) is a different estimate and is left untouched.

## Usage

```bash
python3 scripts/migrations/fix_garmin_vo2max_carried_forward.py --dry-run
python3 scripts/migrations/fix_garmin_vo2max_carried_forward.py
```
