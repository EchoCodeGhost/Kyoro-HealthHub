# Polar H7 — 24h-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_ecg_24h.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Evaluates 24-hour recordings from the Polar H7 chest strap: hourly RMSSD, CV-RR, heart rate profile, arrhythmia windows and comparison with historical baseline.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Hourly aggregation of ppi_raw; RMSSD and CV-RR computed per hour. Arrhythmia windows: CV > 0.15 (heuristic threshold, not validated). Comparison with polar_nightly_hrv as baseline. The daily min/max HR (60000/max resp. 60000/min of the pulse intervals across the whole day) is local-median-filtered via modules/rr_interval_algorithms.filter_beat_artifacts before computation — found while developing compute_orthostatic_detection.py: a single isolated, very short pulse interval (a device/import floor-value artifact) would otherwise show up as the daily max HR, regardless of genuine physiology.

## Scoring

```
Arrhythmie-Fenster: CV-RR > 0,15 je Stunde (heuristisch)
RMSSD-Methode: Task Force ESC/NASPE 1996 (doi:10.1161/01.CIR.93.5.1043)
Basis: CV-Schwelle projektintern, kein publizierter Schwellenwert
```

## Data flow

- **Reads:** `ppi_raw`, `air_quality`, `pollen`, `indoor_environment`
- **Writes:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: CV threshold 0.15 is heuristic, not derived from clinical studies. Polar H7 PPI may contain motion artefacts. Not a clinical Holter ECG. n=1, consumer sensors, single recording. RMSSD computation: validated per Task Force ESC/NASPE 1996 (doi:10.1161/01.CIR.93.5.1043).

## References

- Task Force of the ESC and NASPE (1996). Heart rate variability.
- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart Rate Variability. Circulation, 93(5):1043-1065. doi:10.1161/01.CIR.93.5.1043

## Usage

```bash
python analyse_ecg_24h.py
python analyse_ecg_24h.py --help
python analyse_ecg_24h.py --from 2024-01-01 --to 2024-12-31
```
