## Context

The pipeline is a set of independent CLI scripts behind three orchestrators. An inventory of the current code shows:

| Group | Registry | Count | Notes |
|---|---|---|---|
| Auto importers | `import_all.IMPORTERS` | 43 | Two more (`import_ecg_logger`, `import_ecg_apple`) are special-cased in `main()` |
| Manual importers | none | about 20 | Positional file, `--dir`, `--file`, `--mode`, `--inline`; some are also auto importers |
| Compute | `compute_all.COMPUTE_SCRIPTS` | 23 | Dependency chain only as prose in the header |
| On-demand compute | none | 5 | For example `compute_calibrate_sources`, `compute_histamine_triggers` |
| Analysis | `analyse_all.ANALYSE_SCRIPTS` | 84 | Order is documented as irrelevant |
| On-demand analysis | none (comment block) | 11 | In `scripts/analysis/manual/` |

Facts from the code that shape this design:

- Importing the three orchestrators is cheap and has no visible side effects, so their lists can be used directly.
- `import_all.py` keeps `_NO_COMMON_FLAGS` and `_PERSON_AWARE` local to `main()` and runs `_run_post_import_sanitize()` after the importer loop. Calling an auto importer directly from the TUI would need duplicated flag logic and would **skip the PII sanitising step**.
- `analyse_all.py --only` is a substring match. `analyse_pem` also selects `analyse_pem_cascade` and `analyse_pem_threshold`. `import_polar`, `import_oura` and `import_garmin` have the same collision.
- AI comments are on by default in `analyse_all.py`; `--llm` is a deprecated no-op. Depending on config, a default run can send data to a remote provider.
- `compute_all.py`'s header disagrees with its own list on at least one output table (`compute_hrv_advanced`: `ppi_hrv_advanced` vs. `ppi_windows`), and some dependencies are prose ("all metrics").
- `post_import_sanitize.run()` swallows all errors and has no CLI. Its general PII scan and compliance check open only `health.db`; `medicine.db` only gets provider pseudonymisation.
- `run_pipeline_script()` uses `capture_output=True`, so a child's output reaches the orchestrator's stdout only when that child ends. `analyse_all.py` goes further: it writes each child's output to `<stem>.log` in the run's output directory, and prints only progress and a summary.
- `modules/db.open_db()` installs persistent triggers when it opens a database, so it is not a read-only way in.
- `_log_pipeline_run()` writes `compute_log` and `analysis_log`. Those timestamps use SQLite's `datetime('now')` format, while `post_import_sanitize.py` writes ISO 8601 with an offset into `import_log`, so the formats cannot be compared as strings.
- `post_import_sanitize.py` adds `post_import_*` rows to `import_log`, which are not imports.
- Several scripts have flags that weaken protection: `analyse_synthesis.py --no-scrub`, `datasette_serve.py --host/--writable`, `check_all.py --fix`, `check_anonymization.py --fix/--show-mappings`, `lookup_ingredients.py --api-key` (would be visible in the process list).

## Goals / Non-Goals

**Goals:**
- Every routine pipeline action is reachable without remembering a command or flag.
- Auto and manual paths for import, compute and analyse, with single-script runs in all three.
- Using the TUI is never less safe than using the CLI correctly.
- Same behaviour on Linux and macOS, locally and over SSH.
- New scripts cannot silently go missing from the TUI.

**Non-Goals:**
- Reimplementing pipeline logic, or changing what any existing script computes.
- A web variant, or any listening port beyond the existing Datasette tool.
- Rebuilding interactive scripts as forms.
- Exposing destructive or migration tools.
- A dependency-graph scheduler or parallel job execution.
- Windows support, or result viewing beyond what scripts print (plots stay files).

## Decisions

### 1. Orchestrate through CLIs; add `--only-exact` instead of bypassing orchestrators

Auto importers, compute scripts and analysis scripts run only through their orchestrator, with a new `--only-exact STEM[,STEM]` flag. Stems match exactly, and unknown stems exit non-zero before anything runs. Selected scripts keep the orchestrator's list order. `--only-exact` and `--only` are mutually exclusive on `analyse_all.py`.

