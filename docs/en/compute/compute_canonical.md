# Canonical health data (golden record) across all sources (v2 schema).

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_canonical.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Selects the best value per (date, metric) across all sources by confidence score and writes a golden record. Pure data selection, no clinical claim.

## Relevance

Enables calculation of canonical health metrics, essential for standardization

## Method

CONFIDENCE (metric × source_app) sets source priority; the highest- ranked value per day+metric becomes canonical, all remaining sources are stored as JSON in supplements.

## Data flow

- **Reads:** `measurements`, `sleep`, `blood_pressure`, `body_composition`, `blood_glucose`, `reproductive_health`
- **Writes:** `health_canonical (golden record per day+metric), source_confidence`

## Limitations

Not a measurement or inference — only prioritisation of existing values. Quality depends entirely on the underlying source data.

## Usage

```bash
python3 compute_canonical.py
python3 compute_canonical.py --metric heart_rate
python3 compute_canonical.py --summary
```
