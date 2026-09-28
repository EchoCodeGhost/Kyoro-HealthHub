## Why

`importer-pattern`'s "Uniform importer signature" requirement already mandates
every importer expose `run(conn, data_path, lang='de', person=None) ->
ImportResult`. In practice `import_all.py` has never called any importer's
`run()` — it invokes every entry in `IMPORTERS` as a subprocess of that
importer's own `main()`. Auditing this while building the
`add-importer-person-override-convention` change found that the ~14 `run()`
functions that already exist are effectively untested: two of them
(`import_camerahRV.py`, `import_symptomtagebuch.py`) had a `person` parameter
that was declared and resolved but never actually passed to the function that
performs the insert, and nothing caught it because nothing ever called `run()`
to exercise the bug.

`import_all.py` just gained a `--person` flag (see the person-override-
convention change) that forwards to a small, explicit allowlist of importers
known to support it — a deliberately narrow fix, because forwarding `--person`
to every importer indiscriminately would crash every importer that doesn't
recognize the flag with "unrecognized arguments" (the same failure class found
and fixed in `create_medicine_imaging_schema.py` during the `import_fundus.py`
work). Switching to in-process `run()` calls would remove this class of
problem structurally — a Python keyword argument can't be "unrecognized" the
way a CLI flag can — but it is a materially larger and riskier change than the
allowlist fix, discussed and deliberately deferred past that change:

- Subprocess isolation is a real safety property the pipeline currently
  relies on. A crash, hang, or `sys.exit()` call inside one importer's
  subprocess doesn't affect the next importer. In one shared process, an
  uncaught exception in importer #23 (of ~70) would stop every importer after
  it unless every single call site is wrapped; a `sys.exit()` anywhere in a
  called `run()` (a pattern already seen in `import_kyoro_symptoms.py`'s
  `main()`) would kill the entire orchestrator, not just that importer.
- A shared `sqlite3`/`sqlcipher3` connection across ~70 `run()` calls means
  any importer that changes a `PRAGMA`, leaves a transaction open, or commits
  at an unexpected point affects every importer that runs after it — currently
  each subprocess gets its own connection, opened and closed cleanly.
- Every importer script does `sys.path.insert(...)` and builds module-level
  state (a `Config()` instance, compiled regexes, etc.) at import time.
  Importing ~70 of these into one interpreter for the first time is untested
  territory for import-order and naming collisions that subprocess isolation
  has always made a non-issue.
- The ~14 existing `run()` functions have zero callers today — this change
  would be the first real exercise of that code path project-wide, for all of
  them simultaneously, unless the rollout is incremental.

None of this means in-process dispatch is a bad idea — the safety property
CLAUDE.md and `importer-pattern` already describe for individual importers
(idempotent writes, atomic logging, a callable `run()`) is exactly what a
future in-process orchestrator needs. It means the migration should happen
deliberately, importer by importer, with each one verified safe under
repeated in-process invocation before it's moved off the subprocess path —
not as a single cutover.

## What Changes

- Add a requirement to `importer-pattern`: `import_all.py` SHALL invoke a
  migrated importer's `run()` in-process (via `importlib`, passing the shared
  `conn`) rather than as a subprocess, once that importer is added to an
  explicit `_INPROCESS_READY` allowlist (mirroring the `_PERSON_AWARE`
  pattern already in `import_all.py`) — the migration is per-importer and
  incremental, not a single rewrite.
- Add a scenario describing the per-importer safety checklist an importer
  must satisfy before joining the allowlist: no `sys.exit()` reachable from
  `run()`, no unguarded exceptions expected to propagate to the caller
  (`run()` should return an `ImportResult` with populated `errors` instead),
  no `PRAGMA`/transaction state left in a way that would affect a
  subsequently-called importer sharing the same connection.
- Add a scenario for the orchestrator side: `import_all.py` wraps each
  in-process `run()` call in its own `try/except`, appending to the same
  `errors` list the subprocess path already collects into, so a failing
  in-process importer degrades the same way a failing subprocess importer
  does today (skip and continue, not abort the whole run).
- Deliberately does NOT specify a full cutover date or attempt the migration
  itself in this change — this is a roadmap entry (tracked here as the
  project's top-priority pending architecture item per the user's request),
  not an implementation. Each importer's migration should be its own small,
  independently reviewable change once picked up.
- Deliberately does NOT change the `--person` allowlist mechanism added to
  `import_all.py` — that stays as-is (and keeps working) regardless of when
  or whether this migration happens; an importer moving from the
  `_PERSON_AWARE` subprocess allowlist to the `_INPROCESS_READY` allowlist is
  a pure internal-dispatch change with no effect on the `--person` CLI
  contract.
