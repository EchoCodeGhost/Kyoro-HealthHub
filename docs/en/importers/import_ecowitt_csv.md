# Ecowitt CSV-Importer — verarbeitet CSV-Exporte der Ecowitt-App / ecowitt.net

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_ecowitt_csv.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports Ecowitt weather data from CSV exports

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Processes CSV exports from Ecowitt app or ecowitt.net. Advantages over Home Assistant Statistics: - Hourly or minute values instead of daily aggregates only - Allows real calculation of sunshine hours (solar > SUNSHINE_THRESHOLD W/m2) CSV format: delimiter comma or semicolon, timestamp in first column, units in column headers or as separate line.

## Data flow

- **Reads:** `CSV-Dateien`, `(Ecowitt`, `Export)`
- **Writes:** `weather_ecowitt`

## Limitations

Dependent on Ecowitt CSV export format.

## Usage

```bash
python importers/import_ecowitt_csv.py /pfad/zur/datei.csv
python importers/import_ecowitt_csv.py /pfad/zur/datei.csv --dry-run
```
