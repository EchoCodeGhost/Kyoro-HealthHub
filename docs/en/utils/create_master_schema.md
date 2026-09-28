# create_master_schema.py — Praxisweite Verwaltungsdatenbank erstellen/aktualisieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/create_master_schema.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Creates or migrates ~/.config/kyoro-master/master.db. This database holds practice-wide administrative data (which patient instances exist, shared practice devices) — unlike identity.db, which exists per instance and holds pseudonym mappings for exactly one person.

## Relevance

Enables creation of database schemas, essential for data organization and structure

## Method

Tables: patient_number_map (patient registry), practice_devices (device catalog).

## Data flow

- **Reads:** `~/.config/kyoro-master/master.db`
- **Writes:** `~/.config/kyoro-master/master.db`

## Limitations

Call once. Repeated execution is idempotent. ALWAYS lives in the real operator home, NEVER follows KYORO_ACTIVE_PATIENT_DIR — otherwise the patient list itself would disappear inside a patient instance.

## Usage

```bash
python -m utils.create_master_schema
python3 scripts/utils/create_master_schema.py  # from repo root
```
