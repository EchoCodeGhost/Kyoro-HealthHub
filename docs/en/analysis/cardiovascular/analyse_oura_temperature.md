# Körpertemperatur-Analyse — Oura, Apple Watch, Polar

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_oura_temperature.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses skin temperature data from Oura, Apple Watch and Polar for patterns patterns, circadian rhythm, cycle-related fluctuations and early warning signals.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Daily aggregate per source; Spearman correlation with cycle phase and symptoms; own fever threshold (--fever-threshold, default 0.5°C Oura deviation); circadian comparison via hourly averages.

## Scoring

```
Fever threshold: >=0.5°C Oura deviation | >=37.0°C Apple Watch wrist temperature
Temperature baseline: personal mean (Oura) | absolute (Apple Watch, Polar)
```

## Data flow

- **Reads:** `oura_temperature_raw`, `measurements`, `symptoms`, `reproductive_health`
- **Writes:** `analyses/cardiovascular/oura_temperature_*.{md,png}`

## Limitations

Heuristic method: Three sources with different scales (deviation vs. absolute) not directly comparable; fever threshold (default 0.5°C Oura deviation) is heuristic; Oura deviation is relative to personal baseline, not an absolute limit; Apple Watch threshold 37.0°C (absolute wrist sleep temperature) is heuristic — skin temperature at the wrist is typically below 37°C and is not a direct surrogate for core body temperature.

## References

- Grant A, Smarr B (2022). Feasibility of continuous distal body temperature for passive, early pregnancy detection. PLOS Digital Health, 1(5), e0000034. doi:10.1371/journal.pdig.0000034 (Zyklus-/Schwangerschaftsbezug)
- Pho GN, Thigpen N, Patel S, Tily H (2023). Feasibility of measuring physiological responses to breakthrough infections and COVID-19 vaccine using a wearable ring sensor. Digital Biomarkers, 1-6. doi:10.1159/000528874 (Ring-Temperaturabweichung als Infektions-Frühwarnsignal)
- Smarr BL, Aschbacher K, Fisher SM, et al. (2020). Feasibility of continuous fever monitoring using wearable devices. Scientific Reports, 10(1):21640. doi:10.1038/s41598-020-78355-6 (peer-reviewt, n=50, gleiche Autor:innengruppe wie Grant/Smarr 2022 oben; periphere Hauttemperatur korreliert mit selbstberichtetem Fieber, Krankheit vor Symptomerkennung feststellbar)

## Usage

```bash
python analyse_oura_temperature.py
python analyse_oura_temperature.py --help
python analyse_oura_temperature.py --from 2024-01-01 --to 2024-12-31
```
