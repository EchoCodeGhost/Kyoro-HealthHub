## Why

Kyoro-HealthHub's multi-tenant/clinic feature (`add-privacy-by-design-access-control`,
all tasks done) gives every patient their own
isolated instance (`KYORO_ACTIVE_PATIENT_DIR`, own `health.db`+`db_key`,
registered in `master.db`'s `patient_number_map`). The `research` export
profile already exists (`scripts/exporters/profiles/research.json`) and is
documented in `docs/ARCHITECTURE.md` as the profile for "Research / own
analysis" — but there is no tool that actually assembles a multi-patient
research dataset. Today "research use" means manually running
`export_health.py --profile research` once per instance and combining the
CSVs by hand, with the single-subject pseudonymization from
`scripts/utils/anonymize.py` (device serials, GPS, names) but no cohort-level
de-identification (real calendar dates, exact age, small-group re-identification
risk) and no recorded consent. This is the last structural gap before the
project can honestly claim "research" as a supported deployment context
(the multi-tenant isolation and access control it needs are already built;
only the export path across instances is missing).

## What Changes

- New script `scripts/exporters/export_research_cohort.py`: iterates all
  active patient instances registered in `master.db`, runs the existing
  `research` export profile against each instance's `health.db`, and merges
  the results into one cohort dataset directory.
- New `research_consent` table in `master.db`: per-patient, per-scope
  consent record with revocation support. The exporter **SHALL refuse** to
  include any instance without an active (non-revoked) consent row for the
  requested scope — no silent skip, hard abort listing which patients are
  missing consent.
- New `scripts/utils/manage_consent.py`: CLI to grant/list/revoke consent
  records (mirrors the existing `manage_patients.py` command style).
- Cohort-level de-identification layer on top of the existing
  `scripts/utils/anonymize.py` pseudonymization: per-patient consistent
  date-shifting (preserves relative time deltas, removes real calendar
  dates), age-banding (5-year bands instead of birthdate), and a
  configurable k-anonymity check (default k=5) over the quasi-identifier
  columns present in the profile output (age band, gender, and any
  location-derived field) — groups below the threshold are suppressed or
  further generalized, never passed through.
- Output written only to a local directory
  (`KYORO_MASTER_DIR/research_exports/<YYYY-MM-DD>/`), never uploaded.
- `docs/CLINIC_DEPLOYMENT.md` / `_DE.md`: new section documenting the
  research-cohort-export workflow end to end (consent → export → k-anonymity
  report).

## Assumption & Caveat: multi-tenant isolation is code-complete, but UNTESTED in any real sense

This change builds directly on `add-privacy-by-design-access-control`
(instance isolation, `patient_assignments`, `access_log`, TOTP+JWT broker).
That change is **code-complete** but its
only existing verification (`tests/manual/test_verification.py`, 2
synthetic dummy patients in an isolated throwaway test environment, 1
authorized + 1 unauthorized user) is a **smoke test against fabricated
data in an artificial setup, not a real test of the system under
anything resembling real conditions.** It does not establish that the
system works — only that it did not immediately fail against the single
narrow scenario the test happened to construct. Concretely, this feature
has **not** been:
- exercised with real (or even realistic-volume) patient data,
- load- or concurrency-tested with more than one simultaneous session,
- adversarially reviewed (`authz.py`/`access_log`: can a denied request
  leak data before the deny is logged? can a race condition between
  instance activation and query execution cross-contaminate two patients'
  data?),
- verified with a real TOTP QR-code scan by an actual human (flagged as
  still open in the original change's task 3.5).

Treat the multi-tenant layer as **unvalidated**, not as "validated at
small scale." "Passes a dummy smoke test" and "tested" are not the same
claim, and only the former is currently true. Before this cohort-export
change (or any research/clinic use with real patient data) goes into
real-world use, the multi-tenant layer needs a genuine test pass — not
an extension of the existing dummy scenario, but independent verification
under conditions that resemble actual use.

This change (research cohort export) does not attempt any of that
testing/hardening itself — it only adds the export/consent/de-identification
layer on top. The caveat is recorded here so it isn't lost: "multi-tenant
works" currently means "code-complete, passed one dummy smoke test," not
"tested," and certainly not "production-hardened at clinic/research
scale."

## Capabilities

### New Capabilities
- `research-cohort-export`: consent-gated, k-anonymized, multi-instance
  research dataset export built on top of the existing per-patient
  instance isolation and the existing `research` export profile.

### Modified Capabilities
(none — `privacy-rules` and `db-schema-conventions` apply as-is to all new
code in this change, no requirement text in either spec needs to change)

## Impact

- New files: `scripts/exporters/export_research_cohort.py`,
  `scripts/utils/manage_consent.py`,
  `scripts/utils/create_master_schema.py` (extended with
  `research_consent` table), `scripts/utils/deidentify_cohort.py`
  (date-shift/age-band/k-anonymity helpers, analogous in role to
  `scripts/utils/anonymize.py` but operating on already-queried result
  rows rather than DB writes).
- Modified: `master.db` schema (new table), `docs/CLINIC_DEPLOYMENT.md`,
  `docs/CLINIC_DEPLOYMENT_DE.md`.
- Reused, not modified: `scripts/export_health.py`'s profile
  execution logic, `scripts/exporters/profiles/research.json`,
  `scripts/utils/anonymize.py`'s device/name/GPS pseudonymization,
  `scripts/utils/manage_patients.py`'s command style.
- Does not touch: single-patient/family/individual-user workflows,
  clinic-practice day-to-day workflows (unaffected — this is an additional
  export path, not a change to existing ones).
