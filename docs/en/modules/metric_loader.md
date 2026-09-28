# metric_loader.py — Geraete- und sensoragnostisches Laden einer Tagesreihe

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/metric_loader.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Loads a metric as one value per calendar day, regardless of which device or import path delivered it, and returns for every day the actual source, the sensor class and the resulting confidence level.

## Relevance

Until now every script built its own source selection — with the result that analyses got stuck on empty device-specific tables, counted the same measurement twice across two import paths, or reported a wrist value like a reference measurement. One shared place makes this uniformly verifiable.

## Method

One SELECT over `measurements` with a list of equivalent metric names (vendors name the same quantity differently, e.g. respiration rate as 'respiration_rate' or 'respiratory_rate'). Then EXACTLY ONE source per calendar day, chosen in this order: device configured in `clinical.reference_devices`, then the given or the `source_priority` table's order, otherwise the source with the most readings that day. Several export paths of the same hardware (e.g. a brand's API and its data export) count as one source, otherwise the same measurement is counted twice. Values may optionally be normalised before aggregation (fraction 0..1 versus percent, seconds versus minutes) and clipped to a plausible range. Sensor class and confidence come from the device registry and modules/sensor_confidence.py.

## Data flow

- **Reads:** `health.db`, `(measurements`, `devices`, `ueber`, `modules/device_registry)`
- **Writes:** `keine`

## Limitations

Reads `measurements` only. Quantities living in their own tables (sleep sessions, blood pressure, lab) do not belong here. The sensor information is only as good as the device registry: if it is empty, `sensor_type` is None and confidence deliberately falls back to the most cautious level. Day-to-value mapping uses the `date` column (local calendar day per the importer) and does not convert time zones itself.

## Usage

```bash
from modules.metric_loader import load_metric_daily, pct_normalizer
days = load_metric_daily(conn, ("spo2", "oxygen_saturation"),
                         "2026-01-01", "2026-09-17",
                         person=person, agg="min",
                         normalizer=pct_normalizer, valid_range=(50.0, 100.0))
for date, day in sorted(days.items()):
    print(date, day.value, day.source_app, day.sensor_type, day.confidence)
```
