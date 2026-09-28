# sync_registry_to_devices — registry.json → health.db.devices abgleichen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/sync_registry_to_devices.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Syncs ~/.config/kyoro/registry.json (device_registry) into health.db's devices table. init_db.py only ever populates devices once via INSERT OR IGNORE — later registry.json edits (corrected date_from/date_to, new devices) are never propagated automatically. This script closes that gap.

## Relevance

Keeps device metadata in health.db consistent with the maintained registry, essential for correct device attribution in analysis/compute scripts

## Method

For each device_registry entry: if the device_id doesn't exist in devices yet, insert it. If it does, update serial/sensor_type/person/date_from/date_to/notes/ regulatory_json, but only where a value actually differs (no blind overwrite). The timezone column is never touched — registry.json has no timezone field, so touching it would silently lose manually-set values. Devices present in devices but no longer in registry.json are NOT deleted (would orphan FK references from measurements/sessions).

## Data flow

- **Reads:** `~/.config/kyoro/registry.json`, `health.db.devices`
- **Writes:** `health.db.devices`

## Limitations

Does not delete devices missing from the registry (see @method). Assumes registry.json is valid.

## Usage

```bash
python3 scripts/utils/sync_registry_to_devices.py
python3 scripts/utils/sync_registry_to_devices.py --dry-run
# Oder aus einem anderen Skript (z.B. import_all.py), nicht-blockierend:
from utils.sync_registry_to_devices import run
run()
```
