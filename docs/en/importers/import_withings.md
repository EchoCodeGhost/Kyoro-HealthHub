# Withings Health Mate GDPR-Export → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_withings.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports blood pressure, weight/body composition, height, manually logged SpO2, ECG waveforms with AFib/valvular/interval findings, and menstrual/ovulation data from the Withings Health Mate data export (GDPR request, ZIP with many individual CSVs) into health.db. Only covers data that can plausibly originate from the BPM Core, a Withings scale, or manual app entry — sleep.csv, activities.csv, and all raw_* sensor time series are deliberately excluded (likely Apple Watch data via the Apple Health pairing, see import_apple.py).

## Relevance

Closes the known gap in Withings blood pressure import and adds weight, ECG, and cycle data from a previously unused source

## Method

Reads the needed CSV members directly from the ZIP (no on-disk extraction, avoids an extra PII copy). Blood pressure goes to blood_pressure, weight/height/SpO2 as EAV rows to measurements, ECG waveforms (signal.csv) to ecg_sessions + ecg_samples, AFib/valvular/interval findings plus menstrual/ovulation data (both from other.csv) as EAV rows to measurements — using the same metric names as import_polar.py so cross-source analysis works. Three device slugs separate physical origin (BPM Core/scale/unclear, see @writes and plan section 1). account.csv/user.csv/devices.csv (plain-text PII: name, email, MAC address, device pairing location) are not read.

## Data flow

- **Reads:** `keine`, `(schreibt`, `in`, `bereits`, `bestehende`, `Tabellen)`
- **Writes:**

  ```
  blood_pressure: ts TEXT, date TEXT, systolic INTEGER, diastolic INTEGER, pulse INTEGER, notes TEXT, person TEXT, source TEXT
  measurements: ts TEXT, date TEXT, metric TEXT, value REAL, unit TEXT, device_id TEXT, person TEXT, source_app TEXT
  ecg_sessions: datetime TEXT, classification TEXT, symptoms TEXT, sample_rate_hz INTEGER, lead TEXT, duration_s REAL, device_id TEXT, person TEXT, source TEXT
  ecg_samples: session_dt TEXT, session_person TEXT, sample_index INTEGER, uv REAL
  blood_glucose: ts TEXT, date TEXT, glucose_mgdl REAL, device_id TEXT, person TEXT, source TEXT
  ```

## Limitations

Deliberately does not import: sleep.csv, activities.csv, and all 44 raw_* sensor time series (likely Apple Watch data, belongs to import_apple.py with a fresh Apple Health export, see plan section 1) nor the daily aggregates_*.csv rollups of the same source. AFib/valvular/interval codes from other.csv are Withings' own raw codes without medical interpretation in the importer, only loosely correlated to ecg_sessions via matching timestamp (no FK). Provenance of the single blood glucose row is unclear (no known Withings CGM device).

## Usage

```bash
python3 import_withings.py
python3 import_withings.py --file imports/withings/data_SAN_1788375097.zip
python3 import_withings.py --update
python3 import_withings.py --inbox
```
