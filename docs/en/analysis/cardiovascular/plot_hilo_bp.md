# plot_hilo_bp.py — Hilo/Aktiia Blutdruckdaten Visualisierung

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/plot_hilo_bp.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Creates visualizations for Hilo/Aktiia wrist blood pressure measurements from the blood_pressure table

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Reads blood pressure data (systolic, diastolic, pulse) from blood_pressure table with source='hilo_pdf' or source='hilo_screenshots'. Creates the following plots: - Time series: Systolic, Diastolic, Pulse over time - Histograms: Distribution of measurements - Time of day profile: Average values by hour - Monthly overview: Monthly averages Supports filtering by date (--from, --to) and person.

## Data flow

- **Reads:** `blood_pressure`, `Tabelle`, `(systolic`, `diastolic`, `pulse`, `ts`, `source)`
- **Writes:** `analyses/cardiovascular/hilo_bp_*.png Plot-Dateien`

## Limitations

Depends on available Hilo data in blood_pressure table. No medical interpretation, only visualization.

## Usage

```bash
python plot_hilo_bp.py
python plot_hilo_bp.py --from 2026-01-01
python plot_hilo_bp.py --to 2026-07-01
python plot_hilo_bp.py --from 2026-01-01 --to 2026-07-01
python plot_hilo_bp.py --format png
python plot_hilo_bp.py --format pdf
```
