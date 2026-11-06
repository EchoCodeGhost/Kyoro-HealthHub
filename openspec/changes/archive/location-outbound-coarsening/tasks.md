## 1. Region data

- [x] 1.1 `tools/build_region_data.py`: download the pinned Natural Earth admin-1 release, verify the checksum, clean codes (D3), compute unit areas, simplify to 0.02°, keep code, country code, `name_de`, `name_en`, area; write one gzip file
- [x] 1.2 Generate the data file and commit it; add `shapely` to `requirements.txt` and the lock file
- [x] 1.3 Test for the build tool on a tiny synthetic input (code cleanup, area, output shape)

## 2. Region lookup

- [x] 2.1 `location_store.region_of()` on the data file with an STRtree; 5 km coastal fallback; `XX` for unknown and invalid input
- [x] 2.2 `location_store.region_name(code)` with German/English names via `t()`
- [x] 2.3 Tests with public city coordinates: Würzburg `DE-BY`, Salzburg Austrian code, Basel `CH-BS`, Las Palmas `ES-GC`, Palma `ES-PM`, Honolulu `US-HI`, open sea `XX`, point 0.5 km off a coast
- [x] 2.4 Update callers and tests that expect names ("Bayern", "Ausland") to codes; `export_health` writes codes and a name column

## 3. Registry

- [x] 3.1 Schema: `region` column, nullable `lat`/`lon`, unique index with `region` and `COALESCE` on `lat`/`lon`; migration of existing `location.db`
- [x] 3.2 `record()`: region from the original point, country code when the unit is smaller than the stored cell (D4); `store: "region"` writes region only
- [x] 3.3 `for_prompt` and exports use the stored region
- [x] 3.4 Tests: region before coarsening, small unit at precision 1, region-only entry, region-only duplicate, migration keeps entries

## 4. Outbound precision

- [x] 4.1 `for_external_api(lat, lon, place=False)` with `external_api.precision` (default 1) and `external_api.place_precision` (default 2); missing policy file → 1
- [x] 4.2 Switch every external request listed in design.md from `round_coords()` to `for_external_api()`; `geocode_stays` and the town lookup in `track_location` use `place=True`
- [x] 4.3 Template: `external_api.precision` 1, `place_precision` 2, comment on trade-offs
- [x] 4.4 Tests: default 1, place 2, missing file 1; a grep-style test that no external URL builder uses `round_coords()` directly

## 5. Keyed services and pollen region

- [x] 5.1 `external_api.services.google_pollen` (template `false`); `import_pollen_google` and `fetch_daily` skip with a hint unless enabled
- [x] 5.2 DWD pollen region ID in `health_config.json`; `import_pollen_dwd --list-regions` from the downloaded file; fallback estimate with the missing regions added and a warning
- [x] 5.3 Tests: key without opt-in sends nothing, configured DWD region used, fallback warns

## 6. Documentation and checks

- [x] 6.1 Table of external services (what they receive, key yes/no, setting) in `docs/PRIVACY_ARCHITECTURE.md` and in a new `docs/PRIVACY_ARCHITECTURE_DE.md` (German version of the whole document, same structure)
- [x] 6.2 Region and outbound settings in `docs/PII_Anonymization.md` and `docs/PII_Anonymization_DE.md`; `docs/SETUP.md` / `docs/SETUP_DE.md` for the DWD pollen region and the Google Pollen opt-in
- [x] 6.3 `@limits` of the matching scripts state the point-plus-radius approximation; `region_of` states small units and disputed areas
- [x] 6.4 `tools/gen_docs.py`, `tools/qa_check.py`, `scripts/utils/check_source_privacy.py`, pytest, `openspec validate --strict`
