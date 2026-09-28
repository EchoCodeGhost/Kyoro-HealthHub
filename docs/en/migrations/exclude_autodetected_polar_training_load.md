# exclude_autodetected_polar_training_load.py — Removes training_load from

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/exclude_autodetected_polar_training_load.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Retroactively applies the exclusion logic now built into import_polar.py::import_polar_trainings() (no training_load for startTrigger=TRAINING_START_AUTOMATIC_TRAINING_DETECTION) to sessions rows imported before the fix — the importer change only affects future runs, existing rows keep their old training_load value until this script runs once.

## Relevance

Prevents auto-detected everyday activity from feeding into derived analyses (PEM Evidence Score) as an exercise trigger

## Method

Re-reads every training-session_*.json, checks is_polar_auto_detected(); where True, looks up the matching sessions row via (date, ts_start, ts_end) — not the filename-based id still stored in the DB for rows imported before the identifier fix (see import_polar.py::training_session_identifier). Where a training_load row exists in session_metrics, it is deleted and replaced with auto_detected=1.0 (audit trail for why training_load is absent). Idempotent — already-cleaned rows are skipped.

## Data flow

- **Reads:** `{polar_dir}/training-session_*.json`, `sessions`, `session_metrics`
- **Writes:**

  ```
  health.db (DELETE training_load / INSERT auto_detected in
  session_metrics for auto-detected sessions)
  ```

## Limitations

Only affects type='training' AND source_app='polar_connect'. compute_pem.py (both modes) should be recomputed afterwards.

## Usage

```bash
python3 scripts/migrations/exclude_autodetected_polar_training_load.py --dry-run
python3 scripts/migrations/exclude_autodetected_polar_training_load.py
```
