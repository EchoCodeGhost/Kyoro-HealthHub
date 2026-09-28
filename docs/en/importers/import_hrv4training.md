# HRV4Workout → health.db (hrv4training_daily)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_hrv4training.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports HRV4Workout CSV exports

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Imports the CSV export from the HRV4Workout app into hrv4training_daily. Export path in app: Profiles -> Export -> "Export CSV". Typical columns: Date, HRV4T, Morning Readiness, RMSSD, HR, day, Comment, + any context variables (Sleep, Fatigue, etc.).

## Data flow

- **Reads:** `HRV4Workout`, `CSV-Dateien`
- **Writes:** `hrv4training_daily`

## Limitations

Dependent on app version and export format.

## Usage

```bash
python import_hrv4training.py --file export.csv
python import_hrv4training.py --dir ~/Downloads/
python import_hrv4training.py --file export.csv --dry-run
```
