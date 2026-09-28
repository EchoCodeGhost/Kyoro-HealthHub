# Wellue O2Ring S (ViHealth-App-Export) → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_wellue_o2ring.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports second-resolution SpO2/pulse raw data from the Wellue O2Ring S (ViHealth app CSV export) into health.db. Stores full resolution in o2ring_raw and mirrors per-minute averages into measurements (metrics spo2, heart_rate) for the cross-device calibration pipeline (compute_calibrate_sources.py).

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads CSV with German header, English date format per row (%H:%M:%S %b %d %Y). '--' marks missing SpO2/pulse values (contact loss) and is stored as NULL; movement/alarm flags are kept. Local time is converted to UTC via ZoneInfo(_cfg.home_timezone). The first WARMUP_SECONDS (default 15s) of each file from its first timestamp are marked warmup_flag=1 (descriptive only — own test nights showed no consistent artifact pattern, so it does NOT exclude rows from aggregation). Per-minute aggregation into measurements happens in-memory while parsing (bucket key ts[:16]) over all valid values regardless of warmup_flag.

## Data flow

- **Reads:** `o2ring_raw`, `(MAX(ts)`, `für`, `--update-Modus)`
- **Writes:**

  ```
  o2ring_raw: ts TEXT, date TEXT, spo2 INTEGER, pulse INTEGER,
  movement INTEGER, o2_alarm INTEGER, pr_alarm INTEGER,
  warmup_flag INTEGER, device_id TEXT, person TEXT, source TEXT;
  measurements: ts TEXT, date TEXT, metric TEXT, value REAL,
  unit TEXT, device_id TEXT, person TEXT, source_app TEXT
  ```

## Limitations

No session/device identifier in the CSV itself. Movement scale is not documented by the manufacturer (stored raw). warmup_flag is informational only (no reliable artifact filter found, see plan section 3) — SpO2/pulse jumps in the first seconds (device settling or a real event, e.g. postural change) enter measurements unfiltered. Minutes with only '--' values contribute no measurements entry. No medical interpretation.

## Usage

```bash
python3 import_wellue_o2ring.py
python3 import_wellue_o2ring.py --update
python3 import_wellue_o2ring.py --file imports/_inbox/O2Ring_S_20260715005402.csv
python3 import_wellue_o2ring.py --inbox
```
