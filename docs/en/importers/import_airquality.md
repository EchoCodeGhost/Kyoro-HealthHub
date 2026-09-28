# Open-Meteo Luftqualität, Pollen und Biometeo → health.db (air_quality, pollen, biometeo)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_airquality.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Import environmental data (air quality, pollen, biometeorology) from Open-Meteo API

## Relevance

Enables import of health data, essential for comprehensive data analysis Enables import of health data, essential for comprehensive data analysis

## Method

Fetch air quality data (PM2.5, PM10, NO2, O3, CO, AQI, dust) and pollen data (birch, alder, grass, mugwort, ragweed, olive) via Air Quality API. Biometeo data (sunshine, radiation, apparent temperature, dewpoint, humidity) is fetched via Archive API. Daily values are aggregated.

## Data flow

- **Reads:** `Open-Meteo`, `Air`, `Quality`, `API`, `Open-Meteo`, `Archive`, `API`
- **Writes:** `health.db:air_quality, health.db:pollen, health.db:biometeo, health.db:import_log`

## Limitations

Requires internet connection. Data fetched in 90-day chunks. Coordinates are rounded. Historical data available from 2013-01-01. No real-time data (slightly delayed).

## References

- Open-Meteo Air Quality API: https://open-meteo.com/en/docs/air-quality-api Open-Meteo Archive API: https://open-meteo.com/en/docs/archive-api

## Usage

```bash
python3 import_airquality.py --lat 51.2 --lon 10.5
python3 import_airquality.py --update --from 2024-01-01
```
