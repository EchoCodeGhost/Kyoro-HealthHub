# FDDB Ernährungs-Export → health.db (nutrition_entries, nutrition_daily, body_composition)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_fddb.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Import nutrition data and body measurements from FDDB app/website

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Parse diary_*.csv (nutrition diary), userhistory_*.csv (weight history), and complete_*.csv (FDDB's combined export, contains both as sections separated by marker lines like "diary;"/"userhistory;"). Nutrition data is stored in nutrition_entries and aggregated daily. Weight and body data is stored in body_composition.

## Data flow

- **Reads:** `~/Kyoro-HealthHub/imports/fddb/diary_*.csv`, `~/Kyoro-HealthHub/imports/fddb/userhistory_*.csv`, `~/Kyoro-HealthHub/imports/fddb/complete_*.csv`
- **Writes:** `health.db:nutrition_entries, health.db:nutrition_daily, health.db:body_composition, health.db:import_log`

## Limitations

Only processes FDDB-specific CSV formats. Reference values are parsed as float.

## Usage

```bash
python3 import_fddb.py           # all CSVs
python3 import_fddb.py --update  # only neue entries ergänzen
```
