# CameraHRV → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_camerahRV.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports CSV exports from CameraHRV app

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Imports CSV exports from CameraHRV app (iOS). File routing: All_Features*.csv → camera_hrv_resting (HRV session aggregates) + measurements (hrv_rmssd, heart_rate, breathing_rate) All_RR*.csv → ppi_raw (beat-to-beat RR intervals, ms precision) All_HR*.csv → measurements (per-second heart_rate time series, UTC timestamps) Standard export → camera_hrv_resting

## Data flow

- **Reads:** `CSV-Dateien`, `aus`, `imports/camerahRV/`
- **Writes:** `camera_hrv_resting, measurements, ppi_raw`

## Limitations

Dependent on CameraHRV app export format. --person used to be declared in run() but unused (all write paths hardcoded to OWN_PERSON_ID) and absent from main() entirely — now threaded through to all three write functions in both paths. lf_power/hf_power: unit is app-version-dependent, carried over unchanged from the source. Verified against a real All_Features.csv export: LF/HF carry no unit label in the header at all, and the values are arithmetically normalised proportions (their ratio equals the reported LF/HF column exactly), not absolute ms² power as the column names/template previously claimed. Other app versions might genuinely export ms² -- without a unit label in the source this can't be told apart, so the column name deliberately no longer claims one.

## Usage

```bash
python import_camerahRV.py                    # scannt imports/camerahRV/ (Default)
python import_camerahRV.py --file export.csv
python import_camerahRV.py --dir ~/Downloads/camerahRV/
python import_camerahRV.py --template         # zeigt erwartetes CSV-Format
python import_camerahRV.py --dry-run
python import_camerahRV.py --file export.csv --person PER-xxxxxxxx
```
