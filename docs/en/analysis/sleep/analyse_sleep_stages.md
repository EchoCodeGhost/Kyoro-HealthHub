# Sleep stage analysis: deep sleep and REM distribution from wearable hypnograms (Garmin, Apple)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/sleep/analyse_sleep_stages.py`

**Evidence tier:** calibrated (literature-based + parameters tuned to personal baselines, no external validation)

## Purpose

Analyses sleep stage distribution from Apple Watch hypnogram and Oura ring with norm comparison (deep/REM, see modules/sleep_norms.py) and correlation with nightly HRV.

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

Aggregates sleep stages from sleep_hypnogram (per night Garmin before Apple, never pooled) and oura_sleep_model; comparison against the shared, cited norm ranges in modules/sleep_norms.py (deep 13-23%, REM 18-25%, same values as analyse_sleep_respiration.py); Pearson correlation with HRV.

## Data flow

- **Reads:** `sleep_hypnogram`, `oura_sleep_model`, `polar_nightly_hrv`
- **Writes:** `analyses/sleep/*.{md,png}`

## Limitations

Wearable sleep staging has lower accuracy than polysomnography; norm values are population averages, not individualised targets (see modules/sleep_norms.py @limits for CI-vs-individual-variance detail). Pre/post event comparison is configurable.

## References

- Boulos MG, Jairam T, Kendzerska T, Im J, Mekhael A, Murray BJ (2019). Normal polysomnography parameters in healthy adults: a systematic review and meta-analysis. Lancet Respiratory Medicine, 7(6):533-543. doi:10.1016/S2213-2600(19)30057-8 (Herleitung der Normbereiche siehe modules/sleep_norms.py)
- Iber C, Ancoli-Israel S, Chesson AL, Quan SF (2007). The AASM Manual for the Scoring of Sleep and Associated Events: Rules, Terminology and Technical Specifications (1st ed.). American Academy of Sleep Medicine, Westchester, IL. (kein DOI verfügbar, Handbuch)
- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043

## Usage

```bash
python analyse_sleep_stages.py
python analyse_sleep_stages.py --help
python analyse_sleep_stages.py --from 2024-01-01 --to 2024-12-31
```
