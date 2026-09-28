# DWD Pollenflug-Gefahrenindex → health.db (pollen_dwd)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_pollen_dwd.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Import daily pollen risk index from German Weather Service (DWD) OpenData

## Relevance

Enables import of health data, essential for comprehensive data analysis Enables import of health data, essential for comprehensive data analysis

## Method

Fetch current pollen flight status as JSON from DWD OpenData server. Process data for today, tomorrow and day after tomorrow. Supports all DWD sub-regions with pollen forecast. Values: 0-6 (0=none, 1=low, 2=low-medium, 3=medium, 4=medium-high, 5=high, 6=very high). Range values (e.g. "2-3") are stored as average.

## Data flow

- **Reads:** `DWD`, `OpenData`, `API`, `(https://opendata.dwd.de/climate_environment/health/alerts/s31fg.json)`
- **Writes:** `health.db:pollen_dwd, health.db:import_log`

## Limitations

Only provides current and future data (today + 2 days). Historical data must be built through daily imports. Requires internet connection. No authentication needed.

## References

- DWD OpenData: https://www.dwd.de/DE/leistungen/opendata/opendata.html DWD Pollenflug: https://www.dwd.de/DE/wetter/wetterundklima_vorort/pollenflug/pollenflug.html

## Usage

```bash
python import_pollen_dwd.py
python import_pollen_dwd.py --region 122
python import_pollen_dwd.py --list-regions
```
