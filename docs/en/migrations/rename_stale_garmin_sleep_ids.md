# rename_stale_garmin_sleep_ids.py — Rebuilds garmin_sleep session ids that

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/rename_stale_garmin_sleep_ids.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

import_garmin.py::import_sleep() builds sessions.id as f"garmin_sleep_{date}_{PERSON}" — PERSON at the time of the original import was the then-valid, older person pseudonym id (P-F83C73A3), before it was migrated to the current one (PER-16b249d1). The person COLUMN was corrected during that migration, but the old pseudonym id embedded in the id string was missed, since UPDATE statements on the person column don't touch the id string.

## Relevance

Removes a stale person pseudonym id from primary-key strings — a data-integrity matter, not just cosmetic, since the id otherwise mixes two different pseudonyms for the same person within the same dataset

## Method

For every sessions row with id LIKE '%P-F83C73A3%': compute the new id using the current pseudonym. If the new id doesn't exist yet, rename in place (id column + matching session_metrics.session_id). If it already exists (a later re-import created the row fresh under the correct id), the old row's metrics are merged into the existing one via INSERT OR IGNORE and the old row is deleted.

## Data flow

- **Reads:** `health.db`, `(sessions`, `session_metrics)`
- **Writes:** `health.db (sessions.id, session_metrics.session_id)`

## Limitations

Only affects sessions.id — if any other table were ever to reference these id strings directly (not currently the case, see grep before running), those would not be corrected here.

## Usage

```bash
python3 scripts/migrations/rename_stale_garmin_sleep_ids.py --dry-run
python3 scripts/migrations/rename_stale_garmin_sleep_ids.py
```
