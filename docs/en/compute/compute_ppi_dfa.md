# Detrended Fluctuation Analysis (DFA) on ppi_raw (Polar H10 / ECG Logger).

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_ppi_dfa.py`

**Evidence tier:** research (peer-reviewed literature basis, but no formal clinical validation study with endpoints)

## Purpose

Computes DFA alpha1/alpha2 per 5-minute window as a marker of atrial fibrillation and autonomic regulation from beat-to-beat intervals.

## Relevance

Enables pulse-pulse interval data analysis, essential for HRV analysis

## Method

alpha1 over scales 4-16 (Kubios standard), alpha2 over 16-64. alpha2 stays NULL for windows with < 256 beats.

## Thresholds

| Value | Meaning |
|---|---|
| `Ruhe (is_training=0):` |  |
| `alpha1 < 0.75` | [research] AFib indicator / loss of fractal memory — mechanistic rationale (Ho 1997); no prospective diagnostic study with sensitivity/specificity; combine with additional AFES signals |
| `alpha1 < 0.85` | [research] mortality predictor; validated for post-AMI with EF<35% (Mäkikallio 1999); use as reference value for other user profiles, clinical interpretation depends on individual context |
| `alpha1 ~ 1.0` | normal sinus rhythm (1/f noise) |
| `alpha1 > 1.2` | pathological rigidity (e.g. severe heart failure) |
| `Training (is_training=1):` |  |
| `alpha1 < 0.75` | [validated] HRVT1 – aerobic threshold exceeded; validated against lactate reference in healthy, athletic and cardiac populations (Rogers & Gronwald 2022); use as approximation in autonomic dysfunction or conditions with altered HRV dynamics |
| `alpha1 < 0.50` | [validated] HRVT2 – anaerobic threshold exceeded; validated against VT2/MLSS in exercise studies (Sempere-Ruiz 2024); applicability to clinical populations depends on individual context |

## Data flow

- **Reads:** `ppi_raw`
- **Writes:**

  ```
  ppi_dfa: window_start TEXT, person TEXT, device TEXT, n_beats INT,
  alpha1 REAL, alpha2 REAL, is_training INT, mean_hr_bpm REAL, computed_at TEXT
  measurements: dfa_alpha1_rest_{avg,min,pct_low,pct_risk},
  dfa_alpha1_train_{avg,min,pct_at,pct_hrvt2}, dfa_hrvt1, dfa_hrvt2
  ```

## Limitations

DFA with scales 4-16 systematically yields alpha1 ≈ 0.58 for uncorrelated series instead of the theoretical 0.50 (known finite-scale bias; same in Kubios). Since published thresholds were derived with identical scales, the bias is absorbed into the threshold values — absolute alpha1 values should only be compared intra-individually. Real beat-to-beat data only (ppi_raw); optical HR sensors unsuitable. Known empty result: a 5-minute window needs _MIN_BEATS (100) contiguous beats (gap <= _GAP_S). In this DB, ppi_raw mostly comes from short, ECG-session-linked captures (seconds to a few tens of seconds per recording), not continuous chest-strap streaming — the longest contiguous beat run stays below _MIN_BEATS. For such periods ppi_dfa correctly stays empty; this is not a script bug but missing input data (see pipeline-architecture: "Silent empty results as known behavior" — this script explicitly logs the window count instead of running silently). Remedy only via actually wearing a continuous chest strap/ECG logger, not by artificially populating the table. Training windows are flagged (is_training=1) and ignored by AFES. HRVT1/HRVT2 (alpha1=0.75/0.50) prospectively validated against lactate/VT2 in healthy, athletic and cardiac populations (Rogers 2022, Sempere-Ruiz 2024). In autonomic dysfunction alpha1 is already reduced at rest, pulling HRVT close to resting HR — not a valid AT in this case (dysautonomia margin check in compute_pem.py). alpha1 < 0.85 (Mäkikallio 1999): prospective validation for post-AMI with EF<35%; usable as reference value for other user profiles; clinical interpretation requires individual context. alpha1 < 0.75 at rest as AFib indicator: mechanistically sound, no prospective diagnostic study with published sensitivity/specificity — combine with additional AFES signals for context.

## References

- Peng CK, Havlin S, Stanley HE, Goldberger AL (1995). Quantification of scaling exponents and crossover phenomena in nonstationary heartbeat time series. Chaos: An Interdisciplinary Journal of Nonlinear Science, 5(1):82-87. doi:10.1063/1.166141
- Ho KKL, Moody GB, Peng CK et al. (1997). Predicting Survival in Heart Failure Case and Control Subjects by Use of Fully Automated Methods for Deriving Nonlinear and Conventional Indices of Heart Rate Dynamics. Circulation, 96(3):842-848. doi:10.1161/01.CIR.96.3.842
- Mäkikallio TH, Høiber S, Køber L et al. (1999). Fractal analysis of heart rate dynamics as a predictor of mortality in patients with depressed left ventricular function after acute myocardial infarction. The American Journal of Cardiology, 83(6):836-839. doi:10.1016/s0002-9149(98)01076-5
- Gronwald T, Hoos O (2019). Correlation properties of heart rate variability during endurance exercise: A systematic review. Annals of Noninvasive Electrocardiology, 25(1). doi:10.1111/anec.12697
- Rogers B, Gronwald T (2022). Fractal Correlation Properties of Heart Rate Variability as a Biomarker for Intensity Distribution and Training Prescription in Endurance Exercise: An Update. Frontiers in Physiology, 13. doi:10.3389/fphys.2022.879071
- Sempere-Ruiz N, Sarabia JM, Baladzhaeva S, Moya-Ramón M (2024). Reliability and validity of a non-linear index of heart rate variability to determine intensity thresholds. Frontiers in Physiology, 15. doi:10.3389/fphys.2024.1329360

## Usage

```bash
python compute_ppi_dfa.py                            # recompute all
python compute_ppi_dfa.py --update                   # from last entry
python compute_ppi_dfa.py --recompute                # overwrite existing
python compute_ppi_dfa.py --from 2026-05-01 --to 2026-06-03
```
