# Polar GDPR Export → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_polar.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports data from Polar GDPR exports (JSON files) into health.db. Supports training data, daily activity, 24/7 heart rate, PPI data, fitness assessments, HRV data, sleep details, and orthostatic tests.

## Relevance

Enables import of heart rate and activity data from Polar devices, essential for cardiac analysis

## Method

Reads JSON files from the Polar directory (config: polar_dir). Each file is parsed and data is written to the corresponding tables. Supports multiple Polar devices from the device registry. Mapping: trainings → sessions + session_metrics, daily_activity → measurements, ppi → ppi_raw, nightly_hrv → polar_nightly_hrv, etc. --update/--from/--to now actually filter (every parse function receives date_from/date_to and skips entries outside the window) — previously these flags were pure no-op arguments, every run always reparsed the entire archive (INSERT OR IGNORE just made that invisible, not faster). All files are still opened/parsed to check their embedded date — no filename-based pre-filtering, so no I/O speed gain, only fewer unnecessary DB write attempts. --update derives date_from from the latest already-imported date across sessions/measurements/ppi_raw/polar_nightly_hrv/ polar_sleep_hypnogram/polar_sleep_wake (not just one table — some data types never end up in sessions).

## Data flow

- **Reads:** `{polar_dir}/*.json`, `(Polar`, `GDPR`, `Export)`
- **Writes:**

  ```
  health.db (sessions, session_metrics, measurements, ppi_raw,
  assessments, polar_nightly_hrv, polar_sleep_hypnogram,
  polar_sleep_wake, polar_skin_contact, polar_hrv_spot)
  ```

## Limitations

No validation of Polar data quality. Dependent on the correctness of the GDPR export. No medical interpretation. vo2max comes from physicalInformation.vo2Max — Polar's own daily profile snapshot, not a fresh per-day measurement like Apple/ Garmin. Can repeat the exact same value for months when Polar's algorithm has too little structured training data to compute a new estimate (observed: 2626 values 2017-2026, stuck at exactly 18.0 since late May 2026 — not a Kyoro bug, Polar-side behavior). Do not blend/average uncritically against other devices. --archive moves ALL *.json files in the directory to originals/ — therefore only runs on a full pass (no --update/--from/--to set), otherwise skipped with a notice. Otherwise a file skipped by the date filter and never successfully imported could get archived along with the rest.

## Usage

```bash
python import_polar.py
python import_polar.py --update
python import_polar.py --from 2026-08-01 --to 2026-08-31
python import_polar.py --dir /pfad/zu/polar/daten
```
