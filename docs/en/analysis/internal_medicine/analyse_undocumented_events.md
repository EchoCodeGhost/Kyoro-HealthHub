# Erkennung undokumentierter Gesundheitsereignisse aus Wearable-Metriken (Doppel-Baseline).

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/internal_medicine/analyse_undocumented_events.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Detects potential undocumented health events from wearable metrics using a dual-baseline approach (rolling 42 days + fixed reference period).

## Relevance

Enables health data analysis, essential for medical diagnostics

## Method

Z-score anomaly detection per metric group (median/MAD); composite score across ≥2 groups; flagging at ≥1.8σ against short OR reference baseline; regime-shift detection with 28-day window.

## Scoring

```
Anomaly score: composite >=1.8σ against short OR reference baseline
Metric groups: HRV, RHR, SpO2, activity, sleep (>=2 groups required for flagging)
```

## Data flow

- **Reads:** `measurements`, `sessions`, `session_metrics`, `polar_nightly_hrv`
- **Writes:** `stdout only — keine Datei-Ausgabe`

## Limitations

Heuristic method: Threshold FLAG_Z=1.8σ is heuristic; high false-positive rate during seasonal variation; no causal inference; anomaly ≠ patterns event.

## References

- Goldberger AL, Amaral LAN, Glass L et al. (2000). PhysioBank, PhysioToolkit, and PhysioNet. Circulation, 101(23). doi:10.1161/01.CIR.101.23.e215
- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. Circulation, 93(5), 1043-1065. doi:10.1161/01.CIR.93.5.1043
- Li X, Dunn J, Salins D et al. (2017). Digital Health: Tracking Physiomes and Activity Using Wearable Biosensors Reveals Useful Health-Related Information. PLOS Biology, 15(1):e2001402. doi:10.1371/journal.pbio.2001402

## Usage

```bash
python analyse_undocumented_events.py
python analyse_undocumented_events.py --help
python analyse_undocumented_events.py --from 2024-01-01 --to 2024-12-31
```