*Why:* the orchestrators already own flag assembly, `compute_log` entries, output directories, `SCRIPT_EXTRA_FLAGS` and post-import sanitising. A selective run inherits all of that.

*Alternatives:* calling scripts directly (duplicates this logic and skips sanitising); escaping `--only` patterns (substring semantics cannot express `analyse_pem` alone); changing `--only` itself (breaks existing usage).

With `--only-exact`, `import_all.py` still syncs the device registry and runs post-import sanitising, but skips inbox routing and the outbreak source health check. Routing would start a script nobody selected, and the health check is network traffic unrelated to a single import.

### 2. Registries are imported; only what has no registry goes into a manifest

The TUI imports `IMPORTERS`, `COMPUTE_SCRIPTS`, `COMPUTE_REQUIRES`, `ANALYSE_SCRIPTS` and `REQUIRES_INFECTION_DATE`. `scripts/tui/manifests.py` declares everything else as typed entries:

```python
ScriptEntry(
    script="analysis/manual/analyse_ecg_session.py",
    label=("...", "..."),            # DE, EN; rendered through t()
    group="analyse_manual",
    fields=(TextField("--session"), BoolField("--plot")),
    mode=ScriptMode.PIPED,           # PIPED | INTERACTIVE | SERVICE
    uses_llm=False,
)
```

*Alternative:* generating forms from argparse at runtime. Rejected: importing every script runs module-level code, `--help` costs a subprocess per script, and an allowlist is what makes the safety guarantees in decision 5 possible.

### 3. Drift is caught by tests, not by discipline

A test module enforces:
- Every `importers/import_*.py`, `compute/compute_*.py` and `analysis/manual/*.py`, and every `utils/*.py` with a `__main__` block, is covered by a registry or manifest, or listed in `EXCLUDED` with a reason.
- Every manifest flag exists in the target script, using `analyse_all._supported_flags()`.
- No blocked flag appears in any manifest.
- A script that calls `input(` is `mode="interactive"`, unless the entry declares that the prompt sits behind a flag the TUI never passes.
- `COMPUTE_REQUIRES` has a key for each entry in `COMPUTE_SCRIPTS`, and each dependency is listed earlier.

### 4. Execution: single-writer job runner with three modes

`scripts/tui/runner.py` runs jobs through `asyncio.create_subprocess_exec` inside a Textual worker, always as an argument list and never through a shell.

| Mode | Behaviour |
|---|---|
| `piped` | `stdin=DEVNULL`, stdout and stderr merged and streamed into `RichLog`; `PYTHONUNBUFFERED=1` so output is live |
| `interactive` | `App.suspend()` hands the real terminal to the script; the TUI resumes when it exits |
| `service` | Long-running, not subject to the job lock, start/stop toggle, stopped on quit |

- **One job at a time.** Pipeline scripts write to the same SQLite files, and concurrent writers cause lock errors. Actions are disabled while a job runs.
- **`stdin=DEVNULL`** turns a misclassified interactive script into an immediate `EOFError` instead of an invisible hang.
- **Cancel:** jobs start in their own session, and cancelling sends SIGTERM to the process group, then SIGKILL after a grace period. Orchestrator children die with their parent.
- **Language:** passed through `KYORO_LANG` in the child environment, since not every script has `--lang`.
- **Interactive scripts own their prompts.** The TUI does not add `--yes` or `--no-confirm`.
- **Live output has three granularities.** Directly run scripts stream line by line. `import_all.py` and `compute_all.py` show a child's output when that child ends. `analyse_all.py` shows only progress, so the job view offers the per-script output file afterwards, read-only. The job view always shows elapsed time, so a long step does not look hung. Streaming inside `run_pipeline_script()` is out of scope, because its stderr handling and import-log compliance check depend on the captured result.
- **Plots:** piped jobs run with `MPLBACKEND=Agg`, as `analyse_all.py` does for its children, so no plot window opens and nothing fails over SSH.

