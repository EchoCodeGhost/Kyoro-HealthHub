# Importers Module — Datenimport-Skripte für Kyoro-HealthHub

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/__init__.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Contains all import scripts for health data from various sources

## Method

Import of data from wearables (Polar, Garmin, Apple, Oura, etc.), manual entries, lab values, environmental data, and other sources

## Data flow

- **Reads:** `Externe`, `Datenquellen`, `(CSV`, `JSON`, `APIs)`
- **Writes:** `Rohdaten-Tabellen in Kyoro-HealthHub-Datenbank`

## Limitations

Data format and quality depends on the source

## Usage

```bash
python __init__.py
python __init__.py --help
python __init__.py --from 2024-01-01 --to 2024-12-31
```
