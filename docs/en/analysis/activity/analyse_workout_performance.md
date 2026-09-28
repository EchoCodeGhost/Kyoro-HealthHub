# Training Performance Analysis

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/activity/analyse_workout_performance.py`

**Evidence tier:** calibrated (literature-based + parameters tuned to personal baselines, no external validation)

## Purpose

Analyses training performance from Polar sessions: volume development, HR zone distribution, recovery patterns (next-night HRV delta) and PEM threshold estimation via decile analysis.

## Relevance

Enables activity data analysis, essential for movement and fitness analysis

## Method

Aggregates kcal, duration, HR and distance from sessions/session_metrics; HR zones based on cfg.max_hr (220−time period as fallback); Pearson correlation kcal × next-night HRV delta.

## Data flow

- **Reads:** `sessions`, `session_metrics`, `measurements`
- **Writes:** `analyses/activity/*.{md,png}`

## Limitations

HR zone boundaries (60/70/80/90 % HRmax) are standard but individual anaerobic thresholds may differ. PEM threshold estimation from decile analysis is heuristic.

## References

- Midgley AW, McNaughton LR, Jones AM (2007). Training to Enhance the Physiological Determinants of Long-Distance Running Performance. Sports Medicine, 37(10):857-880. doi:10.2165/00007256-200737100-00003
- Achten J, Jeukendrup AE (2003). Heart Rate Monitoring. Sports Medicine, 33(7):517-538. doi:10.2165/00007256-200333070-00004

## Usage

```bash
python analyse_workout_performance.py
python analyse_workout_performance.py --help
python analyse_workout_performance.py --from 2024-01-01 --to 2024-12-31
```
