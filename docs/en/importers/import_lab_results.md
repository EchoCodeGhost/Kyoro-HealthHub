# Laborbefunde PDF → Review-CSV oder medicine.db (lab_manual)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_lab_results.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports lab results from PDF files

## Relevance

Enables import of laboratory results, essential for integration of clinical data

## Method

Workflow: 1. python import_lab_results.py file.pdf to Kyoro-HealthHub/Laborbefunde/YYYY-MM-DD_lab_ocr.csv 2. Open CSV in LibreOffice/Excel, correct OCR errors, save as YYYY-MM-DD_labor.csv 3. python medical_query.py labor to reads all CSVs directly, no DB needed 4. python import_lab_results.py --db file.pdf to saves data directly into medicine.db (lab_manual table, the same table other lab-value importers already use — previously its own lab_results table in health.db, which violated the DB-split convention and was corrected). --dry-run reports which (date, parameter, labor, person) combinations already exist before any real import, without writing anything.

## Data flow

- **Reads:** `lab_manual`, `(medicine.db)`, `—`, `nur`, `für`, `--dry-run`, `und`, `Duplikat-Check`, `via`, `INSERT`, `OR`, `IGNORE`
- **Writes:** `CSV-Dateien oder lab_manual in medicine.db`

## Limitations

OCR may be inaccurate. Manual correction required. Duplicate protection (UNIQUE on date+parameter+labor+person) only triggers on an exact date match — an OCR misread of the date on a repeat scan of the same report is not caught. The VLM fallback (on low OCR quality) runs exclusively with a local LLM provider (openvino/ovms/ollama/lmstudio/mlx) — with a cloud provider configured, the fallback is skipped rather than sending the image anyway. Does not handle historical trend reports with multiple date columns per parameter row well (assumes one date per page) — that needs its own, not-yet-planned importer. The lab/practice name (--labor or the filename fallback) is pseudonymized via modules/provider_scrubbing.py, but only if it's in the local provider registry — an unregistered name lands unchanged in lab_manual.labor (no data loss, but no guaranteed detection either).

## Usage

```bash
python import_lab_results.py datei.pdf
python import_lab_results.py *.pdf
python import_lab_results.py --datum YYYY-MM-DD alter_befund.pdf
python import_lab_results.py --db datei.pdf
python import_lab_results.py --db --dry-run datei.pdf
```
