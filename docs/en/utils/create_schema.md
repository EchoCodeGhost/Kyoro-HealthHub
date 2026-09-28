# create_schema.py — Datenbank-Schema Phase 1 erstellen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/create_schema.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Creates health_v2.db with full v2 schema and migrates small tables. Phase 1 of database migration.

## Relevance

Enables creation of database schemas, essential for data organization and structure

## Method

Steps: 1) Create health_v2.db with full v2 schema, 2) Populate persons + devices, 3) source_priority (initial entries), 4) Migrate small clinical tables from health.db, 5) Copy context tables (home_*, weather_*, location_*, polar_sleep_*), 6) Write schema_version + import_log. Safely repeatable.

## Data flow

- **Reads:** `data/health.db`
- **Writes:** `data/health_v2.db (schema_version, import_log, kleine Tabellen)`

## Limitations

Migration is one-time. Previous DB is preserved as health.db. Requires Python 3.10+.

## Usage

```bash
python create_schema.py
python create_schema.py --help
python create_schema.py --from 2024-01-01 --to 2024-12-31
```
