# Wetter-Lookup for beliebige Zeitpunkte and Koordinaten.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/weather_lookup.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Enables weather data queries for arbitrary timestamps and coordinates

## Relevance

Enables data lookup and referencing, essential for data integration

## Method

Strategy: Within HOME_RADIUS_M → local weather station; outside → Open-Meteo Archive API with caching in weather_remote

## Data flow

- **Reads:** `Externe`, `Wetter-APIs`, `(Open-Meteo`, `DWD`, `Brightsky)`
- **Writes:** `Keine Tabellen (gibt Wetterdaten als Dict zurueck)`

## Limitations

Accuracy depends on Open-Meteo data and local station

## Usage

```bash
python weather_lookup.py
python weather_lookup.py --help
python weather_lookup.py --from 2024-01-01 --to 2024-12-31
```
