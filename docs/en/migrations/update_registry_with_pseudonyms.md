# update_registry_with_pseudonyms.py — Geräte-Registry mit Pseudonymen aktualisieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/update_registry_with_pseudonyms.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Updates the device_registry in registry.json to use pseudonyms instead of semantic device_ids and person values. Should be run AFTER the database migration to ensure consistency.

## Relevance

Provides health data functions, essential for medical data processing

## Method

1. Reads registry.json 2. Replaces all semantic device_id values with pseudonyms 3. Replaces all semantic person values with pseudonyms 4. Saves updated registry (only with --execute)

## Data flow

- **Reads:** `~/.config/kyoro/registry.json`
- **Writes:** `~/.config/kyoro/registry.json (aktualisierte device_registry)`

## Limitations

Overwrites existing values; no automatic backup. Existing pseudonyms (DEV-*, PER-*) are ignored.

## Usage

```bash
python3 scripts/migrations/update_registry_with_pseudonyms.py --dry-run
python3 scripts/migrations/update_registry_with_pseudonyms.py --execute
```
