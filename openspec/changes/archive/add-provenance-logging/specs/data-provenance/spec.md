## ADDED Requirements

### Requirement: Import/migration writes attribute person and code version
Every call to `log_import()` SHALL record which person's data was affected and which git commit of the codebase produced the write, in addition to the existing `source`, `data_path`, `rows_inserted`, and `rows_skipped` fields.

#### Scenario: Importer logs with explicit person
- **WHEN** an importer calls `log_import(conn, source, data_path, rows_inserted, rows_skipped, person=X)`
- **THEN** the resulting `import_log` row has `person = X` and `git_commit` set to the current `git rev-parse HEAD` output (or `NULL` if no git repository is available at runtime)

#### Scenario: Caller omits person
- **WHEN** a script calls `log_import()` without passing `person` (existing call sites, unmodified by this change)
- **THEN** the resulting `import_log` row has `person` set to `OWN_PERSON_ID` (the configured default person), not `NULL` and not an error

#### Scenario: Caller explicitly declares no single person applies
- **WHEN** a migration that genuinely acts across all persons (e.g. a system-wide device-ID or source-tag cleanup) calls `log_import(..., person=None)` — explicitly, not by omission
- **THEN** the resulting `import_log` row has `person = NULL`, not `OWN_PERSON_ID` — the distinction between "not specified" (defaults to the configured person) and "explicitly not applicable" (stays NULL) is preserved, so the log never falsely attributes a cross-person operation to one person

#### Scenario: import_log predates the git_commit column
- **WHEN** `log_import()` is called against a `health.db`/`medicine.db` created before this change (no `git_commit` column on `import_log` yet)
- **THEN** the column is added via `ALTER TABLE` before the row is inserted, without requiring a separate manual migration step

### Requirement: Analysis runs are logged with script identity, code version, and outcome
Every `analyse_*.py` script invoked through `analyse_all.py` SHALL produce an `analysis_log` entry recording which script ran, at which git commit, its exit code, and its duration — mirroring the existing `compute_log` mechanism already used for `compute_all.py`.

#### Scenario: Analysis script completes successfully
- **WHEN** `analyse_all.py` runs an analysis script to completion
- **THEN** an `analysis_log` row is written with `script` set to the script's filename, `git_commit` set to the current commit hash, `returncode = 0`, and `duration_s` set to the measured wall-clock run time

#### Scenario: Analysis script fails
- **WHEN** an analysis script invoked by `analyse_all.py` exits with a non-zero return code
- **THEN** an `analysis_log` row is still written for that run, with the actual non-zero `returncode`, so failed runs remain in the audit trail rather than silently disappearing

#### Scenario: analysis_log table does not exist yet
- **WHEN** `analyse_all.py` runs against a `health.db` created before this change (no `analysis_log` table yet)
- **THEN** the table is created via `CREATE TABLE IF NOT EXISTS` before the row is inserted, without requiring a separate manual migration step

### Requirement: Compute and analysis logging do not claim per-person attribution
`compute_log` and `analysis_log` entries SHALL NOT include a `person` field, since a `compute_all.py`/`analyse_all.py` run processes data across the whole database rather than a single person's slice.

#### Scenario: Multi-person database
- **WHEN** a `compute_all.py` or `analyse_all.py` run processes a database containing data for more than one person (e.g. a clinic multi-patient deployment)
- **THEN** the resulting `compute_log`/`analysis_log` entry describes the run itself (script, git commit, outcome, duration) without asserting it belongs to any single person
