# pseudonymize_providers.py — Arztpraxis- und Labornamen in der Datenbank pseudonymisieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/pseudonymize_providers.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Replaces real medical practice and laboratory names in health.db and medicine.db with stable pseudonyms (Labor-1A2B3C4D) and removes postal addresses from free-text columns of lab results. Runs entirely locally.

## Relevance

Prevents medical practice and laboratory names or addresses from sitting in the data that is exported or passed to external services

## Method

Columns listed in _SPECS (lab_manual.labor, lab_results.labor, …) are rewritten row by row. The pseudonym is a short SHA-256 hash of the normalised name so the same name always gets the same pseudonym. The pseudonym-to-cleartext mapping lives only in identity.db (provider_pseudonym_map), outside the health database. If a renamed lab_manual key collides with an existing row the existing row is kept. Already pseudonymised values are skipped (idempotent).

## Data flow

- **Reads:** `health.db`, `medicine.db`, `(Tabellen`, `aus`, `_SPECS`, `sofern`, `vorhanden)`
- **Writes:** `health.db, medicine.db, identity.db (provider_pseudonym_map)`

## Limitations

Only the columns in _SPECS. Practice or lab names in arbitrary free text are not detected. Pseudonymisation is not reversible without identity.db; losing identity.db means pseudonyms can no longer be resolved. A database that was already exported or backed up is not changed.

## Usage

```bash
python -m utils.pseudonymize_providers --dry-run
python -m utils.pseudonymize_providers
```
