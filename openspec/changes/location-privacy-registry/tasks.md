## 1. Stage 1 — Policy file and template

- [x] 1.1 Create `templates/location_privacy.example.json` with sections `default`, `importers`, `zones`, `external_api`, `llm`, `exports` and the shipped defaults from the spec (none for Hilo, lab PDFs, fundus, FibriCheck and other measurement importers; 2 for skin photos, home environment, stays/travel; 5 for sport tracks; zones enabled, 500 m, zone precision 2; `external_api.precision` 2; `llm.default` none with empty `allow`; `exports.allow` empty)
- [x] 1.2 Add a `location_privacy` property to `health_config.Config` that reads `KYORO_CONFIG_DIR/location_privacy.json` (same pattern as `synthesis_panel`), returning an empty dict when the file is missing
- [x] 1.3 Copy the template in `onboard.py` if the file does not exist yet (never overwrite)
- [x] 1.4 Unit tests: policy resolution order (importer + file type → importer `*` → default), missing file → store nothing, unknown importer → store nothing

## 2. Stage 1 — location.db and registry module

- [x] 2.1 Create `scripts/utils/create_location_schema.py` with the registry table (importer, file_type, source_file, original_sha256, stored_sha256, ts, date, lat, lon, precision, ref_db, ref_table, ref_id, person, created_at) and indexes; idempotent (`CREATE ... IF NOT EXISTS`)
- [x] 2.2 Add `location_db_path` to `Config` and an `open_location_db()` helper in `modules/db.py` using the same encryption path as `open_db()`
- [x] 2.3 Create `scripts/modules/location_store.py`: `resolve_policy(importer, file_type)`, `record(importer, file_type, lat, lon, ts, ...)` applying precision before write and `INSERT OR IGNORE`, `region_of(lat, lon)` via `modules.geo_bundesland`, `location_token(lat, lon, precision)` via HMAC with the salt in `identity.db`
- [x] 2.4 `file_sha256(path)` helper; importers pass the original file hash (before stripping) and the stored file hash (after stripping)
- [ ] 2.5 Unit tests with synthetic coordinates only: precision applied, `store: none` writes nothing, `region` stores no coordinates, duplicate original hash + ts not inserted twice, token deterministic per cell and different across cells

## 3. Stage 1 — Photos and PDFs

- [x] 3.1 `import_skin`: replace `record_photo_location()` with `location_store.record(...)` including hashes and the `imaging_files` reference
- [x] 3.2 `import_lab_results`: stop writing photo positions; policy `none` means the GPS is stripped and discarded
- [x] 3.3 `import_fundus`, `import_fibricheck`: confirm no location is written; add a test that a geotagged input produces no registry entry
- [x] 3.4 Stop writing `health.db::photo_locations`; one-off migration script copies existing rows into the registry (source_file/hashes NULL, migration marker) and drops rows from `import_lab_results`, with `--dry-run`
- [ ] 3.5 Update the main spec `image-importer-pattern` via sync after review (delta already in this change)

## 4. Stage 1 — Outbound rules

- [x] 4.1 Inventory: list every script that sends prompts or images to a remote provider and whether location data can reach the prompt (record the result in this change's design open questions or a short note)
- [x] 4.2 `modules/llm.py::call_llm`: re-encode `image_b64` without metadata before sending to a remote provider
- [x] 4.3 `location_store.for_prompt(caller, ...)` enforcing `llm.allow` (levels none/region/raster/token); default none
- [x] 4.4 Prompt text filter `location_store.filter_prompt_text(text, caller)` on top of `modules.location_redaction`: level none/region → remove coordinates and configured places; raster N → round coordinates to N, remove places; token → replace coordinates with the location token, remove places; returns text + count
- [x] 4.5 Caller identity: helper returning the entry script stem (`sys.argv[0]`), overridable by an explicit `caller=` argument
- [x] 4.6 `modules/llm.py::call_llm`: apply the filter to prompt and system text when the provider's `is_local` is false; no change for local providers
- [x] 4.7 `analyse_synthesis._scrub_for_cloud`: replace the unconditional `redact_locations` step by the filter with caller `analyse_synthesis`; keep address/name/number scrubbing unconditional; adjust `tests/unit/test_synthesis_scrubbing.py`
- [x] 4.8 Direct cloud callers `analyse_clinical_addendum`, `import_medical_motion`, `llm_benchmark`: pass prompt and system text through the filter before the request
- [x] 4.9 `location_store.for_external_api(lat, lon)` applying `external_api.precision`; switch `fetch_daily`, pollen (DWD, Google), air quality, DWD Brightsky, AEMET, Ecowitt and Home Assistant from `round_coords` to it
- [x] 4.10 `export_health.py`: drop location columns unless the profile is listed in `exports.allow`
- [x] 4.11 Tests for 4.2–4.10 with synthetic data (remote vs. local provider via a fake provider object; every level; caller default and override)

## 5. Stage 2 — Privacy zones

- [ ] 5.1 Zone centres: read `zones.centres` (coordinates per configured place) from the policy file plus the configured home position; places without coordinates are skipped with a warning; no online geocoding
- [ ] 5.2 Apply zones in `location_store.record()` for every source whose precision is finer than the zone precision; never store zone centres
- [ ] 5.3 Optional one-off re-coarsening of existing points inside zones, with `--dry-run`
- [ ] 5.4 Tests: track starting/ending inside a zone, zones disabled, place without coordinates

## 6. Stage 3 — Migrate tracks and stays (BREAKING)

- [ ] 6.1 List every reader of `session_tracks`, `location_stays`, `location_history`, `location_stays_geocoded` (grep) and record the list here
- [ ] 6.2 Migration script: copy the four tables into `location.db`, verify row counts and checksums, `--dry-run` first, backup of `health.db` before dropping
- [ ] 6.3 `import_tracks`, `import_garmin`, `import_oura_csv`, `import_travel_environment` write via `location_store`
- [ ] 6.4 Adapt every reader from 6.1 to `location.db` (via `location_store` read helpers)
- [ ] 6.5 Drop the migrated tables from `health.db` (and from `create_schema.py`) after verification
- [ ] 6.6 Check that `health.db` and `medicine.db` contain no latitude/longitude values (test or check script)

## 7. Documentation and checks

- [ ] 7.1 Update `docs/PRIVACY_ARCHITECTURE.md` and `docs/PII_Anonymization.md` / `_DE.md` (location.db, policy file, outbound rule)
- [ ] 7.2 Structured docstrings on all new/changed scripts; `python tools/gen_docs.py`
- [ ] 7.3 `python tools/qa_check.py`, `python scripts/utils/check_source_privacy.py`, pytest green
