# health_visualize.py — Gesundheitsdaten Dashboard Visualisierung

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/query/health_visualize.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Creates a dashboard with visualizations of health metrics from the database

## Relevance

Provides visualization functions for health data, essential for data presentation

## Method

Creates a multi-page dashboard using matplotlib. Supports two formats: - dashboard: Single PNG with multiple plots in a grid (default) - individual: Separate PNG files per metric Plots include: HRV, resting heart rate, stress score, SpO2, sleep, training load, circadian rhythm, VO2max, blood pressure, weight, orthostatic tests, PEM patterns. Colors and styles are predefined. Data is read from database tables.

## Data flow

- **Reads:** `measurements`, `(HRV/SpO2/VO2max`, `ueber`, `modules/metric_loader.py`, `-`, `geraeteunabhaengig)`, `daily_stress`, `apple_records`, `training-View`, `heart_rate-View`, `sessions`, `session_metrics`, `pem_correlation`
- **Writes:** `analyses/dashboard/ Verzeichnis (PNG-Dateien)`

## Limitations

Depends on data availability. No data manipulation, only visualization.

## Usage

```bash
python health_visualize.py
python health_visualize.py --format individual
python health_visualize.py --only hrv,stress
python health_visualize.py --format png
```
