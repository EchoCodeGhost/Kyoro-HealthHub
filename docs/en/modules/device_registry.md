# device_registry.py — Geräte-Registry Lookup-Hilfsfunktionen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/device_registry.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides lookup utility functions for the device registry from health_config.json. No DB access, no direct user calls.

## Relevance

Enables device management, essential for data integration

## Method

Defines HR priorities per sensor type (ECG > handheld ECG > chest strap > ring > wrist > smartphone). Provides functions: hr_priority(), best_hr_device(), label(), sensor_type() for selecting the best device. is_device_active()/ validity_window() check a timestamp against the registry's date_from/date_to — catching physically impossible readings (device wasn't worn yet/anymore at the time of measurement). collapse_concurrent() bundles the project-wide multi-device Rule B (below) into one reusable function instead of every script building its own GROUP BY/MIN(device).

## Data flow

- **Reads:** `~/.config/kyoro/registry.json`, `(device_registry)`, `health_config.json`, `(Fallback)`
- **Writes:** `Keine Tabellen (statische Lookups)`

## Limitations

Sensor priorities are heuristic. Configuration in registry.json must be correct. is_device_active() returns True for unknown devices or missing date_from (unverifiable is not treated as an error) — not a substitute for a fully maintained registry. collapse_concurrent() only resolves Rule B (differing values); Rule A (exact duplicates) must already be cleaned up via migration, otherwise collapse_concurrent() still counts them (irrelevant to the result, but as an extra unused row).

## Usage

```bash
from modules.device_registry import (
    hr_priority, best_hr_device, spo2_priority, best_spo2_device,
    label, sensor_type, collapse_concurrent,
)
best_device = best_hr_device(conn, OWN_PERSON_ID)
minute_rows = collapse_concurrent(rows)  # rows: [(ts, value, ..., device_id), ...], HF-Prioritaet
night_rows = collapse_concurrent(rows, priority_fn=spo2_priority)  # SpO2-Prioritaet
```
