# KubiosHRV Orthostatic-Import

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_kubios_orthostatic.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports KubiosHRV orthostatic export files

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads KubiosHRV export files and imports into v2: sessions (type='orthostatic') + session_metrics. Supported formats: 1. KubiosHRV Standard TXT report (Desktop software, Windows/Mac) 2. Manual CSV (template: --template) Data sources: kubios_polar_h10 - Kubios + Polar H10 chest strap (most accurate HRV) kubios_ble_hrm - Kubios + any BLE/ANT+ chest strap kubios_camera - Kubios Mobile App with camera PPG (lower accuracy) Note: hr_delta = hr_stand - hr_supine may underestimate POTS.

## Data flow

- **Reads:** `KubiosHRV`, `TXT/CSV-Dateien`
- **Writes:** `sessions, session_metrics`

## Limitations

Segment analysis may underestimate peak HR.

## Usage

```bash
python import_kubios_orthostatic.py               # scannt imports/kubios/ (Default)
python import_kubios_orthostatic.py --file export.txt
python import_kubios_orthostatic.py --dir ~/Downloads/kubios/
python import_kubios_orthostatic.py --csv messung.csv
python import_kubios_orthostatic.py --template
python import_kubios_orthostatic.py --manual
```
