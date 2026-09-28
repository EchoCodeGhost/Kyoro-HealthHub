# reduce_gps_precision — Rundet nachträglich zu hochauflösende GPS-Punkte in session_tracks

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/reduce_gps_precision.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Rounds down existing `session_tracks` coordinates with more than 5 decimal places to 5 decimal places (~1.1m grid). New imports already round at write time (see `import_tracks.py`, `round_coords(..., precision=5)`); this script closes the gap for legacy data imported before rounding was introduced or via a path that skipped `round_coords()`.

## Relevance

Provides utility functions for data processing, essential for system functionality

## Method

Identifies affected rows using the same SQL condition as `check_anonymization_compliance()` (utils/anonymize.py, `high_precision_gps`), rounds lat/lon via `round_coords(precision=5)` and writes them back. Creates a rolling backup of the DB file before changes (overwritten on each run), analogous to `scrub_pii.py`.

## Data flow

- **Reads:** `session_tracks`, `(lat`, `lon)`
- **Writes:** `session_tracks (lat, lon gerundet), health.db.gps_precision_backup (Rolling-Backup)`

## Limitations

Only handles `session_tracks` — the only table `check_anonymization_compliance()` checks for GPS precision. Other tables with lat/lon columns (e.g. `location_history`) are not part of that check and are not touched here.

## Usage

```bash
python scripts/utils/reduce_gps_precision.py --dry-run
python scripts/utils/reduce_gps_precision.py
python scripts/utils/reduce_gps_precision.py --no-backup
```
