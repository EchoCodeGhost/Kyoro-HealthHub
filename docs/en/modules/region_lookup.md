# region_lookup.py — Offline ISO 3166 region for coordinates, worldwide

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/region_lookup.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Maps coordinates offline to the first administrative level (ISO 3166-2, e.g. DE-BY, ES-GC, US-HI) and returns its names and area. Basis for location_store.region_of.

## Relevance

Provides the "region" level of the location policy worldwide, not only for Germany

## Method

Loads the bundled file geodata/admin1.json.gz (Natural Earth, simplified, built by tools/build_region_data.py) on first use and finds the unit containing the point via an STRtree (shapely). If the point lies in no unit, the nearest unit within 5 km counts (coasts, small islands).

## Data flow

- **Reads:** `scripts/modules/geodata/admin1.json.gz`
- **Writes:** `(nichts)`

## Limitations

Outlines simplified to ~2 km: near borders a point can be assigned to the neighbouring unit within that distance. De-facto boundaries as in Natural Earth; disputed areas follow that depiction. In some countries the first level is small (Basel-Stadt, Paris); there the region nearly equals the town.

## Usage

```bash
from modules.region_lookup import lookup, unit_info
code = lookup(49.79, 9.95)          # -> "DE-BY"
info = unit_info("DE-BY")           # -> {"name_de": "Bayern", ...}
```
