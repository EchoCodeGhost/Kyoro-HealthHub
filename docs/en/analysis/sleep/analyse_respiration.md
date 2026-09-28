# Respiration rate im Sleep — Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/sleep/analyse_respiration.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses nightly respiratory rate trends from Garmin and Apple Watch data for outliers, trends and correlations with sleep quality and HRV.

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

Daily aggregate (AVG, MIN, MAX) from measurements; outlier detection with custom thresholds (>18/min warning, <10/min warning); moving average.

## Scoring

```
Respiratory rate: <10/min warning | 12-20/min normal | >18/min warning (night average)
Outlier detection: values outside normal range flagged
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Data flow

- **Reads:** `measurements`
- **Writes:** `analyses/sleep/*.{md,png}`

## Limitations

Heuristic method: Threshold 18/min is literature-based (normal 12–20/min) but script-specific; Garmin respiratory rate is captured during sleep only. Not validated as a detector.

## References

- Cretikos MA, Bellomo R, Hillman K, Chen J, Finfer S, Flabouris A (2008). Respiratory rate: the neglected vital sign. Medical Journal of Australia, 188(11):657-659. doi:10.5694/j.1326-5377.2008.tb01825.x
- Massaroni C, Nicolò A, Schena E, Sacchetti M (2020). Remote Respiratory Monitoring in the Time of COVID-19. Frontiers in Physiology, 11:635. doi:10.3389/fphys.2020.00635

## Usage

```bash
python analyse_respiration.py
python analyse_respiration.py --help
python analyse_respiration.py --from 2024-01-01 --to 2024-12-31
```
