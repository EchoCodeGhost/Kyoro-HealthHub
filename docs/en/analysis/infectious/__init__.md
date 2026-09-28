# Infectious Analysis Module — Infektionsbezogene Analyse-Skripte

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/infectious/__init__.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Contains analysis scripts for infection-related data

## Method

Analysis of infection courses, symptom patterns, and post-infectious patterns

## Data flow

- **Reads:** `infectious`, `symptoms`, `measurements`
- **Writes:** `infectious_analysis, postinfectious_analysis`

## Limitations

Heuristic analyses, no clinical assessment

## Usage

```bash
python __init__.py
python __init__.py --help
python __init__.py --from 2024-01-01 --to 2024-12-31
```
