# migrate_scrub_pii — Historisches PII-Scrubbing für health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/migrate_scrub_pii.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Scrubs personal identifiable information (PII) from all text fields in health.db — historical rows and device_id normalization.

## Relevance

Provides data migration functions, essential for data updates and restructuring

## Method

Loads user name and email from health_config.json, scans all relevant text columns for email addresses, phone numbers, and name fragments, replaces with [SCRUBBED]. Normalises known inconsistent device_id values. Rowid-based — works on tables without a named primary key.

## Data flow

- **Reads:** `health.db`, `(sessions`, `symptoms`, `measurements`, `lab_manual`, `…)`, `~/.config/kyoro/health_config.json`
- **Writes:** `health.db (text columns in scope, sessions.device_id normalization)`

## Limitations

Only recognises device_id values listed in _DEVICE_ID_MAP. Name terms shorter than 3 characters are not scrubbed. Phone numbers without common prefixes (+49, 0) may not be detected. No undo — take a DB backup before --apply.

## Usage

```bash
python3 utils/migrate_scrub_pii.py              # Dry-run (Vorschau)
python3 utils/migrate_scrub_pii.py --apply      # Änderungen schreiben
python3 utils/migrate_scrub_pii.py --apply --quiet
```
