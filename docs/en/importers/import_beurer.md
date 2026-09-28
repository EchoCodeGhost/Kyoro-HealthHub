# Beurer Health Manager Pro → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_beurer.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports CSV exports from Beurer Health Manager Pro into health.db. Supports body composition (BF 990), blood glucose (GL 60), body temperature (FT 95), and pulse oximetry (PO60).

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads CSV files from ~/Kyoro-HealthHub/imports/beurer/ or an explicit path. Each CSV file is parsed and data is written to the corresponding tables: body_composition, blood_glucose, measurements (body_temperature, spo2, heart_rate).

## Data flow

- **Reads:** `{imports/beurer/}*.csv`, `(Beurer`, `Health`, `Manager`, `Pro`, `Export)`
- **Writes:** `health.db (body_composition, blood_glucose, measurements)`

## Limitations

No validation of Beurer data quality. Dependent on the correctness of the CSV export. No medical interpretation. The FT 95 has three measurement modes (body 34.0-42.2°C, object/surface 0-80°C, room), but the CSV export (Datum;Uhrzeit; °C;Kommentar;Medikation) carries NO mode column — an object/room- mode reading is indistinguishable from a body-temperature reading in the export data. Plausibility check: values outside the body- mode range (34.0-42.2°C, see BODY_TEMP_MIN_C/MAX_C) are discarded and the count is reported — but this doesn't catch object-mode readings that happen to fall in a plausible body-temperature range (e.g. a warm bottle at ~37°C). That remains a residual risk, avoidable only through disciplined use (don't log object- mode readings with the same device in the same period as your own fever tracking), not by the importer itself.

## Usage

```bash
python3 import_beurer.py                     # all CSVs im Folder
python3 import_beurer.py --file export.csv
python3 import_beurer.py --update            # only neue Daten
python3 import_beurer.py --user Hauptnutzer
```
