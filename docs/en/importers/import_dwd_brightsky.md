# DWD Stationsdaten via Brightsky API → weather_dwd_station

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_dwd_brightsky.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports DWD station data via Brightsky API

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Brightsky (https://api.brightsky.dev) is a free JSON frontend for DWD station data. No API key, no registration required. Station selection is automatic based on coordinates. Coordinates come from fetch_daily.py (Config or Travel-Log).

## Data flow

- **Reads:** `Brightsky`, `API`, `(online)`
- **Writes:** `weather_dwd_station`

## Limitations

Dependent on DWD/Brightsky API availability.

## Usage

```bash
python3 import_dwd_brightsky.py
python3 import_dwd_brightsky.py --date 2026-01-01
```