- **Waiting for a job:** the runner waits for the process to exit, not for `Process.wait()`, which also waits for the pipes to close and would hang on a grandchild holding them open. After a short drain period, remaining output of such a grandchild is read and discarded, so it cannot block on a full pipe.
- **Service output** is always read, for the same reason.

*Alternative:* a pseudo-terminal widget for interactive scripts. Rejected as far more code than `App.suspend()`, which exists in the current Textual release.

### 5. Safety is an allowlist

Only flags declared in a manifest can be passed, so blocked flags cannot be reached from the UI. The blocked set covers privacy-weakening or secret-exposing options (`--no-scrub`, `--host`, `--writable`, `--api-key`, `--show-mappings`, `--fix` on check scripts, `--no-backup`, `--accept-terms`), plus `--yes` and `--no-confirm`, which would bypass a script's prompts. An entry declaring such a flag cannot be created, and this is asserted by test.

Out of the TUI entirely, listed in `EXCLUDED`: `decrypt_db`, `scrub_*`, `migrate_*`, `pseudonymize_*`, `reduce_gps_precision`, `create_*_schema`, `apply_icd_corrections`, `promote_anamnese_findings`, plus `calibration/`, `medical/` and `cluster/`.

### 6. Remote LLM consent

The analyse form has a single "AI comments" toggle mapped to `--no-llm`; the deprecated `--llm` is not offered. The screen shows the active provider and whether it is local, using `is_local` from `utils/llm_provider.py`. Before a run that may use LLM, if the provider is not local or cannot be determined, the start dialog (decision 16) names the provider and offers: run, run without AI (where supported), or cancel. Consent applies to one run and is never remembered. With a local provider, the dialog has no consent part.

*Why not default AI off in the TUI?* The TUI should not silently produce different results than the same command on the CLI.

### 7. Status comes from existing tables, read-only

The dashboard reads `import_log`, `compute_log` and `analysis_log` through a new read-only opener in `modules/db.py`, reusing its decryption but not its trigger installation, with `PRAGMA query_only=ON` and a short timeout. If a database is locked, missing or undecryptable, or a log table does not exist yet, the affected status shows as unknown and the UI keeps working. This corrects the earlier idea of a TUI that never touches a database: it reads, and only scripts write.

Three rules keep the stale hint correct:
- Timestamps are parsed to UTC before comparing, never compared as strings.
- `post_import_*` and `compute_*` rows do not count as imports. Sanitising and some compute scripts write to `import_log`, which would otherwise make compute look outdated.
- Only imports with new rows make compute outdated. Otherwise a daily run that found nothing new would do the same.
- Only `COMPUTE_SCRIPTS` and `ANALYSE_SCRIPTS` entries count towards a stage being current. Otherwise an on-demand run would hide an outdated full run. A stage is as current as its script with the oldest success, so a single-script run does not hide the others either.

`modules.identity_resolver` still ensures the schema of `identity.db` when it loads, and the orchestrators load it through `OWN_PERSON_ID`. That is what every pipeline script does, so the TUI does not work around it.

### 8. Single compute runs warn and do not block

Selecting a compute script shows, from `COMPUTE_REQUIRES` and `compute_log`:
- **Upstream:** dependencies that never succeeded, or are older than the latest import. Warning only, run stays possible.
- **Downstream:** the transitive dependents that become stale. The user can run the script alone, or together with its dependents through `--only-exact`.

*Alternative:* parsing the header. Rejected: it names tables rather than scripts, contains prose, and already disagrees with the code. The header stays the human-readable documentation; a test covers the mapping's structure. The mapping's initial content is derived from each script's actual SQL, not copied from the header.

The mapping includes reads through views (`heart_rate`, `sleep`, `daily_summary`) and single metrics in `measurements`. Three such reads go against the fixed order: `compute_stress` reads `heart_rate` and `sleep` before their producers run, and `compute_af_evidence` reads `daily_summary` before `compute_daily_context` runs. These scripts see the previous run's state. `COMPUTE_READS_LATER` records them separately, so `COMPUTE_REQUIRES` keeps pointing backwards. The order stays unchanged here, because moving a script changes computed results.

