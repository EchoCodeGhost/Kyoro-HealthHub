## Context

23 importers currently only have `main()` — all logic (arg parsing, file discovery, parsing, DB writes) lives inline in one function, with `OWN_PERSON_ID` imported and used directly at every write site. `add-importer-person-override-convention`'s prior work (on a different set of ~14 importers that already had a `run()`) established the pattern to follow: extract a `run(conn, data_path, lang='de', person=None) -> ImportResult` function, resolve `person` once via `resolve_person(person)`, thread that single resolved value into every write, keep `main()` as a thin CLI wrapper that parses args and calls `run()`.

## Goals / Non-Goals

**Goals:** every one of the 23 importers gets a genuinely functional `person` override — not just accepted and ignored (the exact anti-pattern `add-importer-person-override-convention` named as a defect, not a style nitpick).

**Non-Goals:** no behavior change for the default (no `--person` given) case — every existing invocation without `--person` must produce byte-identical DB writes to before this change. Not touching `import_airquality.py`/`import_outbreak_data.py` structurally (already correct, only need the `log_import()` call updated).

## Decisions

**Per-file individual review, not bulk find-replace.** Each file's `main()` has different structure (some read one file, some glob directories, some have multiple sub-parsers for different sub-sources within one script like `import_beurer.py`'s scale/glucose/thermometer split). A mechanical `s/OWN_PERSON_ID/person/g` risks silently breaking a file that uses `OWN_PERSON_ID` for something other than a row's `person` column (unlikely but not verified without reading each file) — matching this session's own repeatedly-learned lesson (`Genau hinsehen, bevor Architektur-Änderungen gemacht werden`).

**`resolve_person(person)` called once per `run()`, not per write site.** Assign to a local `_person` (or `target_person`) variable at the top of `run()`, matching the pattern already used in `import_airquality.py`.

**`main()` becomes a thin wrapper** that builds argparse (adding `--person` where not already present), then calls `run(conn, data_path, person=args.person)`.

**Verification per file:** `py_compile` + a check that no `OWN_PERSON_ID` reference remains in a DB-write context (grep after edit) + (where feasible without a long pipeline run) a targeted smoke check.

## Risks / Trade-offs

**[Risk] 23 files is a lot of surface for a subtle regression in the default (no `--person`) path.** → Mitigation: `resolve_person(None)` returns exactly `OWN_PERSON_ID` (same as the current hardcoded behavior) — the default-path output is provably identical by construction, not just by testing.

**[Risk] Session fatigue this late increases error risk on repetitive work.** → Mitigation: per-file compile + grep verification catches syntax/leftover-hardcode errors immediately; batching similar-shaped files together (single-file importers vs. directory-scanning importers vs. multi-subsource importers) rather than working alphabetically, so the same mental model applies across a batch.

## Migration Plan

1. `import_airquality.py`, `import_outbreak_data.py` — mechanical `log_import()` fix only.
2. Remaining 23, grouped by structural shape, each: extract `run()`, resolve person once, replace hardcoded `OWN_PERSON_ID` at write sites, `--person` CLI flag, `log_import(..., person=...)`.
3. `check_import_logging.py --path scripts/importers` → 0 person-warnings.
4. `python3 -m compileall -q scripts/importers` clean.
5. `import_all.py`'s `--person` allowlist extended to cover the newly-parameterized importers.
