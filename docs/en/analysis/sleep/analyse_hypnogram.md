# Schlaf-Hypnogramm-Visualisierung

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/sleep/analyse_hypnogram.py`

**Evidence tier:** calibrated (literature-based + parameters tuned to personal baselines, no external validation)

## Purpose

Visualises sleep hypnograms from compute-generated sleep_hypnogram data as single-night step plots or deep sleep/REM time series.

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

Step plot of sleep stages (WAKE/REM/LIGHT/DEEP) per source; trend aggregation over sum of duration_s per stage; multi-source comparison (Polar, Oura, Apple).

## Data flow

- **Reads:** `sleep_hypnogram`
- **Writes:** `analyses/sleep/hypnogram_*.{md,png}`

## Limitations

Staging quality depends on each device's algorithm; optical PPG-based staging accuracy is substantially below PSG standard (~70–80%); no gold-standard comparison.

## References

- Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)
- Goldstone A, Baker FC, de Zambotti M (2018). Actigraphy in the digital health revolution: still asleep? Sleep, 41(9). doi:10.1093/sleep/zsy120

## Usage

```bash
python analyse_hypnogram.py
python analyse_hypnogram.py --help
python analyse_hypnogram.py --from 2024-01-01 --to 2024-12-31
```
