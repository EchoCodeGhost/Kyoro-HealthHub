## Why

Kyoro-HealthHub can already produce curated CSV/JSON exports per doctor
specialty via `scripts/export_health.py` and its export profiles, and (once
`research-cohort-anonymization-pipeline` lands) an anonymized multi-patient
research dataset. None of this speaks a standard clinical data format:
every recipient (a hospital KIS, a research data platform, a REDCap
instance) has to write custom CSV-column-mapping code to ingest Kyoro's
output. FHIR R4 is the current interoperability standard both for clinical
systems (most German/EU hospital information systems now expose or accept
FHIR) and for research data platforms. Adding a FHIR export target turns
every existing export profile into something a receiving system can
ingest with its own standard FHIR importer, instead of a bespoke parser
per recipient.

## What Changes

- New export format `--format fhir` for `scripts/export_health.py`,
  alongside the existing `csv`/`json` formats — reuses the existing
  profile/query machinery unchanged.
- New mapping module `scripts/exporters/fhir_mapping.py`: maps Kyoro's
  internal metric names (the `metric` column values used across
  `measurements`, `session_metrics`, etc. — e.g. `heart_rate`,
  `hrv_rmssd`, `oxygen_saturation`) to standard codes (LOINC preferred,
  SNOMED CT where no LOINC code fits) needed to build valid FHIR
  `Observation` resources.
- New resource builders (`scripts/exporters/fhir_resources.py`):
  `Observation` (numeric time-series metrics), `Condition` (from
  `clinical.events` diagnosis-type entries), `MedicationStatement` (from
  the medication tracking already in the system, if present — confirm
  scope during implementation).
- Output is a FHIR `Bundle` (type `collection`) JSON document per export
  run — written locally like any other export, no network transmission,
  no FHIR server, no receive/import capability. **Export only.**
- Any internal metric with no confident LOINC/SNOMED mapping is **left
  out of the FHIR bundle** (not exported with a fabricated or
  approximate code) and listed in a `fhir_export_unmapped_metrics.txt`
  report alongside the bundle, so the gap is visible rather than silently
  wrong.
- `docs/CLINIC_DEPLOYMENT.md`/`_DE.md` and/or a new `docs/FHIR_EXPORT.md`:
  document what FHIR resources are produced, what is intentionally not
  yet mapped, and validation instructions.

## Capabilities

### New Capabilities
- `fhir-export`: standards-based (HL7 FHIR R4) read-only export of
  existing profile data as a `Bundle` of coded `Observation`/`Condition`/
  `MedicationStatement` resources.

### Modified Capabilities
(none — this adds a new export format alongside existing ones; no
existing profile/query behavior changes)

## Impact

- New files: `scripts/exporters/fhir_mapping.py`,
  `scripts/exporters/fhir_resources.py`, mapping data file (see
  design.md for format decision).
- Modified: `scripts/export_health.py` (new `--format fhir` branch,
  additive — existing `csv`/`json` paths untouched).
- Explicitly out of scope (see design.md Non-Goals): HL7 v2 (ORU)
  messages, a FHIR server/API endpoint, FHIR import/ingestion into
  Kyoro, real-time subscriptions.
- No interaction with `add-privacy-by-design-access-control` or
  `research-cohort-anonymization-pipeline` beyond being usable as a
  fourth output format from the same underlying profile/query data —
  this change does not itself add or change consent/access logic.
