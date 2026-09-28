# Apple Health XML → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_apple.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports data from Apple Health XML exports into health.db. Supports heart rate, HRV, steps, body metrics, workouts, and other health data from iOS devices.

## Relevance

Enables import of health data from Apple Health, essential for integration of iOS health data

## Method

Reads the Apple Health XML file (config: apple_xml) and parses the data. Records are imported into measurements, workouts into sessions + session_metrics. Supports scrubbing for data cleaning. Source device is detected from sourceName (Garmin/Fitbit/Apple Watch/iPhone/Oura/Withings/Polar/unknown) and pseudonymized via resolve_device() before being stored as device_id — never the raw brand/source name. For Apple Watch sources, additionally distinguishes device GENERATION (s. _hardware_id()): sourceName is always just 'Apple Watch' regardless of model -- but the XML 'device' attribute carries Apple's internal hardware identifier (e.g. 'hardware:Watch7,2'), appended to the pseudonymization slug so different watch generations (e.g. after a device swap) get distinct device_ids instead of collapsing into one shared pseudonym.

## Data flow

- **Reads:** `{apple_xml}`, `(Apple`, `Health`, `XML`, `Export)`
- **Writes:** `health.db (measurements, sessions, session_metrics)`

## Limitations

No validation of Apple data quality. Dependent on the correctness of the XML export. No medical interpretation.

## Usage

```bash
python3 import_apple.py           # vollständiger Import
python3 import_apple.py --update  # idempotent, INSERT OR IGNORE
```
