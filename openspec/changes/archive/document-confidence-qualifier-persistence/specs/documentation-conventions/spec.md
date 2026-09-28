## ADDED Requirements

### Requirement: Confidence qualifiers persist through narrative restatement
When a hand-authored narrative synthesis document (e.g. a case-synthesis
document under `intern/`) restates a
finding that originates from a confidence-labeled source — a
`scripts/modules/confidence.py`-labeled script output, or a hedged DB
column/table such as a `<finding>_possible`/`<finding>_suspected` pair — the restatement
SHALL preserve the same confidence qualifier (confirmed/suspected/open
lead, or the source's equivalent hedge). A restatement SHALL NOT silently
upgrade a suspected/possible finding to unqualified fact while
summarizing, copying, or cross-referencing it into a new section.

#### Scenario: A wearable-detected finding is referenced in a new section
- **WHEN** a contributor adds or edits a section in a narrative synthesis
  document that references a finding sourced from a hedged DB column
  (e.g. a `<finding>_possible` column) or a `confidence.py`-labeled script output
- **THEN** the section states the finding with the same qualifier as its
  source (e.g. "wearable-detected, not clinically confirmed"), not as an
  unqualified fact

#### Scenario: A finding is corrected in one section but not others
- **WHEN** a confidence-relevant correction is applied to one section of a
  narrative synthesis document (e.g. a family-history subsection)
- **THEN** the contributor SHALL check (e.g. via `grep`) whether the same
  finding is restated with the dropped qualifier elsewhere in the same
  document, and MUST also correct those occurrences before considering
  the correction complete

#### Scenario: An independently confirmed clinical fact is restated
- **WHEN** a narrative synthesis document restates a finding that is
  independently established (a lab-confirmed diagnosis, a documented
  specialist finding), not sourced from a confidence-labeled script output
  or a hedged DB column
- **THEN** this requirement does not apply — it targets qualifier loss for
  findings whose confidence level is defined by an upstream source, not
  every clinical statement in the document
