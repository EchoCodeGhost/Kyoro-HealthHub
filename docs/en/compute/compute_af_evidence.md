# AF Evidence Score (AFES) — daily multi-signal evidence for atrial fibrillation.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_af_evidence.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Aggregates multiple daily cardiac signals into an AF evidence score (0–100) to prioritise further work-up — not a clinical diagnosis.

## Relevance

Enables atrial fibrillation analysis, essential for cardiological diagnostics

## Method

Direct evidence (device-based / validated signals) plus weighted supporting heuristics, capped at 100. Each signal is assigned to layer 1 (aggregate) or layer 2 (heuristic).

## Scoring

```
direct  = max(ECG_AFib=50, TG_Episode=40, BP_AFib=40, Burden=30, ECG_HiHR=15)
support = sum(IHB=15, HR_Tachy=20, HR_NightCV=15, RMSSD=10, HR_Range=15,
              Oura_HRVChaos=8, H10_PreAF=8, H10_DFA=15, H10_Poincare=6,
              H10_SampEn=5, H10_Turning=8, SpO2=10, AW_HiHR=10, Resp=5,
              Symptoms=10, SkinTemp=5, NightDip=8)  capped at 50
AFES    = min(100, direct + support)
Die fuenf H10_*-Komponenten sind trotz des Namens (historisch — s.
_load_beat_interval_*) geraeteneutral: die Punktzahl wird je Tag mit dem
Gewicht der tatsaechlichen Sensorklasse multipliziert (voll bei EKG-Klasse,
halb bei 'suspected', 0 bei 'lead'/unbekannt) — s. _weight_by_sensor_class.
```

## Data flow

- **Reads:** `ecg_sessions`, `arrhythmie_episoden`, `blood_pressure`, `measurements`, `ppi_hrv_advanced`, `ppi_dfa`, `symptoms`
- **Writes:**

  ```
  af_evidence_scores: date, person, score, direct_pts, support_pts,
  level, components, signals_used, computed_at
  ```

## Limitations

Heuristic method: Composite score, not clinically validated as a whole. Direct evidence rests on FDA-cleared ECG/burden (Apple) and AFDB-calibrated TG episodes; supporting signals (HR tachycardia, night CV) are unvalidated heuristics (layer 2). Prioritises, does not detect. Even the "direct evidence" layer carries real error: the independent BASEL Wearable Study (Mannhart et al. 2023) found FDA-cleared consumer devices (Apple Watch 6, Samsung Galaxy Watch 3) reach only 85%/75% sensitivity/specificity against a 12-lead ECG, with ~25% of recordings inconclusive — "FDA-cleared" does not mean error-free.

## References

- Perez MV, Mahaffey KW, Hedlin H et al. (2019). Large-Scale Assessment of a Smartwatch to Identify Atrial Fibrillation. New England Journal of Medicine, 381(20):1909-1917. doi:10.1056/NEJMoa1901183
- Tateno K, Glass L (2001). Automatic detection of atrial fibrillation using the coefficient of variation and density histograms of RR and ΔRR intervals. Medical and Biological Engineering and Computing, 39(6):664-671. doi:10.1007/BF02345439
- Castro H, Garcia-Racines JD, Bernal-Norena A (2021). Methodology for the prediction of paroxysmal atrial fibrillation based on heart rate variability feature analysis. Heliyon, 7(11):e08244. doi:10.1016/j.heliyon.2021.e08244
- Ho KKL, Moody GB, Peng CK et al. (1997). Predicting Survival in Heart Failure Case and Control Subjects by Use of Fully Automated Methods for Deriving Nonlinear and Conventional Indices of Heart Rate Dynamics. Circulation, 96(3):842-848. doi:10.1161/01.CIR.96.3.842
- Peng CK, Havlin S, Stanley HE, Goldberger AL (1995). Quantification of scaling exponents and crossover phenomena in nonstationary heartbeat time series. Chaos: An Interdisciplinary Journal of Nonlinear Science, 5(1):82-87. doi:10.1063/1.166141
- Mannhart D, Lischer M, Knecht S et al. (2023). Clinical Validation of 5 Direct-to-Consumer Wearable Smart Devices to Detect Atrial Fibrillation: BASEL Wearable Study. JACC Clinical Electrophysiology, 9(2):232-242. doi:10.1016/j.jacep.2022.09.011

## Usage

```bash
python compute_af_evidence.py
python compute_af_evidence.py --update
python compute_af_evidence.py --from 2025-01-01 --to 2025-12-31
python compute_af_evidence.py --person self --recompute
```
