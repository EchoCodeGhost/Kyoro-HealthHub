# apply_privacy_zones.py — Privatsphäre-Zonen auf schon gespeicherte Orte anwenden

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/apply_privacy_zones.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Applies the privacy zones from location_privacy.json to locations in location.db that were stored before a zone was set up: registry entries and track points inside a zone are deleted (zones.inside "hide", default) or rounded to zone_precision ("coarsen"); stays and location history are only coarsened, never deleted.

## Relevance

Location registry: zones also apply to previously stored locations

## Method

Checks points stored finer than zone_precision against the same (shifted) zones as location_store. If coarsening produces a registry entry that already exists, the row is deleted. The audit triggers of the changed tables are bypassed so that the precise coordinates are not copied into audit_log; one count-only entry is written instead. The triggers are installed again afterwards.

## Data flow

- **Reads:** `location.db`, `(location_registry`, `session_tracks`, `location_stays`, `location_history)`, `location_privacy.json`, `health_config.json`, `(privacy_check`, `location)`, `identity.db`, `(Salz)`
- **Writes:**

  ```
  location.db (UPDATE/DELETE in diesen Tabellen),
  location.db::audit_log (ein Eintrag ohne Koordinaten)
  ```

## Limitations

Irreversible. Defaults to a dry run that reports counts only, never coordinates. Zone centres are not stored.

## Usage

```bash
# Trockenlauf (Standard)
python3 scripts/migrations/apply_privacy_zones.py
# Ausführen
python3 scripts/migrations/apply_privacy_zones.py --execute
```
