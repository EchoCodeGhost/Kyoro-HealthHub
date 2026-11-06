## ADDED Requirements

### Requirement: Sanitising covers medicine.db free text
Post-import sanitising SHALL scan the allowlisted free-text columns of `medicine.db` on every run, including runs from `import_all.py`, `import_staged.py` and `import_all.py --sanitize-only`. A missing `medicine.db` SHALL be skipped without an error.

#### Scenario: Personal detail in a comment
- **WHEN** a `lab_manual.kommentar` value contains an e-mail address
- **THEN** the address is replaced and the rest of the comment stays unchanged

#### Scenario: No medicine database
- **WHEN** `medicine.db` does not exist
- **THEN** the step is skipped and the run does not count as failed

### Requirement: Clinical data is never rewritten
Sanitising SHALL rewrite only allowlisted columns. Every `TEXT` column in the medicine schema SHALL be either allowlisted or explicitly excluded, and a test SHALL enforce this.

#### Scenario: Lab parameter resembling a name
- **WHEN** `lab_manual.parameter` contains two capitalised words
- **THEN** the value is not changed and is not reported

#### Scenario: New text column
- **WHEN** a `TEXT` column is added to the medicine schema without a classification
- **THEN** the test suite fails and names the column

### Requirement: Heuristic matches are reported and never rewritten
Only high-confidence matches SHALL be rewritten: e-mail addresses, clearly formatted phone numbers, postal addresses, and names known from local config. Heuristic matches SHALL be written to a local review report and SHALL NOT change the data.

#### Scenario: Clinical term in free text
- **WHEN** an allowlisted column contains a disease name made of two capitalised words
- **THEN** the text stays unchanged and the match appears in the review report

#### Scenario: Known name in free text
- **WHEN** an allowlisted column contains a name from local config
- **THEN** the name is replaced

### Requirement: Rewrites are recoverable
Before the first rewrite of a run, `medicine.db` SHALL be backed up with its encryption preserved. If the backup fails, nothing SHALL be rewritten and the step SHALL count as failed. A report-only mode SHALL show what would change without writing anything.

#### Scenario: Backup fails
- **WHEN** the backup cannot be created
- **THEN** no row changes, and `post_import_sanitize.run()` reports the step as failed

#### Scenario: No rewrite needed
- **WHEN** a run finds no high-confidence match
- **THEN** no backup is created

#### Scenario: Report-only run
- **WHEN** sanitising runs in report-only mode
- **THEN** no row changes and no backup is created, and the would-be changes are listed

### Requirement: Reporting does not leak matched text
`import_log` entries and terminal output SHALL contain only table, column and counts. Matched text SHALL appear only in the local review report, which SHALL NOT be stored in a tracked repo path.

#### Scenario: Rewrite is logged
- **WHEN** a run rewrites values
- **THEN** `import_log` records table, column and count, and no matched text

### Requirement: Audit log stays untouched
Sanitising SHALL NOT rewrite `audit_log`. The compliance check SHALL report how many `audit_log` rows match the high-confidence patterns.

#### Scenario: Rewrite creates an audit entry
- **WHEN** an allowlisted value is rewritten and the audit trigger stores the old value
- **THEN** the `audit_log` row is kept, and the compliance check counts it

### Requirement: Compliance check covers medicine.db
The post-import compliance check SHALL also report on `medicine.db`, using checks valid for its schema. A check that does not apply to a schema SHALL NOT be reported as a violation.

#### Scenario: Remaining cleartext
- **WHEN** an allowlisted column still contains a high-confidence match after a failed rewrite
- **THEN** the compliance check reports it for `medicine.db`

#### Scenario: Table absent in medicine.db
- **WHEN** a compliance check refers to a table that exists only in `health.db`
- **THEN** no error or violation is reported for `medicine.db`