### 9. Daily workflow is a guided sequence

`fetch_daily` → `import_staged` → `process_inbox --dry-run` (preview, explicit confirmation) → `process_inbox --import` → `compute_all` → `analyse_all`. The workflow asks once at its start, not before each step (decision 16), and the inbox preview keeps its own confirmation. If `analyse_all` may use a remote provider, that first question says so and offers the run without AI, and the answer applies to this one sequence only. On a non-zero exit the sequence pauses and asks whether to continue or abort. It does not stop automatically, because `import_all.py` exits non-zero when any one source fails, which would otherwise block the whole day. The preview is mandatory because inbox routing is by file pattern, and a wrong file can end up in the wrong importer.

### 10. Layout and entry point

```
scripts/kyoro_tui.py        thin entry point; clear message if textual is missing
scripts/tui/
├── app.py                  screens, key bindings, language
├── runner.py               job runner (decision 4)
├── manifests.py            ScriptEntry, EXCLUDED (decisions 2, 5)
├── status.py               read-only status queries (decision 7)
├── widgets/                job log, flag form generated from fields, start dialog
└── screens/                dashboard, import, compute, analyse, utils, query, export
```

`scripts/tui.py` next to `scripts/tui/` would make the import ambiguous, hence `kyoro_tui.py`. All UI text uses `t()`. Everything works by keyboard; the mouse is optional. `requirements.txt` carries a major-version bound for `textual`, because its API moves faster than the repo's other dependencies.

### 11. Utility screen selection

Grouped; every entry is declared in the manifest:

| Group | Scripts | Mode |
|---|---|---|
| Capture | `log_exposure`, `track_location`, `orthostatic_test`, `anamnese_interview` | piped, interactive for the last two |
| Lookup | `resolve_pseudonym`, `lookup_ingredients`, `context_query` | piped |
| Checks | `check_all`, `check_source_privacy`, `check_anonymization`, `check_docstrings`, `check_compliance`, `check_import_logging`, `check_sql_columns`, `check_data_source_coverage`, `check_no_dates`, `check_ai_labeling`, `check_location_columns`, `check_syndrome_endemic_regions`, `audit_device_id_usage`, `check_outbreak_source_health`, source freshness checks without `--update` | piped |
| Maintenance | `recalibrate`, `fetch_yearly`, `sync_registry_to_devices`, `cleanup_apple_health --check`, `update_icd10_catalog --check` | interactive for `recalibrate`, otherwise piped with confirmation |
| Documents | `md_to_pdf`, `konsil_pdf`, `sort_scan_batch`, `dump_scan_to_ods`, `md_table_to_ods`, `health_report`, `health_visualize` | piped |
| Service | `datasette_serve` (localhost, read-only) | service |

### 12. Manual imports always sanitise

After a manual importer ends, the TUI runs `import_all.py --sanitize-only` as a second step of the same job, whether the importer succeeded, failed or was cancelled, because partial writes are possible in each case. This matches the full run, which also sanitises after importer errors. Exception: the entry declares a flag as non-writing (`no_write_flags`, for example a dry run) and that flag is set.

`--sanitize-only` runs nothing else and exits non-zero if a step failed. `run()` currently swallows errors, so it additionally returns the failed steps. Existing callers ignore that value, so their exit codes stay the same. If sanitising fails or is cancelled, the UI says the data has not been sanitised and offers a retry.

The direct CLI path is unchanged. A CLI manual import is picked up by the next `import_all.py` or `import_staged.py` run, because the scan covers the whole database and not only new rows.

*Alternative:* a separate small CLI script. Rejected: `import_all.py` already imports this function, and a flag adds no new entry point.

### 13. On-demand runs are logged by the orchestrators

