# Staged Import — Importiert Rohdaten aus dem Staging-Verzeichnis in health.db.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/import_staged.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Reads raw data from data/staging/YYYY-MM-DD/ and imports it into health.db. Enables offline import: data is fetched once by fetch_daily.py and can be imported any number of times.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Scans the staging directory for JSON files with health data. Each file is parsed and the data is written to the corresponding tables in health.db. Supports various data sources (Polar, Apple, Oura, Dyson, Ecowitt, etc.) based on the manifest.json. Location data is sourced from the manifest or configuration.

## Data flow

- **Reads:** `data/staging/YYYY-MM-DD/*.json`, `(Rohdaten)`
- **Writes:** `health.db (alle Tabellen basierend auf den importierten Daten)`

## Limitations

No semantic data validation. Dependent on the quality of raw data from fetch_daily.py. No comparison with existing data - simply imports all available data. No medical interpretation.

## Usage

```bash
python import_staged.py                    # heutiges Staging
python import_staged.py --date 2026-06-01  # bestimmtes Datum
python import_staged.py --list             # verfügbare Staging-Tage anzeigen
python import_staged.py --all              # alle verfügbaren Tage importieren
```
