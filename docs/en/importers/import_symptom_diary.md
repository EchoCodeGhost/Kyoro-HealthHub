# Symptomtagebuch CSV → health.db (symptoms)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_symptom_diary.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Import symptom data from Symptom diary app (Adam C.) for longitudinal analysis

## Relevance

Enables import of symptom data, essential for clinical analysis

## Method

Parse CSV files with wide format (one symptom per column, one day per row). Value mapping to numeric scale (0-4) and storage in symptoms table. Category assignment via KATEGORIE_DEFAULTS and DB lookup.

## Data flow

- **Reads:** `~/Kyoro-HealthHub/imports/symptomtagebuch/*.csv`, `health.db:symptoms`, `health.db:user_context`
- **Writes:** `health.db:symptoms, health.db:user_context, health.db:import_log`

## Limitations

Only processes CSV files. Notes are stored separately in user_context. Historical data cannot be modified retroactively (INSERT OR IGNORE).

## Usage

```bash
python3 import_symptom_diary.py         # all CSVs
python3 import_symptom_diary.py --update # only neue Daten
```
