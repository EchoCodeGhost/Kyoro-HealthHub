# Daily Stress Analysis — Multi-source stress index computation (v2 schema).

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_stress.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Computes a daily stress index (0–100) from HRV, resting heart rate, sleep and training load across multiple sources.

## Relevance

Enables stress analysis, essential for mental well-being

## Method

RMSSD as daily mean from ppi_hrv_advanced (artifact-/ectopy-corrected 5-minute windows; falls back to naive daily ppi_raw RMSSD when window coverage is missing, then nightly Oura), SDNN from Apple Watch, resting HR as 24/7 HR percentile or device resting_heart_rate, sleep from the sleep view, Garmin daily stress as a correction factor. Combined into an index (higher = more stress). The HRV components (RMSSD, SDNN) are based on established HRV metrics (Task Force 1996).

## Scoring

```
stress_index = combined(HRV, resting_HR, sleep, training_load, garmin_stress)
range 0-100, higher = more stress
```

## Data flow

- **Reads:** `measurements`, `ppi_raw`, `ppi_hrv_advanced`, `sleep`, `training`, `daily_stress`
- **Writes:** `daily_stress`

## Limitations

Heuristic method: Proprietary combined index, not validated. Component weighting is heuristic; source-dependent coverage affects comparability over time. HRV-based components use established metrics (Task Force 1996).

## References

- Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Heart Rate Variability. Circulation, 93(5):1043-1065. doi:10.1161/01.CIR.93.5.1043

## Usage

```bash
python compute_stress.py
python compute_stress.py --from 2025-01-01 --to 2025-12-31
python compute_stress.py --person self
```
