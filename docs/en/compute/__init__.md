# Compute Module — Berechnungs-Skripte für Kyoro-HealthHub

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/__init__.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Contains all computation and analysis scripts for health metrics

## Method

Computation of HRV metrics, heart rate analyses, sleep parameters, stress levels, metabolic values, and other health indicators

## Data flow

- **Reads:** `ppi_raw`, `ecg`, `measurements`, `sessions`
- **Writes:** `ppi_hrv_advanced, hrv_daily, sleep_analysis, clinical_analysis`

## Limitations

Computations are based on available sensor data

## Usage

```bash
python __init__.py
python __init__.py --help
python __init__.py --from 2024-01-01 --to 2024-12-31
```
