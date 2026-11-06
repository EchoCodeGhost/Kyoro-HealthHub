# migrate_location_tables_to_location_db.py — Tracks, Aufenthalte und Standortverlauf von health.db nach location.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/migrate_location_tables_to_location_db.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Moves session_tracks, location_stays, location_history and location_stays_geocoded from health.db to location.db and then removes them from health.db so that no coordinates remain there. Audit-log entries of these tables (they contain coordinates) move along.

## Relevance

Stage 3 of the location registry: health.db no longer holds tracks and stays

## Method

With --execute: (1) back up health.db via the SQLite backup API (or use a given existing backup, checked for readability and row counts); (2) copy rows unchanged to location.db (INSERT OR IGNORE, columns by name); (3) verify: every row from health.db must exist identically in location.db (EXCEPT query), plus row counts and a SHA-256 checksum over the sorted rows of both sides; (4) copy the tables' audit-log entries to location.db; (5) in one transaction with secure_delete: delete those entries from the health.db audit log, drop the tables (photo_locations only if empty), write one count-only audit entry. Stops before any deletion if verification fails. Can be run again.

## Data flow

- **Reads:** `health.db`, `(session_tracks`, `location_stays`, `location_history`, `location_stays_geocoded`, `photo_locations`, `audit_log)`, `location.db`
- **Writes:**

  ```
  location.db (dieselben Tabellen, audit_log), health.db (DROP TABLE,
  audit_log), data/backups/health.db.pre_location_migration_<Datum>.bak
  ```

## Limitations

Defaults to a dry run that reports counts only, never coordinates. Data is copied unchanged: no rounding, no privacy zones (use apply_privacy_zones.py). location.db must not already hold stays that do not come from health.db (their ids would collide).

## Usage

```bash
# Trockenlauf (Standard)
python3 scripts/migrations/migrate_location_tables_to_location_db.py
# Ausführen, mit neuem Backup
python3 scripts/migrations/migrate_location_tables_to_location_db.py --execute
# Ausführen mit vorhandenem Backup
python3 scripts/migrations/migrate_location_tables_to_location_db.py --execute \
    --backup data/backups/health.db.pre_location_stage3_<Datum>.bak
```
