# Arrhythmia-Muster & Trigger-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_arrhythmia.py`

**Evidence tier:** calibrated (literature-based + parameters tuned to personal baselines, no external validation)

## Purpose

Analyses patterns, frequency, time-of-day distribution and trigger associations of detected arrhythmia episodes from the Polar PPI data stream.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Reads from compute_arrhythmia-generated arrhythmie_episoden; correlates episode days with HRV (RMSSD), stress score, sleep efficiency and SpO2 via group comparison (episode day vs. non-episode day).

## Data flow

- **Reads:** `arrhythmie_episoden`, `daily_stress`, `symptoms`, `sessions`, `session_metrics`, `polar_nightly_hrv`
- **Writes:**

  ```
  analyses/cardiovascular/*.{md,png}, analyses/cardiovascular/episodes/*.png
  (--plot-episodes: Tachogramm+Lorenz-Plot pro Episode, Quelle via
  identity_resolver menschenlesbar beschriftet) (kein DB-Write)
  ```

## Limitations

CV-based episode detection is not a clinical ECG; Polar data may contain motion artefacts. All correlations are exploratory (n=1).

## References

- Perez MV, Mahaffey KW, Hedlin H et al. (2019). Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation. New England Journal of Medicine, 381(20):1909-1917. doi:10.1056/NEJMoa1901183
- Tateno & Glass 2001, Med Biol Eng Comput (Erkennungsmethode hinter den hier analysierten arrhythmie_episoden, s. compute_arrhythmia.py),
- Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439
- Malmivuo J, Plonsey R (1995). Bioelectromagnetism: Principles and Applications of Bioelectric and Biomagnetic Fields. Oxford University Press, New York. ISBN 978-0-19-505823-9 (kein DOI verfügbar)

## Usage

```bash
python analyse_arrhythmia.py
python analyse_arrhythmia.py --help
python analyse_arrhythmia.py --from 2024-01-01 --to 2024-12-31
python analyse_arrhythmia.py --plot-episodes --detection-method bigeminy_rr_alternation --from 2026-09-01
python analyse_arrhythmia.py --plot-episodes --max-episode-plots 50
```
