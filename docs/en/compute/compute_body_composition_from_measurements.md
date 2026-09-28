# Gewicht aus measurements → body_composition — Brücke für Profil-Gewichtswerte.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/compute/compute_body_composition_from_measurements.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Bridges weight_kg values from the measurements table (currently: Polar's physicalInformation profile snapshot, see import_polar.py::import_polar_activity) into body_composition, so weight trends/analyses reading body_composition aren't limited to the much sparser scale history (FDDB/Beurer/Renpho).

## Relevance

Closes gaps in weight history outside scale imports, relevant for trend analyses and exertion/capacity context

## Method

Reads measurements WHERE metric='weight_kg', grouped by source_app (not hardcoded to Polar — any future source writing weight_kg to measurements is picked up automatically). Uses ts/date directly from measurements (Polar: {date}T00:00:00+00:00) instead of its own timestamp — on collision with an existing body_composition row at the exact same (ts, person), the first-written one wins (INSERT OR IGNORE); unlikely in practice since FDDB/Beurer/Renpho currently use T12:00:00, not T00:00:00 timestamps.

## Data flow

- **Reads:** `measurements`, `(metric='weight_kg')`
- **Writes:** `body_composition (nur weight_kg gesetzt, übrige Spalten NULL)`

## Limitations

Only weight_kg — the other physicalInformation values (VO2max, HRmax, resting HR, aerobic/anaerobic threshold) deliberately stay in measurements, since body_composition has no columns for them and they're a different concept (fitness/HR metrics, not body composition). No duplicate check against other body_composition sources on the same day — if e.g. a scale measurement and a Polar profile value differ for the same day, both remain as separate rows (different time-of-day), no reconciliation/averaging.

## Usage

```bash
python3 scripts/compute/compute_body_composition_from_measurements.py
python3 scripts/compute/compute_body_composition_from_measurements.py --lang en
```
