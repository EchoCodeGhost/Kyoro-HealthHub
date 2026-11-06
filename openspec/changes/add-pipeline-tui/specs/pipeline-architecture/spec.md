## ADDED Requirements

### Requirement: Exact selective execution in orchestrators
`import_all.py`, `compute_all.py` and `analyse_all.py` SHALL accept `--only-exact STEM[,STEM]`, which runs only the scripts whose file stem equals a given value, in the orchestrator's own order. An unknown stem SHALL exit non-zero before any script runs. A selective run SHALL apply the same per-script flags, logging and output handling as a full run. In `analyse_all.py`, `--only-exact` and `--only` SHALL be mutually exclusive, and `--only` SHALL keep its substring behaviour.

#### Scenario: Stem is part of another stem
- **WHEN** `analyse_all.py --only-exact analyse_pem` runs
- **THEN** `analyse_pem` runs, and `analyse_pem_cascade` and `analyse_pem_threshold` do not

#### Scenario: Unknown stem
- **WHEN** `compute_all.py --only-exact compute_missing` runs
- **THEN** it exits non-zero, names the stem, and no compute script has run

#### Scenario: Selection keeps dependency order
- **WHEN** `compute_all.py --only-exact compute_canonical,compute_stress` runs
- **THEN** `compute_stress` runs first because it comes first in `COMPUTE_SCRIPTS`

#### Scenario: Selective compute run is logged
- **WHEN** a compute script runs through `--only-exact`
- **THEN** it gets a `compute_log` entry like in a full run

#### Scenario: Selective import keeps sanitising
- **WHEN** `import_all.py --only-exact import_polar` runs
- **THEN** `import_polar_accesslink` does not run, and post-import sanitising runs afterwards

#### Scenario: Special-cased importer
- **WHEN** `import_all.py --only-exact import_ecg_logger` runs
- **THEN** that importer runs with the same arguments as in a full run

#### Scenario: Run without the flag
- **WHEN** an orchestrator runs without `--only-exact`
- **THEN** it behaves as before this change

### Requirement: Standalone post-import sanitising
`import_all.py --sanitize-only` SHALL run post-import sanitising and nothing else, and SHALL exit non-zero if a sanitising step failed. It SHALL NOT be combinable with options that select or run importers. `post_import_sanitize.run()` SHALL report its failed steps to the caller, and existing callers SHALL keep their current exit behaviour.

#### Scenario: Sanitising only
- **WHEN** `import_all.py --sanitize-only` runs
- **THEN** no importer and no outbreak source health check runs

#### Scenario: Failed step
- **WHEN** a sanitising step raises an error during `--sanitize-only`
- **THEN** the remaining steps still run, and the exit code is non-zero

#### Scenario: Full run unaffected
- **WHEN** a sanitising step fails during a full `import_all.py` run in which all importers succeeded
- **THEN** the exit code is the same as before this change

#### Scenario: Conflicting options
- **WHEN** `import_all.py --sanitize-only --only-exact import_polar` runs
- **THEN** it exits non-zero with an error and nothing runs

### Requirement: Logged on-demand compute runs
`compute_all.py` SHALL define `ON_DEMAND_COMPUTE_SCRIPTS`, separate from `COMPUTE_SCRIPTS`. `compute_all.py --on-demand STEM -- ARGS` SHALL run that one script, forward `ARGS` unchanged, and write a `compute_log` entry with its exit code. A run with `--dry-run` in `ARGS` SHALL NOT be logged. A full run SHALL NOT include on-demand scripts.

#### Scenario: On-demand run is logged
- **WHEN** `compute_all.py --on-demand compute_orthostatic_detection -- --date-from 2020-01-01` runs
- **THEN** the script receives the forwarded flag and its run appears in `compute_log`

#### Scenario: Dry run is not logged
- **WHEN** `compute_all.py --on-demand compute_calibrate_sources -- --dry-run` runs
- **THEN** no `compute_log` entry is written

#### Scenario: Script not on the list
- **WHEN** `--on-demand` names a stem that is not in `ON_DEMAND_COMPUTE_SCRIPTS`
- **THEN** it exits non-zero, names the stem, and nothing runs

#### Scenario: Failing script
- **WHEN** an on-demand script exits non-zero
- **THEN** `compute_log` records that exit code and `compute_all.py` exits non-zero

#### Scenario: Full run unaffected
- **WHEN** `compute_all.py` runs without `--on-demand`
- **THEN** no script from `ON_DEMAND_COMPUTE_SCRIPTS` runs

