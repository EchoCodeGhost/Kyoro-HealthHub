# baseline.py — Hilfsfunktionen für personalisierte Baselines

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/baseline.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides functions for calculating personalized baseline values from health data. Supports various methods for stable periods.

## Relevance

Enables calculation of baseline values, essential for individual health analysis

## Method

Four calculation methods: all_iqr (IQR median of all stable daily means), all_top (best top_pct% of all stable days), device_iqr (IQR median from configured device), device_top (best top_pct% from configured device). Recommended: device_top. Filters unstable periods (infections ± buffer).

## Data flow

- **Reads:** `measurements`, `Tabelle`, `personal_baseline`, `Tabelle`
- **Writes:** `personal_baseline Tabelle`

## Limitations

Requires at least 7 stable measurement days. Missing values are ignored.

## Usage

```bash
python baseline.py
python baseline.py --help
python baseline.py --from 2024-01-01 --to 2024-12-31
```
