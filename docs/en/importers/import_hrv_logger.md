# HRV Logger (A.S.M.A. B.V. / Marco Altini) → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_hrv_logger.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports RR interval sessions from HRV Logger exports into health.db. The RR data is stored in ppi_raw (source='hrv_logger') and is thus available to all HRV calculations (compute_hrv_advanced.py).

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Supported formats: HRV Logger CSV (Time(ms), RR(ms)) — standard export, simple list (one RR value per line in ms), Kubios-compatible (.hrm/.txt with RR values). Session metadata is stored in hrv_logger_sessions.

## Data flow

- **Reads:** `HRV`, `Logger`, `Export`, `(CSV/TXT/HRM`, `Polar`, `H7/H10`, `etc.)`
- **Writes:** `health.db (ppi_raw, hrv_logger_sessions)`

## Limitations

No validation of HRV data quality. No automatic interpretation of HRV data. No medical diagnosis.

## Usage

```bash
python import_hrv_logger.py --file session.csv
python import_hrv_logger.py --dir ~/Downloads/hrv_logger/
python import_hrv_logger.py --file session.csv --dry-run
python import_hrv_logger.py --file session.csv --tags "orthostase,morgen"
```
