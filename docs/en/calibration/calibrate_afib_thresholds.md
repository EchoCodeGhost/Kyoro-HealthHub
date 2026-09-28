# AFib Level-1 Schwellenwert-Kalibrierung

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/calibration/calibrate_afib_thresholds.py`

**Evidence tier:** calibrated (literature-based + parameters tuned to personal baselines, no external validation)

## Purpose

Calibrates thresholds for AFib detection using MIT-BIH AFDB database

## Relevance

Enables calibration of algorithms and thresholds, essential for data quality

## Method

Calibrates AFib Level-1 thresholds using MIT-BIH Atrial Fibrillation Database. 25 records × ~10h each, 250 Hz, with rhythm annotations. Computes optimal thresholds for 5 HRV metrics.

## Data flow

- **Reads:** `MIT-BIH`, `AFDB-Datenbank`, `aus`, `data/calibration/afdb/`
- **Writes:** `data/calibration/afdb_thresholds.json, data/calibration/afdb_calibration.csv, data/calibration/afdb_roc.png`

## Limitations

Calibration based on AFDB data. Validity for other datasets not guaranteed.

## References

- Moody GB, Mark RG (2001). The impact of the MIT-BIH Arrhythmia Database. IEEE Engineering in Medicine and Biology Magazine, 20(3):45-50. doi:10.1109/51.932724
- Goldberger AL, Amaral LAN, Glass L et al. (2000). PhysioBank, PhysioToolkit, and PhysioNet. Circulation, 101(23). doi:10.1161/01.CIR.101.23.e215

## Usage

```bash
cd ~/Kyoro-HealthHub/scripts
python3 calibration/calibrate_afib_thresholds.py
```
