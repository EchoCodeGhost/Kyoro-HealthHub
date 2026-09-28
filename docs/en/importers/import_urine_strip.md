# import_urine_strip.py — Urin-Streifentest und 24h-Sammelurin importieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_urine_strip.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports urine strip test and 24h collection urine data from CSV templates into medicine.db

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads the CSV template (data/templates/urine_strip_template.csv) and writes all parameters as individual rows into medicine.db → lab_manual. Sample type: spot (instant sample) | 24h (collected urine). For 24h collected urine, volume_ml is stored as a separate parameter. 12 parameters are supported: Leukozyten, Urobilinogen, Protein, Bilirubin, Glukose, Ascorbinsaeure, Spez.Gewicht, Ketone, Nitrit, Kreatinin, pH, Blut. Reference values are defined for each parameter.

## Data flow

- **Reads:** `CSV-Datei`, `(Template-Format)`, `mit`, `Urin-Parametern`
- **Writes:** `lab_manual, import_log`

## Limitations

Depends on CSV template format. No automatic validation of values. Reference values are based on standard laboratory values.

## Usage

```bash
python3 scripts/importers/import_urine_strip.py datei.csv
python3 scripts/importers/import_urine_strip.py data/templates/urine_strip_template.csv --dry-run
```
