## 1. Orchestrator additions

- [x] 1.1 Add `--only-exact` to `analyse_all.py`, mutually exclusive with `--only`; unknown stems exit non-zero before any run
- [x] 1.2 Add `--only-exact` to `compute_all.py`, keeping `COMPUTE_SCRIPTS` order, `RECOMPUTE_FLAGS` and `compute_log`
- [x] 1.3 Add `--only-exact` to `import_all.py`, including `import_ecg_logger` and `import_ecg_apple`; keep post-import sanitising, skip the outbreak source health check
- [x] 1.4 Derive `COMPUTE_REQUIRES` from the SQL each compute script actually reads, then add it to `compute_all.py`
- [x] 1.5 Reconcile the `compute_all.py` header with the code, including the `compute_hrv_advanced` output table, and correct the header where it is wrong
- [x] 1.6 Tests: exact matching with the real collisions (`analyse_pem`, `import_polar`, `import_oura`, `import_garmin`), unknown stems, order, sanitising still runs, `compute_log` written, unchanged behaviour without the flag
- [x] 1.7 Make `post_import_sanitize.run()` return its failed steps, keeping the exit behaviour of `import_all.py` and `import_staged.py` unchanged
- [x] 1.8 Add `import_all.py --sanitize-only`, with a non-zero exit on failed steps and an error on conflicting options
- [x] 1.9 Add `ON_DEMAND_COMPUTE_SCRIPTS` and `compute_all.py --on-demand STEM -- ARGS`, with forwarded arguments, `compute_log` entries, and no logging for `--dry-run`
- [x] 1.10 Tests: sanitise-only runs no importer, a failed step gives non-zero while later steps still run, a full run keeps its exit code, on-demand forwarding and logging, dry run not logged, unknown stem rejected, a full compute run excludes on-demand scripts
- [x] 1.11 Add `ON_DEMAND_ANALYSE_SCRIPTS` with preview flags per script, and `analyse_all.py --on-demand STEM -- ARGS` with inherited stdio and `analysis_log` entries
- [x] 1.12 Tests: on-demand analysis forwarding and logging, preview flags not logged, a prompt works on a real pseudo-terminal, unknown stem rejected, a full run excludes on-demand scripts
- [x] 1.13 Test that all three orchestrators import cleanly with an empty config directory; move any config access out of import time if this fails
- [x] 1.14 Change `analyse_all.run_script()`: stdout and stderr to `<stem>.output.txt`, run metadata only in `<stem>.log`, both with mode `600` also on existing files; failure output read from the output file; update the docstring and regenerate docs
- [x] 1.15 Tests with a real child script: output and tracebacks reach only the output file, a marker in an argument value does not reach the log, modes are `600` after a repeat run, a script with only an output file counts as no report, a failure prints the end of the output
- [x] 1.16 Add a cleanup step for old `<stem>.log` files that lists the count first and deletes only after explicit confirmation; test that nothing is deleted without it

## 2. Foundation

- [ ] 2.1 Add `textual` with a major-version bound to `requirements.txt`
- [ ] 2.2 Create `scripts/kyoro_tui.py` with the bilingual install hint when `textual` is missing, and a test for it
- [ ] 2.3 Create `scripts/tui/` with SPDX headers and structured docstrings accepted by `check_docstrings.py`
- [x] 2.4 Implement `runner.py`: piped mode with `stdin=DEVNULL`, `PYTHONUNBUFFERED=1` and `MPLBACKEND=Agg`, `KYORO_LANG` passthrough, own session, SIGTERM then SIGKILL on cancel, single-job lock
- [x] 2.5 Implement interactive mode through `App.suspend()`, and service mode outside the job lock
- [x] 2.6 Tests with real subprocesses: output arrives before exit, cancel ends the child of an orchestrator, `input()` in piped mode fails visibly, shell characters stay literal
- [x] 2.7 Add a read-only opener to `modules/db.py` that installs no triggers, and implement `status.py` on it with `PRAGMA query_only=ON`, reading all three log tables; test locked, missing and undecryptable databases and missing log tables
- [x] 2.8 Tests for `status.py`: timestamps in both formats compare correctly as UTC, `post_import_*` rows are ignored, on-demand rows do not make compute or analysis look current
- [ ] 2.9 Implement the job log widget with a line limit and ANSI handling, the field-driven flag form, and the start dialog naming script, arguments and whether it writes
- [ ] 2.10 Show elapsed time in the job view during every run, and offer the per-script output files after an `analyse_all.py` run, read-only

## 3. Manifest and drift checks

