# Hilo-App Blutdruckdaten Einmalimport

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_hilo_screenshots.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

One-time import of Hilo app blood pressure data from screenshots

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

One-time import of Hilo app blood pressure data from manually read screenshots. Period: June 23-28, 2026, timezone assumption: CEST (UTC+2). Data has already been imported (INSERT OR IGNORE idempotent, so re-running is safe). RAW list cleared for privacy reasons.

## Data flow

- **Reads:** `Hilo`, `App`, `Screenshots`
- **Writes:** `blood_pressure`

## Limitations

One-time import. Period already completed. User used both the cuffless Hilo Band and the Hilo Cuff in parallel during the import period; screenshots don't reliably indicate which device produced which reading, hence device_id="hilo_unspecified" rather than a falsely specific attribution (previously incorrectly "omron_bp").

## Usage

```bash
python3 import_hilo_screenshots.py
python3 import_hilo_screenshots.py --lang en
```
