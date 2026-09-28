# fix_polar_247hr_device_ids.py — Reassigns measurements.device_id for Polar

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/fix_polar_247hr_device_ids.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Corrects `measurements` rows (metric='heart_rate', source_app='polar_connect') whose device_id previously came from the unreliable date-guessing logic (_polar_device_for_date()), even though the 247ohr_*.json files carry the real device serial per day (in each deviceDays entry's 'deviceId' field).

## Relevance

Provides health data functions, essential for medical data processing

## Method

First scans all 247ohr_*.json files and builds a date→device_id mapping from the real deviceId values (fast, only reads the per-day headers, not the samples). Then runs one UPDATE per date (not per row — with ~20M affected rows, row-by-row matching would be impractically slow). Days with an unknown/ unmappable serial are skipped, not falling back to the date rule.

## Data flow

- **Reads:** `{polar_dir}/247ohr_*.json`, `measurements`
- **Writes:**

  ```
  measurements (UPDATE device_id where the real per-day deviceId
  maps to a different device than currently stored)
  ```

## Limitations

Requires a complete device_registry with all Polar wrist serials (see fix_polar_wrist_device_attribution.py). If two 247ohr files for the same day carry different deviceId values (e.g. overlapping device setup), the last one read wins — a rare edge case. Uses UPDATE OR IGNORE instead of UPDATE: (ts, metric, device_id, person) is UNIQUE — if a row already exists under the target device_id for the same timestamp (e.g. from genuinely wearing two devices in parallel on the same day), a plain UPDATE would abort with an IntegrityError. OR IGNORE skips only the colliding row and reports the count at the end; the rest of that day is still corrected. Safe to re-run (idempotent, UPDATE only on mismatch).

## Usage

```bash
python3 scripts/migrations/fix_polar_247hr_device_ids.py
python3 migrations/fix_polar_247hr_device_ids.py  # from inside scripts/
```
