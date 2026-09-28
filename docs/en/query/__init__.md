# Query Module — Abfrage- und Berichts-Skripte für Kyoro-HealthHub

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/query/__init__.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Contains query and report scripts for health data

## Method

Generation of health reports, data queries, and visualizations based on stored data

## Data flow

- **Reads:** `Alle`, `Tabellen`, `aus`, `Kyoro-HealthHub-Datenbank`
- **Writes:** `Berichte, Visualisierungen, Export-Dateien`

## Limitations

Queries are read-only, no data modification

## Usage

```bash
python __init__.py
python __init__.py --help
python __init__.py --from 2024-01-01 --to 2024-12-31
```
