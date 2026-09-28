## Why

Two real gaps surfaced during a targeted review: nine migration scripts that mutate production health data carried no audit trail at all (no `log_import()`, no equivalent), and `analyse_skin.py`'s VLM loop deferred its `conn.commit()` to the end of the run, silently breaking the resume guarantee already required for expensive multi-step pipelines — a crash mid-run would re-trigger (and re-pay for) already-completed analyses on the next attempt, unnoticed. Both were found and fixed. Reviewing why they existed surfaced a deeper gap: the existing `import_log` table already has a `person` column, but `log_import()` never accepts or populates it; no write anywhere records which code version (git commit) produced it; and analysis scripts (`analyse_*.py`, which read derived tables and write reports/plots rather than source tables) have no logging mechanism at all — `import_log` only covers DB writers.

`docs/ETHICS.md` commits this project to being treated as if its output could end up in court. A system that makes that claim needs its own writes and analyses to be as traceable as the medical record-keeping the project's own privacy-rules and pipeline-architecture specs already hold external actors to.

## What Changes

- `import_log` gains a `git_commit` column (commit hash at execution time, with a documented fallback when no git repo / detached HEAD / dirty tree is present).
- `log_import()` gains a `person` parameter and actually populates the existing (currently always-empty) `person` column.
- A new `analysis_log` table and a matching `log_analysis()` helper in `modules/base.py`, following the same call-before-commit convention as `log_import()`, so analysis runs (which don't write to source tables) get their own audit trail: script, person, git commit, timestamp, output path.
- Reference implementations wired into a small number of scripts to prove the pattern end-to-end (one importer, one migration, one analysis script) — **not** a full rollout across all ~30 importers/migrations and the larger set of `analyse_*.py` scripts in this change. The remaining call sites are inventoried as explicit follow-up work (tasks.md), mirroring how `add-importer-person-override-convention` scoped its own rollout.
- `check_import_logging.py`'s heuristic is extended to also flag missing `person`/`git_commit` usage where `log_import(` is already called with the old two-positional-arg shape, so a partial rollout doesn't silently regress.

## Capabilities

### New Capabilities
- `data-provenance`: every database write and every analysis run SHALL be attributable to what changed, for which person, when, from which script, and at which code version — extending the existing chain-of-custody requirement (currently scoped only to multi-step LLM pipeline artifacts) to cover ordinary DB writes and analysis executions across the whole pipeline.

### Modified Capabilities
- `pipeline-architecture`: the existing "Chain of custody for multi-step, expensive pipeline artifacts" requirement remains as-is; this change adds a sibling, broader requirement (in the new `data-provenance` capability) rather than modifying that one, since multi-step-pipeline chain-of-custody and per-write/per-analysis provenance are related but distinct concerns. No requirement text in `pipeline-architecture` itself changes.

## Impact

- `scripts/utils/create_schema.py` — schema change (`import_log.git_commit`, new `analysis_log` table). Needs a migration path for the existing `data/health.db`/`data/medicine.db` (`ALTER TABLE` for the new column, `CREATE TABLE IF NOT EXISTS` for the new table), not just the fresh-schema definition.
- `scripts/modules/base.py` — `log_import()` signature change (new `person` parameter); new `log_analysis()` function.
- `scripts/check_import_logging.py` — heuristic extended.
- A small set of reference scripts across `scripts/importers/`, `scripts/migrations/`, `scripts/analysis/` updated to use the new signatures.
- `docs/CONTRIBUTING.md` / `CONTRIBUTING_DE.md` — "Adding a new importer" section needs the updated `log_import()` call shape; new guidance for analysis scripts needs a short new section.
- No breaking change to existing `log_import()` callers if `person` is added as an optional keyword argument with a safe default — needs to be confirmed in design.md.
