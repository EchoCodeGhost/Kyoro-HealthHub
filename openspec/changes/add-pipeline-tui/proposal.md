## Why

Running Kyoro means remembering dozens of commands, flags and an implicit stage order: 43 auto importers, about 20 manual importers with differing signatures, 23 compute scripts, 84 analysis scripts, 11 on-demand analysis scripts, plus maintenance tools spread over `scripts/` and `scripts/utils/`. That is a real barrier on low-energy days and for anyone who did not write the pipeline. A terminal UI makes the existing pipeline discoverable and safe to operate, on Linux and macOS, including over SSH, without adding a server or changing how data is processed.

## What Changes

- New terminal UI built on `textual`, started with `python3 scripts/kyoro_tui.py`. It is an operating layer only: every action runs an existing script as a subprocess and streams its output live.
- **Auto and manual** coverage for all three pipeline stages:
  - Import: all auto importers, single auto importers, and a manual tab with a file or directory picker.
  - Compute: all scripts, single scripts with a dependency warning, and the on-demand compute scripts that are not part of `compute_all.py`.
  - Analyse: all scripts, single scripts, a full flag form, and the on-demand scripts in `scripts/analysis/manual/`.
- Results browser for analyses: pick a script and a run, read its report and script output, and open its plots.
- Curated utility screen covering data capture, lookups, read-only checks, maintenance, documents and the local Datasette service. Destructive and migration tools stay CLI-only.
- Manual imports started from the TUI always trigger post-import sanitising, which today only runs after `import_all.py` and `import_staged.py`.
- On-demand compute and analysis runs started from the TUI are recorded in `compute_log` and `analysis_log`, like registered scripts.
- Dashboard with last-run status from `import_log`, `compute_log` and `analysis_log`, stale-stage hints, a preview of scripts that would be skipped, and a guided daily workflow.
- Query and export screens wrapping `health_query.py` and `export_health.py`.
- One confirmation before every job start, naming the script, its arguments and whether it writes. A guided daily workflow asks once at its start.
- Consent as part of that confirmation for any run that may send data to a remote LLM provider. The active provider is always visible. This matters because AI comments are on by default in `analyse_all.py`.
- A person selection that lists the persons found in the databases, hidden when there is only one.
- Small additions to the orchestrators, none of which change existing behaviour:
  - `--only-exact STEM[,STEM]` on `import_all.py`, `compute_all.py` and `analyse_all.py`. The existing `analyse_all.py --only` matches substrings, so `analyse_pem` also runs `analyse_pem_cascade` and `analyse_pem_threshold`.
  - A machine-readable `COMPUTE_REQUIRES` mapping in `compute_all.py`. The dependency chain in the header is prose and is not reliably parseable.
  - `import_all.py --sanitize-only`, which runs post-import sanitising alone and reports failures through its exit code.
  - `compute_all.py --on-demand STEM -- ARGS` and `analyse_all.py --on-demand STEM -- ARGS`, which run a script from a new on-demand list with logging.
  - `analyse_all.py` separates output from logs: script output goes to a user-visible output file, and `<stem>.log` holds run metadata only.
- Declarative TUI manifest for everything without a central registry, plus automated checks that fail when a script is neither covered nor explicitly excluded, or when a manifest flag no longer exists.
- New runtime dependency: `textual`.

## Capabilities

### New Capabilities
- `pipeline-tui`: Terminal UI for operating the pipeline: screens, script selection, job execution, consent for remote LLM use, flag allowlisting, and drift checks.

### Modified Capabilities
- `pipeline-architecture`: Adds exact selective execution for the three orchestrators, standalone post-import sanitising, logged on-demand compute and analysis runs, and a machine-readable compute dependency mapping alongside the documented order.

## Impact

- **New code:** `scripts/kyoro_tui.py`, `scripts/tui/` (app, runner, manifests, screens), tests under `tests/`.
- **Modified code:** `scripts/import_all.py`, `scripts/compute_all.py`, `scripts/analyse_all.py` (new flags; `COMPUTE_REQUIRES` and `ON_DEMAND_COMPUTE_SCRIPTS` in `compute_all.py`; `ON_DEMAND_ANALYSE_SCRIPTS` in `analyse_all.py`), `scripts/utils/post_import_sanitize.py` (`run()` also returns its failed steps). Apart from the separated output and log files in `analyse_all.py`, runs without the new flags behave as before.
- **Dependencies:** `textual` in `requirements.txt`. All pipeline scripts keep working without it; only the TUI entry point needs it.
- **Data:** the TUI opens databases read-only for status display. All writes remain in the existing scripts. No new tables, and the TUI persists no logs. Logs never contain script output or health data. `compute_log` and `analysis_log` gain rows for on-demand scripts, so readers must not treat every row as part of a full run.
- **In-flight changes:** `switch-import-all-to-inprocess-run` is compatible, because the TUI calls `import_all.py` through its CLI and does not depend on how it invokes importers internally. `--only-exact` has to be carried over if that change lands first.
- **Related change:** `extend-pii-scan-to-medicine-db` widens what `--sanitize-only` covers. It is independent of this change and needs no work here.
- **Docs:** `CLAUDE.md` (the steps for adding a script now include a manifest entry), `README`.
