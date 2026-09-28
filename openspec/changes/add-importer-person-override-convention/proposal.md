## Why

CLAUDE.md documents the importer convention as
`run(conn, data_path, lang='de', person=None) -> ImportResult`. Investigating a
request to make `import_ecg_logger.py` support an explicit `--person` override
(needed for two real scenarios: manually re-evaluating an ECGLogger recording as
a deliberate orthostatic test, and a device shared between multiple people — e.g.
a sensor used across patients in a clinic setting, where the device identity alone
cannot tell you whose recording it is) surfaced a gap wider than that one file:

- `import_all.py` invokes every importer as a subprocess of its own `main()`
  (`[sys.executable, str(script_path), ...]`), never by importing the module and
  calling `run()` in-process. Grepping the codebase for callers of any importer's
  `run(conn, ...)` function found none — the ~10 importers that already define one
  (`import_shotsy.py`, `import_symptomtagebuch.py`, `import_camerahRV.py`, and
  others) have it as dead code from the live pipeline's perspective.
- Even where `run()` exists and accepts `person`, the parameter is sometimes
  declared but never threaded into the actual save/insert calls
  (`import_symptomtagebuch.py`, `import_camerahRV.py`) — accepting the parameter
  gives the appearance of person-awareness without the substance.
- `import_ecg_logger.py` itself had neither: no `run()` function, no `--person`
  CLI flag, and both its `ppi_raw` and `ecg_logger_sessions` writes hardcoded
  `OWN_PERSON_ID` regardless of whose file was actually being imported.

None of this is hypothetical for this project specifically: it has a separate
shared-access multi-person feature (`utils/manage/shared_access/`) and a real
day-to-day scenario of shared sensors, so an importer that silently attributes
everything to one person is a correctness bug waiting to be hit, not a
theoretical gap.

## What Changes

- Add a requirement to `cross-cutting-conventions`: an importer's person handling
  must be genuinely functional — an accepted `person` parameter (CLI `--person` or
  a `run()` argument) must reach every DB write the importer performs, not just be
  accepted and silently ignored. Resolve it via `resolve_person()` /
  `modules.base.resolve_person`, never a hardcoded `OWN_PERSON_ID`.
- Add a scenario naming the specific anti-pattern found today (a `person`
  parameter that is declared, resolved, and then never passed to the function
  that actually performs the insert) as a defect a reviewer should catch, not a
  style nitpick.
- Add a scenario for the shared-device case: when a data source could plausibly
  belong to a device shared across people (clinic sensor, borrowed device), the
  importer must not infer the person from the device identity — it must require
  an explicit override.
- Deliberately does NOT mandate wiring every importer's `run()` into
  `import_all.py`'s actual call path. That is a separate, larger architectural
  question (subprocess vs. in-process invocation) outside this change's scope;
  this change only requires that when an importer's person parameter exists, it
  works.
- Deliberately does NOT fix the other ~9 importers with the same gap in this
  change. `import_ecg_logger.py` was fixed as part of the session that surfaced
  this (`run()` added, `--person` added, both writes now use `resolve_person()`).
  The remaining inventory is tracked as follow-up work, not bundled here.
