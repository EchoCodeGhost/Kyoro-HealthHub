# rename_kiste_export_source.py — source='kiste_export' → 'symptomtrack_export'

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/rename_kiste_export_source.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Migrates existing symptoms rows from the old source tag ``kiste_export`` (abbreviation "KiSTe") to ``symptomtrack_export``, following the importer rename to ``import_symptomtrack_export.py``.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Before the UPDATE, checks whether a row with the same (date, symptom, person) already exists under source='symptomtrack_export' (would otherwise violate PRIMARY KEY (date, symptom, person, source)) — such rows are skipped and reported instead of being silently dropped.

## Data flow

- **Reads:** `symptoms`, `(source)`
- **Writes:** `symptoms (UPDATE source='kiste_export' → 'symptomtrack_export')`

## Limitations

Meant to run once; safe to re-run (no-op once no kiste_export rows remain).

## Usage

```bash
python3 scripts/migrations/rename_kiste_export_source.py
python3 migrations/rename_kiste_export_source.py  # from inside scripts/
```
