# create_medicine_imaging_schema.py — medicine_imaging.db initialisieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/create_medicine_imaging_schema.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Initializes medicine_imaging.db for medical imaging data.

## Relevance

Enables creation of database schemas, essential for data organization and structure

## Method

Tables: imaging_studies (parent studies), imaging_files (individual files), imaging_analysis (VLM analysis results). Modular: Fundus, X-ray, MRI, CT, Echo all follow this schema. body_part + modality distinguish image type. Core logic lives in ensure_schema(force=False) WITHOUT argparse — main() is now just a thin CLI wrapper around it. Reason: other scripts (e.g. import_fundus.py) used to call main() directly, whose ap.parse_args() read the CALLING process's sys.argv (e.g. import_fundus.py --person X file.dcm) and crashed with "unrecognized arguments" since this script only knows --force.

## Data flow

- **Reads:** `Keine`, `(erstellt`, `neues`, `Schema)`
- **Writes:** `medicine_imaging.db (Tabellen: imaging_studies, imaging_files, imaging_analysis)`

## Limitations

Call once. Repeated execution is idempotent (CREATE IF NOT EXISTS). Until recently, import_log didn't have the same columns as health.db's import_log (data_path/rows_skipped were missing) — modules/base.py's log_import() expects these and crashed on every real medicine_imaging.db import, before the commit, losing the actually-imported rows too. _migrate() now aligns it via ALTER TABLE.

## Usage

```bash
python3 scripts/utils/create_medicine_imaging_schema.py
python3 scripts/utils/create_medicine_imaging_schema.py --force
```
