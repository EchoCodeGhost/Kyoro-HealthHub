# scrub_emails — E-Mail-Adressen in der Datenbank bereinigen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/scrub_emails.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Searches the database for email addresses and removes or pseudonymizes them. This script: 1) Searches all text fields for email addresses, 2) Replaces them with pseudonyms or removes them completely, 3) Creates a backup before changes, 4) Logs all changes.

## Relevance

Provides data cleaning and anonymization functions, essential for data privacy

## Method

Searches defined tables and columns (measurements.source_app, sessions.source_app, blood_pressure.source, devices.notes, persons.notes, import_log.error_detail) for email patterns. Uses pseudonymize_email() from utils.anonymize for pseudonymization or replaces with [EMAIL-REMOVED] when removing. Creates timestamp-based backup. Logs to import_log. Requires user confirmation before execution (except --dry-run). Exit code: 0 = success, 1 = error.

## Data flow

- **Reads:** `health.db`, `(definierte`, `Tabellen`, `und`, `Spalten)`
- **Writes:** `health.db (aktualisierte Felder), health.db.backup (Backup), import_log`

## Limitations

Only searches defined tables/columns - other tables are not checked. Backup is created in the same directory as the database.

## Usage

```bash
python scripts/utils/scrub_emails.py
python scripts/utils/scrub_emails.py --db /path/to/health.db
python scripts/utils/scrub_emails.py --dry-run
python scripts/utils/scrub_emails.py --remove
# --db: Pfad zur Datenbank angeben
# --dry-run: Zeigt Änderungen ohne sie durchzuführen
# --remove: Entfernt E-Mails komplett statt sie zu pseudonymisieren
```
