# documentation-conventions Specification

## Purpose
Defines how scripts and their outputs are documented so that findings
and data collection remain traceable for a specialist, an expert
witness, or a court: what confidence level a
communicated finding has (confirmed/suspected/open lead, via
`scripts/modules/confidence.py`) and why a collected or computed data
type is relevant at all (`@relevance.de/en` in the module docstring, a
required field for every script with `@tier`).
## Requirements
### Requirement: Finding-confidence labeling via a shared module
Every analysis output (report text, plot title, LLM prompt context) that
communicates a concrete association or finding SHALL assign it one of
three confidence levels — **confirmed**, **suspected**, **open lead** —
via the shared helper `scripts/modules/confidence.py`. Scripts SHOULD
NOT introduce their own local ad-hoc vocabulary for the same purpose.

#### Scenario: New analysis script reports an uncertain association
- **WHEN** a script outputs a finding whose evidence is not clearly
  established
- **THEN** it uses `label_finding(...)` from
  `scripts/modules/confidence.py` with `level="suspected"` or
  `level="lead"`, instead of inventing its own wording

#### Scenario: Existing script with its own ad-hoc vocabulary is changed
- **WHEN** `analyse_postinfectious_diagnose.py` (or another script with
  local confidence vocabulary) is changed substantively
- **THEN** the local vocabulary is replaced with
  `scripts/modules/confidence.py`, provided the change touches the
  affected code section

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

### Requirement: Required docstring field `@relevance.de`/`@relevance.en`
The module docstring of **every** Python script with a `@tier` field
(including `heuristic` — no tier is exempt) SHALL contain a
`@relevance.de`/`@relevance.en` field in addition to
`@purpose.de`/`@purpose.en`, explaining why the collected or computed
data type is clinically or scientifically relevant — not just what is
computed.

#### Scenario: New script without `@relevance`
- **WHEN** `python3 scripts/check_docstrings.py` runs against a new or
  changed script with `@tier` whose docstring is missing
  `@relevance.de`/`@relevance.en`
- **THEN** the script reports the missing required field and exits with
  a non-zero exit code

#### Scenario: Fully migrated repo
- **WHEN** `python3 scripts/check_docstrings.py` runs against the entire
  `scripts/` directory
- **THEN** every script with `@tier` has a `@relevance.de`/
  `@relevance.en` field, without exception — the migration of all
  existing scripts is complete (`add-confidence-and-
  relevance-conventions`, archived), there is no grandfathering for
  unchanged legacy scripts anymore

### Requirement: Bilingual text (German before English) in user- and contributor-facing content
All user- and contributor-facing text SHALL be bilingual (German first,
then English). In Python code this SHALL be implemented via the
`t("DE", "EN")` helper from `scripts/modules/i18n.py`, with runtime
language selection via `KYORO_LANG`/`--lang`. In non-Python files without
runtime language switching (e.g. systemd units, Caddyfiles, other infra
configs), both languages SHALL appear as consecutive comment lines in the
same content block (German first, then English). Freely-named Markdown
documentation MAY instead exist as two separate files (`<NAME>.md`
English, `<NAME>_DE.md` German) when the filename is not dictated by an
external tool.

#### Scenario: New docstring in a Python script
- **WHEN** a contributor adds a new script with `@purpose`/`@method`/
  `@limits` fields
- **THEN** each of these fields exists in both a `.de` and an `.en`
  variant

#### Scenario: New systemd unit or config file with a fixed filename
- **WHEN** a contributor adds a new deployment file whose filename is
  dictated by the target system (e.g. `symptom-pwa.service`)
- **THEN** German and English comment lines appear paired side by side
  in the same comment block, not as two separate files

#### Scenario: New freely-named Markdown documentation
- **WHEN** a contributor adds a new Markdown documentation file without
  an externally dictated filename (e.g. a deployment guide)
- **THEN** either an inline-bilingual format or the two-file pattern
  (`<NAME>.md` + `<NAME>_DE.md`) SHALL be used, consistent with existing
  examples in the same directory

### Requirement: Structured docstring field schema as the single source of truth
The module docstring of every Python script under `scripts/` with a
`@tier` field SHALL contain the required fields defined in
`docs/docstring_template.md`: `@tier`, `@purpose.de`/`@purpose.en`,
`@method.de`/`@method.en`, `@limits.de`/`@limits.en`, `@reads`,
`@writes`, `@usage`. Optional fields (`@thresholds`, `@scoring`,
`@refs`) SHALL be used when the script contains clinical thresholds, a
scoring formula, or citable references. The docstring SHALL be the sole
source for the generated files under `docs/de/`/`docs/en/` — generated
by `tools/gen_docs.py`, validated by `scripts/check_docstrings.py`.

#### Scenario: New script with a @tier field missing required fields
- **WHEN** `python3 scripts/check_docstrings.py` runs against a script
  whose docstring has a `@tier` field but not all required fields
- **THEN** the script reports the missing required fields and exits with
  a non-zero exit code

#### Scenario: Docstring change without documentation regeneration
- **WHEN** a contributor changes a `@method.de`/`@method.en` field in a
  script without re-running `python3 tools/gen_docs.py`
- **THEN** `tools/gen_docs.py --check` reports a mismatch between the
  committed generated documentation and the current docstring content

#### Scenario: Script is moved or deleted
- **WHEN** a script with existing generated documentation under
  `docs/de/`/`docs/en/` is moved or deleted
- **THEN** `tools/gen_docs.py` reports the corresponding generated
  documentation file as orphaned, until it is manually removed or
  regenerated at the new path
