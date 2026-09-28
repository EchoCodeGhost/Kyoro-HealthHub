# pseudonymize_device_person_identifiers.py — Geräte-/Personen-Identifier pseudonymisieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/pseudonymize_device_person_identifiers.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Updates existing semantic device_id and person values in health.db and medicine.db to their pseudonym equivalents. Follows the pattern of pseudonymize_polar_device_serials.py but handles both device and person identifiers.

## Relevance

Provides health data functions, essential for medical data processing

## Method

1. Opens health.db/medicine.db via modules.db.open_db()/open_medicine_db() (respects the configured path + SQLCipher encryption — NEVER use a hardcoded filename, see lesson below). 2. Finds all tables with device_id/device/person columns. 3. For columns that are part of the primary key (e.g. ppi_raw (datetime, pulse_ms, device, person)): before the UPDATE, check via NOT EXISTS for exact duplicates already under the target pseudonym (pattern: pseudonymize_polar_device_serials.py). Found duplicates are deleted, no other rows. For columns that are themselves the entire primary key (e.g. devices.device_id): a collision would mean a real hash collision, not a duplicate import — reported and aborted, never auto-resolved. 4. Commit per table (not one big transaction across all tables), so a failure in a later table doesn't roll back already-committed ones. 5. Verification via the table's TOTAL row count before/after (minus reported duplicate deletions) — a plain UPDATE can never change the count of non-NULL values in a column, so that would not be a real verification.

## Data flow

- **Reads:** `health.db`, `medicine.db`, `(alle`, `Tabellen`, `mit`, `Zielspalten`, `über`, `Config-Pfad)`, `~/.config/kyoro/identity.db`, `(für`, `Pseudonym-Lookup)`
- **Writes:** `health.db, medicine.db (aktualisierte device_id/device/person Werte)`

## Limitations

Only semantic values are replaced; existing pseudonyms remain unchanged. No automatic schema adjustment — target columns must already exist. Does NOT create a backup itself — that's task 4.1 (run separately, before this script).

## Usage

```bash
python3 scripts/migrations/pseudonymize_device_person_identifiers.py --dry-run
python3 scripts/migrations/pseudonymize_device_person_identifiers.py --execute
python3 scripts/migrations/pseudonymize_device_person_identifiers.py --database health --execute
```