The TUI must not write to a database, so logging stays in the orchestrator. `compute_all.py --on-demand STEM -- ARGS` and `analyse_all.py --on-demand STEM -- ARGS` run one script from a new on-demand list, forward `ARGS` unchanged and write the log row. The lists are separate from `COMPUTE_SCRIPTS` and `ANALYSE_SCRIPTS`, so full runs do not change. The manifest still declares the form fields, and a test keeps both in sync.

The two differ in execution:
- **Compute** goes through `run_pipeline_script(log_compute=True)`.
- **Analysis** does not go through `analyse_all.run_script()`, because that redirects output to a file, which would break interactive scripts such as `analyse_synthesis.py`, and adds `--plot`. The child inherits stdin and stdout, so it streams live and works under `App.suspend()`, and `_log_analysis_run()` is called afterwards.

A run that only previews or lists computes nothing, and a log row would falsely show a fresh result. `--dry-run` is therefore never logged, and `ON_DEMAND_ANALYSE_SCRIPTS` declares further such flags per script (for example `--list` on `analyse_ecg_session.py`, `--list-backends` on `analyse_reha_klinik_empfehlung.py`).

Limits: direct CLI calls and `recalibrate.py`, which calls `compute_calibrate_sources.py` itself, stay unlogged. Only the path through `--on-demand` is covered.

*Alternatives:* a logging wrapper in the TUI (breaks the no-write rule); adding the scripts to the regular lists (would run calibration and LLM-heavy scripts in every full run).

### 14. Results browser reads the existing output layout

`analyse_all.py` writes to `<analyses_dir>/<run_date>/<stem>/`, with `.md` reports, `.png` plots, and an output file and a metadata log per script (decision 15). The browser lists scripts from `ANALYSE_SCRIPTS`, then the dated runs that have output for the selected script, newest first. Reports render in Textual's Markdown widget, and output files show as text. Terminals cannot show plots reliably, so a plot opens in the system viewer (`xdg-open` on Linux, `open` on macOS). Without a graphical session, for example over SSH, the path is shown instead.

The browser only reads files and needs no index, so it also works for runs started on the CLI. Scripts that ran without a report are marked as such, matching the "no report" state in `analyse_all.py`. On-demand scripts write outside this layout, and their output locations are taken from each script during implementation.

*Alternative:* showing only the script output after a run. Rejected: the report is what users want to read, and the output rarely holds it.

### 15. Results belong to the user, logs hold metadata only

Today `analyse_all.run_script()` sends each script's full stdout and stderr to `<stem>.log`, along with the command line. Those lines include dates, event names and whole reports, and the file is readable by other local users. Results should be shown to the user, not kept in a log.

`run_script()` therefore writes two files in the run directory:

| File | Content | Mode |
|---|---|---|
| `<stem>.output.txt` | The script's stdout and stderr, shown to the user in the job view and results browser | `600` |
| `<stem>.log` | Script file name, start time, duration, exit code, output file name, and names of skipped flags | `600` |

The log holds no script output, no tracebacks and no argument values, because arguments can carry dates. A log may at most name which file was accessed, by which user and for which patient. No script writes user or patient fields into it under this change, and an access log for clinical use would be a separate change.

After a failed script, `analyse_all.py` prints the end of the output file to the terminal as it does with the log today. Only `.md` files count as reports, so a script that leaves just an output file keeps its "no report" state. The mode is set on existing files too, as a second run on the same day reuses them.

Old `.log` files keep their mixed content. Nothing deletes them automatically, because for some runs they are the only copy of the output. The results browser shows such a file as that run's output. Cleaning them up is offered as a separate step that first lists the count and deletes only after explicit confirmation.

*Alternatives:* dropping the output altogether (loses the only result of scripts without a report); scrubbing values from the log (a filter can miss values, and the output would stay in a log).

### 16. Every job start asks once

Every job start shows one dialog before anything runs: single scripts, manual imports, utilities, checks, full orchestrator runs and starting a service. Stopping a service, cancelling and read-only browsing of results do not ask. The dialog names the script, its arguments and whether it writes, so it is worth reading.

