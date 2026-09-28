# tests/

## smoke.sh — end-to-end pipeline smoke test

Catches the runtime/integration bugs that "looks-correct" code hides — the kind
that ship when scripts are edited file-by-file but never run end-to-end against a
real database (e.g. a `SyntaxError` in a script that's never imported, or SQL
against a table that was renamed during the v2 migration).

```bash
./tests/smoke.sh            # compile all scripts + apply compat views
                            # + reference scan (advisory) + analyse_all + unit tests  (~20s)
./tests/smoke.sh --full     # additionally run compute_all (recomputes derived tables)
./tests/smoke.sh --import   # additionally run import_all --update (writes to health.db)
```

Exit code 0 = pipeline runs clean. Non-zero = something is broken. Requires an
initialised `data/health.db` (run `scripts/utils/init_db.py` + an import first).

The real gate is the pipeline actually running (compile + compute_all + analyse_all
exit 0). The static FROM/JOIN reference scan is **advisory only** — its heuristic
also flags prose words and runtime-created tables, so it never fails the run.

`--import` runs the real import pipeline against whatever is currently in
`imports/*/`. It only fails on an importer error that isn't one of the known,
expected ones (missing OAuth credentials for Oura/Polar AccessLink/Garmin,
missing optional Apple Health export, unreachable weather API) — a genuinely
new failure (e.g. a path-resolution bug that silently finds "no files") stands
out immediately instead of blending into the same "9 importers with errors"
noise every run.

## tests/unit/ — pytest unit tests

Pure-logic tests that don't touch `health.db` or personal config — safe to run
anywhere, including CI (`pytest tests/unit`). Covers HRV algorithms, FHIR
export, and regression guards for bug classes that have actually shipped:
config paths that don't resolve `~` (`test_config_paths.py`), inbox files
routed to the wrong importer (`test_process_inbox_sniffing.py`), and pipeline
subprocess output getting lost on a crash (`test_pipeline_runner.py`).

## tests/manual/ — standalone integration tests, run individually only

Tests that need real process-wide environment isolation (e.g. `test_totp_setup.py`,
`test_verification.py`, `test_research_cohort.py` redirect `$HOME` to a fresh temp
directory at module import time, since the modules they exercise resolve `~` at
their own import time and some of that resolution happens in-process, not only in
a subprocess). That redirect is never undone within the process — by design, these
tests assume they own the whole pytest process.

Run them one at a time (`pytest tests/manual/test_totp_setup.py`), not as part of
a batch — collecting more than one `$HOME`-redirecting test (or any test that reads
personal config, e.g. `tests/unit/test_promote_anamnese_findings.py`) in the same
pytest process corrupts every later import that resolves a `~`-based path once and
caches it (e.g. `modules/identity_resolver.IDENTITY_DB_PATH`), producing a confusing
downstream `sqlite3.OperationalError: unable to open database file` in unrelated
tests. `pytest.ini` sets `norecursedirs = manual` specifically so that a plain
`pytest tests/` (as opposed to the documented bare `pytest` / `pytest tests/unit`)
doesn't silently sweep these in and trigger that — explicit invocation
(`pytest tests/manual/<file>.py`) still works, only directory recursion skips it.

## Optional: pre-commit compile gate

A one-line pre-commit hook catches `SyntaxError`s before they're committed (the
whole analysis pipeline once shipped broken on exactly such an error). This is
**not installed automatically** — add it yourself if you want it:

```bash
cat > .git/hooks/pre-commit <<'HOOK'
#!/usr/bin/env bash
cd "$(git rev-parse --show-toplevel)" || exit 1
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
files=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$')
[ -z "$files" ] && exit 0
if ! "$PY" -m py_compile $files; then
  echo "✗ pre-commit: python syntax error above — commit aborted." >&2
  exit 1
fi
HOOK
chmod +x .git/hooks/pre-commit
```
