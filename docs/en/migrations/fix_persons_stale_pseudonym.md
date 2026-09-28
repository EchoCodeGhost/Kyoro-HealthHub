# fix_persons_stale_pseudonym.py — Renames the stale pre-migration person_id

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/fix_persons_stale_pseudonym.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

The earlier pseudonymization pass (P-XXXXXXXX -> PER-XXXXXXXX, see docs/PRIVACY_ARCHITECTURE.md) migrated every person column in data tables, but left the persons reference table itself untouched -- its primary-key row still carried the old ID, while OWN_PERSON_ID in code had long since pointed at the new one. Previously invisible because several importers logged person=None (NULL bypasses FOREIGN KEY checks); since the importer person parameterization (PR#13) they pass a resolved, non-NULL person ID and surfaced the gap as a "FOREIGN KEY constraint failed" during logging.

## Relevance

Fixes a structural gap in the person reference table that caused silent foreign-key failures during import logging

## Method

UPDATE persons SET person_id=OWN_PERSON_ID WHERE person_id= 'P-F83C73A3' -- pure rename of the primary-key row, all other columns (timezone, active, ...) stay unchanged. Idempotent (WHERE clause only matches once).

## Data flow

- **Reads:** `health.db`, `(persons)`
- **Writes:** `health.db (persons.person_id)`

## Limitations

Only handles the one known old ID 'P-F83C73A3'. If further old ID formats exist, they would need separate review.

## Usage

```bash
python3 scripts/migrations/fix_persons_stale_pseudonym.py --dry-run
python3 scripts/migrations/fix_persons_stale_pseudonym.py
```
