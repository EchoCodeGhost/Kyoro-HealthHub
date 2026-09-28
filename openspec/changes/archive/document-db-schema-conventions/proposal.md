## Why

Kyoro-HealthHub's DB schema follows deliberate but unwritten conventions
(EAV for time series, a generic `person` column, strict `INSERT OR
IGNORE`, UTC `ts` vs. local `date`). These conventions currently only
live in CLAUDE.md and in the code itself. Before the GitHub release,
this should be recorded as a spec, so external contributors don't
accidentally violate it with new importers/compute scripts (e.g. a
column per device instead of EAV, or `INSERT OR REPLACE` instead of
`INSERT OR IGNORE`, which would destroy audit trails).

## What Changes

- New spec `db-schema-conventions` documenting the existing schema
  rules as requirements/scenarios.
- No code change; purely documenting existing behavior.

## Capabilities

### New Capabilities
- `db-schema-conventions`: EAV pattern for time series, `person` column
  convention (`OWN_PERSON_ID`, never the string literal `'self'`),
  compatibility views, `INSERT OR IGNORE` requirement, `ts`/`date`
  semantics (UTC ISO 8601 vs. local calendar day via
  `resolve_timezone()`).

### Modified Capabilities
(none — purely new documentation of existing behavior)

## Impact

- Affects no code files directly.
- References: `scripts/utils/create_schema.py`, `scripts/utils/base.py`
  (`resolve_person()`, `resolve_timezone()`), `scripts/health_config.py`
  (`OWN_PERSON_ID`).
- Serves future contributors as an onboarding reference alongside
  CLAUDE.md, especially when writing new importers/compute scripts.
