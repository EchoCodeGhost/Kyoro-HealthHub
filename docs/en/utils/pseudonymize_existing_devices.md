# pseudonymize_existing_devices — Bestehende Geräte-Seriennummern in der Datenbank pseudonymisieren

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/pseudonymize_existing_devices.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Finds all devices without SN prefix in their serial number and replaces them with pseudonyms. This script: 1) Finds all devices without SN prefix, 2) Creates pseudonyms and stores them in identity.db, 3) Updates health.db with pseudonymized serial numbers, 4) Creates a backup before making changes.

## Relevance

Provides utility functions for data processing, essential for system functionality

## Method

Searches the devices table for serial numbers without SN prefix. Uses pseudonymize_device_serial() and get_device_pseudo() from utils.anonymize. Shows all planned changes before execution. Requires user confirmation before execution (except --dry-run). Creates timestamp-based backup. Logs to import_log. Exit code: 0 = success, 1 = error.

## Data flow

- **Reads:** `health.db.devices`
- **Writes:** `health.db.devices, identity.db.device_serial_map, import_log, health.db.backup`

## Limitations

Only checks devices with non-empty serial numbers without SN prefix. Backup is created in the same directory as the database.

## Usage

```bash
python scripts/utils/pseudonymize_existing_devices.py
python scripts/utils/pseudonymize_existing_devices.py --db /path/to/health.db
python scripts/utils/pseudonymize_existing_devices.py --dry-run
# --db: Pfad zur Datenbank angeben
# --dry-run: Zeigt Änderungen ohne sie durchzuführen
```
