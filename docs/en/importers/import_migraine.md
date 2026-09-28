# Migraine-App → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_migraine.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports migraine and headache data from the Migraine-App into health.db. Enables detailed documentation of attacks and assessment of impairment.

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads .mbu backup files from ~/Kyoro-HealthHub/imports/migraene_app/. Mapping: Migraine attacks → sessions (type='migraine') + session_metrics, HIT-6 / MIDAS questionnaires → assessments. Intensity and type are translated according to predefined mappings.

## Data flow

- **Reads:** `{imports/migraene_app/}*.mbu`, `(Migraine-App`, `Backup)`
- **Writes:** `health.db (sessions, session_metrics, assessments)`

## Limitations

No validation of Migraine-App data quality. No medical assessment from the data. HIT-6 and MIDAS are validated questionnaires.

## Usage

```bash
python3 import_migraine.py           # all .mbu files
python3 import_migraine.py --update  # only neue Daten
```
