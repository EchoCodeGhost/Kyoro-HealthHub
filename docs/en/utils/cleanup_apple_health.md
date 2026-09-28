# cleanup_apple_health — Apple Health Datenbank-Bereinigung

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/cleanup_apple_health.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Cleans the apple_records table from duplicates and prevents future duplicates. One-time action: Removes duplicates from apple_records and creates a UNIQUE index that automatically prevents future duplicates. In subsequent imports, known entries are silently skipped via INSERT OR IGNORE.

## Relevance

Provides utility functions for data processing, essential for system functionality

## Method

Identifies duplicates based on (type, value, start_date, end_date, device). Keeps exactly one entry per unique combination (MIN(rowid) strategy). Creates UNIQUE index idx_apple_unique on these columns. Shows statistics before and after cleanup.

## Data flow

- **Reads:** `health.db.apple_records`
- **Writes:** `health.db.apple_records (gelöschte Duplikate), health.db.idx_apple_unique (neuer Index)`

## Limitations

Irreversibly modifies data - backup recommended. In --check mode, no changes are made.

## Usage

```bash
python scripts/utils/cleanup_apple_health.py
python scripts/utils/cleanup_apple_health.py --check
# --check: Nur prüfen, keine Änderungen durchführen
# Standard: Bereinigung durchführen und UNIQUE-Index erstellen
```
