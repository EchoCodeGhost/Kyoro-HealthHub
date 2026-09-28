# Sleepapnoe-Screening & SpO2-Analyse (Multi-Source)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/sleep/analyse_sleep_apnea.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Multi-source sleep apnoea screening from Apple Watch, Oura, Garmin, Polar, Sleep Cycle and Somneo environment data. sleep_spo2_min reported separately as sleep-specific SpO2 minimum, labelled with its actual source.

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

Daily aggregates of breathing events and SpO2 per source; snoring and noise from Sleep Cycle and Somneo; Spearman cross-correlations. WHO Lnight via Leq energy averaging (10*log10(mean(10^(dB/10)))) from raw Somneo timestamps, both in the actual sleep window and the fixed WHO 23:00–07:00 window. No polysomnography validation.

## Scoring

```
Breathing disturbances: >1/h notable | >5/h mild sleep apnea | >15/h moderate | >30/h severe (AASM classification)
SpO2: >=95% normal | 90-94% notable | <90% critical (night average)
Oura BDI: <10 normal | 10-20 mild | >20 needs evaluation
WHO Lnight: <40 dB target | <55 dB interim target | >=55 dB above interim target (WHO Environmental Noise Guidelines for the European Region 2018)
```

## Data flow

- **Reads:** `apple_records`, `measurements`, `sessions`, `session_metrics`, `home_environment_ts`
- **Writes:** `analyses/sleep/*.{md,png}`

## Limitations

Heuristic method: Not a validated AHI substitute. Optical SpO2 accuracy is limited during desaturation. AHI thresholds 5/15/30 per AASM Berry 2012 — applied heuristically to wearable data. Sleep Cycle snoring is not person-specific (microphone picks up partner). Somneo is placed on the user's side of the bed — primarily user-proximate but not fully isolated from loud partner snoring. The fixed WHO 23:00–07:00 window is an approximation relative to the sleep date, not individually calibrated to actual bedtime. Not a substitute for polysomnography.

## References

- Berry RB, Budhiraja R, Gottlieb DJ et al. (2012). Rules for Scoring Respiratory Events in Sleep: Update of the 2007 AASM Manual for the Scoring of Sleep and Associated Events. Journal of Clinical Sleep Medicine, 8(5):597-619. doi:10.5664/jcsm.2172
- WHO Regional Office for Europe 2018, Environmental Noise Guidelines for the European Region, ISBN 978-92-890-5356-3

## Usage

```bash
python analyse_sleep_apnea.py
python analyse_sleep_apnea.py --help
python analyse_sleep_apnea.py --from 2024-01-01 --to 2024-12-31
```
