# Bearable CSV-Export → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_bearable.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports comprehensive health and lifestyle data from Bearable CSV exports into health.db. Supports sleep, health measurements, symptoms, mood, energy, fatigue, pain, anxiety, stress, focus, nausea, lifestyle factors, medications, and notes.

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads CSV files from imports/bearable/ or an explicit path. CSV format: 8 columns (date, formatted date, weekday, time of day, category, rating/amount, detail, notes). Mapping: Sleep → sessions + session_metrics, Health measurements → measurements, Symptoms → symptoms, Mood/Energy/etc. → measurements (<name>_score), Factors → bearable_factors, Medications → medications, Notes → bearable_notes.

## Data flow

- **Reads:** `{imports/bearable/}*.csv`, `(Bearable`, `Export)`
- **Writes:**

  ```
  health.db (sessions, session_metrics, measurements, symptoms,
  bearable_factors, medications, bearable_notes, bearable_custom)
  ```

## Limitations

No validation of Bearable data quality. No medical evaluation from the data. Graceful fallback for unknown categories. run()/import_file() already threaded person through correctly, but main() had no --person flag (hardcoded to OWN_PERSON_ID) — now added.

## Usage

```bash
python3 import_bearable.py                  # alle CSVs in imports/bearable/
python3 import_bearable.py --file path.csv  # einzelne Datei
python3 import_bearable.py --rebuild        # bearable-Einträge löschen + neu
python3 import_bearable.py --dry-run
python3 import_bearable.py --update         # nur neue Einträge
python3 import_bearable.py --person PER-xxxxxxxx
```
