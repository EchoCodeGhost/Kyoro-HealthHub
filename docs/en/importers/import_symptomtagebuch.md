# import_symptomtagebuch.py — Symptomtagebuch-App CSV → Datenbank

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_symptomtagebuch.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports daily data from Symptomtagebuch app CSV exports into health.db

## Relevance

Enables import of symptom data, essential for clinical analysis

## Method

Imports the 7-day CSV report from the Symptomtagebuch app. Format: one line per day, one column per category. Severity: None=0, Light=1, Moderate=2, Severe=3, Yes=1, No=0, Number (0-9) direct. Empty values or "-" are skipped. Column types are automatically detected: Yes/No values → category='behandlung', others 'category'. Notes are stored in user_context.

## Data flow

- **Reads:** `CSV-Dateien`, `aus`, `imports/symptomtagebuch/`, `Verzeichnis`
- **Writes:** `Datenbanktabellen, user_context, import_log`

## Limitations

Depends on the CSV format of the Symptomtagebuch app. No medical validation. --person used to be declared in run() but unused (write path hardcoded to OWN_PERSON_ID) and absent from main() entirely — now threaded through both paths; --rebuild consequently only deletes the selected person's entries, not everyone's.

## Usage

```bash
python import_symptomtagebuch.py
python import_symptomtagebuch.py --file bericht.csv
python import_symptomtagebuch.py --dry-run
python import_symptomtagebuch.py --rebuild
python import_symptomtagebuch.py --file bericht.csv --person PER-xxxxxxxx
```
