## ADDED Requirements

### Requirement: TUI is an operating layer without pipeline logic
The TUI SHALL perform pipeline work only by running existing scripts as subprocesses with an argument list, never through a shell. It SHALL NOT write to any database. Status queries SHALL use a connection set to read-only mode.

#### Scenario: Status query cannot write
- **WHEN** the dashboard reads `import_log`, `compute_log` or `analysis_log`
- **THEN** the connection has `PRAGMA query_only=ON` and no row in any database is changed

#### Scenario: Database unavailable
- **WHEN** a database is locked, missing or cannot be decrypted while the dashboard loads
- **THEN** the affected status is shown as unknown and all screens stay usable

#### Scenario: User input with shell characters
- **WHEN** a form field or query text contains characters such as `;`, `$(` or spaces
- **THEN** the value reaches the script as one unmodified argument and nothing is interpreted by a shell

### Requirement: Auto and manual coverage of all pipeline stages
The TUI SHALL offer, for import, compute and analyse: running all registered scripts, running selected single scripts, and running the scripts that are not part of the orchestrator. Script lists for registered scripts SHALL be read from the orchestrators at runtime, not redeclared.

#### Scenario: Script added to a registry
- **WHEN** a script is added to `IMPORTERS`, `COMPUTE_SCRIPTS` or `ANALYSE_SCRIPTS`
- **THEN** it appears in the matching screen without any TUI change

#### Scenario: Registered script run alone
- **WHEN** the user runs a single script from a registered list
- **THEN** the TUI calls the orchestrator with `--only-exact <stem>` and does not call the script directly

#### Scenario: Name is a prefix of another script
- **WHEN** the user selects `analyse_pem`
- **THEN** only `analyse_pem` runs, and not `analyse_pem_cascade` or `analyse_pem_threshold`

#### Scenario: Manual importer with a file argument
- **WHEN** the user selects a manual importer and picks a path
- **THEN** the importer receives the path in the form its CLI expects, whether positional, `--dir` or `--file`, and only paths of the declared kind can be picked

#### Scenario: On-demand script with a required value
- **WHEN** a manifest entry declares a required field and it is empty or has the wrong type
- **THEN** the run action stays disabled and the field shows why

### Requirement: Manual imports trigger sanitising
After a manual importer started from the TUI ends, the TUI SHALL run `import_all.py --sanitize-only` as part of the same job, whether the importer succeeded, failed or was cancelled. It SHALL skip this only when a flag declared as non-writing is set for that run. The UI SHALL state when sanitising did not complete, SHALL offer a retry, and SHALL NOT claim that `medicine.db` was fully scanned.

#### Scenario: Successful manual import
- **WHEN** a manual importer exits with code 0
- **THEN** `import_all.py --sanitize-only` runs next, and both exit codes are shown

#### Scenario: Failed manual import
- **WHEN** a manual importer exits non-zero or is cancelled
- **THEN** sanitising still runs, because partial writes are possible

#### Scenario: Non-writing run
- **WHEN** a manual importer runs with a flag declared in `no_write_flags`
- **THEN** sanitising does not run

#### Scenario: Sanitising fails
- **WHEN** `import_all.py --sanitize-only` exits non-zero or is cancelled
- **THEN** the UI states that the data has not been sanitised and offers a retry

### Requirement: On-demand runs are logged
The TUI SHALL run on-demand compute and analysis scripts through `--on-demand` on their orchestrator, and SHALL NOT call them directly. Their last run SHALL be shown in the matching screen. These runs SHALL NOT count towards the dashboard's assessment of whether a stage is current.

#### Scenario: On-demand run from the TUI
- **WHEN** the user runs an on-demand compute or analysis script
- **THEN** the form values are forwarded after `--`, and the run appears in that screen's status

#### Scenario: Interactive on-demand analysis
- **WHEN** the user starts `analyse_synthesis.py`
- **THEN** it runs through `analyse_all.py --on-demand` under `App.suspend()`, its own prompt works, and the run is logged

#### Scenario: On-demand run after an import
- **WHEN** only an on-demand script ran after the latest import
- **THEN** the dashboard still reports compute as older than the import

### Requirement: Flag forms expose orchestrator options
The analyse form SHALL offer AI comments on or off, date range, single date, run date, person, all data, dry run and a skip selection. The compute form SHALL offer skip-quality and recompute. The import form SHALL offer update, date range and person. The deprecated `--llm` flag SHALL NOT be offered.

#### Scenario: Analyse defaults match the CLI
- **WHEN** the user starts an analyse run without changing the form
- **THEN** the command line equals `analyse_all.py` without added flags, apart from the selection

#### Scenario: Invalid date
- **WHEN** a date field does not contain a valid ISO date
- **THEN** the run action stays disabled and the field shows why

