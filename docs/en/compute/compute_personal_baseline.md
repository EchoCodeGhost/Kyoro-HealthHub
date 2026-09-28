# Berechnet personalisierte Baselines für Kernmetriken.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_personal_baseline.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Personalised baseline from best/stable periods — replaces per-script ad-hoc calculations with a single consistent table.

## Relevance

Enables calculation of personal baseline values, essential for individual health analysis

## Method

Four methods: IQR-median across devices (all_iqr), top-N% across devices (all_top), IQR-median for one device (device_iqr), top-N% for one device (device_top). Unstable periods (infections ±7/+90 days) are excluded. Result stored in personal_baseline (median, SD, P25/P75, n).

## Data flow

- **Reads:** `measurements`, `(hrv_rmssd`, `met_min`, `spo2`, `sleep_deep_pct`, `sleep_rem_pct`, `respiratory_rate`, `skin_temperature)`
- **Writes:**

  ```
  personal_baseline: metric, method, device_id, median_val, sd_val,
  p25, p75, n_days, ts_computed, person
  ```

## Limitations

Baseline quality depends on data density and device availability; method choice (IQR vs. top-N%) affects the result; minimum 30 days required. No automatic re-compute on new data — must be run manually.

## Usage

```bash
python compute_personal_baseline.py
python compute_personal_baseline.py --help
python compute_personal_baseline.py --from 2024-01-01 --to 2024-12-31
```
