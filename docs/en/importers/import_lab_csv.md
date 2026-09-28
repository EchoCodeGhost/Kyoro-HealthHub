# Manuelle Laborbefund-CSVs → health.db (lab_manual)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_lab_csv.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Import manually recorded lab results from CSV files for longitudinal analysis

## Relevance

Enables import of laboratory results, essential for integration of clinical data

## Method

Parse CSV files with fixed format (header mandatory). Comment lines (starting with #) are skipped. Numeric values are parsed as float, textual values as string. Storage in lab_manual table with PRIMARY KEY (date, parameter, labor, person).

## Data flow

- **Reads:** `medicine/laborbefunde/*_labor.csv`, `imports/manual/labor*.csv`
- **Writes:** `health.db:lab_manual, health.db:import_log`

## Limitations

Only processes files with all mandatory fields (date, parameter, value). Duplicate entries (same date, parameter, lab, person) are ignored. OCR-corrected files must comply with validation rules.

## Usage

```bash
python3 import_lab_csv.py                    # alle CSVs in Standardverzeichnissen
python3 import_lab_csv.py --update           # nur neue (ignoriert via PRIMARY KEY)
python3 import_lab_csv.py --file /pfad.csv   # einzelne Datei
python3 import_lab_csv.py --dry-run          # Vorschau ohne DB-Schreibzugriff
```