- [x] 3.1 Implement `ScriptEntry`, the field types and `EXCLUDED` in `manifests.py`
- [ ] 3.2 Read each script's argparse and add entries for all manual importers, including those also run automatically (lab results, HRV logger, ECG logger, Kubios, manual genetics, Aniva)
- [x] 3.3 Add entries for the 5 on-demand compute scripts and the 11 on-demand analysis scripts
- [ ] 3.4 Add the utility entries from design decision 11, confirming the correct mode from each script's source; give `EXCLUDED` a reason per entry
- [ ] 3.5 Add drift tests: coverage, flags exist through `_supported_flags()`, blocked flags absent, `input(` requires interactive mode or a declared gating flag, `COMPUTE_REQUIRES` consistent, on-demand manifest entries match `ON_DEMAND_COMPUTE_SCRIPTS` and `ON_DEMAND_ANALYSE_SCRIPTS`
- [ ] 3.6 Declare `no_write_flags` for each manual importer from its source, including dry-run and list modes

- [x] 3.7 Remove the `confirm` field from `ScriptEntry`, because every job start asks (design decision 16)

## 4. LLM consent

- [ ] 4.1 Determine the active provider and `is_local` through `utils/llm_provider.py` without any network call; verify this against the provider classes, and treat errors as unknown
- [ ] 4.2 Check how per-tool routing resolves, so the display and dialog cover every route an action can use
- [ ] 4.3 Implement the provider indicator and the per-run consent as part of the start dialog; set `uses_llm` in the manifest from each script's source
- [ ] 4.4 Tests: remote asks and is not remembered, unknown asks, local shows no consent part, run without AI adds `--no-llm`

## 5. Screens

- [ ] 5.1 Import screen: auto tab (all, single through `--only-exact`, form) and manual tab (picker restricted to the declared path kind, sanitising as a second job step after success, failure and cancel, retry when it did not complete)
- [ ] 5.2 Compute screen: all, single with upstream and downstream warning and "with dependents", on-demand tab through `compute_all.py --on-demand` with last-run status
- [ ] 5.3 Analyse screen: all, single and multi-select through `--only-exact`, skip selection, form without `--llm`, on-demand tab through `analyse_all.py --on-demand` with last-run status
- [ ] 5.4 Utility screen with groups and the Datasette toggle (localhost, read-only)
- [ ] 5.5 Query screen: single question, `--sql` option, interactive mode through suspend
- [ ] 5.6 Export screen: profiles read at runtime, including `aliases`; time range, person, format, output directory
- [ ] 5.7 Dashboard: last-run status, stale hint, skipped scripts from `REQUIRES_INFECTION_DATE`
- [ ] 5.8 Resolve the open question on empty-inbox behaviour of `process_inbox --import`, then implement the daily workflow with one question at its start, including remote AI consent, mandatory preview and pause on failure
- [ ] 5.9 Show the person selection from `status.read_person_choices()` in the forms, loaded in a background worker, hidden with one person, and nothing stored; pilot test with one and several persons
- [ ] 5.10 Pilot tests per screen: expected argument list per action, start dialog before every job and once per sequence, no process after cancelling it, disabled states, keyboard-only navigation, quit confirmation with a running job
- [ ] 5.11 Results browser: scripts from `ANALYSE_SCRIPTS`, runs newest first, Markdown reports, output files including old `.log` files, plots through `xdg-open` or `open` with the path as fallback, the no-report state, and the output locations of on-demand scripts

## 6. Verification against real data

- [ ] 6.1 For each stage, run one auto script and one manual script from the TUI against the real databases and compare output and DB changes with the same CLI command
- [ ] 6.2 Run a real manual import from the TUI and confirm in `import_log` that sanitising ran; run a real on-demand compute and analysis script and confirm their log entries
- [ ] 6.3 Run `orthostatic_test.py` and `anamnese_interview.py` through suspend, and confirm that the terminal is restored
- [ ] 6.4 Start and stop Datasette through the toggle and through quit, and confirm that the decrypted temp file is gone; fix `datasette_serve.py` if not
- [ ] 6.5 Cancel a real importer mid-run, and confirm that a re-run gives a consistent result
- [ ] 6.6 Confirm that a session leaves no new files apart from those the scripts themselves create
- [ ] 6.7 Verify on a macOS host, including `Terminal.app`, and over SSH on Linux
- [x] 6.8 Run `analyse_all.py --only-exact` on real data with a known date as argument, and confirm by count only that the new log contains no output and not that date

## 7. Docs and compliance

- [ ] 7.1 Update `CLAUDE.md`: TUI entry point, the manifest step when adding an importer or on-demand script, and the `--sanitize-only` and `--on-demand` flags
- [ ] 7.2 Add a README section with start command and a note on remote LLM consent
- [ ] 7.3 Run `check_source_privacy.py`, `check_no_dates.py`, `check_docstrings.py`, `check_ai_labeling.py` and the full test suite, all clean
