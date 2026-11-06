# location-region Specification

## Purpose
Defines the "region" level of location data: an offline, worldwide ISO
3166 lookup (first administrative level, country code where units are
smaller than the stored grid cell), display names in German and English, and
how the region is stored per registry entry and read back for prompts and
exports.
## Requirements
### Requirement: Region as ISO code, worldwide and offline
`location_store.region_of(lat, lon)` SHALL return the ISO 3166-2 code of
the first-level administrative unit containing the point (e.g. `DE-BY`,
`ES-GC`, `US-HI`), using boundary data shipped with the repository and no
network access. When the unit has no valid subdivision code, the ISO
3166-1 country code SHALL be returned; when neither is known, `XX`.

#### Scenario: Point inside a German state
- **WHEN** `region_of(49.79, 9.95)` is called
- **THEN** it returns `DE-BY`

#### Scenario: Islands are separate from the mainland
- **WHEN** `region_of` is called for a point on Gran Canaria and for a point
  on Mallorca
- **THEN** it returns `ES-GC` and `ES-PM`, not `ES`

#### Scenario: Unit without a valid subdivision code
- **WHEN** the containing unit carries a placeholder code in the boundary
  data (e.g. a code with `~` or `-99`)
- **THEN** the country code of that unit is returned, or `XX` if it has none

#### Scenario: Invalid input
- **WHEN** `region_of(None, None)` is called
- **THEN** it returns `XX`

### Requirement: Points just off the coast
A point that lies in no unit SHALL be assigned to the nearest unit if that
unit is at most 5 km away; otherwise the result SHALL be `XX`.

#### Scenario: Small island or beach
- **WHEN** a point lies 0.5 km outside the simplified coastline of a unit
- **THEN** that unit's code is returned

#### Scenario: Open sea
- **WHEN** the nearest unit is 17 km away
- **THEN** `XX` is returned

### Requirement: Display names
`location_store.region_name(code)` SHALL return the unit's name in the
active language (German or English, via `t()`), taken from the boundary
data. Unknown codes SHALL return the code itself.

#### Scenario: German output
- **WHEN** the language is German and `region_name("DE-BY")` is called
- **THEN** it returns `Bayern`

### Requirement: Region stored per registry entry
`location_store.record()` SHALL compute the region from the coordinates
before precision is applied and store it in a `region` column of
`location_registry`. If the unit is smaller than the grid cell of the
stored precision, the country code SHALL be stored instead, so that the
region never reveals more than the stored coordinates.

#### Scenario: Region from unrounded coordinates
- **WHEN** a point is recorded with precision 0
- **THEN** `region` holds the unit of the original point, not of the
  rounded one

#### Scenario: Unit smaller than the stored cell
- **WHEN** a point in a unit of about 40 km² is recorded with precision 1
  (cell of about 90 km²)
- **THEN** `region` holds the country code

### Requirement: Region-only storage
With `store: "region"` the registry entry SHALL hold the region and no
coordinates (`lat` and `lon` NULL). Duplicate protection SHALL still apply.

#### Scenario: Region-only entry
- **WHEN** an importer whose policy is `store: "region"` records a point
- **THEN** the entry has `region` set and `lat`/`lon` NULL

#### Scenario: Region-only duplicate
- **WHEN** the same file is imported twice under `store: "region"`
- **THEN** only one entry exists

### Requirement: Region level reads the stored region
The `region` level in `for_prompt` and in exports SHALL use the stored
`region` value and SHALL NOT recompute it from coordinates. Where only
coordinates are available (exports of other tables), `region_of` SHALL be
used.

#### Scenario: Prompt with region level
- **WHEN** a caller with level `region` asks `for_prompt` for an entry
- **THEN** the result contains the stored region code and no coordinates

