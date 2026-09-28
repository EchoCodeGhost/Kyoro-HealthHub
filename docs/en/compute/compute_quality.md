# Data-quality checks before AI analysis (v2 schema).

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_quality.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Detects anomalies in health.db before an LLM interprets the data and writes quality flags. Pure data checking, no clinical claim.

## Relevance

Enables data quality assessment, essential for data validation

## Method

Scans measurement tables for outliers, gaps, duplicates and implausible values; findings are stored with a severity in data_quality_flags.

## Data flow

- **Reads:** `measurements`, `blood_pressure`, `ppi_raw`, `polar_nightly_hrv`, `symptoms`, `devices`
- **Writes:** `data_quality_flags`

## Limitations

Heuristic plausibility checking, no ground-truth comparison. May flag genuine extremes and miss subtle errors.

## Usage

```bash
python3 compute_quality.py
python3 compute_quality.py --table heart_rate
python3 compute_quality.py --severity critical
python3 compute_quality.py --summary
```
