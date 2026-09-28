## Context

`scripts/export_health.py` already parametrizes export by profile
(`scripts/exporters/profiles/*.json`, one JSON per specialty, `queries`
dict of named SQL `SELECT`s using `:person`/`:date_from`/`:date_to`) and
by format (`csv`/`json` today). Internal metric names live in the
`metric` column of EAV tables (`measurements`, `session_metrics`) — e.g.
`heart_rate`, `hrv_rmssd`, `hrv_sdnn`, `oxygen_saturation`,
`breathing_disturbance_index`, `avg_stress`, `total_sleep_min`, `steps`,
`cycle_day`, `duration_min`, `sleep_analysis`. These names are Kyoro-
internal and not clinically standardized; FHIR `Observation.code` needs
a real coding system (LOINC is the norm for lab/vital-sign observations).

## Goals / Non-Goals

**Goals:**
- Produce a valid, FHIR-R4-schema-conformant `Bundle` from existing
  profile export data, reusing the query layer as-is.
- Be honest about mapping coverage: every metric either has a real
  LOINC/SNOMED code behind it, or is excluded and reported as unmapped —
  never a guessed or placeholder code.
- Keep the mapping table as a reviewable, versionable artifact (not
  buried in code) so future contributors can extend coverage by adding
  rows, not by editing logic.

**Non-Goals:**
- No FHIR server, no `$validate` operation call to an external service
  by default (see Decisions for the offline-validation approach), no
  receiving/importing FHIR data into Kyoro.
- No HL7 v2 (ORU/ADT) support in this change — only build it later if a
  specific target system (e.g. a hospital's actual interface engine)
  requires it; FHIR is the default target for anything new.
- No attempt to map every one of Kyoro's ~dozens of internal metrics in
  v1 — ship with a first tranche of the clinically highest-value,
  best-standardized metrics (heart rate, HRV RMSSD/SDNN, SpO2, sleep
  duration) and leave the rest unmapped-and-reported rather than blocking
  the whole change on 100% coverage.

## Decisions

**D1 — Mapping table lives in a plain data file
(`scripts/exporters/fhir_metric_codes.json`), not hardcoded in Python.**
Format:
```json
{
  "heart_rate": {"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"},
  "hrv_rmssd": {"system": "http://loinc.org", "code": "80404-7", "display": "R-R interval RMSSD"},
  "oxygen_saturation": {"system": "http://loinc.org", "code": "59408-5", "display": "Oxygen saturation in Arterial blood by Pulse oximetry"},
  "total_sleep_min": {"system": "http://loinc.org", "code": "93832-4", "display": "Sleep duration"}
}
```
Alternative considered: a Python dict alongside the resource builder —
rejected because a plain JSON file is easier for a non-Python contributor
(e.g. a clinician helping verify codes) to review and extend, and keeps
the "is this code actually correct" question separate from "is the
Python code correct."

**D2 — Every LOINC/SNOMED code in the mapping table MUST be verified
against a real terminology source before being committed, not guessed
from memory by whichever model writes the table.** Concretely: look each
candidate code up on loinc.org (or the cached LOINC table if the project
already has one, e.g. via UMLS) and record the source. This is the one
place in this change where an AI implementer (Mistral) MUST NOT
fabricate a plausible-looking code — a wrong LOINC code silently
corrupts every downstream system that trusts it. If a code cannot be
verified, leave that metric unmapped for this iteration rather than
guessing.

**D3 — Validate structurally offline, not against a network FHIR
server by default.** Use a local FHIR R4 JSON Schema (vendored once,
`scripts/exporters/fhir_r4.schema.json`, from the public HL7 FHIR
distribution) and `jsonschema` (already-or-newly a dependency) to
validate the generated `Bundle` before writing it. A live validator
call (e.g. `https://hl7.org` or a public validation service) is not
part of the default path — this project's data never leaves the
machine unasked (see NOTICE), and schema validation should not be the
first exception to that. Document in `docs/FHIR_EXPORT.md` how a user
who *wants* an external validator run can do so manually.

**D4 — `Observation.subject` references a pseudonymous `Patient`
resource identifier, never a real name.** The bundle includes exactly
one minimal `Patient` resource (`id` = the existing pseudonym scheme
already used elsewhere in the project — reuse whatever `OWN_PERSON_ID`/
`patient_pseudo` convention is already established, do not invent a new
identifier scheme for FHIR specifically).

**D5 — Unmapped-metric reporting is a separate plain-text file, not
silent exclusion.** `fhir_export_unmapped_metrics.txt` lists every
distinct `metric` value found in the queried rows that had no entry in
`fhir_metric_codes.json`, with a count of how many rows were skipped —
so a user who expects a metric in their FHIR bundle and doesn't find it
has an immediate answer why.

## Risks / Trade-offs

- **[Risk]** LOINC code selection is genuinely hard to get right without
  clinical/informatics domain review (e.g. RMSSD has several plausible
  candidate codes depending on measurement context/window length).
  → **Mitigation:** ship the mapping table with a `"verified_by"` and
  `"verified_date"` field per entry (human, not AI-only, sign-off
  before merge) — this is a place to slow down deliberately.
- **[Risk]** FHIR R4 schema is large; vendoring the full JSON Schema
  adds a sizeable file to the repo.
  → **Mitigation:** vendor only the resource-type schemas actually used
  (Bundle, Observation, Condition, MedicationStatement, Patient), not
  the entire FHIR spec.
- **[Trade-off]** Read-only/export-only scope means this does not yet
  give a clinic a live FHIR endpoint to query — it's a batch export, not
  integration middleware. Explicitly acceptable for v1; document as a
  known limitation, not a hidden gap.

## Migration Plan

Purely additive — a new `--format fhir` branch in an existing script, a
new mapping data file, new resource-builder modules. No existing output
format or profile changes. Rollback = remove the new files and the new
branch in `export_health.py`.

## Open Questions

- Which specific metrics beyond heart_rate/hrv_rmssd/hrv_sdnn/
  oxygen_saturation/total_sleep_min make the first tranche? Resolved in
  tasks.md as a concrete starter list, extensible later.
- MedicationStatement scope depends on whether medication data already
  has a clean internal source table — to be confirmed at the start of
  implementation (task 1 in tasks.md) rather than assumed here.
