# Muster-Analyse — tägliche/wöchentliche Gesundheitsübersicht

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/internal_medicine/analyse_overview.py`

**Evidence tier:** calibrated (literature-based + parameters tuned to personal baselines, no external validation)

## Purpose

Combines all key biomarkers (RHR, HRV, sleep, SpO₂, activity, symptoms) into a daily/weekly overview analysis with event markers from clinical.events.

## Relevance

Provides an integrated overview of all health data, essential for quick orientation and identification of anomalies in complex datasets

## Method

7-day rolling average per biomarker; aggregation from multiple compute and import tables (measurements, sessions, oura_sleep_model); event lines from configured clinical.events list.

## Data flow

- **Reads:** `measurements`, `sessions`, `session_metrics`, `oura_sleep_model`, `symptoms`
- **Writes:** `analyses/internal_medicine/overview_*.{md,png}`

## Limitations

Aggregation dashboard without significance tests; SpO₂ thresholds (94/90%) are clinical orientation values, not individually calibrated; data quality varies substantially by available devices.

## References

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Shaffer F, Ginsberg JP (2017). An overview of heart rate variability metrics and norms. Frontiers in Public Health, 5:258. doi:10.3389/fpubh.2017.00258

## Usage

```bash
python analyse_overview.py
python analyse_overview.py --help
python analyse_overview.py --from 2024-01-01 --to 2024-12-31
```
