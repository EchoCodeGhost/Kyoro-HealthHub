## ADDED Requirements

### Requirement: EAV pattern for time-series data
All time-series tables (e.g. `measurements`, `session_metrics`) SHALL
follow the EAV pattern (`ts`, `metric`, `value`) instead of a column per
device or metric type. New device sources SHALL NOT require a schema
change.

#### Scenario: New device delivers a new metric
- **WHEN** a new importer imports a previously unknown metric (e.g. a new
  sensor reading)
- **THEN** the metric is inserted as an additional row in `measurements`
  (or `session_metrics`) with the matching `metric` name, without
  creating a new column or table

#### Scenario: Contributor plans a new column per metric
- **WHEN** a contributor considers adding a dedicated column for a new
  metric to an existing time-series table
- **THEN** the existing EAV pattern MUST be used instead

### Requirement: Uniform `person` column
Every health table SHALL have a `person` column (default `'self'`).
Code SHALL never use the string literal `'self'`, but always
`OWN_PERSON_ID` from `scripts/health_config.py`.

#### Scenario: New importer writes data
- **WHEN** a new importer inserts rows into a health table
- **THEN** it uses `resolve_person()` from `utils/base.py` or
  `OWN_PERSON_ID`, never the string `'self'` directly in code

#### Scenario: Code review finds a string literal
- **WHEN** a code review or privacy check finds the string `'self'` used
  as a person identifier in source code
- **THEN** this counts as a convention violation that MUST be fixed
  before merge

### Requirement: Compatibility views as a migration bridge
After schema migrations (e.g. v1→v2), old query patterns SHALL continue
to work via compatibility views (defined in
`scripts/utils/create_schema.py`, e.g. `sleep_sessions`,
`polar_trainings`), instead of requiring existing analysis/query code to
be updated immediately.

#### Scenario: Old analysis script after migration
- **WHEN** an analysis script written before a schema migration runs
  against the migrated DB
- **THEN** the corresponding compatibility view returns the same result
  shape as before the migration

### Requirement: `INSERT OR IGNORE` instead of `INSERT OR REPLACE`
All importers SHALL use `INSERT OR IGNORE` for writes. `INSERT OR
REPLACE` SHALL NOT be used, since it would reset audit trails (e.g. the
`import_log` history).

#### Scenario: Importer runs again over an already-imported file
- **WHEN** an importer runs a second time over the same raw file
- **THEN** already-present rows are skipped unchanged (`INSERT OR
  IGNORE`); no existing rows are overwritten

#### Scenario: Contributor uses INSERT OR REPLACE
- **WHEN** a new importer uses `INSERT OR REPLACE` instead of `INSERT OR
  IGNORE`
- **THEN** this counts as a convention violation in review, since it
  would silently replace existing audit-trail rows and thereby destroy
  history

### Requirement: `ts` vs. `date` semantics
`ts` columns SHALL always be UTC ISO 8601. `date` columns SHALL represent
the local calendar day, resolved via `resolve_timezone(conn, person)` or
`cfg.home_timezone` as a fallback — never a hardcoded IANA timezone.

#### Scenario: Importer writes a timestamp
- **WHEN** an importer writes a row with a timestamp
- **THEN** `ts` is stored as a UTC ISO-8601 string and `date` is derived
  via `resolve_timezone()` into the local calendar day, not via a
  timezone hardcoded in code (e.g. `"Europe/Berlin"` as a string literal
  in source code)
