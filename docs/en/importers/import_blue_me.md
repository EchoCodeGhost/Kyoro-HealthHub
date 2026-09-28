# import_blue_me.py — blue-ME JSON-Export → health.db (symptoms, sessions)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_blue_me.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports JSON exports from the blue-ME symptom-tracking app into the shared symptoms table ("tracking" section: daily symptom/ exertion/mindfulness values) and sessions/session_metrics ("activity" section: individual activities with duration, exertion type and level).

## Relevance

Provides health data functions, essential for medical data processing

## Method

Reads a blue-ME export file (keys "tracking"[] and "activity"[]). Each tracking object is split field-by-field into symptoms (one field = one symptom record, EAV pattern); numeric fields → value_num, non-empty string fields → value_text, the supplement list is joined into a comma- separated text. Each activity object becomes one sessions row (type='activity') with duration/exertion/description/record type as session_metrics. Timestamps in the export are naive local time without offset — interpreted via resolve_timezone() and converted to UTC.

## Data flow

- **Reads:** `blue_me_data_export_*.json`, `(blue-ME`, `app`, `export)`
- **Writes:** `symptoms, sessions, session_metrics`

## Limitations

Field names are taken verbatim from the export as symptom identifiers (no fixed mapping onto a controlled symptom taxonomy) — new app fields automatically appear as new symptom names without a code change, but also without validation against typos/renames on the app's side. The "average*" fields are values computed by the app itself, not a raw measurement — tagged with category='berechnet'. Only JSON exports are supported, not CSV. Any blue-ME user can define their own activities — "exertionType" and "description" in the activity section are therefore free, user-defined text, not a fixed value list known to the app. The importer deliberately does not validate/filter these fields against an enum (plain value_text pass-through into session_metrics) — any future analysis of these fields (currently no script reads sessions type='activity') must likewise assume open vocabulary instead of a fixed category list (e.g. "Körperlich"/ "Geistig"/"Emotional"/"Sozial").

## Usage

```bash
python3 scripts/importers/import_blue_me.py blue_me_export.json
python3 scripts/importers/import_blue_me.py blue_me_export.json --person oma
```
