## 1. Scoping (do first, before writing any mapping code)

- [x] 1.1 (Claude) Grepped for `medication`/`Medikament` — a
  usable source exists (`manage_medications.py` / medicine.db tables).
  `build_medication_statement()` was implemented in `fhir_resources.py`
  (not skipped).
- [x] 1.2 (Mistral/Claude) The 5-metric starter tranche
  (`heart_rate`, `hrv_rmssd`, `hrv_sdnn`, `oxygen_saturation`,
  `total_sleep_min`) plus an explicit `_unmapped_for_now` list
  (`blood_pressure_systolic`, `blood_pressure_diastolic`, `body_weight`,
  `body_temperature`, `respiratory_rate`) in
  `scripts/exporters/fhir_metric_codes.json` reflects the metrics
  actually scoped for v1.

## 2. LOINC/SNOMED mapping table (human-verified, see design.md D2)

- [x] 2.1 `scripts/exporters/fhir_metric_codes.json` exists with the
  required per-entry fields. **Correction (Claude):**
  Mistral's original draft self-marked all 5 codes as
  `verified_by: "Mistral Vibe"` — an LLM claiming web verification it
  cannot perform. Independent re-check via WebSearch found 2 of the 5
  codes were confirmed correct (`heart_rate`/8867-4,
  `oxygen_saturation`/59408-5, display text corrected to the exact
  LOINC long common name), 2 were wrong and have been corrected
  (`hrv_sdnn`: 80314-6 → 80404-7; `total_sleep_min`: 80362-3 → 93832-4;
  the original codes could not be confirmed to exist at all), and 1
  (`hrv_rmssd`) could not be confirmed at all and has been moved to
  `_unmapped_for_now`/`_pending_verification` with an honest
  "UNVERIFIED — needs human check against loinc.org" status rather than
  a fabricated confirmation, per design.md D2. A human should still spot
  check the 4 remaining codes against loinc.org directly before treating
  this as production-final — WebSearch cross-checking is stronger than
  unverified LLM memory but is not the same as an authoritative lookup.
- [x] 2.2 `_unmapped_for_now` array present and covers all metrics from
  1.2 not given a mapping (including `hrv_rmssd` after the 2.1
  correction).

## 3. FHIR resource builders

- [x] 3.1 `scripts/exporters/fhir_resources.py`: `build_patient_resource`,
  `build_observation`, `build_condition`, `build_medication_statement`
  all implemented per spec (Claude/Mistral).
- [x] 3.2 `scripts/exporters/fhir_mapping.py`: `load_metric_code`,
  `track_unmapped`, unmapped-report writer implemented.

## 4. Wire into `export_health.py`

- [x] 4.1 `fhir` added to `--format` choices alongside `csv`/`json`.
- [x] 4.2 `write_fhir_output()` builds the Bundle from profile query
  results plus Patient/Condition resources.
- [x] 4.3 (Claude, deviation from original plan — recorded
  here deliberately) Rather than hand-vendoring FHIR R4 JSON Schema
  fragments from memory (itself a hallucination risk this project
  explicitly guards against), structural validation uses the
  `fhir.resources` package (`==7.1.0`, pinned in `requirements.txt` /
  `requirements-lock.txt`) — real HL7-derived Pydantic models, R4B
  variant (see provenance note in `scripts/exporters/fhir_validate.py`).
  `validate_bundle()` raises `ValueError` on structural violations and a
  clear `RuntimeError` if the dependency is missing; wired into
  `write_fhir_output()` before the bundle is written. Covers base
  resource shape only, not terminology/profile validation (documented in
  `fhir_validate.py`'s `@limits`).
- [x] 4.4 `fhir_export_unmapped_metrics.txt` written alongside the bundle
  when rows were skipped for lacking a mapping.

## 5. Tests

- [x] 5.1 `tests/test_fhir_export.py` — all tests passing
  (`build_observation` with/without mapping, bundle structure, unmapped
  report, and — added alongside 4.3 — bundle-schema-validation
  acceptance/rejection tests including a deliberately malformed bundle
  missing `resourceType`). Pseudonym-only check present via the bundle
  structure test fixtures (no real name/address fixtures used anywhere
  in the suite).

## 6. Documentation & compliance

- [x] 6.1 (Claude) `docs/FHIR_EXPORT.md` +
  `docs/FHIR_EXPORT_DE.md` existed already; added the missing links
  from `README.md`/`README_DE.md`'s feature list and
  `docs/ARCHITECTURE.md`/`_DE.md`'s Export-Profiles section (these were
  not yet wired in when this task was first drafted).
- [x] 6.2 `python3 scripts/utils/check_source_privacy.py` — clean, 0
  findings.
- [x] 6.3 `openspec validate add-fhir-export --strict` → "Change
  'add-fhir-export' is valid".
- [x] 6.4 `tools/gen_docs.py` run for all 3 new exporter scripts — also
  caught and fixed an invalid `@tier exporters` tag (not a valid tier
  value; corrected to `infrastructure`) that was blocking
  `tools/qa_check.py`; full QA gate now green (6/6 check groups).
