# health_ecg.py — EKG-Analyse fuer Apple Watch ECG CSVs

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/query/health_ecg.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Analyzes Apple Watch ECG recordings: R-peak detection, heart rate from ECG, RR interval variability, rhythm irregularities

## Relevance

Enables ECG-specific queries, essential for cardiological analysis

## Method

Loads ECG CSV files from Apple ECG directory and performs algorithmic analysis: - Bandpass filter (5-25 Hz) for baseline correction - R-peak detection with dynamic threshold (0.5 SD) - Validation: RR intervals 300-1800ms (33-200 bpm) - HRV metrics: RMSSD, SDNN, pNN50, coefficient of variation - Irregularity metrics: CV_RR, irregularity index Optional: plots (ECG signal + RR tachogram) and detailed metrics (experimental) Shows summary with classifications and PEM warnings.

## Data flow

- **Reads:** `Apple`, `Watch`, `EKG-CSV`, `Dateien`, `aus`, `data/ecg/`, `oder`, `health_config.apple_xml.parent/electrocardiograms/`
- **Writes:** `analyses/ekg/ Verzeichnis (Plots als PNG-Dateien)`

## Limitations

Experimental algorithmic analysis. Results should be interpreted with caution. Depends on Apple Watch ECG data availability.

## Usage

```bash
python health_ecg.py
python health_ecg.py --plot
python health_ecg.py --full
```
