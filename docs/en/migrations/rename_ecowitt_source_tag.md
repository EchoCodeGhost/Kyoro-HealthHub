# rename_ecowitt_source_tag.py — Renames weather_station.source

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/rename_ecowitt_source_tag.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

import_homeassistant.py tagged Ecowitt weather station data with the exact gateway model name ('ecowitt_gw3000a') instead of just the brand. Unlike device-class tags that are technically needed for calibration logic (e.g. polar_h10/polar_v3), the exact weather-station gateway model isn't functionally relevant to anything in the code — only the brand matters. The importer now uses 'ecowitt', this migration brings already-imported databases in line.

## Relevance

Removes an unnecessarily specific device designation from a DB value -- a privacy/data-hygiene matter, not functionality.

## Method

UPDATE weather_station SET source='ecowitt' WHERE source='ecowitt_gw3000a'. Idempotent: checks first whether any rows with the old tag exist.

## Data flow

- **Reads:** `health.db`, `(weather_station.source)`
- **Writes:** `health.db (weather_station.source only, no other columns changed)`

## Limitations

Only affects weather_station.source — if any other table were ever to reference this string directly (not currently the case), those would not be corrected here.

## Usage

```bash
python3 scripts/migrations/rename_ecowitt_source_tag.py --dry-run
python3 scripts/migrations/rename_ecowitt_source_tag.py
```
