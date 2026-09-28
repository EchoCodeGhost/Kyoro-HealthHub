# Intraday-Stress-Architektur

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_intraday_stress.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses the intraday autonomic load from Garmin stress scores (5-minute) and Oura recovery values; identifies critical times of day and weekday patterns.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Hourly averages of stress/recovery scales (Garmin 0–100, Oura 0–100) aggregated across all days; no formally validated stress algorithm.

## Scoring

```
Garmin stress: 0-25 recovery | 25-50 low | 50-75 moderate | >75 high
Oura recovery: 0-100 (higher = better recovery)
```

## Data flow

- **Reads:** `measurements`, `oura_daytime_stress`, `symptoms`
- **Writes:** `analyses/cardiovascular/intraday_stress_*.{md,png}`

## Limitations

Heuristic method: Garmin stress and Oura recovery are proprietary scores without published validation studies; aggregation over many days loses day-specific variation; no causal conclusions.

## References

- Thayer JF, Åhs F, Fredrikson M, Sollers JJ, Wager TD (2012). A meta-analysis of heart rate variability and neuroimaging studies: implications for heart rate variability as a marker of stress and health. Neuroscience & Biobehavioral Reviews, 36(2), 747-756. doi:10.1016/j.neubiorev.2011.11.009
- Kim HG, Cheon EJ, Bai DS, Lee YH, Koo BH (2018). Stress and heart rate variability: a meta-analysis and review of the literature. Psychiatry Investigation, 15(3), 235-245. doi:10.30773/pi.2017.08.17

## Usage

```bash
python analyse_intraday_stress.py
python analyse_intraday_stress.py --help
python analyse_intraday_stress.py --from 2024-01-01 --to 2024-12-31
```
