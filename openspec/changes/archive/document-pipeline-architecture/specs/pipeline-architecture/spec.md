## ADDED Requirements

### Requirement: Three-stage pipeline
The system SHALL process raw data in three strictly separated,
sequential stages: import (`imports/` → `import_all.py`), compute
(`compute_all.py`), and analysis (`analyse_all.py`). Each stage SHALL
only read data from the preceding stage(s), never the other way around.

#### Scenario: Order followed
- **WHEN** a user runs `import_all.py`, then `compute_all.py`, then
  `analyse_all.py`, in that order
- **THEN** `analyse_all.py` produces complete results based on the
  previously computed derived tables

#### Scenario: Compute skipped before import
- **WHEN** a user runs `compute_all.py` without having run
  `import_all.py` first for new raw data
- **THEN** the compute scripts only compute based on the already-present
  (older) raw data — new raw data is not included, but there is no error

#### Scenario: Analysis skipped before compute
- **WHEN** a user runs `analyse_all.py` without `compute_all.py` having
  run again since the last `import_all.py` run
- **THEN** the analysis scripts read from stale or empty derived tables
  and thereby produce incomplete or empty output **without an error
  message**

### Requirement: Fixed compute dependency order
`compute_all.py` SHALL run its compute scripts in a fixed, documented
order that follows the table dependencies between the scripts (e.g.
scripts that produce `ppi_raw` run before scripts that read `ppi_raw`).
The authoritative source for this order SHALL be the `@method` section
in the header comment of `scripts/compute_all.py` — this spec
deliberately does not duplicate the list, to avoid drift as new compute
scripts are added.

#### Scenario: New compute script with a dependency
- **WHEN** a new compute script reads a table written by another compute
  script
- **THEN** the new script MUST be placed in `compute_all.py` after the
  script that produces the required table, and the dependency MUST be
  added to the `@method` header comment of `compute_all.py`

#### Scenario: Error in a compute script
- **WHEN** an individual compute script within `compute_all.py` raises
  an error
- **THEN** `compute_all.py` logs the error and continues running the
  remaining scripts instead of aborting

### Requirement: Silent empty results as known behavior
Analysis scripts SHALL NOT emit a warning when the derived tables they
read from are empty or stale — this behavior is known and MUST be
explicitly documented for contributors, so they don't mistake it for a
bug.

#### Scenario: Contributor encounters empty analysis output
- **WHEN** a contributor runs an analysis script against a fresh DB
  without a prior `compute_all.py` run
- **THEN** documented knowledge (this spec, CLAUDE.md) should explain
  that `compute_all.py` must run first, instead of suspecting a bug in
  the analysis script
