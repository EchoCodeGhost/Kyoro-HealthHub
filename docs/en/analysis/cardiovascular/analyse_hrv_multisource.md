# Multi-Source HRV-Vergleich — Polar vs. Oura vs. Apple Watch vs. Kubios

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_hrv_multisource.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Compares HRV RMSSD values from Polar, Oura, Apple Watch and Kubios on overlapping days, checking consistency, systematic offsets and trends.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Pearson correlation and mean absolute difference between source pairs; descriptive statistics (n, mean, std, min, max) per source; no common calibration standard.

## Scoring

```
Correlation strength: |r| <0.7 poor | 0.7-0.85 moderate | 0.85-0.95 good | >0.95 excellent
Mean absolute difference: lower = better consistency
```

## Data flow

- **Reads:** `polar_nightly_hrv`, `oura_sleep_model`, `measurements`, `kubios_hrv_resting`
- **Writes:** `analyses/cardiovascular/hrv_multisource_*.{md,png}`

## Limitations

Heuristic method: Consumer devices measure HRV in different contexts (sleep vs. spot measurement) and with different algorithms; no gold-standard comparison; DFA/LF-HF metrics only available from Kubios import. Across device types, the validation literature shows PPG-based HRV (watch, ring) systematically deviates from ECG, especially under movement (Hernando et al. 2018; Kinnunen et al. 2020; Gilgen-Ammann et al. 2019) — sources are therefore comparable but not directly interchangeable. CRITICAL: LF/HF ratio is not a valid stress measure at the individual level — LF power does not exclusively reflect sympathetic activity (Billman 2013, doi:10.3389/fphys.2013.00026); LF/HF values are exploratory only.

## References

- Task Force of the ESC/NASPE (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. European Heart Journal, 17(3), 354-381. doi:10.1093/oxfordjournals.eurheartj.a014868
- Billman GE (2013). The LF/HF ratio does not accurately measure cardiac sympatho-vagal balance. Frontiers in Physiology, 4:26. doi:10.3389/fphys.2013.00026 (LF/HF-Ratio: methodische Einschränkungen für Einzelpersonen)
- Hernando D, Roca S, Sancho J, Alesanco Á, Bailón R (2018). Validation of the Apple Watch for heart rate variability measurements during relax and mental stress in healthy subjects. Sensors, 18(8), 2619. doi:10.3390/s18082619 (PPG-Watch vs. EKG)
- Kinnunen H, Rantanen A, Kenttä T, Koskimäki H (2020). Feasible assessment of recovery and cardiovascular health: accuracy of nocturnal HR and HRV assessed via ring PPG in comparison to medical grade ECG. Physiological Measurement, 41(4), 04NT01. doi:10.1088/1361-6579/ab840a (PPG-Ring vs. EKG, Nachtmessung)
- Gilgen-Ammann R, Schweizer T, Wyss T (2019). RR interval signal quality of a heart rate monitor and an ECG Holter at rest and during exercise. European Journal of Applied Physiology, 119(7), 1525-1532. doi:10.1007/s00421-019-04142-5 (Brustgurt-RR-Signalqualität in Ruhe und unter Belastung)

## Usage

```bash
python analyse_hrv_multisource.py
python analyse_hrv_multisource.py --help
python analyse_hrv_multisource.py --from 2024-01-01 --to 2024-12-31
```
