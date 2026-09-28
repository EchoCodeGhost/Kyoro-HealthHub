# Subjektives Aktivitätsprotokoll → health.db (activity_log)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_activity_log.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports subjective activity and load data

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads daily YAML files with subjective load scores (1-10) from imports/activity_log/ and writes them to the activity_log table. YAML format supports single days or multi-day lists. Fields: date, sensory_load, cognitive_load, social_effort, triggers, notes.

## Data flow

- **Reads:** `YAML-Dateien`, `aus`, `imports/activity_log/`
- **Writes:** `activity_log`

## Limitations

Subjective data. Quality depends on manual input. run() already threaded person through correctly, but main() had no --person flag — now added.

## Usage

```bash
python3 import_activity_log.py           # alle YAML-Dateien
python3 import_activity_log.py --update  # nur neue Daten
python3 import_activity_log.py --template  # Beispiel-YAML ausgeben
python3 import_activity_log.py --person PER-xxxxxxxx
```
