# fix_polar_wrist_device_attribution.py — Reassigns historical device_id='polar_vantage'

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/fix_polar_wrist_device_attribution.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Corrects historical measurements/sessions rows that were wrongly tagged device_id='polar_vantage', even though a different Polar wrist device was actually worn at the time. Cause: import_polar.py's _polar_device_for_date() fell back to the only registered Polar wrist device for years, because earlier/other wrist devices were never in device_registry.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Plain UPDATE statements against fixed date boundaries from clinical.polar_wrist_date_reassignments (local config, see below), not hardcoded in the repo. Only touches rows with device_id='polar_vantage'; rows in the actual Vantage V3 period are left untouched. No DDL, no rows deleted.

## Data flow

- **Reads:** `measurements`, `sessions`, `(device_id`, `date)`
- **Writes:**

  ```
  measurements, sessions (UPDATE device_id for polar_vantage-tagged
  rows outside the real Vantage V3 ownership window)
  ```

## Limitations

Date boundaries are mostly user-provided estimates; only some can be derived exactly from a manufacturer export (e.g. an archive timestamp), the rest remain approximations. Under genuine simultaneous multi-watch wear, exact attribution isn't reconstructable from the data at all (Polar's export doesn't carry a per-entry device ID for daily activity/HR history/HRV) — this migration is a best-effort approximation, not an exact fix. Safe to re-run (boundaries are exact, no blast radius beyond the affected rows).

## Usage

```bash
python3 scripts/migrations/fix_polar_wrist_device_attribution.py
python3 migrations/fix_polar_wrist_device_attribution.py  # from inside scripts/
```
