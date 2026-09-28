## Why

The public README/ARCHITECTURE currently claim Kyoro-HealthHub "scales from
single user to household to clinic (thousands of patients)". Investigation
found this is only true at the schema level: `resolve_person()`
accepts any `person` value as trusted input with zero access control, DB
encryption (`db_key`) is per-file not per-patient, and there is no patient
registry, no roles, and no audit log of data reads. The user has decided:
**the public release does not happen until this gap is closed** — a real,
tested multi-user permission system is a release requirement, equally for
research, GP practice, family, individual, and clinic deployment contexts
(no context gets a lower security/privacy bar).

## What Changes

- New patient registry (`patient_number_map` in `identity.db`) mapping
  external patient numbers to pseudonyms, analogous to the existing
  `device_serial_map` pattern.
- Per-patient instance isolation (`KYORO_ACTIVE_PATIENT_DIR` env var) so
  each patient has their own `health.db` + `db_key` — no shared-DB
  row-level security is attempted; blast radius stays per-patient.
- A real authorization broker reusing Kyoro SymptomTrack's
  existing TOTP+JWT auth (`pwa/backend/auth.py`), extended with a
  `patient_assignments` table (default-deny) and an `access_log` audit
  table covering reads, not just writes.
- Direct-DB-access tools (Datasette, Grafana, `sqlite3` CLI,
  `health_query.py`/`export_health.py`/`medical_query.py`, Kyoro SymptomTrack itself)
  are gated by which instance/DB file they are pointed at — not
  individually retrofitted with access checks.

## Capabilities

### New Capabilities
- `privacy-by-design-access-control`: binding principles (equal-standing
  target contexts, security/privacy by design and by default,
  anonymization-first with pseudonymization as the floor, real
  authorization, research-equals-clinic, ethics binding) plus the
  concrete patient-registry + broker mechanism that implements them.

### Modified Capabilities
(none — this is new capability, no existing spec's requirements change)

## Impact

- `scripts/health_config.py`, `scripts/utils/create_identity_schema.py`,
  new `scripts/utils/manage_patients.py` (Kyoro-HealthHub repo).
- `pwa/backend/auth.py`, `pwa/backend/db.py` (Kyoro SymptomTrack —
  restored from a stale worktree branch onto `main`, see `tasks.md` 1.1/1.2).
- README.md/_DE.md, docs/ARCHITECTURE.md/_DE.md wording adjusted to not
  overclaim, then finalized once implementation/verification landed (see
  `tasks.md` 5.2).
- **Was a release blocker** until implemented and verified — that work is
  now complete (see `tasks.md`); only task 7.3 (a real TOTP QR-code scan
  by a human) remains, explicitly descoped from blocking the release
  (`tasks.md` 7.4), still needed before clinic/research use is certified.
