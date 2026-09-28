# Umweltdaten für Reiseaufenthalte → health.db (air_quality, pollen, biometeo)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_travel_environment.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Retrospective import of environmental data (air quality, pollen, biometeorology) for travel stays to enable correlation analysis with health symptoms

## Relevance

Enables import of environmental data, essential for environmental factor analysis Enables import of environmental data, essential for environmental factor analysis

## Method

Aggregate stay data from travel_history.json, location_stays (DB) and GPS training tracks. For each non-home stay, historical environmental data is fetched from Open-Meteo (air quality, pollen, biometeorology) and optionally AEMET (Spain) and stored in the DB. Data is stored in regular tables (air_quality, pollen, biometeo).

## Data flow

- **Reads:** `~/Kyoro-HealthHub/.config/kyoro/travel_history.json`, `health.db:location_stays`, `health.db:location_stays_geocoded`, `health.db:sessions`, `health.db:session_tracks`
- **Writes:** `health.db:air_quality, health.db:pollen, health.db:biometeo, health.db:import_log`

## Limitations

Requires internet connection for API queries. Coordinate resolution for stays without GPS data via Nominatim. AEMET requires API key (free, but manual registration). Stays < 2 km from home are skipped.

## References

- Open-Meteo API: https://open-meteo.com/en/docs AEMET OpenData: https://opendata.aemet.es/

## Usage

```bash
python3 import_travel_environment.py                   # alle Aufenthalte
python3 import_travel_environment.py --from 2022-01-01
python3 import_travel_environment.py --sources travel  # nur travel_history
python3 import_travel_environment.py --dry-run
python3 import_travel_environment.py --force           # vorhandene überschreiben
```
