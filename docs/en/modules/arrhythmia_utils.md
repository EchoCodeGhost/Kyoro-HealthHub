# arrhythmia_utils.py — Hilfsfunktionen für Arrhythmie-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/arrhythmia_utils.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Shared utility functions for arrhythmia analysis scripts.

## Relevance

Provides utility functions for arrhythmia detection, essential for cardiological analysis

## Method

Covers: CV classification, burst grouping, pre-episode context loading, training-overlap detection, and auxiliary data loaders (pressure, BP). Defines thresholds for AFib classification based on CV values.

## Data flow

- **Reads:** `arrhythmie_episoden`, `blood_pressure`, `Tabellen`
- **Writes:** `Keine Tabellen (Hilfsfunktionen)`

## Limitations

Internal helper module — do not call directly. Changes may break analysis scripts.

## Usage

```bash
python arrhythmia_utils.py
python arrhythmia_utils.py --help
python arrhythmia_utils.py --from 2024-01-01 --to 2024-12-31
```
