## ADDED Requirements

### Requirement: Importer-pattern conformance
The Sun-a-ware importer SHALL follow the pattern documented in
`openspec/specs/importer-pattern/spec.md`: `run(conn, data_path,
lang='de', person=None) -> ImportResult`, `INSERT OR IGNORE`,
`resolve_person()`/`resolve_timezone()`, atomic `log_import()` before
commit, registration in `IMPORTERS`.

#### Scenario: Importer is implemented
- **WHEN** the importer is implemented after the export format has been
  clarified
- **THEN** it fulfills all requirements from `importer-pattern/spec.md`,
  without exception

### Requirement: Blocked without a sample file
The importer SHALL NOT be implemented as long as no real sample export
file from the Sun-a-ware device is available.

#### Scenario: Attempted implementation without a sample file
- **WHEN** a contributor attempts to write the parser without first
  reviewing a real export file
- **THEN** the work MUST be stopped until a sample file has been
  obtained — speculative format assumptions are not permitted
