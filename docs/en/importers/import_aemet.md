# AEMET-Importer — Agencia Estatal de Meteorología

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_aemet.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports daily climate data from AEMET weather stations

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Fetches daily climate data (including sunshine hours, radiation) from the nearest AEMET weather station. API-Key: Free registration at https://opendata.aemet.es/ In health_config.json: { "apis": { "aemet_api_key": "eyJ..." } }

## Data flow

- **Reads:** `AEMET`, `API`, `(online`, `spanische`, `Wetterdaten)`
- **Writes:** `health.db (Tabelle weather_aemet)`

## Limitations

Only for stays in Spain. Requires API key.

## Usage

```bash
python importers/import_aemet.py --lat 40.4 --lon -3.7 --date-from 2026-06-01 --date-to 2026-06-05
python importers/import_aemet.py --discover --lat 40.4 --lon -3.7
```
