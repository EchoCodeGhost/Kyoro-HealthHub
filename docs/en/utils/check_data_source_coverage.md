# check_data_source_coverage — Findet Tabellen mit Daten, die kein Analyseskript abfragt

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/check_data_source_coverage.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Cross-references every table from the schema definitions (health.db, medicine.db, medicine_imaging.db) against the actual SQL queries in all analysis/module scripts and reports tables that hold data but are never referenced via FROM/JOIN by any script — the same pattern that was found by chance for pollen/user_context (Oura tags)/acute_events (migraine detail metrics), here found systematically instead of by chance.

## Relevance

Prevents data sources from staying silently disconnected — exactly the class of bug found four times by chance tonight.

## Method

1. Extracts table names via regex from every CREATE TABLE IF NOT EXISTS statement in the three create_*_schema.py files. 2. Scans scripts/analysis/**/*.py, scripts/modules/*.py, scripts/compute/*.py, scripts/query/*.py, scripts/utils/*.py, and scripts/exporters/*.py for FROM <table>/JOIN <table> occurrences (case-insensitive, word boundary) — a table counts as "referenced" as soon as it appears in any of these scripts even once. Compute/query/utils scripts are deliberately included: ecg_rpeaks, for instance, is never mentioned in any analysis/ script, only read by compute_orthostatic_detection.py — without these directories that would have been a false positive (and was, on the first run, see git history). 3. For every never-referenced table: query its row count in the relevant DB. Zero-row tables are not a finding (nothing to miss); tables with data are reported as candidates, sorted by row count.

## Data flow

- **Reads:** `scripts/utils/create_schema.py`, `create_medicine_schema.py`, `create_medicine_imaging_schema.py`, `(table`, `definitions);`, `scripts/analysis/**/*.py`, `scripts/modules/*.py`, `scripts/compute/*.py`, `scripts/query/*.py`, `scripts/utils/*.py`, `scripts/exporters/*.py`, `(query`, `text);`, `health.db`, `medicine.db`, `medicine_imaging.db`, `(row`, `counts)`
- **Writes:** `Keine Tabellen (reiner Report auf stdout)`

## Limitations

Grep-based, not real SQL parsing: cannot detect dynamically assembled table names (f-string with a variable) or access via compatibility views (see utils/create_schema.py). Export profiles (exporters/profiles/*.json) are not Python and are not scanned — a table that only appears there (for clinician exports) but in no Python script is deliberately still counted as "not analyzed" (exporting for clinician review is not the same as running an analysis on it). A match only means "some script mentions the table in its query text", not "the data meaningfully feeds an analysis" — false negatives are possible (table mentioned but only in a dead code path), just as seen with analyse_undocumented_events.py/analyse_pathogen_exposure.py (table referenced, but feature never fully wired up) — this script checks only the reference, not completeness of wiring.

## Usage

```bash
python3 scripts/utils/check_data_source_coverage.py
python3 scripts/utils/check_data_source_coverage.py --min-rows 10
```
