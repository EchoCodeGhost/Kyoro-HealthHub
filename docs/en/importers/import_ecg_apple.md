# Apple Watch ECG CSV → health.db (ecg_sessions + ecg_samples)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_ecg_apple.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports Apple Watch ECG data

## Relevance

Enables import of health data from Apple Health, essential for integration of iOS health data

## Method

Imports ECG CSV files from Apple Health Export (subfolder electrocardiograms/) into two tables: - ecg_sessions: metadata (date, classification, lead, duration) - ecg_samples: raw data (uV values at 512 Hz, lead I) File format: key/value metadata, separator line, unit line, measurement points as German decimal comma.

## Data flow

- **Reads:** `Apple`, `Health`, `Export`, `CSV-Dateien`
- **Writes:** `ecg_sessions, ecg_samples`

## Limitations

Only Apple Watch ECG files. Dependent on export format.

## Usage

```bash
python3 import_ecg_apple.py --dir imports/apple_health/electrocardiograms/
python3 import_ecg_apple.py --dry-run --no-samples
```
