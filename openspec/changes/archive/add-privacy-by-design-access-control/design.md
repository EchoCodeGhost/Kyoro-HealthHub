## Context

**Starting point (before this change):** two explore agents
confirmed all of Kyoro-HealthHub's CLI scripts trusted `person`/`--person`
as unchecked input; SQLCipher `db_key` encrypted per DB file, not per
patient; no patient registry, roles, or read-audit existed. The sister
PWA "Kyoro SymptomTrack" already had real TOTP+JWT auth in
`pwa/backend/auth.py`, but its symptom data hung off a global `_PERSON`
constant rather than the logged-in user, and Kyoro SymptomTrack itself
was absent from `main` (squashed out at an earlier point, only present
in two stale worktree branches).

**Current status:** all of the above has since been addressed — see
`tasks.md` for the full implementation record (patient registry +
instance isolation, `pwa/` restored, authorization broker with
default-deny `patient_assignments` + `access_log`, race-condition and
audit-timing fixes verified under a concurrency load test with 0
cross-contamination). Only task 7.3 (a real TOTP QR-code scan by a human
with a phone) remains open — explicitly descoped from blocking the
public release (7.4), still required before clinic/research use is
certified.

## Goals / Non-Goals

**Goals:**
- Real, tested, default-deny access control before any multi-patient
  deployment is called "supported".
- Equal security/privacy floor across research, GP practice, family,
  individual, and clinic contexts — no tiering.
- Reuse existing code (Kyoro SymptomTrack's `auth.py`) rather than building new auth
  infrastructure from scratch.
- Every direct-DB-access tool (Datasette, Grafana, CLI, Kyoro SymptomTrack) inherits
  restriction via instance-selection gating, not per-tool retrofits.

**Non-Goals:**
- No FHIR/EHR interoperability.
- No shared-database row-level security for "thousands of patients in one
  DB" — the model is N isolated per-patient instances, not multi-tenancy
  within a single database.
- No changes to the existing importer/compute/analysis scripts
  themselves.

## Decisions

- **Isolation over in-DB ACL:** retrofitting access checks into 
  scripts that currently trust `person` input was rejected as too large
  and risky pre-release. Per-patient instance isolation (separate
  `health.db` + `db_key` per patient) achieves the same security goal
  with zero changes to those scripts.
- **Gate at instance selection, not per-tool:** rather than adding
  authorization logic to Datasette, Grafana, `sqlite3`, and every query
  tool individually, the broker's only job is deciding which instance
  directory/DB file a user may open. Everything downstream operates
  inside an already-authorized single-patient sandbox.
- **Reuse Kyoro SymptomTrack's auth.py:** it already has TOTP, JWT sessions, and a
  readonly flag — extending it with a `patient_assignments` table is
  far less work and risk than a new auth stack.
- **`git checkout <branch> -- pwa/` instead of a real merge** to restore
  Kyoro SymptomTrack: a full merge would pull the entire pre-squash commit graph back
  into `main`; checking out just the current tree state as a new commit
  keeps the squashed history intact.

## Risks / Trade-offs

- [Risk] only a few days to build and field-test TOTP end-to-end
  plus the assignment/audit system is tight → Mitigation: explicit user
  decision that the release date moves before the standard is lowered.
- [Risk] Kyoro SymptomTrack's two stale worktree branches may have diverged →
  Mitigation: diff both before restoring, pick the more current one
- [Risk] Datasette/Grafana instance-gating requires operational discipline
  (must actually be (re)started per active instance, not left pointed at
  a stale/wrong DB) → Mitigation: document in `docs/CLINIC_DEPLOYMENT.md`
  as an explicit operational requirement, not just a code mechanism.
