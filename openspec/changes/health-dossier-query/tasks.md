## 1. Foundations: schema discovery, date-window, lab nearest-value lookup

- [ ] 1.0 Implement generic table discovery: `discover_day_tables(conn)` introspecting `sqlite_master`/`PRAGMA table_info` for tables with a `date` or `ts` column, returning table name, matched column, and whether a `person` column exists; exclude tables on an explicit `EXCLUDED_TABLES` set (with inline one-line reasons) covering: handled-elsewhere tables (`measurements`, `session_metrics`, `sessions`, `lab_results`, `lab_manual`, `user_context`, any location table), administrative tables (`schema_version`, `import_log`, `import_file_hashes`, `compute_log`, `devices`, `device_firmware_history`, `persons`, `source_priority`, `data_quality_flags`), population-level surveillance tables (`outbreak_events`, `wastewater_amelag`, `ed_syndromic_surveillance`, `outbreak_exposure`), and non-day-keyed reference tables (`genetic_variants`, `genetic_risk_markers`)
- [ ] 1.0a Unit test for `discover_day_tables`: confirms it finds known date/ts-keyed tables (e.g. `symptoms`, `weather_station`, `self_care`), confirms excluded tables are never returned, confirms a table without a `person` column is flagged as such (for the unconditional-include path) rather than silently dropped
- [ ] 1.0b Generic query execution: for each discovered table, build and run `SELECT * FROM <table> WHERE <date_col> BETWEEN :from AND :to [AND person = :person]`, grouping results by table/source for display
- [ ] 1.1 Add `nearest_lab_values(conn, target_date, max_distance_days=90, person=OWN_PERSON_ID)` to a shared module (e.g. new `scripts/modules/lab_lookup.py`), querying `lab_manual`/`lab_results` per `parameter`, returning the closest value and its actual date, omitting parameters beyond `max_distance_days`
- [ ] 1.2 Unit tests for `nearest_lab_values`: exact-day match, nearest-within-cutoff match, beyond-cutoff omission, multiple parameters with independent nearest dates
- [ ] 1.3 Extend `context_query.py`'s underlying query function to accept a `date_from`/`date_to` window (reuse, don't fork) if it doesn't already support one cleanly
- [ ] 1.4 Add `stays_and_tracks_for_window(person, date_from, date_to)` to `scripts/modules/location_store.py`, reusing existing privacy-zone redaction internally; no new SQL outside this module

## 2. Core health_dossier.py script

- [ ] 2.1 Create `scripts/query/health_dossier.py` with SPDX header, `t("DE","EN")` i18n, `argparse` CLI accepting a single date positional, `--days N` (lookaround, default 0), `--from`/`--to`, `--last <N><unit>` (generic parser: any non-negative integer N, unit ∈ d/w/m/y — not a fixed preset list), `--json`
- [ ] 2.1a Unit tests for the `--last` parser across several arbitrary N/unit combinations (e.g. 4d, 4w, 17w, 3m, 2y) confirming each resolves to the correct `date_from`/`date_to` — not just one hardcoded example
- [ ] 2.2 Implement single-day assembly: measurements/sessions (health.db), `symptoms` (health.db, direct query), `user_context` join (via 1.3), nearest lab values (via 1.1), location stays/tracks (via 1.4), plus every table returned by `discover_day_tables`/1.0b (weather, air quality, pollen, home environment, self-care, nutrition, cognitive/functional tests, etc.), each rendered under its own table-name/source heading
- [ ] 2.3 Implement the unverified-documents section: scan `medicine/arztbriefe/`, `medicine/laborbefunde/`, `medicine/krankenakte/` for filename/mtime matches within the window; render as a clearly separated, explicitly-labeled "unverified" block; show a "no candidates found" message when empty
- [ ] 2.4 Implement range mode: loop the single-day assembly (2.2+2.3) over every calendar day in `--from`/`--to` or the resolved `--last` window, using `resolve_timezone()`/`cfg.home_timezone` (never hardcoded) to resolve "today" for `--last`; produce one dated section per day, no cross-day aggregation
- [ ] 2.5 Implement "no data found" messaging per source/day rather than silent empty output
- [ ] 2.6 Implement `--json` output mode mirroring the text structure exactly (same sections/sources)

## 3. Optional LLM pattern analysis

- [ ] 3.1 Add `--llm` flag; wire into the same provider-resolution path as `health_query.py` (opt-in, configured via `health_config.json`, no silent default)
- [ ] 3.2 Build the LLM payload from an explicit allow-list of dossier sections (not the full object): measurements/sessions/symptoms/user_context/lab values summary, with location reduced to `region_of()`/`stored_region()` output only, and the unverified-documents section excluded by default
- [ ] 3.3 Write the analysis prompt generically (no hardcoded diagnosis names/condition identifiers) — condition-specific framing, if any, flows only from existing config values already used elsewhere in the pipeline
- [ ] 3.4 Handle "no provider configured" explicitly: clear error, no fallback to an unconfigured default
- [ ] 3.5 Verify `--llm` works unchanged across both single-day and range mode (reuses the same payload builder over however many per-day sections were assembled)

## 4. Privacy and convention compliance

- [ ] 4.1 Run `scripts/utils/check_source_privacy.py` against the new files — must exit 0
- [ ] 4.2 Confirm no raw coordinates, place names, or un-pseudonymized device/person identifiers appear anywhere in `health_dossier.py` itself (all such data stays behind `location_store.py`'s existing accessors)
- [ ] 4.3 Confirm `person` is always `OWN_PERSON_ID`/resolved from config, never a literal `'self'`, anywhere in the new code
- [ ] 4.4 Confirm no hardcoded IANA timezone string anywhere in the new code (range/`--last` resolution included)

## 5. Manual verification

- [ ] 5.0 Run `discover_day_tables` against the live schema and manually review the full list of included vs. excluded tables once — confirm nothing date-keyed and clearly day-relevant was missed by the exclusion list, and nothing clearly irrelevant/administrative leaked in
- [ ] 5.1 Run `health_dossier.py <a real recent date>` and manually cross-check the output against what `context_query.py --with-context`, a direct lab query, and a location export would separately show for that day
- [ ] 5.2 Run `health_dossier.py --last 4w` and `health_dossier.py --last 17w` (arbitrary N/unit, not just the one example) and confirm 28 resp. 119 per-day sections appear, dated correctly, with no aggregation
- [ ] 5.3 Run with `--llm` once against a configured provider and manually inspect the actual outgoing payload (e.g. via provider request logging) to confirm the allow-list/minimization in 3.2 is honored in practice, not just in code review
- [ ] 5.4 Confirm behavior on a date/range with genuinely no data in any source (clear "no data" messaging, no crash)
