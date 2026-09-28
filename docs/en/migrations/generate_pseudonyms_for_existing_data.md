# generate_pseudonyms_for_existing_data.py — Pseudonyme für bestehende Daten generieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/generate_pseudonyms_for_existing_data.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Scans health.db and medicine.db for all unique device and person identifiers and generates deterministic pseudonyms for them using the identity_resolver module. Pure backfill step (task 4.2) — the actual data migration (task 4.3, pseudonymize_device_person_identifiers.py) creates new identity.db entries automatically as a side effect of resolving anyway; this script lets you inspect the pseudonyms BEFORE migration (e.g. for a report).

## Relevance

Provides health data functions, essential for medical data processing

## Method

1. Reads all unique values from target columns — known per column name (device_id/device → device, person → person), NO heuristic on the value itself (an earlier version guessed device vs. person from substrings like 'polar'/'apple' in the value — that can silently mispseudonymize an unfamiliar device name). 2. Generates pseudonyms with resolve_device() / resolve_person(). 3. Stores mappings in identity.db (side effect of resolve()).

## Data flow

- **Reads:** `health.db`, `medicine.db`, `(über`, `Config-Pfad`, `alle`, `Tabellen`, `mit`, `device_id/device/person-Spalten)`
- **Writes:** `~/.config/kyoro/identity.db (device_id_map, person_map Tabellen)`

## Limitations

Only semantic values are pseudonymized; existing pseudonyms (DEV-*, PER-*) are ignored.

## Usage

```bash
python3 scripts/migrations/generate_pseudonyms_for_existing_data.py
python3 migrations/generate_pseudonyms_for_existing_data.py  # from inside scripts/
```
