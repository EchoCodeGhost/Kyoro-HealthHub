## ADDED Requirements

### Requirement: One rule for all GPS and location data
All GPS coordinates and location data handled by Kyoro-HealthHub —
regardless of source (photos, PDFs, sport tracks, stays, travel,
environment fetches, configuration) — SHALL be governed by the location
policy in `location_privacy.json` and stored only through the location
registry. No importer, compute, analysis, query or export script SHALL
store, derive or pass on coordinates through any other path.

#### Scenario: A new importer reads coordinates from its source
- **WHEN** a contribution adds or changes an importer whose source data
  contains coordinates
- **THEN** the importer stores them only via the location registry module,
  applying the policy for its importer name and file type, and the change
  is a convention violation if it writes coordinates to `health.db`,
  `medicine.db`, a sidecar file or any other location

#### Scenario: A script derives a position from other data
- **WHEN** a script computes a location (e.g. a stay centroid, a session
  start point) from stored data
- **THEN** the derived location is written to and read from the registry
  under the same policy as its source, never to another table

### Requirement: Separate location database
Coordinates SHALL be stored only in `location.db`, a local database
separate from `health.db`, `medicine.db` and `identity.db`, opened through
the same encryption path as `health.db` when `db_key` is configured.
`health.db` and `medicine.db` SHALL contain at most references to registry
entries and coarse derived attributes (region, location token), never
latitude/longitude values.

#### Scenario: health.db is inspected after an import with GPS data
- **WHEN** an import of a source with coordinates has completed
- **THEN** no latitude/longitude column in `health.db` or `medicine.db`
  holds values for that import; the coordinates exist only in
  `location.db`

#### Scenario: location.db with db_key configured
- **WHEN** `db_key` is set in the configuration
- **THEN** `location.db` is opened encrypted like `health.db`

### Requirement: Registry records provenance per location entry
Every registry entry SHALL record: source importer, file type, path of the
source file relative to the imports archive, hash of the original file
before cleaning, hash of the stored file after cleaning (if a file is
stored), timestamp, latitude, longitude, the precision actually stored, a
reference to the record it belongs to (e.g. session, `imaging_files` row,
stay), and person (via `OWN_PERSON_ID` or the resolved person pseudonym).
Inserts SHALL use `INSERT OR IGNORE`.

#### Scenario: A skin photo with GPS is imported
- **WHEN** `import_skin` imports a photo whose EXIF contains a position and
  a capture date, and the policy allows storing it
- **THEN** exactly one registry entry exists with importer `import_skin`,
  the file type, the relative source path, both file hashes, the capture
  time, the coordinates rounded to the configured precision, that
  precision, and a reference to the photo's `imaging_files` row

#### Scenario: The same file is imported twice
- **WHEN** a file whose original hash is already registered is imported
  again
- **THEN** no duplicate registry entry is created

### Requirement: Separate location policy file, per importer and file type
The location policy SHALL be read from `location_privacy.json` in the
configuration directory (`KYORO_CONFIG_DIR`), separate from
`health_config.json`, with a template in
`templates/location_privacy.example.json` that `onboard.py` copies. For
each importer and file type the policy SHALL resolve in the order:
importer + file type → importer `"*"` → `default`. A resolved policy SHALL
be one of: `precision` 0–5 (decimal places of latitude/longitude),
`store: "region"` (federal state or country only), or `store: "none"`.

#### Scenario: File-type entry overrides the importer entry
- **WHEN** the policy contains `import_skin: {"*": {"precision": 2},
  ".dng": {"precision": 1}}` and a `.dng` file is imported
- **THEN** its location is stored at precision 1

#### Scenario: Importer without any entry
- **WHEN** an importer that has no entry in the policy encounters
  coordinates, and `default` is `{"store": "none"}`
- **THEN** no location is stored and the import otherwise succeeds

#### Scenario: Policy file missing
- **WHEN** `location_privacy.json` does not exist
- **THEN** no location is stored by any importer and a single clear
  warning names the missing file and the template to copy

### Requirement: Privacy by default and irreversible coarsening
An importer or file type without a policy entry SHALL store no location.
The configured precision SHALL be applied before writing; the registry
SHALL NOT keep a more precise copy, and a later change to a finer
precision SHALL NOT be able to refine existing entries.

#### Scenario: Policy changed to a finer precision
- **WHEN** the precision for an importer is raised from 2 to 4 after data
  was imported
- **THEN** existing entries keep precision 2; only newly imported entries
  are stored at precision 4

### Requirement: Shipped default policy
The template SHALL ship these defaults: Hilo importers, lab-report PDFs,
fundus images, FibriCheck PDFs and all other measurement or finding
importers → `store: "none"`; skin photos → precision 2; environment data
at the home location (daily fetch, pollen, air quality, weather services,
home weather station, home automation) → precision 2; stays and travel →
precision 2; sport tracks (GPX/track importer, Garmin activity details) →
precision 5 with privacy zones enabled.

#### Scenario: A lab-report PDF with an embedded geotagged photo
- **WHEN** `import_lab_results` imports a PDF whose embedded JPEG carries
  GPS, using the shipped defaults
