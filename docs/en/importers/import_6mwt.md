# 6-Minuten-Gehtest (6MWT) → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_6mwt.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports results of the 6-Minute Walk Test (6MWT) as a standardized outcome measure for ME/CFS, Long COVID, and heart failure. Monthly execution shows functional capacity over time.

## Relevance

Enables import of health data, essential for comprehensive data analysis Enables import of health data, essential for comprehensive data analysis

## Method

Protocol according to ATS 2002 standard (modified for home use): 1) Sit for 10 min → measure resting HR, SpO2, Borg 2) Walk as far as possible in 6 minutes (flat surface) 3) Breaks allowed (time continues, stops documented) 4) After 6 min: measure distance, HR, SpO2, Borg 5) Sit for 1 min: measure recovery HR CSV format: ts,distance_m,hr_rest,hr_peak,hr_recovery,spo2_pre, spo2_post,borg_pre,borg_post,stops,notes

## Data flow

- **Reads:** `{imports/6mwt/}*.csv`, `(6MWT`, `Ergebnisse)`
- **Writes:** `health.db (functional_tests)`

## Limitations

No automatic evaluation of 6MWT results. Reference values are for orientation only. No medical diagnosis.

## References

- American Thoracic Society (2002). ATS Statement: Guidelines for the Six-Minute Walk Test. American Journal of Respiratory and Critical Care Medicine, 166(1):111-117. doi:10.1164/ajrccm.166.1.at1102

## Usage

```bash
python3 import_6mwt.py                    # alle CSVs
python3 import_6mwt.py --manual           # interaktive Eingabe
python3 import_6mwt.py --template         # CSV-Vorlage ausgeben
python3 import_6mwt.py --file test.csv    # einzelne Datei
```
