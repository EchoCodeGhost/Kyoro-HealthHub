# import_shotsy.py — Shotsy-Export → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_shotsy.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports injection data from Shotsy app exports into health.db

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Supports JSON and CSV export formats from Shotsy. Timestamps are converted from local time to UTC. Data is written to tables with fields: ts, date, id, drug_name, dose_value, dose_unit, route, injection_site, is_skipped, notes, person, source. Side effects and notes are additionally stored. Also supports .shotsyjson format with daily structure and side effect tracking. After import, side effects (symptoms, source='shotsy') are linked via attribute_side_effects_to_medication() to the name of the most recent preceding injection (symptoms.value_text) — Shotsy logs side effects per day, not per injection, so this is best-effort rather than exact attribution.

## Data flow

- **Reads:** `Shotsy`, `JSON/CSV/.shotsyjson`, `Dateien`, `aus`, `imports/shotsy/`, `Verzeichnis`
- **Writes:** `Tabellen: Injektionsdaten, Nebenwirkungen (inkl. Medikamenten-Zuordnung), Notizen, import_log`

## Limitations

Depends on Shotsy export format. Timezone conversion requires correct timezone configuration. No medical validation of dosages.

## Usage

```bash
python3 import_shotsy.py
python3 import_shotsy.py --update
python3 import_shotsy.py --file export.json
python3 import_shotsy.py --file export.csv --lang en
python3 import_shotsy.py --dir /pfad/zu/exports
```
