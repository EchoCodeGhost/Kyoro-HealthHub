# pipeline_runner.py — gemeinsamer Subprozess-Runner für Master-Pipeline-Skripte.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/pipeline_runner.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Runs a pipeline script (importer/compute/analysis) as a subprocess and ensures its output isn't lost on a crash. Shared by import_all.py, compute_all.py and analyse_all.py so all three master scripts behave identically on failure.

## Relevance

Enables pipeline processing, essential for data processing workflows

## Method

subprocess.run(..., capture_output=True, env with PYTHONUNBUFFERED=1) instead of inheriting stdout/stderr. capture_output gives clean ordering and lets us print the last 20 stderr lines on failure; PYTHONUNBUFFERED prevents a hard-killed child (e.g. OOM-killed) from losing block-buffered, unflushed output before it was ever written. check_import_log=True (set by import_all.py) counts the total row count across all tables (except import_log) in health.db and medicine.db before/after the subprocess; if a successful run leaves more data rows but no new import_log entry, that's treated as a chain-of-custody violation. Checked deliberately at the run level, not per SQL transaction: many importers commit multiple times and log only once at the end (e.g. import_polar.py: 21 commits, 1 log_import() call) — a per-commit check would break this existing, working architecture. log_compute=True (set by compute_all.py) writes a compute_log entry to health.db after every subprocess run (script name, current git commit hash via `git rev-parse HEAD`, return code, duration) — the compute-side counterpart to import_log, since derived tables are overwritten via DELETE+recompute on every run and would otherwise leave no way to reconstruct which code version produced a given result. log_analysis=True (set by analyse_all.py) analogously writes an analysis_log entry (same fields as compute_log, via the same internal _log_pipeline_run() helper) — analysis scripts don't write to source tables and would otherwise be unauditable.

## Data flow

- **Reads:** `health.db`, `medicine.db`, `(nur`, `für`, `den`, `Zeilenzahl-Vergleich`, `bei`, `check_import_log)`
- **Writes:** `compute_log in health.db, wenn log_compute=True; analysis_log in health.db, wenn log_analysis=True (sonst nichts direkt) — die aufgerufenen Kindskripte lesen/schreiben die DB selbst`

## Limitations

No live streaming — output only appears after the process exits. For long-running individual scripts (e.g. Polar import) this is a deliberate trade-off against swallowed error messages. check_import_log only detects "data written but no log entry at all" at the run level — no fine-grained attribution of which table/source was affected, and no detection of wrong/incomplete (but present) log entries.

## Usage

```bash
from modules.pipeline_runner import run_pipeline_script
errors: list[str] = []
run_pipeline_script("import_all", script_path, cmd, errors)
run_pipeline_script("import_all", script_path, cmd, errors, check_import_log=True)
run_pipeline_script("compute_all", script_path, cmd, errors, show_command=True)
run_pipeline_script("compute_all", script_path, cmd, errors, log_compute=True)
run_pipeline_script("analyse_all", script_path, cmd, errors, log_analysis=True)
```
