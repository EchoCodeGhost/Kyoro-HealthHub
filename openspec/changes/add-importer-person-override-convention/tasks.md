## 1. Spec extension

- [x] 1.1 Add requirement "Functional person override in importers" to `cross-cutting-conventions`
- [x] 1.2 Formulate scenario "Person parameter declared but not passed through"
- [x] 1.3 Formulate scenario "Shared device"
- [x] 1.4 Document the boundary: does not apply to structurally single-person sources

## 2. import_ecg_logger.py (already done in the same session)

- [x] 2.1 Added `run(conn, data_path, lang='de', person=None) -> ImportResult`
- [x] 2.2 Added `--person` CLI flag in `main()`
- [x] 2.3 Passed `person` through to both write paths (`ppi_raw`, `ecg_logger_sessions`)
- [x] 2.4 Extracted the `_import_files()` core loop so `run()` and `main()` don't duplicate it

## 3. Inventory of remaining importers (not part of this change)

- [x] 3.1 Listed all importers with `run(conn, ...)` (14 total incl. `import_ecg_logger.py`;
      13 more: `import_dwd_brightsky.py`, `import_kyoro_symptoms.py`, `import_fundus.py`,
      `import_bearable.py`, `import_camerahRV.py`, `import_activity_log.py`,
      `import_travel_environment.py`, `import_nightmare_log.py`, `import_shotsy.py`,
      `import_symptomtagebuch.py`, `import_outbreak_data.py`, `import_symptomtrack_export.py`,
      `import_tracks.py`)
- [x] 3.2 For each finding, checked whether `person` is actually passed through to the write path,
      AND whether `main()`/CLI even has a `--person` flag at all (the actually-used path,
      see proposal.md — `run()` has no caller in the code for any of these importers)

      Result:
      - **Correctly wired, including a `--person` CLI flag** (reference examples, no fix needed):
        `import_shotsy.py`, `import_symptomtrack_export.py`
      - **`run()` internally correct (person passed through via `resolve_person()`/fallback), but
        NO `--person` CLI flag** — `run()` itself has no caller, so the only actually usable path
        (the CLI) is still hardwired to the owner's own person:
        `import_kyoro_symptoms.py`, `import_bearable.py`, `import_activity_log.py`,
        `import_nightmare_log.py`, `import_tracks.py`
      - **`person` parameter declared but NEVER used in the function body** (exactly the
        anti-pattern from requirement "Functional person override in importers"), and also
        no CLI flag: `import_camerahRV.py`, `import_symptomtagebuch.py`
      - **No `person` parameter at all, `OWN_PERSON_ID` hardwired, no CLI flag**:
        `import_fundus.py` (medical fundus images — plausible shared device in an
        ophthalmology practice, clinically relevant case), `import_outbreak_data.py` (global
        outbreak data — edge case, data isn't personal in the strict sense,
        lower priority)
      - **`person` parameter exists, but the table column is never populated —
        REAL, ACTIVE data defect in the production DB** (not a theoretical risk, already occurred):
        `import_travel_environment.py` — the `pollen`/`biometeo` tables only have `person` as the
        schema default `'unknown'`, never set explicitly; verified against the real DB:
        the large majority of all rows carry `person='unknown'` instead of the real pseudonym ID
      - **No real hit** (no `person` column in the target table, the data source is
        inherently not personal — weather at the home location, not measured on the body):
        `import_dwd_brightsky.py`
- [x] 3.3 Submitted the gaps found as their own fixes, not part of this change — priority:
      1. [x] `import_travel_environment.py` / `import_airquality.py` — the code itself was
         already correct (the underlying bug had long been fixed, no active code fix
         needed); instead created `migrations/backfill_travel_environment_person.py` and
         ran it against the real DB (migrated the historical `person='unknown'` rows across
         pollen/biometeo/air_quality to the real pseudonym ID, at the user's explicit
         request — a deliberate deviation from the `pseudonymize_device_person_identifiers.py`
         exclusion rule for 'unknown', see the migration's `@limits` docstring for the rationale)
      2. [x] `import_fundus.py` — added `person` (via `resolve_person()`) to `run()`/
         `_import_file()`, added the `--person` CLI flag. In the process found and also
         fixed a separate, blocking bug: `_ensure_db()` called
         `create_medicine_imaging_schema.py`'s `main()`, whose `argparse` read the
         CALLING process's `sys.argv`, which would have crashed on every real invocation with
         `--person`/file paths — core logic now extracted into
         `ensure_schema(force=False)` without argparse. Also, `medicine_imaging.db`'s
         `import_log` table was missing the columns `data_path`/`rows_skipped` (among
         others) that `modules/base.py`'s `log_import()` expects —
         every real fundus import therefore crashed BEFORE the commit and also lost
         the actually-imported row, not just the log entry. Fixed via an
         `ALTER TABLE` migration in `_migrate()`, verified against a copy AND then
         against the real DB (existing imaging_files rows
         unchanged).
      3. [x] `import_camerahRV.py`, `import_symptomtagebuch.py` — passed `person` through
         to all write functions (`_save`/`_save_hr_to_measurements`/
         `_save_rr` resp. `_save`), added the `--person` CLI flag (was
         entirely missing from `main()`). For `import_symptomtagebuch.py` also
         scoped `--rebuild` to the selected person (previously blindly deleted all persons).
         Both verified against real data (test copy): new rows land
         correctly under the passed-in person, existing rows untouched.
      4. [x] Added the `--person` CLI flag to the 5 importers that were already internally correct:
         `import_kyoro_symptoms.py` (additionally scoped the `--rebuild` DELETE + completion
         summary to the person, previously both were unfiltered), `import_bearable.py`,
         `import_activity_log.py`, `import_nightmare_log.py` (had no argparse at all,
         only sys.argv[1] — now a proper CLI with --person), `import_tracks.py`.
         Verified against real data (test copy): new rows under the test person
         in measurements/symptoms/sessions, existing rows untouched.
      5. [x] `import_outbreak_data.py` — reviewed and deliberately NOT fixed: it fetches
         WHO/ECDC/RKI case-report data plus a static endemic-disease reference table
         (location/pathogen/season), both independent of the owner's own travel/location
         history (no connection to travel_history.json/location_stays found in the code).
         `person` here isn't a real data-ownership field, just a
         blanket relevance tag on otherwise fully generic data — edge case
         deliberately documented as an exception in the docstring (`@limits.de`/`@limits.en`),
         not fixed.
- [ ] 3.4 Separate, larger question (not part of this change): whether/how `import_all.py` should call
      each importer's `run()` in-process instead of via subprocess
