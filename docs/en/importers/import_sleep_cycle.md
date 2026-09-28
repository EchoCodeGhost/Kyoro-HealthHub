# Sleep Cycle CSV → health.db (sessions, session_metrics)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_sleep_cycle.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Import sleep data from Sleep Cycle app (iOS) for sleep analysis

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Parse semicolon-separated CSV files with sleep metrics. Create sessions entries (type='sleep') and store metrics in session_metrics. Supports update mode to add new nights.

## Data flow

- **Reads:** `~/Kyoro-HealthHub/data/sleep_cycle/sleepdata*.csv`
- **Writes:** `health.db:sessions, health.db:session_metrics, health.db:user_context, health.db:import_log`

## Limitations

Only processes sleepdata*.csv files. Timestamps are converted from local to UTC. Historical data is not overwritten (INSERT OR IGNORE).

## Usage

```bash
python3 import_sleep_cycle.py           # all CSVs
python3 import_sleep_cycle.py --update  # only neue Nights ergänzen
```
