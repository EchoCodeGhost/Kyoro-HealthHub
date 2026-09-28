# Stryd (Laufleistungsmesser) → health.db

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_stryd.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Imports second-by-second running dynamics data (power, cadence, ground contact time, vertical oscillation, heart rate) from Stryd CSV exports. Objectifies the exertion cost of everyday movement under a pronounced aerobic deficit — in particular the mismatch between minimal wattage and a disproportionate heart rate response, which plain pace/speed metrics alone don't reveal.

## Relevance

Enables import of running dynamics data, important for exertion analysis under aerobic deficit

## Method

CSV format (one header row, then one row per second): Timestamp (Unix epoch, seconds) + 20 Stryd columns (Power/Form Power/Air Power in W/kg, watch and Stryd speed/distance, stiffness, ground time, cadence, vertical oscillation, watch and Stryd elevation, heart rate, four balance metrics, vertical ratio). Unix timestamp is treated as UTC (the Stryd export carries no timezone) and converted to ISO 8601. session_id = ISO timestamp of the first row. Footpod device resolved via cfg.footpod_device_id (sensor_type=='footpod' in device_registry, otherwise a generic 'footpod_1' fallback — brand deliberately not hardcoded, see cross-cutting-conventions).

## Data flow

- **Reads:** `{imports/stryd/}*.csv`, `(Stryd-Sekunden-Export)`
- **Writes:** `health.db (stryd_sessions, stryd_samples)`

## Limitations

No GPS lat/lon in the Stryd export — elevation only. Balance metrics (ground time/vertical oscillation/leg spring stiffness/ impact loading rate balance) require a dual-footpod setup and are consistently 0 with a single pod — not an error, no leg-symmetry statement possible in that case. No automatic linking to a separately imported watch session (e.g. Apple Watch) — both remain independent records, no duplicate risk but also no automatic merged view.

## Usage

```bash
python3 import_stryd.py --file lauf.csv
python3 import_stryd.py --dir imports/stryd/
python3 import_stryd.py --file lauf.csv --person PER-xxxx
```
