## Context

Location data enters Kyoro-HealthHub through several unrelated paths:

- Sport tracks: `import_tracks` (GPX from several devices) and
  `import_garmin` (activity details) write `health.db::session_tracks` at
  precision 5 (~1 m) via `utils.anonymize.round_coords(..., precision=5)`.
- Stays and travel: `import_oura_csv` derives stays into `location_stays`
  (precision 2), `import_travel_environment` rounds to precision 2; there
  are also `location_history` and `location_stays_geocoded` (with
  reverse-geocoded place names).
- Photos: `imaging_utils.record_photo_location()` writes
  `health.db::photo_locations` (precision 2) from `import_skin` and from
  photos embedded in lab-report PDFs (`import_lab_results`). Nothing reads
  `photo_locations`; it has no reference to the image file.
- Environment at home: `fetch_daily`, pollen, air-quality, weather and home
  automation importers round the configured home position to precision 2
  and send it to external APIs.
- Text scrubbing for cloud calls (the location/coordinate redaction used by
  the synthesis panel) removes coordinates from prompt text, but there is
  no allowlist, and images passed to `call_llm` are not re-checked for
  metadata at send time.

`identity.db` already holds a pseudonym salt (`pseudonym_salt`) used for
device and person pseudonyms. `imaging_files` lives in `medicine.db` with a
unique `file_path`.

## Goals / Non-Goals

**Goals:**
- One place (`location.db`) and one module for all coordinates.
- One configuration file for all location decisions, adjustable per
  importer and per file type, safe by default.
- One outbound rule for LLMs, external APIs and exports.
- Provenance per location entry (source file + hashes) so a point can be
  traced back to the file it came from.
- Keep `health.db`/`medicine.db` free of coordinates so they can be shared
  as intended by `post_import_sanitize`.

**Non-Goals:**
- Reverse geocoding or new location features.
- Detecting location from image content (backgrounds, street signs).
- Changing how environment data itself is analysed.
- A general place-name gazetteer.

## Decisions

### D1: Separate `location.db`, not `identity.db` or `health.db`
`identity.db` is a small mapping store; millions of track points do not
belong there. Keeping them in `health.db` contradicts its shareability. A
separate `location.db` under the data directory, opened through the same
helper as `health.db` (SQLCipher when `db_key` is set), keeps coordinates
isolated and backup-able on their own.
*Alternatives:* column-level encryption in `health.db` (adds key
management and loses SQL on coordinates); coordinates in `identity.db`
(wrong size class).

### D2: One module `scripts/modules/location_store.py`
Responsibilities: open `location.db`, resolve the policy for
(importer, file type), apply precision and zones, write registry rows,
compute location tokens, and serve the single output function for prompts
and exports. Importers never round or write coordinates themselves.

### D3: Policy file `location_privacy.json`
Loaded by `health_config.Config` like `synthesis_panel.json` (separate file
in `KYORO_CONFIG_DIR`). Sections: `default`, `importers`, `zones`,
`external_api`, `llm`, `exports`. File types are matched by lower-case
extension including the dot; the importer key is the module name
(`import_skin`). A missing file means "store nothing" plus one warning —
not `sys.exit`, because importing medical data must keep working; the
safe outcome of a missing file is less data, not a crash.

### D4: Precision as decimal places, applied before write
Decimal places are already the project's unit (`round_coords`). 5 ≈ 1 m,
4 ≈ 11 m, 3 ≈ 110 m, 2 ≈ 1.1 km, 1 ≈ 11 km, 0 ≈ 111 km. `store: "region"`
stores no coordinates, only the federal state (via
`modules.geo_bundesland`) or the country.

### D5: Hashes of original and stored file
SHA-256 of the file as received (before metadata stripping) proves which
input a point came from; SHA-256 of the stored file links to the archived
copy. Deduplication uses the original hash plus timestamp.

### D6: Privacy zones from existing configuration
Zone centres come from `privacy_check.patient_places` (geocoded once,
locally, from a configured coordinate list — see open question) and the
configured home position. Zone handling happens inside `location_store`,
so every source benefits.

### D7: Location token
`LOC-` + first 8 hex characters of HMAC-SHA256(salt, "<lat>|<lon>|<precision>")
using the existing pseudonym salt in `identity.db`. Same cell → same token;
not reversible without the salt.

### D8: Outbound enforcement
- LLM: one function `location_store.for_prompt(caller, refs, level)`
  checks `llm.allow`; `call_llm` re-encodes images without metadata.
- Prompt text: one filter `location_store.filter_prompt_text(text,
  caller)` built on `modules.location_redaction` (coordinate and place
  detection) applies the caller's level (none/region → remove, raster →
  round, token → replace). `call_llm` calls it when the provider's
  `is_local` is false; the scripts that call a cloud API directly
  (`analyse_synthesis`, `analyse_clinical_addendum`,
  `import_medical_motion`, `llm_benchmark`) call it themselves. In
  `analyse_synthesis._scrub_for_cloud` it replaces the unconditional
  `redact_locations` step; the address/name/number scrubbing there stays
  unconditional. The caller defaults to the stem of `sys.argv[0]` so
  existing `call_llm` call sites need no change.
- External APIs: `location_store.for_external_api(lat, lon)` applies
  `external_api.precision`; the weather/pollen/air importers call it
  instead of `round_coords`.
- Exports: `export_health.py` drops location columns unless the profile is
  in `exports.allow`.

### D9: Three stages
Stage 1 (registry, policy, outbound rules, photos/PDFs) brings the rule
into force for new data without touching large tables. Stage 2 adds zones.
Stage 3 migrates `session_tracks` and the `location_*` tables and adapts
readers — the only breaking part, done last and with a dry run.

## Risks / Trade-offs

- [Coarsening is irreversible] → Defaults equal today's precision for every
  source that stores something; the migration in stage 3 copies values as
  they are, it does not coarsen existing tracks unless zones apply.
- [Readers of moved tables break] → Stage 3 lists every reader (grep for
  the table names), adapts them in the same change, and keeps a
  compatibility view in `health.db` only if a reader cannot be adapted;
  the view must not expose coordinates at higher precision than the policy.
- [Missing policy file silently drops locations] → One clear warning per
  run and a check in `onboard.py`/doctor-style validation.
- [Zone centres themselves are sensitive] → They are never written to
  `location.db`; they are computed in memory from configuration.
- [Hash of the original file can identify a file shared elsewhere] → Hashes
  stay in `location.db`, which never leaves the machine.

## Migration Plan

1. Stage 1: create `location.db`; new imports use the registry;
   `photo_locations` rows are copied into the registry with
   `source_file`/hashes unknown (NULL) and a migration marker, then the
   table is no longer written. Rows from `import_lab_results` are dropped
   (policy `none`) after a dry-run report.
2. Stage 2: enable zones for new data; optional one-off re-coarsening of
   existing track points inside zones (dry run first).
3. Stage 3: copy `session_tracks`, `location_stays`, `location_history`,
   `location_stays_geocoded` into `location.db`, verify row counts and
   checksums, switch readers, then drop the tables from `health.db` after
   a backup. Rollback: restore the `health.db` backup and revert readers.

## Open Questions

- Zone centres for `privacy_check.patient_places`: geocoding a place name
  needs a lookup. Proposal: the policy file takes optional coordinates per
  place (`zones.centres`), filled by the user locally; places without
  coordinates are skipped with a warning (no online geocoding).
- Whether `location_stays_geocoded` place names are needed at all after
  the migration, or only the region.
