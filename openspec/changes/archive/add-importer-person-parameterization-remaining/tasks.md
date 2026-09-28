## 1. Mechanical fixes

- [x] 1.1 `import_airquality.py` — wired the already-resolved `_person` value into both `log_import()` calls (`import_airquality`, `import_biometeo`); verified `_person` is genuinely in scope at each call site (not just present somewhere in the file)
- [x] 1.2 `import_outbreak_data.py` — **correction during implementation**: this file does NOT already resolve a real per-person value (initial grep-based categorization was wrong — it matched the word "person" in a docstring, not an actual parameter). This is the same file `add-importer-person-override-convention` already reviewed and *deliberately* did not parameterize (WHO/ECDC/RKI outbreak data isn't person-specific). Fixed with explicit `person=None`, matching the same pattern already used for `dedupe_plaintext_device_ids.py` etc. in `add-provenance-logging` — not moved to group 2/3/4, no `run()` changes needed.

## 2. Single-file/single-directory importers (simplest shape)

- [x] 2.1 `import_aemet.py`
- [x] 2.2 `import_amelag.py` — non-personal wastewater surveillance data; only `log_import(..., person=None)` on the outbreak_data precedent, data rows keep `OWN_PERSON_ID`
- [x] 2.3 `import_ecowitt_csv.py` — treated as personal (home weather station)
- [x] 2.4 `import_hilo_screenshots.py`
- [x] 2.5 `import_homeassistant.py` — only `indoor_air_quality` table has a `person` column (1 write site); `home_environment`/presence/weather tables have none, correctly left untouched
- [x] 2.6 `import_kubios_orthostatic.py`
- [x] 2.7 `import_notaufnahme.py` — non-personal ED surveillance data, `log_import(..., person=None)`
- [x] 2.8 `import_pollen_dwd.py` — non-personal pollen surveillance data, `log_import(..., person=None)`
- [x] 2.9 `import_pollen_google.py` — non-personal pollen surveillance data, `log_import(..., person=None)`
- [x] 2.10 `import_renpho_tape.py`
- [x] 2.11 `import_saliva_ph.py`
- [x] 2.12 `import_sleep_cycle.py`
- [x] 2.13 `import_urine_strip.py`
- [x] 2.14 `import_womanlog.py` (5 write sites)

## 3. Directory-scanning importers (glob over multiple files)

- [x] 3.1 `import_fddb.py` — includes the `aggregate_daily()` write-side aggregate (not just diary/weight rows)
- [x] 3.2 `import_hrv4training.py`
- [x] 3.3 `import_hrv_logger.py`
- [x] 3.4 `import_migraine.py`
- [x] 3.5 `import_polar_accesslink.py` — most complex file in this batch: OAuth2 `--setup` member-id registration + 4 API-fetch functions (sleep, nightly recharge, exercises, activities) all threaded

## 4. Larger/multi-subsource importers (need closer individual reading)

- [x] 4.1 `import_apple.py`
- [x] 4.2 `import_beurer.py` (scale/glucose/thermometer sub-sources) — new `--person` flag kept deliberately separate from the existing `--user` CSV-row filter (which selects whose rows within a shared-device CSV export to import; `--person` controls DB attribution), mirroring the `import_fundus.py` shared-device precedent
- [x] 4.3 `import_lab_results.py`
- [x] 4.4 `import_oura_csv.py` — largest file in this batch (34-entry `IMPORTERS` dispatch table); only 13 of the write functions touch a `person` column, so a local `_PERSON_AWARE` set gates the dispatch loop, mirroring `import_all.py`'s own `_PERSON_AWARE` allowlist pattern

## 5. Verification

- [x] 5.0 **found during verification, not in the original 25**: `import_travel_environment.py` — `run()` forwarded no `person` to its three delegate calls (`import_airquality()`, `import_biometeo()`, `fetch_and_import()` from `import_aemet.py`) despite all three already accepting one; threaded `person` through `run()`/`main()`/`_fetch_openmeteo()`/`_fetch_aemet()`
- [x] 5.1 `python3 scripts/check_import_logging.py --path scripts/importers` → 0 person-warnings
- [x] 5.2 `python3 -m compileall -q scripts/importers` clean
- [x] 5.3 Per-file: grep confirms no remaining `OWN_PERSON_ID` at a DB-write call site (only in the `resolve_person`/default-fallback path)
- [x] 5.4 `python3 -m pytest tests/unit -q` still 200/200
- [x] 5.5 `python3 tools/qa_check.py` 8/8 (ruff skipped — not installed in this environment, pre-existing/environmental, not a regression)
- [x] 5.6 `openspec validate --changes` green (10/10 changes)

## 6. import_all.py allowlist

- [x] 6.1 Extended `_PERSON_AWARE` in `import_all.py` with the 11 files from this batch that are both (a) registered in `IMPORTERS` and (b) gained a real `--person` CLI flag: `import_apple.py`, `import_homeassistant.py`, `import_polar_accesslink.py`, `import_oura_csv.py`, `import_beurer.py`, `import_renpho_tape.py`, `import_womanlog.py`, `import_migraine.py`, `import_sleep_cycle.py`, `import_fddb.py`, `import_travel_environment.py`. The other 14 files either aren't in `IMPORTERS` at all (need a file/dir argument — `import_aemet.py`, `import_ecowitt_csv.py`, `import_hilo_screenshots.py`, `import_kubios_orthostatic.py`, `import_saliva_ph.py`, `import_urine_strip.py`, `import_hrv4training.py`, `import_hrv_logger.py`, `import_lab_results.py`) or deliberately have no `--person` flag (non-personal data: `import_amelag.py`, `import_notaufnahme.py`, `import_pollen_dwd.py`, `import_pollen_google.py`, `import_outbreak_data.py`) — adding either to the allowlist would either be a no-op or crash the importer with "unrecognized arguments"
