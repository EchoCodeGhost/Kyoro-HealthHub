# WomanLog CSV → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_womanlog.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports cycle and health data from WomanLog CSV exports into health.db. Supports menstruation start, ovulation, symptoms, and weight.

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads CSV files from imports/WomanLogApp/ (pattern: womanlog*.csv). Format: Date, Type, Value, Unit. Mapping: Start period → reproductive_health (period_start, cycle_length), Ovulation → reproductive_health (ovulation), Symptom → symptoms, Weight → measurements (body_weight).

## Data flow

- **Reads:** `{imports/WomanLogApp/}/womanlog*.csv`, `(WomanLog`, `Export)`
- **Writes:** `health.db (reproductive_health, symptoms, measurements)`

## Limitations

No validation of WomanLog data quality. Dependent on the correctness of the CSV export. No medical diagnosis.

## Usage

```bash
python import_womanlog.py
python import_womanlog.py --rebuild
```
