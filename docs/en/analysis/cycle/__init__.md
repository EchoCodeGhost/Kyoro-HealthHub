# Cycle Analysis Module — Zyklus-Analyse-Skripte

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cycle/__init__.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Contains analysis scripts for menstrual cycle data

## Method

Analysis of cycle length, ovulation, hormone patterns, and cycle-related symptoms

## Data flow

- **Reads:** `cycle`, `symptoms`, `measurements`
- **Writes:** `cycle_analysis, ovulation_prediction`

## Limitations

Heuristic analyses based on subjective data

## Usage

```bash
python __init__.py
python __init__.py --help
python __init__.py --from 2024-01-01 --to 2024-12-31
```
