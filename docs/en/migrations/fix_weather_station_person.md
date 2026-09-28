# fix_weather_station_person.py — Corrects person attribution for existing

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/fix_weather_station_person.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

import_homeassistant.py::import_weather_to_db() and import_reise_weather() never set the person column explicitly — both INSERT statements fell back to the table default ('unknown'). A later system-wide pseudonymization pass turned part of that into a freshly minted pseudonym (PER-982e9b5c) instead of resolving it to the actual person — weather_station is single-household weather data, not a genuine second identity. The importer bug is fixed alongside this commit; this script corrects the already-imported rows.

## Relevance

Enables correct person-filtered queries on weather station data, including compute_pem.py's environmental hints

## Method

UPDATE weather_station SET person=OWN_PERSON_ID WHERE person IN ('unknown', 'PER-982e9b5c') — both known wrong values in one run. Idempotent, safe to re-run.

## Data flow

- **Reads:** `health.db`, `(weather_station)`
- **Writes:** `health.db (weather_station.person)`

## Limitations

Only affects weather_station. Other tables with a similar person-attribution defect would need separate review.

## Usage

```bash
python3 scripts/migrations/fix_weather_station_person.py --dry-run
python3 scripts/migrations/fix_weather_station_person.py
```
