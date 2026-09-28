# import_pollen_google.py — Google Pollen API → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_pollen_google.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports pollen flight data from Google Maps Platform Pollen API into health.db

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Uses Google Pollen API (Universal Pollen Index UPI 0-5) for 13 pollen types. Supported types: ALDER, ASH, BIRCH, COTTONWOOD, ELM, GRASS, MAPLE, MUGWORT, OAK, OLIVE, PINE, RAGWEED, WEED. Data is written to pollen_google table with columns: date, plant_code, upi, category, person. Daily execution provides data for today + up to 4 following days. Historical data is built through regular imports.

## Data flow

- **Reads:** `health_config.json`, `(google_pollen_key)`
- **Writes:** `pollen_google, import_log`

## Limitations

Depends on Google API availability and key configuration. No medical validation.

## Usage

```bash
python import_pollen_google.py
python import_pollen_google.py --days 5
python import_pollen_google.py --lat 48.1 --lon 11.6 --days 3
```
