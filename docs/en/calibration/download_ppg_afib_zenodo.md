# Long-term wrist-PPG AFib dataset download (Zenodo record 5815074)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/calibration/download_ppg_afib_zenodo.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Downloads the open-access Zenodo dataset "Long-term electrocardiogram and wrist-based photoplethysmogram recordings with annotated atrial fibrillation episodes" (8 patients, 5-8 days, ~1306 hours ECG+PPG+ACC, beat-to-beat AFib annotation) for Dash 2009 calibration.

## Relevance

Enables download of reference data, essential for calibration and validation

## Method

Single download of Data.zip (~7 GB) from Zenodo, extracted to data/calibration/zenodo_afib_ppg/. No login/credentialing required (unlike many PhysioNet datasets).

## Data flow

- **Reads:** `https://zenodo.org/records/5815074`, `(online)`
- **Writes:** `data/calibration/zenodo_afib_ppg/ (MAT-Dateien + subject_info.xlsx + LICENSE.txt)`

## Limitations

LICENSE: "Other (Non-Commercial)" — dataset usable for non-commercial research/calibration only, see downloaded LICENSE.txt. Raw data therefore stays in .gitignore (data/calibration/zenodo_afib_ppg/); only the distilled thresholds (dash2009_thresholds.json) get committed. ~7 GB download, requires internet connection.

## References

- Bacevičius J, Abramikas Ž, Badaras I et al. (2022). Long-term electrocardiogram and wrist-based photoplethysmogram recordings with annotated atrial fibrillation episodes [Data set]. Zenodo. doi:10.5281/zenodo.5815074

## Usage

```bash
python3 scripts/calibration/download_ppg_afib_zenodo.py
python3 calibration/download_ppg_afib_zenodo.py  # from inside scripts/
```
