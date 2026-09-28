# DFA Alpha1 & Autonome Komplexität

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_dfa_alpha1.py`

**Evidence tier:** calibrated (literature-based + parameters tuned to personal baselines, no external validation)

## Purpose

Analyses advanced HRV metrics from the PPI data stream: DFA Alpha1/Alpha2, sample entropy, LF/HF ratio and SD1/SD2 as long-term markers of autonomic regulation and system complexity.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Reads from compute_ppi_dfa-generated ppi_dfa (alpha1/alpha2) and ppi_hrv_advanced (SampEn, LF/HF, SD1/SD2). Thresholds (α1 < 0.75; 0.85; 1.0; 0.50) from published studies (Mäkikallio, Gronwald, Sempere-Ruiz).

## Data flow

- **Reads:** `ppi_dfa`, `ppi_hrv_advanced`
- **Writes:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Limitations

Original thresholds derived from clinical populations (post-AMI, sport); Ruijgt et al. 2026 supports transferability specifically for the Long-COVID/PEM context (n=121), but does not replace individual calibration. Polar H10 beat-to-beat data may contain ectopic artefacts. n=1.

## References

- Peng CK, Havlin S, Stanley HE, Goldberger AL (1995). Quantification of scaling exponents and crossover phenomena in nonstationary heartbeat time series. Chaos: An Interdisciplinary Journal of Nonlinear Science, 5(1):82-87. doi:10.1063/1.166141
- Ho KKL, Moody GB, Peng CK et al. (1997). Predicting Survival in Heart Failure Case and Control Subjects by Use of Fully Automated Methods for Deriving Nonlinear and Conventional Indices of Heart Rate Dynamics. Circulation, 96(3):842-848. doi:10.1161/01.CIR.96.3.842
- Mäkikallio TH, Høiber S, Køber L et al. (1999). Fractal analysis of heart rate dynamics as a predictor of mortality in patients with depressed left ventricular function after acute myocardial infarction. The American Journal of Cardiology, 83(6):836-839. doi:10.1016/s0002-9149(98)01076-5
- Gronwald T, Hoos O (2019). Correlation properties of heart rate variability during endurance exercise: A systematic review. Annals of Noninvasive Electrocardiology, 25(1). doi:10.1111/anec.12697
- Sempere-Ruiz N, Sarabia JM, Baladzhaeva S, Moya-Ramón M (2024). Reliability and validity of a non-linear index of heart rate variability to determine intensity thresholds. Frontiers in Physiology, 15. doi:10.3389/fphys.2024.1329360
- Ruijgt TM, Slaghekke A, Ellens A, Janssen KW, Wüst RCI (2026). Wearable Heart Rate Variability Monitoring, Autonomic Dysfunction and Post-exertional Malaise in Long COVID: An Observational Study. Sports Medicine, online ahead of print. doi:10.1007/s40279-026-02487-4 (peer-reviewed; n=121 Long-COVID + 21 Kontrollen; HRV bleibt nach Belastung nahe/über der ersten ventilatorischen Schwelle einen vollen Tag supprimiert — stützt DFA-α1-Schwelle 0.75 speziell für Long-COVID/PEM-Kontext, nicht nur post-AMI/Leistungssport)

## Usage

```bash
python analyse_dfa_alpha1.py
python analyse_dfa_alpha1.py --help
python analyse_dfa_alpha1.py --from 2024-01-01 --to 2024-12-31
```
