# geo_bundesland.py — Deutsche Bundesländer: Namen, ISO-Codes, Zentroid-Koordinaten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/geo_bundesland.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Canonical list of the 16 German federal states (name, ISO 3166-2 code, approximate centroid coordinates) plus mapping from home coordinates to the nearest federal state — analogous to _nearest_region in import_pollen_dwd.py, but at federal-state level instead of DWD sub-regions.

## Relevance

Enables geographical functions, essential for spatial analysis

## Method

Euclidean distance to state-capital coordinates (accurate enough for federal-state assignment, not real polygon matching).

## Data flow

- **Reads:** `Keine`, `Tabellen`, `(statische`, `Daten)`
- **Writes:** `Keine Tabellen (statische Daten)`

## Limitations

Coordinates near a state border can be assigned to the wrong neighboring state (centroid approximation, no polygon borders).

## Usage

```bash
from modules.geo_bundesland import nearest_bundesland
name, code = nearest_bundesland(48.14, 11.58)  # -> ("Bayern", "BY")
```
