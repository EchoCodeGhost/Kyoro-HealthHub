## ADDED Requirements

### Requirement: Incremental in-process invocation via an explicit allowlist
`import_all.py` SHALL invoke a migrated importer's `run(conn, data_path,
lang, person)` in-process (via `importlib`, reusing the shared database
connection) instead of as a subprocess, once that importer is added to an
explicit `_INPROCESS_READY` allowlist. Migration SHALL happen one importer
at a time; an importer not yet on the allowlist SHALL continue to run via
the existing subprocess mechanism. This mirrors the `_PERSON_AWARE`
allowlist already used to scope `--person` forwarding, and exists for the
same reason: a project-wide, all-at-once switch would exercise ~14 `run()`
functions that currently have zero callers, plus require writing `run()`
for the ~56 importers that only have `main()`, simultaneously and without
an incremental safety net.

#### Scenario: An importer is added to the in-process allowlist
- **WHEN** a contributor verifies an importer's `run()` is safe under
  repeated in-process invocation (see the per-importer safety checklist
  requirement) and adds its filename to `_INPROCESS_READY`
- **THEN** `import_all.py` calls that importer's `run()` directly instead
  of spawning a subprocess for it, and every other importer not yet on the
  allowlist is unaffected

#### Scenario: An importer is not yet on the in-process allowlist
- **WHEN** an importer's filename is absent from `_INPROCESS_READY`
- **THEN** `import_all.py` continues to invoke it as a subprocess of its
  `main()`, exactly as it does today — the allowlist's absence is the
  default, safe state, not an error

### Requirement: Per-importer safety checklist before in-process migration

Before an importer is added to `_INPROCESS_READY`, its `run()` SHALL satisfy
all of the following, because they hold under subprocess isolation
automatically but do not hold automatically once multiple importers share
one Python process and one database connection:

- No code path reachable from `run()` calls `sys.exit()` or otherwise
  terminates the process — errors are returned via `ImportResult.errors`,
  not raised uncaught or used to exit.
- `run()` does not leave `PRAGMA` settings, an open transaction, or other
  connection-level state changed in a way that could affect an importer
  called afterward on the same shared connection.
- Module-level side effects at import time (opening files, network calls,
  mutating global state) are either absent or idempotent under repeated
  import within the same process.

#### Scenario: An importer calls sys.exit() internally
- **WHEN** an importer's code path (directly or via a helper) can call
  `sys.exit()` during a `run()` invocation
- **THEN** it does not qualify for `_INPROCESS_READY` until that call is
  replaced with a normal return carrying the error in `ImportResult.errors`

#### Scenario: Orchestrator error handling for in-process importers
- **WHEN** `import_all.py` calls an in-process `run()` for an allowlisted
  importer
- **THEN** the call is wrapped in its own `try/except`, and any exception is
  appended to the same `errors` list the subprocess path already collects
  into — a failing in-process importer is skipped and logged, not allowed
  to abort the rest of the run
