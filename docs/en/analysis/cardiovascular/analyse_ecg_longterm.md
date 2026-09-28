# Polar H10 Langzeit-Analyse (5-days-Monitoring)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cardiovascular/analyse_ecg_longterm.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Evaluates multi-day Polar H10 continuous recordings: hourly RMSSD, daily HRV summary (sleep vs. day), post-exertion reactions and arrhythmia indicators.

## Relevance

Enables cardiovascular analysis, essential for cardiac diagnostics

## Method

Hourly aggregation of ppi_raw; RMSSD and CV-RR per hour; post-workout HRV trend in subsequent hours. CV > 0.15 as arrhythmia window (heuristic). Comparison with polar_nightly_hrv as historical baseline.

## Scoring

```
Arrhythmie-Fenster: CV-RR > 0,15 je Stunde (heuristisch)
Tagesklassifikation: arrhythmia_stunden > 2 = Auffälligkeit (heuristisch)
RMSSD-Methode: Task Force ESC/NASPE 1996 (doi:10.1161/01.CIR.93.5.1043)
Basis: CV-Schwelle und Stunden-Grenze projektintern, kein publizierter Schwellenwert
```

## Data flow

- **Reads:** `ppi_raw`, `polar_nightly_hrv`, `air_quality`, `pollen`, `indoor_environment`
- **Writes:** `analyses/cardiovascular/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: CV threshold 0.15 is heuristic, not derived from clinical studies. Arrhythmia-hours threshold (>2 h) is heuristic. RMSSD computation: validated per Task Force ESC/NASPE 1996 (doi:10.1161/01.CIR.93.5.1043). Multi-day wearing of H10 is practically limited (comfort, battery). Not a clinical Holter ECG. n=1, consumer sensors.

## References

- Task Force of the ESC and NASPE (1996). Heart rate variability.
- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart Rate Variability. Circulation, 93(5):1043-1065. doi:10.1161/01.CIR.93.5.1043

## Usage

```bash
python analyse_ecg_longterm.py
python analyse_ecg_longterm.py --help
python analyse_ecg_longterm.py --from 2024-01-01 --to 2024-12-31
```
