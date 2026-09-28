# post_import_sanitize — Automatische Post-Import PII-Bereinigung und Compliance-Check

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/post_import_sanitize.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Called automatically by import_all.py and import_staged.py after each successful import so that the database can always be shared with Cloud-LLMs without leaking PII.

## Relevance

Provides utility functions for data processing, essential for system functionality

## Method

Executes three steps sequentially: 1. scrub_pii: Cleans known PII patterns in text columns 2. pseudonymize_devices: Replaces real serial numbers with SN pseudonyms 3. check_anonymization: Checks GPS precision, serial numbers, person IDs No step is blocking - errors only generate warnings. Logs all changes to import_log.

## Data flow

- **Reads:** `health.db`, `(alle`, `Tabellen`, `für`, `PII-Prüfung)`
- **Writes:** `health.db (bereinigte Felder), import_log`

## Limitations

Only outputs warnings, never exits (non-blocking). Does not create backups (managed by import scripts).

## Usage

```bash
# Wird automatisch von import_all.py und import_staged.py aufgerufen
from utils.post_import_sanitize import run
run()
# Oder direkt:
python -c "from utils.post_import_sanitize import run; run()"
```
