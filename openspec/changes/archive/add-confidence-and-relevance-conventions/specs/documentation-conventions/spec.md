## ADDED Requirements

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

#### Scenario: Transitional phase during the full migration
- **WHEN** the migration of all existing scripts (see the associated
  `tasks.md`) is not yet complete
- **THEN** the requirement initially only applies to new/changed
  docstrings; once all migration batches are checked off, enforcement
  switches to repo-wide without exception — there is no permanent
  grandfathering for unchanged legacy scripts

#### Scenario: Fully migrated repo
- **WHEN** `python3 scripts/check_docstrings.py` runs against the entire
  `scripts/` directory after all migration batches are complete
- **THEN** every script with `@tier` has a `@relevance.de`/
  `@relevance.en` field, without exception
