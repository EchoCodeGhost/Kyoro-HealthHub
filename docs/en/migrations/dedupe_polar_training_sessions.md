# dedupe_polar_training_sessions.py — Removes duplicate and phantom Polar

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/dedupe_polar_training_sessions.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Cleans up `sessions` rows (type='training', source_app='polar_connect') from two fixed import bugs: (1) duplicates, because the session ID used to be derived from the filename instead of the stable Polar `identifier.id` (see import_polar.py::training_session_identifier) — every re-sync/re-export of the same physical training produced a new filename and therefore a new sessions row, INSERT OR IGNORE never caught it because the IDs differed. (2) phantom rows from training-target-*.json — planned, per their own 'done': false NEVER completed workout targets from Polar's training diary, which the previously too-broad file glob ('training*.json') also imported as if they were real sessions.

## Relevance

Cleans up inflated training triggers (training_load) that feed into derived analyses such as the PEM Evidence Score

## Method

Phase 1: deletes all rows with id LIKE 'polar_training_training-target-%' (always training_load=NULL, no stopTime/deviceId — never real events). Phase 2: groups the remaining rows by (person, date, ts_start, ts_end) — two genuinely independent trainings do not start and end on the exact same second, making this a robust duplicate key. From each group (>1 row) one row is kept (preferring a device_id starting with 'DEV-', otherwise the smallest id as a deterministic tie-breaker); the rest, including their session_metrics, are deleted.

## Data flow

- **Reads:** `health.db`, `(sessions`, `session_metrics)`
- **Writes:**

  ```
  health.db (DELETE auf sessions + session_metrics für Duplikat- und
  Phantom-Zeilen)
  ```

## Limitations

Only affects type='training' AND source_app='polar_connect' — other sources (Apple Health etc.) use different ID generation and are unaffected by the fixed bugs. compute_pem.py (both modes) should be recomputed afterwards, since tl_d (SUM(training_load) per day) can change.

## Usage

```bash
python3 scripts/migrations/dedupe_polar_training_sessions.py --dry-run
python3 scripts/migrations/dedupe_polar_training_sessions.py
```
