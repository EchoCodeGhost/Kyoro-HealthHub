# recalibrate.py — Source-Confidence-Scores manuell neu kalibrieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/recalibrate.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Coordinates recalibration of source confidence scores by running compute_calibrate_sources.py and compute_canonical.py. Allows interactive review of calibration results before applying.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Executes two steps: 1) compute_calibrate_sources.py (Pearson-r vs anchor, blend with literature score), 2) compute_canonical.py (recompute golden records). Intentionally not integrated in compute_all.py as calibration is a design decision.

## Data flow

- **Reads:** `Keine`, `direkten`, `Tabellen`, `(koordiniert`, `andere`, `Skripte)`
- **Writes:**

  ```
  Quelle: source_confidence (über compute_calibrate_sources.py),
  sessions, measurements, canonical Daten (über compute_canonical.py)
  ```

## Limitations

Calibration is a design decision. Results should be manually reviewed before applying. No automatic validation.

## Usage

```bash
python3 scripts/recalibrate.py             # interaktiv: Report zeigen, dann fragen
python3 scripts/recalibrate.py --yes       # direkt durchlaufen ohne Bestätigung
python3 scripts/recalibrate.py --dry-run   # nur Report, keine Änderungen
```