- **THEN** the GPS is stripped from the stored file and no registry entry
  is written

#### Scenario: A Hilo export is imported
- **WHEN** a Hilo PDF or screenshot is imported with the shipped defaults
- **THEN** no location of any kind is stored

### Requirement: Privacy zones around personal places
When zones are enabled, every point within the configured radius (default
500 m) of a place from `privacy_check.patient_places` or of the town and
address in `privacy_check.patient_addresses` SHALL be stored at the zone
precision (default 2), even if the source's policy is finer. The
coordinates of the zone centres SHALL NOT be stored in the registry.

#### Scenario: A run starts at home
- **WHEN** a sport track at precision 5 starts and ends within 500 m of the
  configured home address
- **THEN** the points inside the zone are stored at precision 2 and the
  points outside at precision 5

#### Scenario: Zones disabled
- **WHEN** `zones.enabled` is `false`
- **THEN** all points are stored at their source precision

### Requirement: No location to external LLMs unless explicitly allowed
No location data SHALL be sent to an external LLM provider unless the
calling script is listed in the `llm.allow` section of
`location_privacy.json` with a level (`none`, `region`, a coarse raster
precision, or `token`). The default level SHALL be `none`. Location data
for prompts SHALL be obtained only through one output function that
enforces this list. For callers without an allowance the text scrubber for
cloud calls SHALL remove coordinates and configured place names from the
prompt, and images SHALL be re-encoded without metadata before they are
sent.

#### Scenario: A query tool builds a prompt with a session's start point
- **WHEN** a script not listed in `llm.allow` requests location data for a
  prompt to a remote provider
- **THEN** it receives nothing, and any coordinate present in the prompt
  text is removed before sending

#### Scenario: An allowed exposure analysis
- **WHEN** a script is listed with level `region`
- **THEN** it receives only the federal state or country for the requested
  entries, never coordinates

#### Scenario: A skin photo is sent to a vision model
- **WHEN** an image is passed to `call_llm` for a remote provider
- **THEN** it is re-encoded without EXIF/XMP or other metadata before
  encoding, regardless of how the file was stored

### Requirement: Location text in prompts to remote providers
Every prompt and system text sent to a remote LLM provider SHALL pass
through one location text filter, whichever path sends it: `call_llm` when
the configured provider is not local (`is_local` is false), and every
script that calls a remote API directly. Prompts to local providers SHALL
NOT be filtered by it. The caller SHALL be the entry script name (stem of
the executed script, e.g. `analyse_synthesis`) unless passed explicitly.
The filter SHALL apply the caller's level from `llm.allow`:
- `none` (default) and `region`: coordinates removed, configured place
  names removed;
- raster precision `N`: coordinates rounded to `N` decimal places instead
  of removed, configured place names removed;
- `token`: coordinates replaced by the location token of their raster
  cell, configured place names removed.
The filter SHALL log only counts.

#### Scenario: A query script sends a prompt with coordinates to a cloud provider
- **WHEN** `health_query` (not listed in `llm.allow`) sends a prompt that
  contains `48.13514, 11.58198` to a provider whose `is_local` is false
- **THEN** the coordinates are replaced by the coordinate placeholder
  before sending, and the log shows one removed location

#### Scenario: The same prompt goes to a local provider
- **WHEN** the configured provider is local (e.g. Ollama, llama.cpp)
- **THEN** the prompt is sent unchanged

#### Scenario: An allowed caller with raster level 2
- **WHEN** a caller is listed with level `2` and its prompt contains
  `48.13514, 11.58198`
- **THEN** the remote provider receives `48.14, 11.58`

#### Scenario: A script that calls a cloud API directly
- **WHEN** a script sends a request to a remote API without `call_llm`
- **THEN** it passes its prompt and system text through the same filter
  first, or the change is a convention violation

### Requirement: Precision for external services
Coordinates sent to external non-LLM services (weather, pollen, air
quality and similar APIs) SHALL be reduced to the precision configured
under `external_api` in `location_privacy.json` before the request is
made.

#### Scenario: Daily weather fetch
- **WHEN** `fetch_daily` requests weather data for the home location with
  `external_api.precision` set to 2
- **THEN** the request carries the home position rounded to 2 decimal
  places

### Requirement: Exports follow the location policy
Export tools SHALL include location fields only if the export profile is
listed in the `exports.allow` section of `location_privacy.json`, at the
level given there; otherwise location fields SHALL be omitted.

#### Scenario: A cardiology export
- **WHEN** a doctor export runs with a profile not listed in
  `exports.allow`
- **THEN** the exported files contain no coordinates and no location
  tokens

### Requirement: Location tokens for analyses without coordinates
Analyses that need to know whether two records come from the same place,
but not where, SHALL use a location token derived from the raster cell at
the stored precision and the pseudonym salt in `identity.db`. The token
SHALL be deterministic for the same cell and SHALL NOT be reversible
without `identity.db`.

#### Scenario: Two skin photos from the same campsite
- **WHEN** two photos are registered in the same raster cell
- **THEN** both have the same location token, and the token reveals no
  coordinates without access to `identity.db`
