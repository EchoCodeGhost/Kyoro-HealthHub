## 1. Spec

- [x] 1.1 Formulated requirement "Incremental in-process invocation via an explicit allowlist"
- [x] 1.2 Formulated requirement "Per-importer safety checklist before in-process migration"
- [x] 1.3 Formulated scenarios for both requirements (allowlist member/non-member,
      sys.exit() case, orchestrator error handling)

## 2. Orchestrator scaffolding (one-time, small)

- [ ] 2.1 Add an `_INPROCESS_READY` set to `import_all.py` (analogous to `_PERSON_AWARE`), initially empty
- [ ] 2.2 Extend the loop with a branch: `script_path.name in _INPROCESS_READY` →
      `importlib.import_module(...).run(conn, ..., person=args.person)` in try/except instead of a subprocess
- [ ] 2.3 Use a shared `conn` for all in-process-invoked importers (opened once,
      closed at the end of the run); subprocess importers keep their own connection unchanged

## 3. Migration per importer (each line its own independently reviewable/mergeable change)

- [ ] 3.1 Check the safety checklist (see requirement) against each candidate before it
      goes on the allowlist — starting with the `run()` functions already correct today from
      add-importer-person-override-convention: `import_shotsy.py`, `import_kyoro_symptoms.py`,
      `import_bearable.py`, `import_activity_log.py`, `import_nightmare_log.py`, `import_tracks.py`,
      `import_camerahRV.py`, `import_symptomtagebuch.py`, `import_ecg_logger.py`
- [ ] 3.2 For each of the ~56 importers without a `run()` (only `main()`): add a `run()` per the
      `importer-pattern` signature, then check against the checklist
- [ ] 3.3 For each successfully migrated importer: remove from the subprocess loop de facto
      (by adding it to `_INPROCESS_READY`), update the `@method` docstring

## 4. Wrap-up (far in the future, not part of the current roadmap priority)

- [ ] 4.1 Once `_INPROCESS_READY` contains all importers from `IMPORTERS`: remove the subprocess
      path and the `_NO_COMMON_FLAGS`/`_PERSON_AWARE` special-case handling as dead code
- [ ] 4.2 Update `import_all.py`'s `@method` docstring to "exclusively in-process"
