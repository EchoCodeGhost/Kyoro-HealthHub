## Context

The pending change `location-privacy-registry` introduced `location.db`,
the policy file and `for_external_api()`. Two parts of it turned out weak in
review:

- `region_of()` uses the nearest German state capital (Euclidean distance
  in degrees) inside a bounding box. Tests with public city coordinates gave
  wrong states (Würzburg, Aschaffenburg) and German states for Salzburg and
  Basel. Outside the box it only knows "Abroad".
- `external_api.precision` defaults to 2 (~1 km). The DWD pollen importer
  guesses its region from 25 approximate centres; Brandenburg/Berlin and
  Mecklenburg-Vorpommern are missing from that list, and Regensburg and
  Görlitz land in the wrong region compared with the DWD region polygons.

Where Kyoro uses locations today:

| Purpose | Scripts | Leaves the machine |
|---|---|---|
| Environment at a place (weather, air, pollen, UV) | `fetch_daily`, `import_airquality`, `import_dwd_brightsky`, `import_aemet`, `import_pollen_google`, `import_travel_environment`, `weather_lookup`, `analyse_sport_environment` | coordinates to Open-Meteo, Bright Sky, Google, AEMET |
| Place lookup (country, state, town) | `geocode_stays`, `track_location`, `analyse_pathogen_exposure` | coordinates to Nominatim |
| Place name → coordinates | `import_travel_environment`, `track_location` | place names to Nominatim, Open-Meteo geocoding |
| Outbreak, endemic, FSME, airport, wastewater matching | `analyse_outbreak_exposure`, `analyse_pathogen_exposure`, `analyse_postinfectious_diagnose`, `airport_proximity`, `import_amelag`, `analyse_background_infection_activity` | nothing (local point plus radius) |
| Time zone | `modules/base` | nothing |
| Own devices | `import_ecowitt_csv`, `import_homeassistant` | nothing (local network) |
| LLM prompts | `health_query` and prompt modules | via the prompt filter of `location-privacy-registry` |

## Goals / Non-Goals

**Goals:**
- A region that is correct worldwide, offline, and fine enough to separate
  islands from mainlands.
- Fewer bits of location to external services with one simple setting.
- No service that ties location to a personal key without an explicit
  opt-in.
- A list of what each external service receives.

**Non-Goals:**
- Precision per service. One coarse value plus one value for place names.
- Boundary data per domain (pollen regions, FSME districts) or per country.
- Preferring bulk downloads over per-location queries as a rule.
- Replacing Nominatim by local reverse geocoding.
- Regions below the first administrative level.

## Decisions

### D1 Natural Earth admin-1, bundled
Natural Earth is public domain, covers the world, carries ISO 3166-2 codes
and names in many languages. Alternatives: GADM (non-commercial licence,
incompatible), OpenStreetMap (ODbL share-alike), geoBoundaries (licence and
meaning of each level differ per country). A build tool downloads a pinned
release with a checksum, simplifies to 0.02° (about 2 km) and writes one
gzip file into the repository (about 1.3 MB measured). The pinned release
is a dependency reference, like a version in `requirements.txt`, not a
changelog entry.

### D2 Lookup with shapely
`shapely` (BSD) with an STRtree index; the data is loaded lazily on first
use. Alternative: pure-Python point-in-polygon. Rejected because of edge
cases (holes, multipolygons, antimeridian) that shapely already handles.

### D3 Code cleanup at build time
Natural Earth has placeholder codes (`XK-X02~`, `-99-X11~`, …). The build
tool replaces them by the unit's country code (`iso_a2`) or `XX`. Several
polygons may share a code; that is expected.

### D4 Region computed before coarsening, never finer than the stored cell
`record()` computes the region from the original point. If the unit's area
(computed at build time and stored in the data file) is smaller than the
grid cell of the stored precision, the country code is stored. With the
shipped precisions (2 and 5) this never applies; it protects users who set
0 or 1.

### D5 Schema
`location_registry` gets `region TEXT`; `lat` and `lon` become nullable for
`store: "region"`. The unique index adds `region` and wraps `lat`/`lon` in
`COALESCE`. Existing `location.db` files are migrated by recreating the
table (SQLite cannot drop NOT NULL in place); entries are copied, regions
filled from the stored coordinates.

### D6 Two outbound precisions
`external_api.precision` (default 1) for everything, `external_api.place_precision`
(default 2) only for town-level reverse geocoding. `for_external_api(lat,
lon, place=False)` is the only rounding function for external requests;
callers of `round_coords()` for requests switch to it.

### D7 Opt-in for keyed services
`external_api.services.google_pollen` (default `false` in the template).
In Germany DWD covers pollen without sending a location at all; elsewhere
users can enable Google knowingly.

### D8 Home pollen region in configuration
A DWD region ID in `health_config.json` (e.g. `environment.dwd_pollen_region`).
The importer lists the regions from the DWD file it already downloads, so
there is no list to maintain. The approximate centres remain as fallback,
with the missing regions added and a warning. Mecklenburg-Vorpommern and
Brandenburg/Berlin have no sub-regions in the DWD file (`partregion_id` -1) and
are addressed by their `region_id`. For stays away from home in Germany the
region is estimated from the stay location without a warning; abroad DWD pollen
is skipped and pollen comes from Open-Meteo. All of this is decided locally.

## Risks / Trade-offs

- [Coarser environment data] Weather from a station ~11 km away can differ
  in temperature or precipitation → users can set precision 2; the docs say
  so.
- [Small units] In a few countries first-level units are small (Basel-Stadt,
  Paris) → region roughly equals the town there; documented in `@limits`; D4
  covers coarse storage.
- [Disputed areas] Natural Earth shows de-facto boundaries → documented.
- [BREAKING Google Pollen] Existing users lose Google pollen until they
  enable it → the skip message names the setting.
- [Repository size] ~1.3 MB binary data, updated only when borders change.

## Migration Plan

1. Ship data file, lookup and schema migration; `create_location_schema`
   migrates existing `location.db` on first open.
2. Switch external callers to `for_external_api()`; template default 1.
3. Existing `location_privacy.json` files keep their `external_api.precision`;
   `onboard.py` does not overwrite them. The release notes suggest setting 1.

## Open Questions

- Exact name of the DWD region setting and where `onboard.py` asks for it.
