## MODIFIED Requirements

### Requirement: Uniform importer signature
Every importer SHALL provide a function
`run(conn, data_path, lang='de', person=None) -> ImportResult` under
`scripts/importers/import_<source>.py`, where `ImportResult` comes from
`scripts/modules/base.py`.

(No wording change — this delta exists only to record that this change
brings the 23 importers inventoried in `design.md` into actual compliance
with a requirement that was already normative before this change. See
`proposal.md` for why no capability behavior changes.)

#### Scenario: A new importer is written
- **WHEN** a contributor implements an importer for a new data source
- **THEN** the file exposes a `run(conn, data_path, lang='de',
  person=None)` function that returns an `ImportResult` object
  (`source`, `rows_inserted`, `rows_skipped`, `errors`)
