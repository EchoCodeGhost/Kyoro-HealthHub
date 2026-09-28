# DRV-Reha-Kliniken → LibreOffice-Calc-Export

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/drv_kliniken_export_ods.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Exports the kliniken.json produced by drv_kliniken_parse.py as an .ods spreadsheet with AutoFilter enabled, for manually browsing and filtering the rehab clinics in LibreOffice Calc.

## Relevance

Provides a browsable reference for rehabilitation planning, no direct relevance to personal health data

## Method

Only defines the column mapping and delegates the actual sheet construction (odfpy, no LibreOffice process required, table:database-range for immediately visible filter arrows) to modules/ods_export.py — the same module rehaportal_export_ods.py uses.

## Data flow

- **Reads:** `imports/drv-kliniken/kliniken.json`
- **Writes:** `analyses/reha_klinik/kliniken.ods`

## Limitations

No data validation; cell contents are taken 1:1 from the JSON.

## Usage

```bash
python3 drv_kliniken_export_ods.py
python3 drv_kliniken_export_ods.py --help
```
