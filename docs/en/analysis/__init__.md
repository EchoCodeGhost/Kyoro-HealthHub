# Analysis Module — Analyse-Skripte für Kyoro-HealthHub

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/__init__.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Contains all analysis scripts for health data from various domains

## Method

Module organizes analysis scripts in thematic subdirectories: - activity: Physical activity and fitness - cardiovascular: Cardiovascular analyses - cycle: Menstrual cycle analyses - environment: Environmental factors - immunology: Immunological analyses - infectious: Infection-related analyses - internal_medicine: Internal medicine - metabolic: Metabolic analyses - neurology: Neurological analyses - psychiatry: Psychiatric analyses - psychology: Psychological analyses - sleep: Sleep analyses

## Data flow

- **Reads:** `Alle`, `Tabellen`, `aus`, `Kyoro-HealthHub-Datenbank`
- **Writes:** `Analyse-Ergebnisse in verschiedenen Zieltabellen`

## Limitations

Analysis scripts are heuristic and not clinically validated

## Usage

```bash
python __init__.py
python __init__.py --help
python __init__.py --from 2024-01-01 --to 2024-12-31
```
