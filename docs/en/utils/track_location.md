# iPhone location tracker via Home Assistant

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/track_location.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Tracks iPhone location data via Home Assistant for weather and travel analysis

## Relevance

Enables tracking and analysis of location data, essential for mobility analysis

## Method

Queries current location from Home Assistant every few hours; stores in location_history; weather importer uses this data for Open-Meteo location determination

## Data flow

- **Reads:** `~/.config/kyoro/travel_history.json`, `ext.`, `Geolocation-APIs`
- **Writes:** `~/.config/kyoro/travel_history.json`

## Limitations

Dependent on Home Assistant configuration and iPhone location sharing

## Usage

```bash
python track_location.py
python track_location.py --help
python track_location.py --from 2024-01-01 --to 2024-12-31
```
