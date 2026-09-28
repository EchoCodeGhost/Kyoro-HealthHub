# Unified sleep hypnogram from Polar, Oura, Apple and Garmin.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_sleep_hypnogram.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Unifies device-reported sleep stages into a common hypnogram schema. No own classification algorithm.

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

Remaps source-specific stage encodings to WAKE/LIGHT/DEEP/REM. The stage classification itself comes from the device algorithms (Polar, Oura), not from this script.

## Data flow

- **Reads:** `polar_sleep_hypnogram`, `oura_sleep_model`, `measurements`, `sessions`
- **Writes:**

  ```
  sleep_hypnogram: session_id, ts, date, stage, duration_s, source,
  device_id, person
  ```

## Limitations

Inherits the accuracy and errors of the consumer-device staging algorithms; no comparison against polysomnography.

## Usage

```bash
python compute_sleep_hypnogram.py
python compute_sleep_hypnogram.py --from 2024-01-01 --to 2024-12-31
python compute_sleep_hypnogram.py --update
```
