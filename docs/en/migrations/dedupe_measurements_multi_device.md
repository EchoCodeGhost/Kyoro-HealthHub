# dedupe_measurements_multi_device.py — Removes measurements rows that are the

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/dedupe_measurements_multi_device.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Cleans up `measurements` rows that are the exact same real-world reading stored under TWO different device_id values (identical ts, metric, value/value_text, source_app, person -- only device_id differs). Largest finding: a substantial share of heart_rate rows from source_app='polar_connect' are such twin pairs.

## Relevance

Primarily affects heart_rate/polar_connect (high duplicate rate) and feeds into practically every HR-based analysis in the project (sleep/day HR comparison, orthostatic detection, PEM score, ...). Averages are arithmetically unaffected under uniform 2x duplication, but any sample-size-dependent logic (minimum-n thresholds) has been counting double.

## Method

Root-cause analysis (via identity_resolver.reverse_resolve + health_config.device_registry): the affected device_ids are REAL, distinct devices of the same sensor type (different serial numbers on record in device_registry) -- not a pseudonymization bug that assigned one device multiple IDs. An affected device_registry entry already independently documents overlapping wear periods with other wrist devices ("date-based single-device attribution occasionally ambiguous"). The duplicates themselves (identical value to the decimal, second by second over extended periods) are not physically plausible for two independent optical wrist sensors -- instead, one and the same underlying Polar API reading gets attributed to two registered devices at import time (or already in Polar's own export), likely because measurements' PRIMARY KEY (ts, metric, device_id, person) treats device_id as part of the identity -- two different device_ids for the same ts+metric are therefore not a schema conflict, INSERT OR IGNORE does not catch it. Fix: group by (person, metric, ts, value, value_text, source_app) -- deliberately WITHOUT device_id/unit in the grouping key, since device_id is exactly the source of the error. From each group (>1 row) the row with the smallest rowid is kept (device_id is not used by any known analysis in this project -- only source_app is), the rest are deleted.

## Data flow

- **Reads:** `health.db`, `(measurements)`
- **Writes:** `health.db (DELETE auf measurements fuer Duplikat-Zeilen)`

## Limitations

Only covers the metrics listed in METRICS_TO_CHECK (where the duplication was concretely demonstrated) -- not a global scan over all measurements metrics, to keep runtime manageable on a 40+ million row table. HR-dependent compute/analysis scripts should be rerun afterwards (compute_orthostatic_detection.py, analyse_sleep_day_hr.py, compute_pem.py, ...).

## Usage

```bash
python3 scripts/migrations/dedupe_measurements_multi_device.py --dry-run
python3 scripts/migrations/dedupe_measurements_multi_device.py
```
