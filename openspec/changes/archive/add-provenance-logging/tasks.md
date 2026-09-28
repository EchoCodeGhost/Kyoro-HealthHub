## 1. Shared infrastructure

- [x] 1.1 Move `_git_commit_hash()` from `modules/pipeline_runner.py` to `modules/base.py`; re-export it from `pipeline_runner.py` for its existing internal callers
- [x] 1.2 Add self-healing `git_commit` column check to `log_import()` (`PRAGMA table_info(import_log)` → `ALTER TABLE ... ADD COLUMN git_commit TEXT` if missing) before the `INSERT`
- [x] 1.3 Add `person: str | None = None` parameter to `log_import()`, resolved via the existing `resolve_person()` helper; populate both `person` and `git_commit` in the `INSERT`
- [x] 1.4 Factor `_log_compute_run()` into a shared `_log_pipeline_run(table_name, script_name, returncode, duration_s)` helper in `pipeline_runner.py`
- [x] 1.5 Add `analysis_log` table (same shape as `compute_log`: `id, ts_run, script, git_commit, returncode, duration_s`) via `_log_pipeline_run()`, and a `log_analysis=True` option on `run_pipeline_script()` mirroring `log_compute=True`

## 2. Wire analysis logging into analyse_all.py

- [x] 2.1 Read `analyse_all.py`'s current `run_script()` (analyse_all.py:186) in full — found real, load-bearing behavior (per-script log files, `MPLBACKEND`/`KYORO_ANALYSES_DIR` env injection, dry-run support) not present in `pipeline_runner.run_pipeline_script()`; decided NOT to replace it (see design.md decision + risk update)
- [x] 2.2 Call `pipeline_runner._log_analysis_run(script_path.name, result.returncode, elapsed)` directly from inside the existing `run_script()`, at its existing return point — no change to its subprocess-invocation logic, env handling, or dry-run behavior
- [x] 2.4 Verified via isolated test (mocked `open_db`) that `_log_analysis_run`/`_log_compute_run` self-heal and record correctly, including a non-zero-returncode case. A full real-data `analyse_all.py` run was not executed this session (the real `health.db` is large enough that this would take a long time) — the underlying mechanism is proven; a real end-to-end run is reasonable to do once, non-blocking, next time `analyse_all.py` runs normally

## 3. check_import_logging.py heuristic

- [x] 3.1 Extend `check_file()` to additionally flag `log_import(` calls with no `person=` keyword present on the same call — as a distinct, non-blocking warning category (not a new hard-fail condition), so the report shows partial-rollout progress instead of hiding it
- [x] 3.2 Update the script's own docstring (`@method`, `@limits`) to describe the new warning category accurately

## 4. Reference implementations — grew larger than "reference only" after review

- [x] 4.1 `import_shotsy.py` updated to pass `person=` explicitly (already resolved it at the top of `run()` — trivial, safe change)
- [x] 4.2 All 9 migration scripts fixed earlier this session got real person-handling, not just honest logging — split into three groups after careful per-script review (not the original two-group guess):
  - **Explicitly person-filtered in SQL, real `--person` CLI flag added**: `backfill_travel_environment_person.py`, `curate_acute_medication_courses.py`, `pseudonymize_polar_device_serials.py`
  - **Implicitly single-person via `POLAR_DIR`/device-registry scope — made genuinely `--person`-aware**: `fix_polar_247hr_device_ids.py`, `fix_polar_training_device_ids.py` got real `--person`/`--polar-dir` flags, backed by a new `polar_serial_to_device_id_for_person()` in `import_polar.py` (queries the `devices` table's existing `person` column instead of the global config-derived serial map — the existing module-level `_POLAR_SERIAL_TO_DEVICE_ID` used by the live daily import pipeline is untouched, zero risk to it, verified by test). Also added `AND person=?` to their UPDATE WHERE clauses — a genuine correctness fix, not just logging (previously these could have touched another person's rows sharing the same date in a multi-person install). `fix_polar_wrist_device_attribution.py` got the same `--person`/WHERE-clause treatment, but with a documented remaining gap: `polar_wrist_date_reassignments` itself lives in a single, non-person-keyed config structure — the flag filters which rows a reassignment can touch, but not where the reassignment rules come from (see design.md decision + open question).
  - **Genuinely cross-person by design, `person=None` passed explicitly**: `dedupe_plaintext_device_ids.py`, `pseudonymize_device_person_identifiers.py`, `rename_kiste_export_source.py`
  - Required extending `log_import()`'s `person` handling to a three-state design (unset → default; explicit value → that value; explicit `None` → `NULL`, never silently `OWN_PERSON_ID`) — verified correct via isolated test for all three states
- [x] 4.3 `check_import_logging.py --path scripts/migrations` → 0 warnings, all 9 person-aware. `--path scripts/importers` → 0 hard failures, 26/67 soft warnings (accurate rollout-in-progress signal, `import_shotsy.py` no longer among them)

## 5. Docs

- [x] 5.1 Updated `docs/CONTRIBUTING.md` "Log the import" section — was showing a stale raw `conn.execute(INSERT INTO import_log...)` example that didn't even use the `log_import()` helper; replaced with the actual current call shape plus guidance on when to pass `person=None` explicitly
- [x] 5.2 Mirrored in `docs/CONTRIBUTING_DE.md`
- [x] 5.3 Added a short "Analysis scripts get logging automatically" note (both language versions)

## 6. Verification

- [x] 6.1 `python3 tools/qa_check.py` → 8/8 passed (after `tools/gen_docs.py` regeneration for the touched docstrings)
- [x] 6.2 Isolated in-memory/file-based tests (not a copy of the real `health.db` — impractical for a quick check given its size, used synthetic DBs instead) confirmed self-healing for `import_log.git_commit`, `compute_log`, `analysis_log`, and the new `polar_serial_to_device_id_for_person()`
- [x] 6.2b `python3 -m pytest tests/unit -q` → 200/200 passed, including `test_pipeline_runner.py`
- [x] 6.3 `openspec validate --changes` — run once more after all edits above, before archiving

## 7. Follow-up inventory (explicitly NOT done in this change)

- [x] 7.1 25 remaining `log_import()` call sites in `scripts/importers/` — investigated further in a follow-up session, turned out bigger than "wire an existing person value through": only 2 of the 25 (`import_airquality.py`, `import_outbreak_data.py`) already resolved `person` internally. The other 23 had **no `run()` function at all** (only `main()`) and wrote `OWN_PERSON_ID` directly at 2-9 call sites each — a previously-uninventoried population, distinct from the ~14 importers `add-importer-person-override-convention` already covers. Initially flagged for deferral to a follow-up change, then implemented the same session instead (user: "Setze den Change jetzt um") — see `openspec/changes/add-importer-person-parameterization-remaining/` (all 23 + one more found during verification, `import_travel_environment.py`, now parameterized).
- [ ] 7.2 Open question (design.md): whether an `analyse_all.py`-side chain-of-custody check should be added later
- [ ] 7.3 New, found during 4.2: `polar_wrist_date_reassignments` config structure is not person-keyed — a real config-schema change (sibling to `add-importer-person-override-convention`, but for this one config value), deliberately not attempted this session
- [ ] 7.4 Actor/operator identity logging (who *ran* a script, as opposed to whose data it touched) — explicitly discussed and deferred; no existing session/auth identity to hook into for the multi-patient clinic deployment without touching its TOTP auth system, which this session didn't want to improvise against
