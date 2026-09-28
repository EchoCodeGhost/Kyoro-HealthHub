# Home Assistant → health.db Import

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_homeassistant.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Fetches sensor data from Home Assistant devices and stores it as daily mean/min/max in health.db. Supports Philips Somneo (bedroom environment), EcoWitt weather stations, DWD stations, and air purifiers (Dyson, VeSync).

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Uses the Home Assistant Statistics API. Configuration via ~/.config/kyoro/ha_config.json with URL, token, and entities. Supports: temperature, humidity, light, noise level, weather data, air quality. Data is stored as daily aggregates.

## Data flow

- **Reads:** `Home`, `Assistant`, `Statistics`, `API`, `(http://homeassistant.local:8123)`
- **Writes:** `health.db (weather_station, indoor_air_quality, etc.)`

## Limitations

Dependent on the availability of the Home Assistant API and configuration. No medical interpretation.

## Usage

```bash
python import_homeassistant.py --setup
python import_homeassistant.py --discover
python import_homeassistant.py
python import_homeassistant.py --update
python import_homeassistant.py --from 2024-01-01 --to 2025-12-31
python import_homeassistant.py --discover-airpurifiers
python import_homeassistant.py --add-airpurifier sensor.dyson_pm25
```
