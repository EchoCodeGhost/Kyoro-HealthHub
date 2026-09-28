# pseudonymize_polar_device_serials.py — ppi_raw.device: Rohseriennummer → device_id

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/migrations/pseudonymize_polar_device_serials.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Replaces the raw Polar serial number (device column) in existing ppi_raw rows with the human-readable device_id (e.g. 'ABCD1234' → 'polar_v3'). Needed because these rows were imported before registry.json had a matching pseudonym for that raw serial value — import_polar.py, per its own fallback (_POLAR_SERIAL_TO_DEVICE_ID.get(serial, serial or DEVICE_H10)), used the raw serial itself as the device value.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Reads (serial_real, device_id) pairs from identity.db (device_serial_map) — NOT from registry.json, whose serial field now holds the pseudonym again (see scrub_polar_json.py: it scrubs the raw export files in place before import_polar.py ever reads them, so registry.json must mirror the pseudonyms found in those scrubbed files, not the real serials). identity.db remains the stable source for "which real serial maps to which device_id", independent of registry.json's current content. For each device: UPDATE ppi_raw SET device=<device_id> WHERE device=<serial_real>. PRIMARY KEY is (datetime, pulse_ms, device, person) — before each UPDATE, a NOT EXISTS check guards against a row already existing under the target device_id with the same key. Collisions are reported, not silently dropped.

## Data flow

- **Reads:** `ppi_raw`, `(device)`, `identity.db`, `(device_serial_map)`
- **Writes:** `ppi_raw (UPDATE device: raw serial → device_id)`

## Limitations

Meant to run once; safe to re-run (no-op once no raw serial values remain in ppi_raw). Only touches ppi_raw.device for rows whose device value exactly matches one of the known real Polar serials — rows with device='polar' (generic fallback, no identifiable serial) are left untouched since there's no way to reconstruct which device that was.

## Usage

```bash
python3 scripts/migrations/pseudonymize_polar_device_serials.py
python3 scripts/migrations/pseudonymize_polar_device_serials.py --dry-run
```
