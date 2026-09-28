## ADDED Requirements

### Requirement: Uniform importer signature
Every importer SHALL provide a function
`run(conn, data_path, lang='de', person=None) -> ImportResult` under
`scripts/importers/import_<source>.py`, where `ImportResult` comes from
`scripts/modules/base.py`.

#### Scenario: A new importer is written
- **WHEN** a contributor implements an importer for a new data source
- **THEN** the file exposes a `run(conn, data_path, lang='de',
  person=None)` function that returns an `ImportResult` object
  (`source`, `rows_inserted`, `rows_skipped`, `errors`)

### Requirement: Person and timezone resolution via shared helpers
Importers SHALL use `resolve_person()` and `resolve_timezone()` from
`scripts/modules/base.py` instead of implementing person or timezone
logic themselves (see also the requirements "Person identifiers
exclusively via `OWN_PERSON_ID`" and "No hardcoded timezones" in the
`privacy-rules` spec).

#### Scenario: Importer without an explicit person parameter
- **WHEN** an importer is called without a `person` argument
- **THEN** `resolve_person(person_arg=None)` internally resolves to
  `OWN_PERSON_ID` from `health_config`

### Requirement: Idempotent writes
Importers SHALL use `INSERT OR IGNORE` for all inserts, so that a
repeated run over the same file does not change existing rows (see the
requirement "`INSERT OR IGNORE` instead of `INSERT OR REPLACE`" in
`db-schema-conventions`).

#### Scenario: Importer runs twice over the same file
- **WHEN** a contributor runs the same importer twice with the same
  `data_path`
- **THEN** the row count in the target tables is unchanged after the
  second run (`rows_skipped` increases, `rows_inserted` stays 0 for
  already-existing rows)

### Requirement: Atomic import logging before commit
Every importer SHALL call `log_import()` within the same transaction as
the imported data, before `conn.commit()` runs, so that the log entry is
atomic with the data and holds up forensically.

#### Scenario: Importer writes data and ends the transaction
- **WHEN** an importer completes its import successfully
- **THEN** `log_import(conn, source, data_path, rows_inserted,
  rows_skipped)` is called before `conn.commit()`, so that on a rollback
  neither the data nor the log entry persist

### Requirement: Registration in `import_all.py`
A new importer SHALL be registered in the `IMPORTERS` list in
`scripts/import_all.py`, so it runs as part of
`python3 scripts/import_all.py --update`.

#### Scenario: A new importer is not registered
- **WHEN** an importer script exists but is not entered in the
  `IMPORTERS` list
- **THEN** it is not run by `import_all.py --update`, even if matching
  raw data is present in `imports/`

#### Scenario: A registered importer is missing as a file
- **WHEN** an entry in `IMPORTERS` points to a script that doesn't exist
- **THEN** `import_all.py` skips that entry with a log message instead
  of aborting
