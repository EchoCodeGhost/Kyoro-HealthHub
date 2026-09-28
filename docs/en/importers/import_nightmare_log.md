# import_nightmare_log.py — Kyoro-SleepGuard Nightmare-Log importieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_nightmare_log.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports manually transcribed nightmare alarms from the Kyoro SleepGuard app via CSV into the database.

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads CSV (template: templates/nightmare_log_template.csv); writes nightmare_hr and nightmare_baseline into measurements, and nightmare_alarm into symptoms.

## Data flow

- **Reads:** `CSV-Datei`, `(Template:`, `templates/nightmare_log_template.csv)`
- **Writes:** `measurements (nightmare_hr, nightmare_baseline), symptoms (nightmare_alarm), import_log`

## Limitations

Manual data entry — timestamps must be read from the watch display (nmLogTs) and correctly transcribed as UTC. Free-text notes from the CSV are not persisted (symptoms table has no notes field). run() already threaded person through correctly (resolve_person()); the CLI script called run() with no --person option — now added.

## Usage

```bash
python3 scripts/importers/import_nightmare_log.py nightmare_events.csv
python3 scripts/importers/import_nightmare_log.py templates/nightmare_log_template.csv
python3 scripts/importers/import_nightmare_log.py events.csv --person PER-xxxxxxxx
```
