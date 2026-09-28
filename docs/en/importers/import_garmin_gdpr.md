# Garmin GDPR-Export → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_garmin_gdpr.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports Garmin GDPR export data

## Relevance

Enables import of health and activity data from Garmin devices, essential for comprehensive wearable data analysis

## Method

The GDPR data export contains data that the Connect API does NOT provide: - ECG waveforms (DI-Connect-Health-ECG) → ecg_sessions + ecg_samples - Monitoring FIT files with intraday stress → measurements (full history!) (the API only provides intraday for ~3 months) - LifestyleLogging.json (DI-Connect-Wellness) → user_context: lifestyle tags logged daily in the Garmin Connect app (alcohol, caffeine, exercise intensity, meal timing, sauna, massage, acupuncture, light therapy, etc.), presence-coded per day+tag name, same target table as the Oura tags from import_oura_csv.py.

## Data flow

- **Reads:** `Garmin`, `GDPR-Export-ZIP-Dateien`
- **Writes:** `ecg_sessions, ecg_samples, measurements, user_context`

## Limitations

Only for GDPR export. Larger data volumes.

## Usage

```bash
python3 import_garmin_gdpr.py                      # nutzt paths.garmin_gdpr aus health_config.json
python3 import_garmin_gdpr.py --dir /pfad/zum/GDPR-Export [--ecg] [--stress] [--lifestyle]
python3 import_garmin_gdpr.py --dir /path/to/GDPR-Export [--ecg] [--stress] [--lifestyle]
```
