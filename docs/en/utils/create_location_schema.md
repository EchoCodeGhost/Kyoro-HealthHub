# create_location_schema.py — Erstellt das Schema für location.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/create_location_schema.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Creates location.db with the central location registry schema. Idempotent: can be run multiple times.

## Relevance

Essential for storing GPS data in a separate database

## Method

Creates table location_registry and the location data tables session_tracks, location_history, location_stays and location_stays_geocoded with CREATE TABLE IF NOT EXISTS. An older table without the region column is rebuilt once (nullable lat/lon, region from the stored coordinates).

## Data flow

- **Reads:** `location.db`, `(wenn`, `existiert`, `zum`, `Prüfen)`
- **Writes:** `location.db (Tabellen, Indizes; einmaliger Umbau location_registry)`

## Limitations

During the rebuild the region is derived from already rounded coordinates; near borders it can differ from the original point's region.

## Usage

```bash
# Schema erstellen
python3 scripts/utils/create_location_schema.py
```
