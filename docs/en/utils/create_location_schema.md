# create_location_schema.py — Erstellt das Schema für location.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/create_location_schema.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Creates location.db with the central location registry schema. Idempotent: can be run multiple times.

## Relevance

Essential for storing GPS data in a separate database

## Method

Creates tables location_registry and location_tokens (if needed). Uses CREATE TABLE IF NOT EXISTS.

## Data flow

- **Reads:** `location.db`, `(wenn`, `existiert`, `zum`, `Prüfen)`
- **Writes:** `location.db (neue Tabellen)`

## Limitations

No data migration — only schema creation

## Usage

```bash
# Schema erstellen
python3 scripts/utils/create_location_schema.py
```
