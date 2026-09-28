## Why

`add-provenance-logging` found that 23 of 25 importers flagged by `check_import_logging.py`'s new `person=` warning have no person handling at all — no `run()` function (only `main()`), `OWN_PERSON_ID` written directly at 2-9 call sites each. This is a distinct, previously-uninventoried population from the ~14 importers `add-importer-person-override-convention` already covers (that change's inventory was scoped to importers that already had a `run()` function). Without this, these 23 importers cannot support a second person (multi-patient clinic deployment, a shared device) at all — not a logging gap, a functional one.

## What Changes

- Each of the 23 importers gains a `run(conn, data_path, lang='de', person=None) -> ImportResult` function per the CLAUDE.md convention, extracted from its existing `main()` logic where not already structured that way.
- Every hardcoded `OWN_PERSON_ID` reference at a DB-write site is replaced with the resolved `person` value (`resolve_person(person)`).
- `main()` gains a `--person` CLI flag, threaded into the new `run()`.
- `log_import()` calls in all 23 get the resolved `person` passed through.
- Two already-person-aware importers (`import_airquality.py`, `import_outbreak_data.py`) get only the small, mechanical `log_import(..., person=<already-resolved value>)` fix — no structural change needed.

## Capabilities

No capability changes. `importer-pattern`'s "Uniform importer signature" requirement and `cross-cutting-conventions`' "Functional person override in importers" requirement already mandate exactly this — this change is pure implementation catch-up against existing, unchanged requirements, not a spec change. No delta spec files.

## Impact

- 25 files in `scripts/importers/` (23 structural, 2 mechanical).
- `scripts/import_all.py`'s `--person` allowlist (added by `add-importer-person-override-convention`) grows to include these 23 once each is verified working.
- No schema changes. No changes to `add-provenance-logging`'s infrastructure (`log_import()`, `modules/base.py`) — this change only adds callers that use the `person=` parameter that infrastructure already supports.
