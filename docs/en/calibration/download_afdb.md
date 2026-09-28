# MIT-BIH AFDB-Datenbank Download

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/calibration/download_afdb.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Downloads all 25 records from MIT-BIH Atrial Fibrillation Database from PhysioNet

## Relevance

Enables download of reference data, essential for calibration and validation

## Method

Downloads all 25 records from MIT-BIH AFDB database from PhysioNet. Records are saved to data/calibration/afdb/. Skips already existing files.

## Data flow

- **Reads:** `PhysioNet`, `AFDB-Datenbank`, `(online)`
- **Writes:** `data/calibration/afdb/ (HEA-Dateien und zugehörige Daten)`

## Limitations

Requires internet connection and wfdb library.

## References

- Goldberger AL, Amaral LAN, Glass L et al. (2000). PhysioBank, PhysioToolkit, and PhysioNet. Circulation, 101(23). doi:10.1161/01.CIR.101.23.e215

## Usage

```bash
python3 scripts/calibration/download_afdb.py
python3 calibration/download_afdb.py  # from scripts/ directory
```