A sequence asks once at its start. Asking before each of six daily steps would train the user to confirm without looking, and then the question protects nothing.

Remote LLM consent is part of the same dialog (decision 6), so two questions never follow each other. Scripts with their own prompts, such as the cost question in `analyse_synthesis.py`, still ask afterwards, because the TUI does not bypass them.

This is a property of starting a job, so it does not depend on a manifest entry, and `ScriptEntry` has no `confirm` field. There are no exceptions for read-only checks: one rule without exceptions is easier to rely on.

*Alternative:* asking only for actions that write. Rejected, because the user wants to be asked everywhere.

### 17. Person selection comes from the databases

The person field lists the persons found in the databases, read through the read-only opener (decision 7), with names from `identity_resolver.reverse_resolve`. A pseudonym without a name is shown as it is, and the own person is shown as "Myself". The default is `OWN_PERSON_ID`. Tables without health data, such as `devices` and the log tables, do not count. Values that are no pseudonym are ignored, and so is the pseudonym that stands for `unknown`, because it marks unassigned data and not a person. Reading all tables can take long with a cold disk cache, so it runs in a background worker. With only one person, the field is hidden and no `--person` is passed. Names appear only on screen, and the TUI stores neither the list nor the selection.

`identity_resolver` has no function that lists persons, so the list comes from the data. This also keeps persons out of the list for whom no data exists.

*Alternatives:* no field (other persons would need the CLI); free text for the `PER-` ID (nobody remembers these, and a typo runs against the wrong person).

## Risks / Trade-offs

- **[Confirmation fatigue]** Every start asks → A sequence asks once, the dialog states what will happen, and confirming takes one key.
- **[Names on screen]** The person selection shows display names, for example over a shared screen → It appears only with more than one person, and nothing is stored.

- **[Script output contains health data]** → In the TUI it stays in memory and on the alternate screen, and `RichLog` has a line limit. The TUI saves no logs. `analyse_all.py` writes output only to the user's own output file (decision 15).
- **[A CLI user expects output in `<stem>.log`]** → `analyse_all.py` names the output file after a failure, and the file sits next to the log. Docs are updated.
- **[Service temp copy]** `datasette_serve.py` works on a decrypted temporary database → Stop and quit send SIGTERM and verify that the temp file is gone. This is a test case, and if cleanup does not hold, the script gets fixed rather than worked around.
- **[Cancelling a job mid-write]** → SIGTERM can interrupt an importer. Inserts are `INSERT OR IGNORE`, so a re-run is safe, and the UI says so after a cancel.
- **[Sanitising covers less of `medicine.db`]** Manual lab imports write there, but the general PII scan only opens `health.db` → Handled in `extend-pii-scan-to-medicine-db`, as the existing scan would destroy clinical text there. The UI does not claim full coverage: even after that change, heuristic matches are only reported.
- **[Orchestrator output is delayed per script]** → Elapsed time is always visible, and direct scripts stream live.
- **[Provider display can differ from what a sub-script uses]** Providers are configurable per tool → Consent appears whenever any route is remote or unknown, so errors fall on the side of asking.
- **[`textual` API churn]** → Major-version bound and pilot-based tests make breakage visible.
- **[Importing orchestrators ties the TUI to their module level]** → A test imports them with an empty config directory, so config access at import time fails CI.
- **[macOS not tested in CI]** → Textual declares macOS support, and the TUI uses only POSIX process groups. Manual verification on a macOS host is a task, not an assumption.
- **[Manifest maintenance]** → One extra step per new manual script, enforced by decision 3.

## Migration Plan

Purely additive. Existing commands and flags are unchanged. Rollback: remove `scripts/tui/`, `scripts/kyoro_tui.py` and the `textual` line. `--only-exact` and `COMPUTE_REQUIRES` can stay, as they are harmless on their own.

## Open Questions

- Does `process_inbox --import` run `import_all.py --update` when the inbox is empty? This decides whether the daily workflow needs a separate import step.
