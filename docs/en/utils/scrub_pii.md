# scrub_pii — Umfassende PII-Bereinigung für health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/scrub_pii.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Searches the database for personally identifiable information (PII) and pseudonymizes or removes it. PII categories: email addresses, phone numbers, IP addresses, insurance numbers, health insurance names, birth dates, full names, addresses, city names.

## Relevance

Provides data cleaning and anonymization functions, essential for data privacy

## Method

Searches defined tables/columns for various PII patterns. Uses scrub_sensitive_health_data() from utils.anonymize. Creates rolling backup (overwritten on each run). Supports modes: pseudonymization (default) or complete removal (--remove-all). Can run automatically without prompt (--auto). Logs to import_log. Exit code: 0 = success, 1 = error.

## Data flow

- **Reads:** `health.db`, `(measurements`, `sessions`, `blood_pressure`, `devices`, `persons)`
- **Writes:** `health.db (aktualisierte Felder), health.db.pii_scrub_backup (Rolling-Backup), import_log`

## Limitations

Only searches defined tables/columns. Skips already pseudonymized fields. Rolling backup overwrites previous backup. Skips very short texts (<10 characters). Explicitly contains NO medical diagnoses, demographic data or locations in docstrings.

## Usage

```bash
python scripts/utils/scrub_pii.py
python scripts/utils/scrub_pii.py --db /path/to/health.db
python scripts/utils/scrub_pii.py --dry-run
python scripts/utils/scrub_pii.py --remove-all
python scripts/utils/scrub_pii.py --auto --no-backup
# --db: Pfad zur Datenbank angeben
# --dry-run: Zeigt Änderungen ohne sie durchzuführen
# --remove-all: Entfernt alle PII komplett
# --auto: Kein interaktives Prompt
# --no-backup: Kein Backup erstellen
```
