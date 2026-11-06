# geo_bundesland.py — Deutsche Bundesländer: Namen, ISO-Codes, Zuordnung von Koordinaten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/geo_bundesland.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Canonical list of the 16 German federal states (name as spelled in RKI datasets, ISO 3166-2 code) and assignment of coordinates to a federal state, for RKI and AMELAG series.

## Relevance

Enables geographical functions, essential for spatial analysis

## Method

Assignment uses the worldwide region lookup (modules/region_lookup.py, Natural Earth boundaries). Points outside Germany give None instead of a neighbouring state.

## Data flow

- **Reads:** `scripts/modules/geodata/admin1.json.gz`, `(über`, `region_lookup)`
- **Writes:** `Keine Tabellen (statische Daten)`

## Limitations

Borders simplified to ~2 km and the source itself is accurate to about 1–2 km at borders: places right at a state or national border can be assigned to the neighbouring unit.

## Usage

```bash
from modules.geo_bundesland import bundesland_of
bundesland_of(48.14, 11.58)  # -> ("Bayern", "BY")
bundesland_of(47.80, 13.04)  # -> None (Österreich)
```
