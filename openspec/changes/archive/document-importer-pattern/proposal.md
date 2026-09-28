## Why

New data importers are the most common expected contribution type from
external contributors after the GitHub release. The pattern (function
signature, `INSERT OR IGNORE`, `log_import()` before commit,
registration in `import_all.py`) currently only exists as prose in
CLAUDE.md ("Adding a new importer") and is conveyed informally via the
`plan-importer` skill. A spec makes the requirements for a conformant
importer explicit and checkable — complementing `review-importer`,
which reviews contributions against exactly this pattern.

## What Changes

- New spec `importer-pattern` documenting the structural and behavioral
  requirements for `scripts/importers/import_<source>.py` files.
- No code change; purely documenting existing behavior.

## Capabilities

### New Capabilities
- `importer-pattern`: required signature `run(conn, data_path,
  lang='de', person=None) -> ImportResult`, `INSERT OR IGNORE`
  requirement (see the already-existing `db-schema-conventions` spec),
  use of `resolve_person()`/`resolve_timezone()`, `log_import()` before
  `conn.commit()`, registration in the `IMPORTERS` list in
  `scripts/import_all.py`.

### Modified Capabilities
(none — purely new documentation of existing behavior; overlaps
partially with `db-schema-conventions`, but does not repeat its
requirements, instead references them)

## Impact

- Affects no code files directly.
- References: `scripts/import_all.py` (`IMPORTERS` list),
  `scripts/modules/base.py` (`ImportResult`, `resolve_person()`,
  `resolve_timezone()`, `log_import()`).
- Direct benefit for contributors who get an implementation plan via the
  `plan-importer` skill and whose result gets checked via the
  `review-importer` skill — this spec is the third, written reference
  point shared between both skills.
