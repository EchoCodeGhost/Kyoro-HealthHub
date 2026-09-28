# backfill_garmin_training_load.py — Adds training_load to already-imported

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/backfill_garmin_training_load.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Retroactively applies the training_load derivation now built into import_garmin.py::import_activities() (from aerobic/anaerobic Training Effect) and the source priority resolution (see claim_training_load_slot, modules/base.py — Garmin beats Polar/ Oura on overlap) to already-imported Garmin sessions. The importer change only affects future runs.

## Relevance

Ensures Garmin activities imported before this fix get the same exercise-trigger status as future imports

## Method

Reads every type='training' AND source_app='garmin_connect' session without a generic 'other' sport, fetches aerobic_training_effect/anaerobic_training_effect from session_metrics, calls claim_training_load_slot (which may evict training_load from an overlapping, lower-priority Polar/Oura session), and writes training_load. Idempotent — sessions with training_load already set are skipped.

## Data flow

- **Reads:** `health.db`, `(sessions`, `session_metrics)`
- **Writes:**

  ```
  health.db (session_metrics.training_load for Garmin sessions;
  possibly DELETEs training_load from lower-priority overlapping
  Polar/Oura sessions via claim_training_load_slot)
  ```

## Limitations

Only affects type='training' AND source_app='garmin_connect'. compute_pem.py (both modes) should be recomputed afterwards.

## Usage

```bash
python3 scripts/migrations/backfill_garmin_training_load.py --dry-run
python3 scripts/migrations/backfill_garmin_training_load.py
```
