## Context

Two related audit-trail mechanisms already exist independently:

- `import_log` (health.db/medicine.db, defined in `scripts/utils/create_schema.py`) — written by `log_import()` in `modules/base.py`, called in-process by individual importer/migration scripts before `conn.commit()`. Has a `person` column that is never populated (no caller ever had a way to set it — `log_import()`'s signature doesn't accept it).
- `compute_log` (health.db, defined ad-hoc via `CREATE TABLE IF NOT EXISTS` inside `modules/pipeline_runner.py`) — written by `_log_compute_run()`, called by `run_pipeline_script(..., log_compute=True)`, itself called only from `compute_all.py`. Already has `script`, `git_commit` (via a working, cached `_git_commit_hash()` helper using `git rev-parse HEAD`), `returncode`, `duration_s`, `ts_run`. No `person` column — compute runs process the whole DB, not one person's slice, so this is by design, not an oversight (see Non-Goals).
- `analyse_all.py` does **not** use `pipeline_runner.run_pipeline_script()` — it has its own bespoke `run_script()` subprocess wrapper (`analyse_all.py:186`), duplicating logic that already exists and is already tested via `compute_all.py`/`import_all.py`. This is why analyses currently have zero run-level audit trail: they were never wired into the mechanism that already solves this for compute.
- `pipeline_runner.py` also already contains a working, run-level chain-of-custody check (`_check_import_log_compliance`): it snapshots total row counts before/after a subprocess run and flags it as an error if data grew without a new `import_log` entry. This is currently wired only for `import_all.py` (`check_import_log=True`). It is not modified by this change — it already does its job for imports.

So the real gap is narrower than it first looked: `git_commit`-level provenance for pipeline runs is already solved for compute; it just was never extended to analysis, and `import_log` never got `person` wired up despite already having the column.

## Goals / Non-Goals

**Goals:**
- Every `import_log` entry SHALL record which person's data was affected (column already exists; now populated) and which git commit produced it (new column, same mechanism `compute_log` already uses).
- Analysis runs (`analyse_all.py` → individual `analyse_*.py` scripts) SHALL get the same run-level audit trail compute runs already get — by unifying `analyse_all.py` onto the shared `pipeline_runner.run_pipeline_script()` instead of its parallel bespoke implementation, not by inventing a third mechanism.
- All schema additions SHALL be self-healing (checked/added on first use, matching the existing `CREATE TABLE IF NOT EXISTS` pattern already used for `compute_log`) — no separate manual migration step a future run can silently skip, which is exactly the class of gap this change exists to close.

