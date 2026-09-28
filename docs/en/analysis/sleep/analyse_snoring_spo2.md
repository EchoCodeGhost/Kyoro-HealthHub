# Snoring × Breathing disturbances — Sleepapnoe-Screening

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/sleep/analyse_snoring_spo2.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses snoring and breathing interruptions from Sleep Cycle app data as a heuristic sleep apnoea screening with AHI estimation.

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

AHI estimation = breathing_disrupt / (time_asleep_s / 3600); snoring classification by fraction of sleep duration; AASM thresholds (5/15/30) applied as orientation to app data.

## Scoring

```
AHI estimation: breathing_disrupt / (time_asleep_s / 3600) events per hour
AHI classification: <5 normal | 5-15 mild | 15-30 moderate | >30 severe (AASM Berry 2012)
Snoring fraction: snore_s / time_asleep_s percentage of sleep time
```

## Data flow

- **Reads:** `sessions`, `session_metrics`
- **Writes:** `analyses/sleep/*.{md,png}`

## Limitations

Heuristic method: Sleep Cycle app is not a clinically validated instrument; no SpO2 available; AHI estimate does not distinguish apnoeas from hypopnoeas. AHI thresholds (5/15/30) are AASM PSG classification (Berry 2012) — transfer to app data is heuristic. Sleep lab required for assessment.

## References

- Berry RB, Budhiraja R, Gottlieb DJ et al. (2012). Rules for Scoring Respiratory Events in Sleep: Update of the 2007 AASM Manual for the Scoring of Sleep and Associated Events. Journal of Clinical Sleep Medicine, 8(5):597-619. doi:10.5664/jcsm.2172

## Usage

```bash
python analyse_snoring_spo2.py
python analyse_snoring_spo2.py --help
python analyse_snoring_spo2.py --from 2024-01-01 --to 2024-12-31
```
