# Sleep-Staging & nächtliche HRV-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/sleep/analyse_sleep_polar.py`

**Evidence tier:** calibrated (literature-based + parameters tuned to personal baselines, no external validation)

## Purpose

Analyses Polar sleep architecture (deep/REM/light/wake), nightly HRV course and Polar sleep score and their correlation with recovery and symptoms.

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

Reads Polar hypnogram sequences (2-minute intervals) and HRV time series; aggregates sleep stage proportions and correlates with next-day metrics. Polar-specific proprietary algorithm.

## Data flow

- **Reads:** `polar_sleep_hypnogram`, `polar_nightly_hrv_series`, `polar_sleep_score`, `sessions`, `session_metrics`
- **Writes:** `analyses/sleep/*.{md,png}`

## Limitations

Polar sleep staging is not AASM-certified and shows lower accuracy than polysomnography. No external validation of the Polar reference values used.

## References

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)

## Usage

```bash
python analyse_sleep_polar.py
python analyse_sleep_polar.py --help
python analyse_sleep_polar.py --from 2024-01-01 --to 2024-12-31
```