**Non-Goals:**
- No `person` column on `compute_log`/`analysis_log`. A `compute_all.py`/`analyse_all.py` run processes the whole database, not one person's data in isolation (even under the multi-patient clinic feature) — attributing a whole-DB recompute to a single person would misrepresent what actually happened. `person`-level provenance stays scoped to `import_log`, where it's already meaningful (one import run = one data source = typically one person).
- No rollout to all ~30 existing `log_import()` call sites or all `analyse_*.py` scripts in this change. Reference implementations only (see tasks.md); the rest is inventoried as explicit follow-up, same pattern as `add-importer-person-override-convention`.
- No change to the existing `_check_import_log_compliance` chain-of-custody check itself — it already works for imports. Whether an equivalent check is worth adding for `analyse_all.py` (comparing output file counts, say) is left as an open question, not built here.
- No retroactive backfill of `git_commit`/`person` for existing `import_log`/`compute_log` rows — those stay `NULL`, which is honest (we don't actually know).

## Decisions

**`import_log.git_commit`, self-healing add:** `log_import()` checks `PRAGMA table_info(import_log)` for `git_commit` and issues `ALTER TABLE import_log ADD COLUMN git_commit TEXT` if missing, before the `INSERT`. Same defensive pattern already used for `compute_log`'s `CREATE TABLE IF NOT EXISTS` — no separate migration script to remember to run.

**Shared git-commit-hash helper:** `_git_commit_hash()` moves from `modules/pipeline_runner.py` to `modules/base.py` (where `log_import()` lives), re-exported from `pipeline_runner.py` for backward compatibility with its existing internal use. Avoids two independent `git rev-parse` implementations drifting apart. Caching behavior (module-level, computed once per process) is preserved as-is.

**`log_import()` signature:** add `person: str | None = None` as a new keyword argument, defaulting through `resolve_person(person)` (existing helper — falls back to `OWN_PERSON_ID` when `None`). This is additive and keyword-only in practice (existing positional calls are `log_import(conn, source, data_path, rows_inserted, rows_skipped)`; the new parameter is appended after, so no existing call site breaks). Existing callers silently start logging `person=OWN_PERSON_ID` (correct default for a single-person install) until explicitly updated to pass the actual acted-upon person — which matters for the multi-patient clinic deployment and for migrations that touch a specific person's rows (e.g. `pseudonymize_device_person_identifiers.py`).

**New `analysis_log` table, not a renamed/repurposed `compute_log`:** same shape as `compute_log` (`ts_run, script, git_commit, returncode, duration_s`). Considered adding a `stage` column to `compute_log` and reusing it for both — rejected: existing installs already have `compute_log` rows and a name that specifically says "compute"; renaming or overloading it is a bigger, riskier migration for existing data than adding one more small table following an already-proven shape. `_log_compute_run()` and the new `_log_analysis_run()` share their `CREATE TABLE IF NOT EXISTS` + `INSERT` logic through one internal `_log_pipeline_run(table_name, script_name, returncode, duration_s)` helper in `pipeline_runner.py`, parameterized by table name, to avoid duplicating the two nearly-identical functions.

**`analyse_all.py` logging, without replacing its runner:** initial design assumed `analyse_all.py`'s `run_script()` was a thin duplicate of `pipeline_runner.run_pipeline_script()` and could simply be swapped out. Reading it revealed real, load-bearing behavior `run_pipeline_script()` doesn't have — per-script log files under the analysis output directory, `MPLBACKEND`/`KYORO_ANALYSES_DIR` env injection, dry-run support. Replacing it wholesale would have risked losing that. Revised approach: keep `run_script()` as-is, call the shared `pipeline_runner._log_analysis_run()` helper directly from inside it, right where it already has `result.returncode` and `elapsed`. Same shared logging mechanism (`analysis_log` table, same helper `compute_log` uses), without an unnecessary and riskier subprocess-runner swap. This still answers "wann wurden welche Analysen von wem durchgeführt" for the "von wem" (script identity) and "wann"/"mit welcher Version" parts. It does **not** answer per-person attribution for analyses (see Non-Goals) — an analysis run covers whatever the script itself reads, which may span multiple persons.

**`check_import_logging.py` heuristic extension:** flag `log_import(` calls that don't also reference a `person=` keyword, as a soft warning category (not a hard failure) — so a partially-updated call site is visible in the report rather than silently looking "compliant" just because `log_import(` is present. Hard-failing on this immediately would break CI for every one of the ~30 unmigrated call sites at once, which is explicitly out of scope for this change (see Non-Goals).

## Risks / Trade-offs

**[Risk] Self-healing `ALTER TABLE` runs on every `log_import()` call, not just once.** → Mitigation: the `PRAGMA table_info` check is cheap (single metadata query) and the actual `ALTER TABLE` only fires once per DB file (subsequent calls see the column already present and skip it) — same cost profile as the existing `compute_log` `CREATE TABLE IF NOT EXISTS`, which already runs on every compute-logged subprocess with no observed problem.

**[Risk] `person=None` default silently attributes ambiguous/system-wide migrations to `OWN_PERSON_ID`.** → Mitigation: this is a deliberate, honest default for a single-person install (the overwhelming majority of current usage) rather than leaving the column NULL, which would be less informative, not more. Migrations that genuinely act on a specific, non-default person's data are expected to pass `person=` explicitly as part of their own correctness (same principle as the already-completed importer-person-override-convention work) — this change does not weaken that.

**[Risk] `analyse_all.py`'s `run_script()` and `pipeline_runner.run_pipeline_script()` looked interchangeable but weren't** — the former has per-script log files, `MPLBACKEND`/`KYORO_ANALYSES_DIR` env injection, and dry-run support that the latter doesn't. → Mitigation: resolved by not unifying them. `run_script()` keeps its own subprocess-invocation logic unchanged; only the logging call (`_log_analysis_run()`) was added at its existing return point. Zero behavior change to anything except the new `analysis_log` row.

## Migration Plan

1. Move `_git_commit_hash()` to `modules/base.py`, re-export from `pipeline_runner.py`.
2. Add `git_commit` self-healing check + column to `import_log` path in `log_import()`.
3. Add `person` parameter to `log_import()`, wire through `resolve_person()`.
4. Add `analysis_log` table + `_log_analysis_run()` (factored via shared `_log_pipeline_run()`) to `pipeline_runner.py`.
5. Refactor `analyse_all.py` to call `run_pipeline_script(..., log_analysis=True)` instead of its own `run_script()`.
6. Update `check_import_logging.py` heuristic (soft `person=` warning).
7. Wire reference implementations: one importer, one migration (reuse tonight's already-fixed migration scripts as the reference — they already call `log_import()`, just need the new `person=` kwarg added where meaningful), confirm `analyse_all.py`'s new path end-to-end against a real analysis script.
8. `docs/CONTRIBUTING.md`/`CONTRIBUTING_DE.md` updated for both the new `log_import()` shape and the (mostly invisible-to-authors) analysis logging.
9. Remaining ~29 `log_import()` call sites and confirmation that all `analyse_*.py` scripts work correctly through the unified `analyse_all.py` path: tracked as explicit follow-up tasks, not blocking this change's completion.

No rollback concerns beyond standard git revert — all schema additions are additive (`ADD COLUMN`, `CREATE TABLE IF NOT EXISTS`), nothing is dropped or renamed.

## Relationship to add-tamper-evident-audit-log

A separate, not-yet-implemented change (`openspec/changes/add-tamper-evident-audit-log/`, 0/17 tasks done) addresses a different concern: making `import_log` entries tamper-*evident* via hash chaining, independent of what fields that log contains. This change is complementary — it makes the log's *content* more complete (person, git commit, analysis coverage) — and should land first: if hash-chaining is implemented before the `git_commit`/`person`/`analysis_log` additions here, its hash payload would need to be revisited to include the new columns.

## Open Questions

- Should an `analyse_all.py`-side chain-of-custody check (analogous to `_check_import_log_compliance`) be added later, and what would "chain of custody violation" even mean for a read-mostly analysis stage (missing expected output file? no `analysis_log` entry despite non-zero exit?) — deliberately left open, not designed here.
- Whether `check_import_logging.py`'s new `person=` warning should eventually become a hard failure once the ~29-site rollout is complete — a decision for that follow-up work, not this change.
