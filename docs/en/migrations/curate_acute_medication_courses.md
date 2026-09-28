# curate_acute_medication_courses.py — Markiert bekannte Akutkuren als is_chronic=0

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/curate_acute_medication_courses.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Sets ``is_chronic=0`` for a manually curated list of known one-off acute courses (e.g. antibiotics) so analyses can distinguish them from ongoing long-term medication. The ``is_chronic`` column itself is created/migrated by ``create_medicine_schema.py`` — this script only curates data, not structure.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Plain ``UPDATE`` statements against ``ACUTE_COURSES`` (list of (drug_name, date) pairs); sets is_chronic=0 only for exactly matching (person, drug_name, date) rows. No DDL.

## Data flow

- **Reads:** `medications`, `(drug_name`, `date`, `person)`
- **Writes:** `medications (UPDATE is_chronic=0 for entries in ACUTE_COURSES)`

## Limitations

Manually curated list — future acute courses should be imported with ``is_chronic=0`` directly rather than added here. Safe to re-run (WHERE clause is exact, no blast radius beyond the listed rows).

## Usage

```bash
python3 scripts/migrations/curate_acute_medication_courses.py
python3 migrations/curate_acute_medication_courses.py  # from inside scripts/
```
