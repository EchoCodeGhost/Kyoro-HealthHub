# Laborbefunde PDF → Review-CSV oder health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_lab_results.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports lab results from PDF files

## Relevance

Enables import of laboratory results, essential for integration of clinical data

## Method

Workflow: 1. python import_lab_results.py file.pdf to Kyoro-HealthHub/Laborbefunde/YYYY-MM-DD_lab_ocr.csv 2. Open CSV in LibreOffice/Excel, correct OCR errors, save as YYYY-MM-DD_labor.csv 3. python medical_query.py labor to reads all CSVs directly, no DB needed 4. python import_lab_results.py --db file.pdf to saves data directly in the database

## Data flow

- **Reads:** `PDF-Dateien`, `(Laborbefunde)`
- **Writes:** `CSV-Dateien oder lab_results in health.db`

## Limitations

OCR may be inaccurate. Manual correction required.

## Usage

```bash
python import_lab_results.py datei.pdf
python import_lab_results.py *.pdf
python import_lab_results.py --datum YYYY-MM-DD alter_befund.pdf
python import_lab_results.py --db datei.pdf
```
