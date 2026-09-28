# init_db.py — Datenbank initialisieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/init_db.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Initializes a new health.db with the current schema. Safe to re-run — exits immediately if schema_version table already exists.

## Relevance

Provides database initialization functions, essential for system setup

## Method

Creates data/health.db with full schema. With --sync, new CREATE IF NOT EXISTS tables/views are added to an existing DB and columns newly defined in the schema are added to existing tables.

## Data flow

- **Reads:** `Keine`, `(erstellt`, `neues`, `Schema)`
- **Writes:** `data/health.db`

## Limitations

Call once. With --sync idempotent. Encryption requires SQLCipher.

## Usage

```bash
python3 scripts/utils/init_db.py
python3 utils/init_db.py
python3 scripts/utils/init_db.py --sync
```
