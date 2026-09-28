# endemic_matching — Geteilte Geo-/Zeit-Logik für strukturelle Endemie-Treffer

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/endemic_matching.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Bundles the distance, radius, and "timeless source" logic that until recently was duplicated almost identically across analyse_outbreak_exposure.py, analyse_pathogen_exposure.py, and analyse_postinfectious_diagnose.py -- every bugfix previously had to be applied separately in all three places.

## Relevance

Without this module every future fix to the endemic/FSME matching logic would again need to be applied in sync across up to three files -- exactly the pattern today's session had to repeat several times.

## Method

geo_dist_km(): standard Haversine formula. resolve_radius_km(): uses a per-entry radius_km override when set, else a default depending on whether the source is in TIMELESS_SOURCES (200 km) or not (100 km). since_floor_ok(): compares an optional since_date against a reference date (usually the stay's end) -- if the stay ended before since_date, the (younger, actively expanding) risk does not apply.

## Data flow

- **Reads:** `Keine`, `(reine`, `Funktionsbibliothek`, `keine`, `DB-/Dateizugriffe)`
- **Writes:** `Keine`

## Limitations

Deliberately covers ONLY the distance/radius/timelessness logic, not the more complex region-based text matching (island-group handling, "Gesamt*" special case, etc.) -- that stays local to each script, since it's tied to that script's own data shape (dict vs. Stay dataclass) and already behaves slightly differently across the three (e.g. the diagnosis engine needs no island-group special case).

## Usage

```bash
from modules.endemic_matching import geo_dist_km, resolve_radius_km, since_floor_ok, TIMELESS_SOURCES
radius = resolve_radius_km(outbreak_dict)
if geo_dist_km(lat1, lon1, lat2, lon2) <= radius: ...
```
