# fix_apple_sleep_unspecified_null.py — Backfills the numeric code for

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/fix_apple_sleep_unspecified_null.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

import_apple.py's CATEGORY_MAP previously did not know the string 'HKCategoryValueSleepAnalysisAsleepUnspecified' (only 'HKCategoryValueSleepAnalysisAsleep', the semantically identical, older name for the same raw value). float() on the unknown string failed, so every affected row was imported with value=NULL. This migration backfills the code for already-imported rows that import_apple.py (now fixed) uses for new imports.

## Relevance

Fixes data loss for 2,561 sleep segments (2018-2023) whose raw value was previously silently imported as NULL -- data quality, not a feature.

## Method

One targeted UPDATE on measurements: metric='sleep_analysis' AND value IS NULL AND value_text='HKCategoryValueSleepAnalysisAsleepUnspecified' -> value=1.0. The value_text filter is the only reliable identification: a row with value IS NULL could in principle be NULL for a different reason (an unknown future category value); without an exact value_text match the row is left untouched rather than rewritten on a guess. Code 1.0 is deliberately identical to the existing code for 'HKCategoryValueSleepAnalysisAsleep' (see CATEGORY_MAP in import_apple.py) -- both mean "was asleep, no stage information", not a sleep stage. Code 1.0 is absent from compute_sleep_hypnogram.APPLE_STAGE_MAP (only knows 2/3/4/5) and from its build_apple() query (WHERE value IN (2.0,3.0,4.0,5.0)), so it does not get misclassified into a WAKE/LIGHT/DEEP/REM stage. Idempotent: after the first run, the WHERE filter (value IS NULL) no longer matches any row.

## Data flow

- **Reads:** `health.db`, `(measurements:`, `metric`, `value`, `value_text)`
- **Writes:**

  ```
  health.db (measurements.value only for the matched rows --
  metric, value_text, ts, date, device_id, person, source_app
  untouched)
  ```

## Limitations

Only affects already-imported rows. A fresh run of import_apple.py (after the CATEGORY_MAP fix) would have the same effect on these rows and would make this migration unnecessary afterwards -- it exists so the fix does not depend on a full re-import of the (large) Apple Health XML export.

## Usage

```bash
python3 scripts/migrations/fix_apple_sleep_unspecified_null.py --dry-run
python3 scripts/migrations/fix_apple_sleep_unspecified_null.py
```
