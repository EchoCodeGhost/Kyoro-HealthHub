# Omron Connect → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_omron.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports blood pressure measurements from Omron Connect CSV exports into health.db. Supplements Apple Health with specific Omron data such as IHB flag, possible atrial fibrillation (AFib), TruRead, and complete measurement series.

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads CSV files from the Omron directory and parses blood pressure measurements. Supports Omron AFib-capable blood pressure monitors. Additional data: IHB (Irregular Heartbeat), AFib detection, TruRead (multiple measurements), complete measurement series.

## Data flow

- **Reads:** `{imports/omron/}*.csv`, `(Omron`, `Connect`, `Export)`
- **Writes:** `health.db (blood_pressure)`

## Limitations

No validation of Omron data quality. Dependent on the correctness of the CSV export. No medical evaluation from IHB/AFib data.

## Usage

```bash
python3 import_omron.py                   # all CSVs in Omron/
python3 import_omron.py --update          # only neue Daten
python3 import_omron.py --file export.csv
```
