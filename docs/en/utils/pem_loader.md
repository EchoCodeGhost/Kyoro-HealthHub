# Zentraler Datenlader für Reaktionsmuster-Scores mit Konfidenz-Filterung.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/pem_loader.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Unified loader for reaction pattern scores from the database

## Relevance

Provides functions for Post-Exertional Malaise analysis, essential for ME/CFS diagnostics

## Method

Loads scores from pre-computed tables with optional confidence filtering; supports time range queries and person filtering

## Data flow

- **Reads:** `pem_scores`, `symptom_scores`, `ms_scores`, `(je`, `nach`, `Konfiguration)`
- **Writes:** `Keine Tabellen (gibt vorberechnete Scores zurueck)`

## Limitations

Quality depends on upstream computations; scores are heuristic

## Usage

```bash
python pem_loader.py
python pem_loader.py --help
```
