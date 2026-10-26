# migrate_photo_locations_to_registry.py — Einmalige Migration von

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/migrate_photo_locations_to_registry.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Moves existing photo_locations rows into the location registry (location.db) and then removes them from health.db so that no coordinates remain there.

## Relevance

Completes stage 1: photo_locations is no longer written

## Method

Rows from import_lab_results are discarded (lab reports store no location). All others follow the policy in location_privacy.json: if it allows storage, location_store.record() writes the entry with migrated_from='photo_locations' (source file, hashes, reference and ts stay NULL); otherwise the row is discarded. With --execute, migrated and discarded rows are deleted from photo_locations; rows that failed to write are kept. The audit trigger is bypassed for this delete so that it does not copy the coordinates into audit_log; one count-only entry is written instead.

## Data flow

- **Reads:** `health.db::photo_locations`, `location_privacy.json`
- **Writes:**

  ```
  location.db::location_registry, health.db::photo_locations (DELETE),
  health.db::audit_log (ein Eintrag ohne Koordinaten)
  ```

## Limitations

One-off. Defaults to a dry run that reports counts only, never coordinates.

## Usage

```bash
# Trockenlauf (Standard)
python3 scripts/migrations/migrate_photo_locations_to_registry.py
# Ausführen
python3 scripts/migrations/migrate_photo_locations_to_registry.py --execute
```
