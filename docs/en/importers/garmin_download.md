# Garmin Connect → FIT-Dateien Download

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/garmin_download.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Downloads activity data from Garmin Connect

## Relevance

Enables import of health and activity data from Garmin devices, essential for comprehensive wearable data analysis

## Method

Downloads all activities from Garmin Connect and saves them as FIT files to ~/Kyoro-HealthHub/imports/garmin/. After download: run import_garmin.py to import into health.db. Configuration: ~/.config/kyoro/garmin_config.json

## Data flow

- **Reads:** `Garmin`, `Connect`, `API`, `(online)`
- **Writes:** `FIT-Dateien in ~/Kyoro-HealthHub/imports/garmin/`

## Limitations

Requires Garmin Connect API access and configuration.

## Usage

```bash
python3 garmin_download.py --setup          # E-Mail speichern
python3 garmin_download.py                  # alle Aktivitäten
python3 garmin_download.py --update         # nur neue (seit letztem Download)
python3 garmin_download.py --days 30        # letzte 30 Tage
python3 garmin_download.py --limit 50       # max. 50 Aktivitäten
```
