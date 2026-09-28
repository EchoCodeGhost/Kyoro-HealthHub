# Daily Fetch — holt Daten von allen Online-Quellen und speichert sie als JSON.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/fetch_daily.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Fetches health and environmental data from online sources and stores them as JSON files in data/staging/YYYY-MM-DD/. Enables offline import via import_staged.py without direct database access.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Fetches data from various APIs: Open-Meteo (air quality, biometeo), DWD (pollen flight), Google Pollen API, Home Assistant (Dyson, Ecowitt). Also directly syncs device data: Oura Ring API and Garmin Connect API (--update, writes directly to health.db). Polar has no API — import via import_all.py --update after manual export. Location data is sourced from configuration or travel log. Each source is stored as a separate JSON file with status information in a manifest.json.

## Data flow

- **Reads:** `Open-Meteo`, `API`, `DWD/Brightsky`, `API`, `Google`, `Pollen`, `API`, `Home`, `Assistant`, `API`, `(Dyson`, `Ecowitt)`, `Reiseprotokoll`, `(DB)`, `Oura`, `Cloud`, `API`, `Garmin`, `Connect`, `API`
- **Writes:**

  ```
  data/staging/YYYY-MM-DD/*.json (Rohdaten)
  data/staging/YYYY-MM-DD/manifest.json (Metadaten)
  health.db (Oura + Garmin direkt via --update)
  ```

## Limitations

No semantic data validation. Dependent on the availability of external APIs and the quality of returned data. No medical interpretation of data.

## Usage

```bash
python fetch_daily.py
python fetch_daily.py --date 2026-06-01
python fetch_daily.py --days-back 7    # letzte 7 Tage nachholen
python fetch_daily.py --no-ha          # Home Assistant überspringen
python fetch_daily.py --no-devices     # Oura/Garmin-Sync überspringen
```