### Requirement: Logged on-demand analysis runs
`analyse_all.py` SHALL define `ON_DEMAND_ANALYSE_SCRIPTS`, separate from `ANALYSE_SCRIPTS`, with the flags per script that make a run preview-only. `analyse_all.py --on-demand STEM -- ARGS` SHALL run that one script with stdin and stdout inherited, forward `ARGS` unchanged, and write an `analysis_log` entry with its exit code. A run with `--dry-run` or a declared preview flag in `ARGS` SHALL NOT be logged. A full run SHALL NOT include on-demand scripts.

#### Scenario: On-demand analysis is logged
- **WHEN** `analyse_all.py --on-demand analyse_ecg_session -- --session 42` runs
- **THEN** the script receives the forwarded flags and its run appears in `analysis_log`

#### Scenario: Preview is not logged
- **WHEN** `analyse_all.py --on-demand analyse_ecg_session -- --list` runs
- **THEN** no `analysis_log` entry is written

#### Scenario: Script with a prompt
- **WHEN** an on-demand script calls `input()` while attached to a terminal
- **THEN** the prompt reaches the user, and the answer reaches the script

#### Scenario: Script not on the list
- **WHEN** `--on-demand` names a stem that is not in `ON_DEMAND_ANALYSE_SCRIPTS`
- **THEN** it exits non-zero, names the stem, and nothing runs

#### Scenario: Failing script
- **WHEN** an on-demand script exits non-zero
- **THEN** `analysis_log` records that exit code and `analyse_all.py` exits non-zero

### Requirement: Machine-readable compute dependencies
`compute_all.py` SHALL define `COMPUTE_REQUIRES`, which maps each entry of `COMPUTE_SCRIPTS` to the entries it directly depends on. Each dependency SHALL appear earlier in `COMPUTE_SCRIPTS`. The mapping SHALL be importable without running any script.

#### Scenario: Script without dependencies
- **WHEN** a compute script reads no table produced by another compute script
- **THEN** its entry in `COMPUTE_REQUIRES` is an empty list

#### Scenario: Inconsistent mapping
- **WHEN** an entry is missing, or a dependency appears later in `COMPUTE_SCRIPTS`
- **THEN** the test suite fails

### Requirement: Analysis output is separate from run logs
`analyse_all.py` SHALL write each script's stdout and stderr to `<stem>.output.txt` in the run's output directory. `<stem>.log` SHALL contain run metadata only: script file name, start time, duration, exit code, output file name and names of skipped flags. It SHALL NOT contain script output, tracebacks or argument values. Both files SHALL be readable by the owner only. Old log files SHALL NOT be deleted without explicit user confirmation.

#### Scenario: Script prints health data
- **WHEN** a script prints a line to stdout or stderr during an `analyse_all.py` run
- **THEN** the line is in `<stem>.output.txt` and not in `<stem>.log`

#### Scenario: Script fails
- **WHEN** a script ends with a traceback
- **THEN** the log records the exit code, the traceback is only in the output file, and the terminal shows the end of the output file

#### Scenario: Argument values stay out of the log
- **WHEN** a script is run with a date as a flag value
- **THEN** that date does not appear in `<stem>.log`

#### Scenario: Repeat run on the same day
- **WHEN** a second run reuses existing files with wider permissions
- **THEN** both files are readable by the owner only afterwards

#### Scenario: Output file is not a report
- **WHEN** a script exits 0 and leaves only an output file
- **THEN** it is counted as having produced no report

#### Scenario: Cleaning up old logs
- **WHEN** the cleanup step runs without confirmation
- **THEN** it reports the number of old log files and deletes none

## MODIFIED Requirements

### Requirement: Fixed compute dependency order
`compute_all.py` SHALL run its compute scripts in a fixed, documented
order that follows the table dependencies between the scripts (e.g.
scripts that produce `ppi_raw` run before scripts that read `ppi_raw`).
The authoritative source for this order SHALL be the `@method` section
in the header comment of `scripts/compute_all.py` — this spec
deliberately does not duplicate the list, to avoid drift as new compute
scripts are added. `COMPUTE_REQUIRES` SHALL be the machine-readable form
of the direct dependencies, and SHALL be kept consistent with that
section.

#### Scenario: New compute script with a dependency
- **WHEN** a new compute script reads a table written by another compute
  script
- **THEN** the new script MUST be placed in `compute_all.py` after the
  script that produces the required table, and the dependency MUST be
  added to the `@method` header comment of `compute_all.py` and to
  `COMPUTE_REQUIRES`

#### Scenario: Error in a compute script
- **WHEN** an individual compute script within `compute_all.py` raises
  an error
- **THEN** `compute_all.py` logs the error and continues running the
  remaining scripts instead of aborting
