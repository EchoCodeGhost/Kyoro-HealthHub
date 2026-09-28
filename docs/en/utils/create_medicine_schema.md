# create_medicine_schema.py — medicine.db initialisieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/create_medicine_schema.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Initializes medicine.db with tables for medical data.

## Relevance

Enables creation of database schemas, essential for data organization and structure

## Method

Tables (identical schemas as in health.db for lossless migration): lab_manual (manual lab results), lab_results (structured lab results), medications, assessments (clinical scores), findings (with ICD codes). Also runs ``_migrate_medications_is_chronic`` on every call — adds is_chronic via ALTER TABLE if an older medicine.db is missing it (idempotent, checked via PRAGMA table_info).

## Data flow

- **Reads:** `Keine`, `(erstellt`, `neues`, `Schema)`
- **Writes:** `medicine.db (Tabellen: lab_manual, lab_results, medications, assessments, findings)`

## Limitations

Call once. Repeated execution is idempotent (CREATE IF NOT EXISTS).

## Usage

```bash
python3 scripts/utils/create_medicine_schema.py
python3 scripts/utils/create_medicine_schema.py --force
```
