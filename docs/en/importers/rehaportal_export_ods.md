# dasrehaportal.de → LibreOffice-Calc-Export

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/rehaportal_export_ods.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Exports the kliniken.json produced by rehaportal_parse.py as an .ods spreadsheet with AutoFilter enabled, for manually browsing and filtering in LibreOffice Calc.

## Relevance

Provides a browsable reference for rehabilitation planning, no direct relevance to personal health data

## Method

Only defines the column mapping (including cost-carrier and room/accommodation data, if the matching detail pages were already fetched via rehaportal_details_download.py) and delegates the actual sheet construction to modules/ods_export.py — the same module drv_kliniken_export_ods.py uses.

## Data flow

- **Reads:** `imports/rehaportal/kliniken.json`
- **Writes:** `analyses/reha_klinik/kliniken_rehaportal.ods`

## Limitations

No data validation; cell contents are taken 1:1 from the JSON. Cost-carrier/accommodation columns stay empty if no detail page was downloaded for that facility.

## Usage

```bash
python3 rehaportal_export_ods.py
python3 rehaportal_export_ods.py --help
```
