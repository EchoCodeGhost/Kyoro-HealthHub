## ADDED Requirements

### Requirement: Bundled names come from verified public sources
Bundled first-name lists SHALL contain only names derived from public datasets whose licence has been verified and allows redistribution in this repository. Each source SHALL be documented with publisher, URL, licence and required attribution. A source with an unclear licence SHALL NOT be used.

#### Scenario: Unclear licence
- **WHEN** a candidate dataset's licence cannot be confirmed from its publisher
- **THEN** the dataset is not used, and any resulting coverage gap is documented

#### Scenario: Undocumented source
- **WHEN** the list files change without a matching source entry in `SOURCES.md`
- **THEN** the build script refuses to write the output

### Requirement: Lists are reproducible and contain no raw data
A build script SHALL generate the lists from downloaded source files, applying a frequency cut-off, a minimum length and the exclusion list. The same input SHALL give identical output. Raw data and frequency counts SHALL NOT be committed.

#### Scenario: Repeated build
- **WHEN** the build runs twice on the same input
- **THEN** the output files are byte-identical

#### Scenario: Output format
- **WHEN** the build finishes
- **THEN** each output file has one name per line, sorted, with no counts or other columns

### Requirement: No personal names in repo lists or code
Names of the owner and relatives SHALL be configured only in local config or `identity.db`. `scrub_pii.py` and `anonymize.py` SHALL NOT contain hardcoded first-name data.

#### Scenario: Code after the change
- **WHEN** `scrub_pii.py` and `anonymize.py` are inspected
- **THEN** neither contains a literal list of first names

#### Scenario: Known name still detected
- **WHEN** text contains a name from `privacy_check.patient_names`
- **THEN** the name is detected on its own, whether or not it is in a bundled list

### Requirement: Names that are also words are excluded
An exclusion list SHALL remove entries that are also German or English words or medical terms from the bundled lists. A listed first name SHALL be matched only when followed by a capitalised word. An excluded name SHALL still be matched with a title or field label.

#### Scenario: Clinical phrase
- **WHEN** synthetic text contains a clinical phrase whose first word is on the exclusion list
- **THEN** no name span is reported

#### Scenario: Excluded name with a title
- **WHEN** text contains an excluded name after "Frau"
- **THEN** a name span is reported

#### Scenario: Single common name
- **WHEN** a listed first name stands alone without a following capitalised word
- **THEN** list matching reports no span

#### Scenario: Exclusion ignored
- **WHEN** a bundled list contains an entry from the exclusion list
- **THEN** the test suite fails

### Requirement: Detection scales with list size
List matching SHALL use a per-word lookup and SHALL NOT compile first names into one regular expression. Existing merge behaviour for adjacent matches SHALL stay unchanged.

#### Scenario: Name of three words
- **WHEN** text contains a listed first name followed by two capitalised words
- **THEN** one merged span covers the whole name, as before this change

#### Scenario: Existing behaviour
- **WHEN** the existing tests for name redaction run
- **THEN** they pass without changes to their expectations, other than cases documenting newly detected names

### Requirement: Missing lists are a visible error
If a bundled list is missing or unreadable, the operation using it SHALL fail with a clear error. It SHALL NOT continue with reduced detection or built-in fallback data.

#### Scenario: List file removed
- **WHEN** `find_name_spans()` runs and a bundled list cannot be read
- **THEN** an error names the file, and no text is reported as clean

### Requirement: Database scan does not rewrite on a single common word
`find_pii_in_database()` SHALL NOT flag a value as personal data based only on a bundled first name standing alone.

#### Scenario: Common name as a note
- **WHEN** a scanned value contains only one word, which is on a bundled list
- **THEN** the value is not flagged or rewritten

### Requirement: Rollout is measured first
Before the new lists are enabled, a report-only comparison of old and new detection SHALL run on real local data and SHALL output counts only. Matched text SHALL stay on the local machine and SHALL NOT enter the repo.

#### Scenario: Comparison output
- **WHEN** the comparison runs
- **THEN** its terminal output has counts per source and column, and no matched text
