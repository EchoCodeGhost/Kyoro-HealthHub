# check_location_columns.py — Prüft, dass health.db und medicine.db keine persönlichen Koordinaten enthalten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/check_location_columns.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Checks that coordinates live only in location.db: every lat/lon/latitude/longitude column (also with a prefix such as trip_lat) in health.db and medicine.db is empty, with two exceptions: environment tables keyed by the coarsened query point for external services (at most 2 decimal places), and outbreak reports (public places, not the person's).

## Relevance

Ensures personal locations exist only in location.db

## Method

Reads the columns of all tables, counts non-empty values and the highest number of decimal places. Also counts audit-log copies of rows from location tables (they hold coordinates as JSON). Prints only table names and counts, never coordinates. Exit 1 on findings.

## Data flow

- **Reads:** `health.db`, `medicine.db`
- **Writes:** `(nichts)`

## Limitations

Detects coordinates by column name only; coordinates in free text are checked by check_anonymization.py.

## Usage

```bash
python3 scripts/utils/check_location_columns.py
```
