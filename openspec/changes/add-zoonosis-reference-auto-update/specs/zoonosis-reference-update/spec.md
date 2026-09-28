## ADDED Requirements

### Requirement: Human confirmation before any reference-data merge
The system SHALL NOT write a candidate animal-pathogen association into
`ANIMAL_SYNDROME_MAP` or a syndrome's `endemic_regions` list without
explicit human confirmation via the review-queue CLI.

#### Scenario: New candidate discovered
- **WHEN** the extraction pipeline finds a new candidate association
  from a ProMED item
- **THEN** it is written to the local review queue with status
  `pending` and is NOT merged into any reference-data file

#### Scenario: Candidate confirmed
- **WHEN** a human runs `confirm <n>` on a pending candidate
- **THEN** the candidate is merged into `ANIMAL_SYNDROME_MAP` and/or the
  matching syndrome's `endemic_regions`, carrying its source citation

### Requirement: No forced approximate syndrome matching
The system SHALL NOT map a candidate association to an existing syndrome
slug unless the extraction clearly supports that mapping.

#### Scenario: No matching syndrome slug exists
- **WHEN** an extracted case report describes a pathogen with no
  corresponding file in `scripts/analysis/syndromes/`
- **THEN** the candidate is surfaced as "needs a new syndrome file" and
  is excluded from the normal confirm/merge path

### Requirement: Source provenance carried through to merged data
Every merged candidate SHALL retain its source citation (URL/ID and
date) in the reference data it was merged into.

#### Scenario: Reviewing a merged entry later
- **WHEN** a maintainer inspects `ANIMAL_SYNDROME_MAP` or an
  `endemic_regions` entry that originated from this pipeline
- **THEN** the originating source citation is visible alongside the
  entry, distinguishing it from manually/originally curated entries

### Requirement: Reuse existing ProMED fetch logic
The extraction pipeline SHALL reuse the ProMED source-fetching already
implemented in `import_outbreak_data.py` rather than implementing a
parallel fetch mechanism.

#### Scenario: Fetching new items
- **WHEN** the pipeline checks for new ProMED items since the last run
- **THEN** it calls into the existing `import_outbreak_data.py` ProMED
  source code path instead of a separately implemented HTTP/RSS client
