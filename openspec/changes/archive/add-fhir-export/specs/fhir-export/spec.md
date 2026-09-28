## ADDED Requirements

### Requirement: FHIR export as an additional output format
`scripts/export_health.py` SHALL support `--format fhir` for any existing
export profile, producing a FHIR R4 `Bundle` JSON document, without
changing the behavior of the existing `csv`/`json` formats.

#### Scenario: Existing profile exported as FHIR
- **WHEN** an operator runs `export_health.py --profile cardiology
  --format fhir`
- **THEN** the tool writes a FHIR R4 `Bundle` JSON document built from
  the same underlying query results the `csv`/`json` formats would use
  for that profile, and the `csv`/`json` formats remain unchanged and
  independently selectable

### Requirement: No fabricated terminology codes
The FHIR export SHALL only include an `Observation` (or other coded
resource) for a metric if that metric has a human-verified LOINC or
SNOMED CT code entry in the mapping table. It SHALL NOT invent,
approximate, or guess a code for an unmapped metric.

#### Scenario: Metric with a verified mapping
- **WHEN** a queried row's `metric` value has a corresponding entry in
  `scripts/exporters/fhir_metric_codes.json`
- **THEN** the generated `Observation.code` uses exactly that entry's
  `system`/`code`/`display`

#### Scenario: Metric with no mapping
- **WHEN** a queried row's `metric` value has no entry in the mapping
  table
- **THEN** no `Observation` resource is generated for that row, and the
  metric name plus a count of skipped rows appears in
  `fhir_export_unmapped_metrics.txt` alongside the bundle

### Requirement: Pseudonymous patient reference only
Every resource in the generated bundle that references a subject SHALL
reference a `Patient` resource identified by the project's existing
pseudonym scheme. The bundle SHALL NOT contain a real name, address, or
other direct identifier.

#### Scenario: Bundle inspected for identifiers
- **WHEN** a generated FHIR bundle is inspected
- **THEN** the single included `Patient` resource's `id`/`identifier` is
  a pseudonym (not a real name), and no other resource in the bundle
  contains a real name, address, or other direct identifier field

### Requirement: Offline schema validation before writing output
The export SHALL validate the generated bundle against a locally
vendored FHIR R4 JSON Schema before writing it to disk, and SHALL abort
with a clear error (not write a partially-invalid file) if validation
fails.

#### Scenario: Valid bundle
- **WHEN** the generated bundle passes local schema validation
- **THEN** the bundle file is written to the export output directory

#### Scenario: Invalid bundle
- **WHEN** the generated bundle fails local schema validation (e.g. a
  required field missing due to a bug)
- **THEN** the tool exits with a non-zero status and a description of
  the validation failure, and does not write the invalid file

### Requirement: Export-only, no network transmission
The FHIR export SHALL perform no network calls (no live validation
service, no FHIR server submission) as part of its default execution
path.

#### Scenario: Export run while offline
- **WHEN** an operator runs the FHIR export with no network connectivity
  available
- **THEN** the export completes successfully with identical output to a
  run performed with network connectivity available
