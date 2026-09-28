# rename_camerahrv_power_columns.py — Renames camera_hrv_resting.lf_ms2/hf_ms2

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/rename_camerahrv_power_columns.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

import_camerahRV.py carried LF/HF over from the app CSV unchanged and named the target columns lf_ms2/hf_ms2, as if they were absolute power values in ms². Verification against a real All_Features.csv export showed: the header carries no unit label at all, and the values are arithmetically normalised proportions (their ratio equals the reported LF/HF column exactly), not ms² raw power. Other app versions might genuinely export ms² -- without a unit label in the source this can't be told apart, so the importer now names the columns without a unit claim (lf_power/hf_power). This migration brings already- imported databases in line.

## Relevance

Fixes an incorrect unit claim in the column name — a data- integrity matter, not just cosmetic, since later analyses could otherwise assume ms² where none is present.

## Method

SQL column rename via RENAME COLUMN (SQLite >= 3.25) on camera_hrv_resting. Idempotent: checks first whether lf_ms2/ hf_ms2 still exist (no-op if already renamed or the table doesn't exist).

## Data flow

- **Reads:** `health.db`, `(camera_hrv_resting`, `schema)`
- **Writes:** `health.db (camera_hrv_resting column names only, no row data changed)`

## Limitations

Renames columns only, no values change — if an installation genuinely imported real ms² values (different CameraHRV app version), the numbers remain correct, only the column name no longer claims a unit.

## Usage

```bash
python3 scripts/migrations/rename_camerahrv_power_columns.py --dry-run
python3 scripts/migrations/rename_camerahrv_power_columns.py
```
