# export_arzt_komplett.py - Vollständige medizinische Übersicht für Ärzte

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/exporters/export_arzt_komplett.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Exports doctor-specific ODS spreadsheets from manually maintained Kyoro config JSON files (family history, medical history, medications, lifestyle exposures, travel history). Supports 9 specialty profiles with individual sheet selection.

## Relevance

Enables export of health data, essential for data sharing and interoperability

## Method

Reads JSON files from KYORO_CONFIG_DIR, converts them to DataFrames via pandas and writes a multi-sheet ODS file. Falls back to xlsx if odfpy is not installed. Doctor mapping defines which sheets are exported per specialty.

## Data flow

- **Reads:** `~/.config/kyoro/family_history.json`, `clinical_events.json`, `medication_history.json`, `known_risk_exposures.json`, `own_risk_markers.json`, `exposure_profile.json`, `travel_history.json`
- **Writes:** `<output>.ods — arztspezifische Tabellenmappe`

## Limitations

Reads only manually maintained JSON config files — no wearable time-series or lab data from health.db. Output reflects only what is present in the JSON files.

## Usage

```bash
python3 scripts/exporters/export_arzt_komplett.py
python3 scripts/exporters/export_arzt_komplett.py --type Infektiologe -o arzt_infektiologe.ods
python3 scripts/exporters/export_arzt_komplett.py --type alle --output arzt_komplett.ods
python3 scripts/exporters/export_arzt_komplett.py --list
```
