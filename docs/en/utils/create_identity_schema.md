# create_identity_schema.py — Identity-Datenbank erstellen/aktualisieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/create_identity_schema.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Creates or migrates identity.db under KYORO_CONFIG_DIR (~/.config/kyoro/identity.db for single-user operation, or <instance_dir>/.config/kyoro/identity.db when KYORO_ACTIVE_PATIENT_DIR is set). This database holds the only mapping between real device serials/service account IDs and their pseudonyms. It lives outside the project directory and outside health.db so that the health database alone cannot be de-anonymized.

## Relevance

Enables creation of database schemas, essential for data organization and structure

## Method

Tables: device_serial_map (device serials), account_pseudo_map (account IDs).

## Data flow

- **Reads:** `KYORO_CONFIG_DIR/identity.db`
- **Writes:** `KYORO_CONFIG_DIR/identity.db`

## Limitations

Call once. Repeated execution is idempotent (CREATE IF NOT EXISTS).

## Usage

```bash
python -m utils.create_identity_schema
python -m utils.create_identity_schema --show
```
