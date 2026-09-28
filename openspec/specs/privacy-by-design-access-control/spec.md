# privacy-by-design-access-control Specification

## Purpose
Kyoro-HealthHub is meant to run in several private deployment contexts —
a single individual, a family, or a friend group with one person helping
another — and the multi-person/shared-access capability this enables must
not become a weaker-security side door relative to the single-user case.
This project is deliberately scoped to private use and does not pursue
certification for institutional (clinic/research) deployment; the
mechanism described here is strong access control for private use, not an
institutional feature. This spec fixes one default-deny, technically enforced
access-control model across all of them: no context gets a relaxed
standard, new capabilities are designed with access control from the
start rather than secured afterward, every instance and account starts
locked down, real identifiers never leave the pseudonym mapping, access
is gated once at instance selection instead of per tool, every access
(including denials) is logged, and every script resolves config paths
through the same two mechanisms so no per-scenario fork can bypass it.
## Requirements
### Requirement: Equal-standing target contexts
Kyoro-HealthHub SHALL apply the same security and privacy floor to all
declared private deployment contexts — individual user, family, and
friend group, whether using the simple trust-based mode or the
access-controlled shared-access mode — with none receiving a lower
standard than another.

#### Scenario: New deployment context proposed
- **WHEN** a new private deployment context is proposed
- **THEN** it MUST meet the same access-control, encryption, and
  anonymization/pseudonymization requirements as the existing
  access-controlled shared-access mode, not a relaxed variant

### Requirement: Security and privacy by design
Any new multi-user or multi-patient capability SHALL be designed together
with its access-control model, never added in isolation and secured
afterward.

#### Scenario: New multi-patient feature proposed without access control
- **WHEN** a contributor proposes a feature that exposes more than one
  patient's data to more than one user
- **THEN** the proposal MUST include an access-control design before
  implementation begins

### Requirement: Security and privacy by default
The default state of any new instance, account, or capability SHALL be
the most private/secure option — not opt-in privacy.

#### Scenario: New patient instance created
- **WHEN** a new patient instance is registered
- **THEN** it is isolated (separate database and encryption key) and no
  staff member has access until explicitly granted

#### Scenario: New staff account created
- **WHEN** a new staff user account is created
- **THEN** it has zero patient assignments by default (default-deny, not
  default-allow-until-revoked)

### Requirement: Anonymization first, pseudonymization as the floor
Wherever an analysis, export, or research use case works with anonymized
data, anonymized data SHALL be used. Where re-identifiability is clinically
necessary (e.g. treatment, critical-finding callback), pseudonymization —
using the existing `identity.db`/pseudonym mapping pattern — is the
minimum acceptable standard. Real identifiers SHALL never leave
`identity.db` into `health.db`, exports, analyses, or dashboards.

#### Scenario: Research dataset requested
- **WHEN** a dataset is prepared for a research use case
- **THEN** it uses anonymized or pseudonymized identifiers, never real
  patient names or numbers

#### Scenario: Dashboard tool (Datasette, Grafana) queries patient data
- **WHEN** Datasette, Grafana, or any similar direct-DB-access tool
  displays patient data
- **THEN** it only ever sees the pseudonymized `person`/`patient_pseudo`
  identifier, never a real name or external patient number

### Requirement: Real, tested multi-user authorization
Access from one user to another person's data SHALL be enforced by a
technical, default-deny authorization check (`patient_assignments`), not
by convention or trust in the caller.

#### Scenario: Unauthorized access attempt
- **WHEN** a staff user without a `patient_assignments` entry for a given
  patient attempts to activate/access that patient's instance
- **THEN** access is denied and the attempt is recorded in `access_log`

#### Scenario: Authorized access
- **WHEN** a staff user with a valid, non-revoked `patient_assignments`
  entry accesses a patient's instance
- **THEN** access is granted and recorded in `access_log`

### Requirement: Access gated at instance selection, not per-tool
Direct-database-access tools (Datasette, Grafana, `sqlite3` CLI,
`health_query.py`, `export_health.py`, `medical_query.py`, Kyoro
SymptomTrack/Kyoro SymptomTrack, and any future such tool) SHALL inherit their access
restriction from which patient instance/database file they are pointed
at — they SHALL NOT require individual per-tool authorization logic.

#### Scenario: Datasette started against an active instance
- **WHEN** Datasette or Grafana is started for a staff member's current
  session
- **THEN** it is pointed only at the one patient instance that member is
  currently authorized and activated for

### Requirement: Read-access audit logging
Every data access — not only writes — to a patient's instance by a
non-owner user SHALL be logged, including denied attempts.

#### Scenario: Compliance review
- **WHEN** a compliance review asks "who accessed patient X's data and
  when"
- **THEN** `access_log` provides a complete answer, including denied
  attempts

### Requirement: Single config-path resolution mechanism, no per-scenario forks
Every script SHALL resolve instance-scoped configuration/data paths via
`KYORO_CONFIG_DIR` (follows the active patient instance) and
practice-wide administrative paths via `KYORO_MASTER_DIR` (always the
real operator home, never follows an active instance) — both defined
exactly once in `scripts/health_config.py`. No script SHALL construct a
`~/.config/kyoro` (or equivalent) path itself. This mechanism SHALL be
identical for single-user and multi-patient deployments — single-user
mode simply never uses `KYORO_MASTER_DIR`, not a different code path.

#### Scenario: Instance-scoped data accessed while a patient is active
- **WHEN** any script reads or writes instance-scoped data (health config,
  identity/pseudonym maps, per-patient encryption key, per-patient
  registries such as medications or clinical events) while
  `KYORO_ACTIVE_PATIENT_DIR` is set
- **THEN** it resolves the path via `KYORO_CONFIG_DIR` and therefore reads/
  writes the active patient's own instance, never another patient's or the
  operator's real home

#### Scenario: Practice-wide administrative data accessed
- **WHEN** any script reads or writes practice-wide administrative data
  (patient registry, device catalog, staff login credentials)
- **THEN** it resolves the path via `KYORO_MASTER_DIR`, which stays fixed
  at the real operator home regardless of which patient instance is active

#### Scenario: New script introduces its own config path
- **WHEN** a new or existing script constructs `Path.home() / ".config" /
  "kyoro"` (or an equivalent hardcoded path) itself instead of importing
  `KYORO_CONFIG_DIR`/`KYORO_MASTER_DIR`
- **THEN** an automated check flags this as a violation before merge

### Requirement: Ethical use boundaries
The access-control system SHALL NOT be extended to enable use by
insurers, employers, or other actors seeking to profile or discriminate
against people, consistent with `NOTICE` and `docs/ETHICS.md`.

#### Scenario: Non-private third party requests access
- **WHEN** an insurer, employer, or other institutional actor requests an
  account under this system
- **THEN** the request is refused as out of scope per `NOTICE`/`docs/ETHICS.md`
  — this project is scoped to private use only

