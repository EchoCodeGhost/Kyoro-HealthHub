# Detaillierte EKG-Analyse — Apple Watch ECG Sessions

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_ecg_detail.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses Apple Watch ECG sessions: classification distribution, temporal clustering, time-of-day distribution, PPI analysis for AFib windows and cross-reference with arrhythmie_episoden.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Normalisation of Apple Watch classifications (atrial_fibrillation / sinus_rhythm / high_hr / inconclusive); group and time-series analysis. No independent arrhythmia classification — pure evaluation of existing labels.

## Scoring

```
ECG classification: sinus_rhythm | atrial_fibrillation | high_hr | inconclusive
AFib indicator: CV > 10% in PPI data (heuristic threshold)
Artifact-suspect (excluded from findings): CV-RR > 50% or RMSSD > 200 ms per window
```

## Data flow

- **Reads:** `ecg_sessions`, `ppi_raw`, `arrhythmie_episoden`
- **Writes:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: Apple Watch ECG (Series 4+) is FDA-cleared for rhythm analysis in adults (FDA De Novo K172503, 2018). Detects rhythm patterns only in explicit 30-second recordings; intermittent episodes may be missed. CV > 10% as indicator for consumer PPI data: heuristic threshold, project-internal — no clinically validated cut-off. n=1. IMPORTANT — two independent bases in the same report: the device classification (Section 1) comes from the raw ECG waveform (electrical signal); the CV-RR/RMSSD metrics in Section 5 come from ppi_raw (optical pulse-to-pulse intervals, different measurement principle, temporally close but independent window). A high CV/RMSSD there does NOT automatically contradict a "sinus rhythm" classification — Section 5 states this explicitly. Per-window plausibility check (Section 5): CV-RR > 50% or RMSSD > 200 ms are considered outside what occurs in documented rhythm classes (sinus, AFib) and are flagged as artifact-suspect instead of being printed as a finding (_CV_IMPLAUSIBLE_PCT / _RMSSD_IMPLAUSIBLE_MS in this script). Rationale: documented AFib cohorts typically reach CV-RR ~15-30%, occasionally up to ~40% (Task Force ESC/NASPE 1996; arrhythmia_utils.CV_AFIB_HIGH=15% as "highly AFib-suspect" in this project); the theoretical maximum under ppi_raw's 350-2000 ms filter is ~70%, but that does not occur physiologically. RMSSD at healthy rest is ~20-100 ms, and rarely exceeds ~150-200 ms even in cardiac-compromised cohorts. These thresholds are heuristic/project-internal, not a published diagnostic cut-off — they separate "plausible measurement" from "artifact", not "healthy" from "diseased". n=1.

## References

- FDA De Novo Authorization K172503 (2018). Apple Watch ECG for AFib detection. https://www.accessdata.fda.gov/cdrh_docs/reviews/DEN170037.pdf
- Task Force of the ESC and NASPE (1996). Heart rate variability.
- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart Rate Variability. Circulation, 93(5):1043-1065. doi:10.1161/01.CIR.93.5.1043

## Usage

```bash
python analyse_ecg_detail.py
python analyse_ecg_detail.py --help
python analyse_ecg_detail.py --from 2024-01-01 --to 2024-12-31
```
