# research-cohort-export Specification

## Purpose
Defines the multi-patient research export pipeline that assembles a
de-identified, consent-gated cohort dataset across the isolated
per-patient instances created by `privacy-by-design-access-control`,
closing the last structural gap before "research" can honestly be called
a supported deployment context.
## Requirements
### Requirement: Consent-gated instance inclusion
The cohort exporter SHALL refuse to include any patient instance in a
cohort export unless an active (non-revoked) `research_consent` row
exists for that patient's pseudonym and the requested consent scope.

#### Scenario: Patient without consent record
- **WHEN** an operator runs `export_research_cohort.py` for a scope that
  a given active patient instance has no `research_consent` row for
- **THEN** the tool aborts before writing any output file and prints the
  list of patient pseudonyms missing consent for that scope

#### Scenario: Revoked consent
- **WHEN** a `research_consent` row exists for a patient/scope but its
  `revoked_at` is set
- **THEN** that instance is treated identically to having no consent row
  (excluded, listed in the abort/skip report)

#### Scenario: All active instances consented
- **WHEN** every active patient instance in `master.db` has a matching,
  non-revoked `research_consent` row for the requested scope
- **THEN** the export proceeds and includes all of them

### Requirement: Per-patient deterministic date shifting
All calendar dates and timestamps in the merged cohort dataset SHALL be
shifted by an offset that is deterministic per `patient_pseudo` (same
patient → same offset across repeated runs) and not derivable from the
output alone.

#### Scenario: Same patient exported twice
- **WHEN** the same patient instance is included in two separate cohort
  export runs (e.g. after a bug fix)
- **THEN** all of that patient's dates in both output datasets are
  shifted by the identical offset, so relative time deltas for that
  patient are unchanged between the two runs

#### Scenario: Different patients get different offsets
- **WHEN** a cohort export includes two or more patient instances
- **THEN** each patient's date-shift offset is independent of the others'
  (not a single cohort-wide shift), so cross-patient date alignment
  cannot be reconstructed from the shifted dates

### Requirement: Age banding instead of birthdate
The merged cohort dataset SHALL NOT contain exact birthdates. Age SHALL
be represented as a configurable-width band (default: 5 years).

#### Scenario: Default banding
- **WHEN** a cohort export runs without an explicit age-band-width
  argument
- **THEN** each patient's age in the output is represented as a 5-year
  band (e.g. "30-34") and no birthdate field is present in any output file

### Requirement: k-anonymity enforcement over stated quasi-identifiers
The exporter SHALL accept an explicit, operator-specified list of
quasi-identifier columns and SHALL suppress or further generalize any
group of rows sharing a quasi-identifier combination that appears fewer
than `k` times (default `k=5`) in the merged dataset, rather than
including it as-is.

#### Scenario: Group below threshold
- **WHEN** a combination of quasi-identifier values (e.g. a specific age
  band + gender pairing) occurs in fewer than `k` rows across the whole
  cohort
- **THEN** those rows are excluded from the delivered dataset and written
  instead to a locally-retained, clearly-labeled suppressed-rows file that
  is not part of the deliverable

#### Scenario: Cohort too small overall
- **WHEN** the pre-suppression group-size histogram shows that most or
  all groups fall below `k`
- **THEN** the tool prints this histogram before writing any output, so
  the operator can recognize an unusably small cohort before relying on
  a near-empty result

### Requirement: Local-only output
The cohort export SHALL write only to a local directory under
`KYORO_MASTER_DIR/research_exports/<date>/` and SHALL perform no network
transmission of any kind.

#### Scenario: Export completes
- **WHEN** a cohort export run finishes successfully
- **THEN** all output files (deliverable dataset, run manifest,
  suppressed-rows file) exist only under
  `KYORO_MASTER_DIR/research_exports/<date>/` and no HTTP/network call was
  made during the run

### Requirement: Run manifest records de-identification methodology
Every cohort export run SHALL write a manifest recording the parameters
used: age-band width, k threshold, quasi-identifier columns, number of
instances included, number of instances excluded for missing/revoked
consent, and number of rows suppressed for k-anonymity — but SHALL NOT
record the per-patient date-shift offsets themselves (that would defeat
their purpose).

#### Scenario: Manifest written alongside deliverable
- **WHEN** a cohort export completes
- **THEN** a manifest file in the same run directory lists all of the
  above parameters and counts, and contains no patient pseudonym-to-offset
  mapping and no real calendar dates

