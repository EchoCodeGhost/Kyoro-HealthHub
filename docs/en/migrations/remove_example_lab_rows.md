# remove_example_lab_rows.py — Entfernt Zeilen aus der Beispieldatei aus lab_manual.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/remove_example_lab_rows.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Finds and deletes lab rows that come from templates/labor.example.csv. These synthetic values must never reach analyses or letters to doctors.

## Relevance

Prevents made-up lab values from counting as real results

## Method

Compares date, parameter and value with the example file rather than the lab name, because that gets pseudonymised. Checks health.db and medicine.db. Without --yes it only counts. The audit triggers from open_db record each deleted row.

## Data flow

- **Reads:** `templates/labor.example.csv`, `lab_manual`, `in`, `health.db`, `und`, `medicine.db`
- **Writes:** `lab_manual (DELETE), audit_log, import_log`

## Limitations

A real result with an identical date, parameter and value would be deleted too, so the output lists the count per date. Only exact matches count.

## Usage

```bash
python3 scripts/migrations/remove_example_lab_rows.py        # nur zählen
python3 scripts/migrations/remove_example_lab_rows.py --yes  # löschen
```
