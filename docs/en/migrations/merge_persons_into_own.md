# merge_persons_into_own.py — Ordnet alle Daten der eigenen Person zu.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/merge_persons_into_own.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

For single-person installations: rows stored under another value in the person column (unknown, outdated pseudonyms) are assigned to the own person. They came from column defaults and earlier migrations and are partly duplicates; analyses with a person filter do not see them otherwise.

## Relevance

Prevents analyses from missing data or counting it twice

## Method

Per table, UPDATE OR IGNORE to the own person. What fails on the unique key already exists there and is deleted; the existing row of the own person stays. The dry run does the same and rolls back. A copy of the database is made before writing. The audit triggers from open_db also record each changed row in audit_log.

## Data flow

- **Reads:** `health.db`, `medicine.db:`, `alle`, `Tabellen`, `mit`, `person-Spalte`
- **Writes:** `Dieselben Tabellen, audit_log, import_log, eine Kopie neben der Datenbank`

## Limitations

Only for installations with exactly one person: data of other persons would be assigned to the own person, so without --yes it only does a dry run. Logs stay unchanged, and NULL stays NULL. Derived tables should be recomputed afterwards.

## Usage

```bash
python3 scripts/migrations/merge_persons_into_own.py        # Probelauf
python3 scripts/migrations/merge_persons_into_own.py --yes  # Kopie anlegen und ausführen
```