### Requirement: Compute dependency warning for single runs
When a single compute script is selected, the TUI SHALL show upstream dependencies that never succeeded or are older than the latest import, and SHALL show transitive downstream dependents. It SHALL warn and SHALL NOT block the run. It SHALL offer running the script together with its dependents.

#### Scenario: Missing upstream result
- **WHEN** the user selects a compute script whose dependency has no successful `compute_log` entry
- **THEN** a warning names the dependency and the run stays possible

#### Scenario: Run with dependents
- **WHEN** the user chooses to include dependents
- **THEN** the TUI passes the script and its transitive dependents to `--only-exact`, and they run in `COMPUTE_SCRIPTS` order

#### Scenario: Compute log unavailable
- **WHEN** `compute_log` cannot be read
- **THEN** the warning states that status is unknown and still lists the declared dependencies

### Requirement: Single-writer job execution
The TUI SHALL run at most one pipeline job at a time. Output SHALL stream into a log view as the running process emits it, and elapsed time SHALL be visible while a job runs. The exit code SHALL be shown when a job ends. Jobs SHALL be cancellable, and cancelling SHALL end the whole process group.

#### Scenario: Action while a job runs
- **WHEN** a job is running
- **THEN** all actions that start another job are disabled until it ends

#### Scenario: Live output of a directly run script
- **WHEN** a directly run Python script prints a line while still running
- **THEN** the line appears in the log view before the script exits

#### Scenario: Orchestrator run with a long step
- **WHEN** an orchestrator's child runs for minutes without its output being passed on
- **THEN** the view shows the started step and the rising elapsed time

#### Scenario: Analysis output after a run
- **WHEN** an `analyse_all.py` run ends
- **THEN** the user can open each script's log file read-only from the job view

#### Scenario: Cancelling an orchestrator
- **WHEN** the user cancels a running `import_all.py`
- **THEN** the orchestrator and its current child process both end, and the UI states that a re-run is safe

#### Scenario: Quit with a running job
- **WHEN** the user quits while a job runs
- **THEN** the TUI asks for confirmation, and on confirmation ends the job before exiting

### Requirement: Interactive scripts keep the real terminal
Scripts declared as interactive SHALL run with the terminal handed over by `App.suspend()`, and SHALL keep their own prompts. The TUI SHALL NOT answer or bypass their prompts through flags. All other scripts SHALL run with stdin closed.

#### Scenario: Guided test
- **WHEN** the user starts `orthostatic_test.py`
- **THEN** the TUI suspends, the script's prompts work normally, and the TUI resumes when the script exits

#### Scenario: Misclassified script
- **WHEN** a script declared as non-interactive calls `input()`
- **THEN** it fails with a visible error instead of hanging

### Requirement: Remote LLM use requires per-run consent
The TUI SHALL show the active LLM provider and whether it is local on every screen that can start LLM use. Before a run that may use LLM, if the provider is remote or cannot be determined, the TUI SHALL name the provider and ask for consent. Consent SHALL apply to one run only.

#### Scenario: Remote provider configured
- **WHEN** the user starts `analyse_all.py` with AI comments on and a remote provider
- **THEN** a dialog names the provider and offers run, run without AI, and cancel, and nothing runs before a choice

#### Scenario: Local provider
- **WHEN** the active provider is local
- **THEN** no dialog appears and the local provider stays visible on the screen

#### Scenario: Provider unknown
- **WHEN** the provider cannot be determined
- **THEN** the TUI treats the run as remote and asks for consent

#### Scenario: Consent is not remembered
- **WHEN** the user consented once and starts another run
- **THEN** the dialog appears again

### Requirement: Flag allowlist and excluded tools
The TUI SHALL pass only flags declared in its manifest. Flags that weaken privacy protection or expose secrets SHALL NOT be declared, including `--no-scrub`, `--host`, `--writable`, `--api-key`, `--show-mappings`, `--no-backup`, `--accept-terms`, and `--fix` on check scripts. Destructive and migration tools SHALL be listed as excluded with a reason and SHALL NOT be reachable from the UI.

#### Scenario: Blocked flag added to the manifest
- **WHEN** a manifest entry declares a blocked flag
- **THEN** the test suite fails

#### Scenario: Excluded tool
- **WHEN** the user browses the utility screen
- **THEN** `decrypt_db.py`, `scrub_*.py`, `migrate_*.py` and `pseudonymize_*.py` are not offered

### Requirement: Browsing analysis results
The TUI SHALL let the user select an analysis script and one of its runs, read its reports, read its log and open its plots, without starting a job. It SHALL read existing output files only, and SHALL include runs started outside the TUI.

#### Scenario: Reading the latest report
- **WHEN** the user selects a script with output in several runs
- **THEN** its runs are listed newest first, and the newest report is rendered

