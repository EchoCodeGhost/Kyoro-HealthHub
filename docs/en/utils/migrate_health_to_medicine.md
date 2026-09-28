# migrate_health_to_medicine — Migration klinischer Daten von health.db nach medicine.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/migrate_health_to_medicine.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Migrates clinical tables from health.db to the dedicated medicine.db. Affected tables: lab_manual, lab_results, medications and assessments. Data remains in health.db (no deletion).

## Relevance

Provides data migration functions, essential for data updates and restructuring

## Method

Uses INSERT OR IGNORE for all tables to avoid duplicates and make migration repeatable. Before migration, ensures that the medicine.db schema exists (calls create_medicine_schema). Supports dry-run mode (--dry-run) for preview without write operations. Columns are dynamically extracted from the source table.

## Data flow

- **Reads:** `health.db.lab_manual`, `health.db.lab_results`, `health.db.medications`, `health.db.assessments`
- **Writes:** `medicine.db.lab_manual, medicine.db.lab_results, medicine.db.medications, medicine.db.assessments`

## Limitations

Data is not deleted from health.db - manual deletion required after verification. Requires access to both databases (health.db and medicine.db). Dry-run mode only shows the number of rows to be migrated without writing them.

## Usage

```bash
python scripts/utils/migrate_health_to_medicine.py
python scripts/utils/migrate_health_to_medicine.py --dry-run
# Vorraussetzung: health.db und medicine.db müssen existieren
# --dry-run: Zeigt an, welche Daten migriert würden, ohne sie zu schreiben
```
