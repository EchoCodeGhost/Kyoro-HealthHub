# fix_polar_training_device_ids.py — Reassigns sessions.device_id for Polar

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/fix_polar_training_device_ids.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Corrects `sessions` rows (type='training', source_app='polar_connect') whose device_id previously came from the unreliable date-guessing logic (_polar_device_for_date()), even though the training JSON files carry the real device serial in the 'deviceId' field.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Re-reads every training-session_*.json, maps deviceId via _POLAR_SERIAL_TO_DEVICE_ID (device_registry) to the correct device_id, UPDATEs the matching sessions row (ID = 'polar_training_{identifier}'). Files without deviceId (older exports) are skipped, not falling back to the date rule — those rows are left unchanged.

## Data flow

- **Reads:** `{polar_dir}/training-session_*.json`, `sessions`
- **Writes:**

  ```
  sessions (UPDATE device_id where the JSON's real deviceId maps
  to a different device than currently stored)
  ```

## Limitations

Requires a complete device_registry with all Polar wrist serials (see fix_polar_wrist_device_attribution.py for the companion fix to the date-fallback logic). Safe to re-run (idempotent, UPDATE only on mismatch).

## Usage

```bash
python3 scripts/migrations/fix_polar_training_device_ids.py
python3 migrations/fix_polar_training_device_ids.py  # from inside scripts/
```
