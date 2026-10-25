## Why

Location data in Kyoro-HealthHub is handled per importer, with no common
rule for how precise it may be, where it lives, or who outside the machine
may see it. Sport tracks sit in `health.db::session_tracks` at ~1 m
precision (a track that starts at the front door reveals the home address),
stays and reverse-geocoded place names sit next to them, and
`photo_locations` stores positions from lab-report PDFs although no analysis
ever reads that table. At the same time `post_import_sanitize` aims to keep
`health.db` shareable with cloud LLMs — which location data currently
contradicts. This change makes one rule apply to all GPS and location data:
stored only where the source needs it, only as precise as configured, kept
in its own database, and passed to anything outside the machine only where
strictly required.

## What Changes

- New local database `location.db` (encrypted like the other databases when
  `db_key` is set) holding a central location registry: source importer,
  file type, relative source-file path, hash of the original file (before
  cleaning) and of the stored file (after cleaning), timestamp, latitude,
  longitude, stored precision, a reference to the record it belongs to
  (session, `imaging_files` row, stay), and person.
- New configuration file `~/.config/kyoro/location_privacy.json` (template
  `templates/location_privacy.example.json`, copied by `onboard.py`),
  separate from `health_config.json`. Location handling is configurable per
  importer and per file type; resolution order is importer + file type →
  importer `"*"` → `default`. Values: `precision` 0–5 decimal places,
  `store: "region"` (federal state / country only) or `store: "none"`.
- **Privacy by default:** an importer or file type without an entry stores
  no location at all. Precision is applied at write time and is
  irreversible (coarsened values cannot be refined later).
- Shipped defaults: Hilo (PDF and screenshot importers), lab-report PDFs,
  fundus images, FibriCheck and all other measurement/finding importers →
  `none`; skin photos → 2 (~1 km); environment at the home location
  (daily fetch, pollen, air quality, weather services, home weather
  station, home automation) → 2; stays and travel → 2 (~1 km, unchanged);
  sport tracks → 5 (~1 m) with privacy zones.
- Privacy zones: points within 500 m (configurable) of places from
  `privacy_check.patient_places` and the town/address in
  `privacy_check.patient_addresses` are stored at precision 2 even for
  sources configured finer.
- One rule for every way location data leaves the machine:
  - **External LLMs:** no location by default; a per-caller allowlist in
    `location_privacy.json` grants a level (`none`, `region`, a coarse
    raster, or a location token). A single output function enforces it;
    the text scrubber for cloud calls removes coordinates for every caller
    not on the list; images are re-encoded without metadata before sending.
  - **External services** (Open-Meteo and similar weather/pollen/air APIs):
    the precision sent is set by an `external_api` key in the same file.
  - **Exports** (doctor/research exports): location fields follow the same
    file and are omitted unless an export profile is allowed to include
    them.
- `health.db` and `medicine.db` keep only references and coarse attributes
  (region, location token derived from the raster cell and the salt in
  `identity.db`), never coordinates.
- **BREAKING** (stage 3): `session_tracks`, `location_stays`,
  `location_history` and `location_stays_geocoded` move from `health.db`
  to `location.db`; every reader is adapted.
- `photo_locations` is replaced by the registry; lab-report PDFs no longer
  store positions from embedded photos.
- Delivered in three stages: (1) registry, configuration, outbound rules,
  photos/PDFs; (2) privacy zones; (3) migration of tracks and stays.

## Capabilities

### New Capabilities
- `location-privacy`: Central location registry in `location.db`,
  per-importer/per-file-type precision policy in `location_privacy.json`,
  privacy zones, and one outbound rule for LLMs, external services and
  exports covering all GPS and location data.

### Modified Capabilities
- `image-importer-pattern`: "GPS capture before discard" changes from
  "always store in `photo_locations` at ~1 km" to "store via the location
  registry only if the policy for this importer/file type allows it, at the
  configured precision"; "location data only in medically relevant
  analyses" is tied to the new outbound rule.

## Impact

- New: `scripts/modules/location_store.py` (registry access, policy
  resolution, zones), `scripts/utils/create_location_schema.py`,
  `templates/location_privacy.example.json`, migration script for stage 3.
- Changed importers: `import_skin`, `import_lab_results`, `import_fundus`,
  `import_tracks`, `import_garmin`, `import_oura_csv`,
  `import_travel_environment`, `import_homeassistant`, `import_ecowitt_csv`,
  the pollen/air/weather importers and `fetch_daily` (outbound precision).
- Changed consumers of the moved tables (stage 3): every analysis, compute
  and query script reading `session_tracks` or the `location_*` tables.
- `scripts/modules/llm.py` (`call_llm` with images: re-encode without
  metadata; location output function), synthesis/query tools that build
  prompts, `export_health.py` and export profiles.
- `health_config.py` (load the new file), `onboard.py` (copy template),
  `docs/PRIVACY_ARCHITECTURE.md`, `docs/PII_Anonymization*.md`.
- No new third-party dependency; `location.db` uses the same
  SQLCipher/plain-sqlite opening path as `health.db`.