#### Scenario: Run from the CLI
- **WHEN** `analyse_all.py` ran on the command line
- **THEN** its results appear in the browser

#### Scenario: Script without a report
- **WHEN** a selected run contains only a log file
- **THEN** the browser says that no report exists and shows the log

#### Scenario: Plot without a graphical session
- **WHEN** the user opens a plot and no system viewer is available
- **THEN** the file path is shown and no error occurs

### Requirement: Curated utility screen
The TUI SHALL offer grouped utilities for capture, lookup, checks, maintenance, documents and services. Maintenance actions that change data SHALL require confirmation. The Datasette service SHALL run read-only on localhost, SHALL have a start/stop toggle and SHALL stop when the TUI exits.

#### Scenario: Service stopped
- **WHEN** the user stops the Datasette service or quits the TUI
- **THEN** the process has ended and its decrypted temporary database no longer exists

#### Scenario: Job runs while the service is active
- **WHEN** the Datasette service is running
- **THEN** the job lock does not block other actions

### Requirement: Dashboard and guided daily workflow
The dashboard SHALL show last-run status per stage, a hint when compute is older than the latest import, and the analysis scripts that would be skipped for lack of `clinical.infection_date`. It SHALL offer a guided daily workflow, with a mandatory inbox preview before the inbox import. On a non-zero exit the workflow SHALL pause and ask whether to continue or abort.

#### Scenario: Stale compute
- **WHEN** the latest import is newer than the latest successful compute run
- **THEN** the dashboard says that analyses may be outdated or empty and offers the compute action

#### Scenario: Sanitising is not an import
- **WHEN** the newest `import_log` rows are `post_import_*` entries
- **THEN** they are ignored when determining the latest import

#### Scenario: Different timestamp formats
- **WHEN** `import_log` and `compute_log` store timestamps in different formats
- **THEN** both are converted to UTC before they are compared

#### Scenario: Infection date not set
- **WHEN** `cfg.infection_date` is empty
- **THEN** the dashboard lists the affected scripts from `REQUIRES_INFECTION_DATE`

#### Scenario: Inbox preview
- **WHEN** the workflow reaches the inbox step
- **THEN** `process_inbox.py --dry-run` output is shown, and `--import` runs only after confirmation

#### Scenario: Failing step
- **WHEN** a workflow step exits non-zero
- **THEN** the workflow pauses and shows the exit code, and the user chooses to continue or abort

### Requirement: Query and export screens
The query screen SHALL send a question to `health_query.py` and SHALL offer its interactive mode as an interactive script. The export screen SHALL list profiles from `scripts/exporters/profiles/*.json` at runtime and SHALL offer time range, person, format and output directory.

#### Scenario: New export profile
- **WHEN** a JSON file is added to the profiles directory
- **THEN** it appears in the export screen without any TUI change

#### Scenario: Export finished
- **WHEN** an export exits successfully
- **THEN** the output path is visible in the log view

### Requirement: Output is not persisted
The TUI SHALL NOT write script output, form values or query text to disk. The log view SHALL have a line limit.

#### Scenario: After a session
- **WHEN** the TUI exits after running jobs
- **THEN** the TUI has created no log, history or state file

### Requirement: Coverage and manifest drift checks
Automated tests SHALL fail when a script is neither registered, declared in the manifest, nor excluded with a reason; when a manifest flag no longer exists in its script; when a script calling `input()` is not declared interactive and declares no gating flag; or when `COMPUTE_REQUIRES` is inconsistent with `COMPUTE_SCRIPTS`.

#### Scenario: New manual importer without an entry
- **WHEN** `scripts/importers/import_new.py` is added without a registry entry, manifest entry or exclusion
- **THEN** the test suite fails and names the file

#### Scenario: Flag renamed in a script
- **WHEN** a script renames a flag declared in the manifest
- **THEN** the test suite fails and names the script and flag

### Requirement: Platform and language behaviour
The TUI SHALL work on Linux and macOS, including over SSH, and SHALL be fully usable by keyboard. All UI text SHALL use `t()` and follow `KYORO_LANG`, which SHALL also be passed to child processes. If `textual` is not installed, the entry point SHALL exit with an install hint, and all other scripts SHALL keep working.

#### Scenario: Language switch
- **WHEN** the TUI starts with `KYORO_LANG=en`
- **THEN** UI text is English and child processes receive `KYORO_LANG=en`

#### Scenario: Missing dependency
- **WHEN** `python3 scripts/kyoro_tui.py` runs without `textual`
- **THEN** it exits non-zero with a bilingual install hint and no traceback

#### Scenario: Pipeline without textual
- **WHEN** `textual` is not installed
- **THEN** `import_all.py`, `compute_all.py` and `analyse_all.py` run as before
