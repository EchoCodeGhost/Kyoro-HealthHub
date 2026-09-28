## ADDED Requirements

### Requirement: Prohibited uses
The project SHALL prohibit the uses listed in `docs/ETHICS.md` section 4,
regardless of technical feasibility: profiling for insurance
underwriting, employer screening, credit decisions, or law enforcement;
surveillance of employees, patients, family members, or other people
without their knowledge and voluntary consent; training commercial AI
models on personal health data without explicit, specific, and revocable
consent; disclosure of health, gender, or identity data to unauthorized
third parties; discrimination based on disability, chronic illness,
gender identity, sexual orientation, or other protected characteristics.

#### Scenario: Contributor proposes a profiling feature
- **WHEN** a contribution introduces a function that would make health
  data usable for insurance underwriting, employer screening, credit
  decisions, or law enforcement
- **THEN** the contribution is rejected in review, regardless of whether
  the feature is technically well implemented

#### Scenario: Contributor proposes a surveillance feature
- **WHEN** a contribution introduces a function that surveils a person
  without their knowledge and voluntary consent (e.g. covert tracking of
  family members)
- **THEN** the contribution is rejected in review

#### Scenario: Contributor proposes AI training on user data
- **WHEN** a contribution proposes using personal health data to train a
  commercial AI model without obtaining explicit, specific, and
  revocable consent
- **THEN** the contribution is rejected in review

#### Scenario: Export profile would involve unauthorized third parties
- **WHEN** a new or changed export profile (`scripts/exporters/profiles/`)
  would pass health, gender, or identity data to a party the affected
  person has not explicitly authorized
- **THEN** the profile is adjusted or rejected before merge

#### Scenario: Feature would discriminate based on a protected characteristic
- **WHEN** a contribution introduces behavior that treats users
  differently (to their detriment) based on disability, chronic illness,
  gender identity, sexual orientation, or other protected characteristics
- **THEN** the contribution is rejected in review

### Requirement: Local data storage by default
The database SHALL reside locally by default; automatic cloud sync or
remote backup SHALL only occur after an explicit user action. Database
encryption (`PRAGMA key`) SHALL remain supported and documented; new
contributions SHALL NOT disable or bypass it. Export files containing
health data SHALL NOT be written to world-readable directories.

#### Scenario: New contribution adds automatic cloud sync
- **WHEN** a contribution introduces a mechanism that automatically
  (without an explicit user call) transmits database contents to a cloud
  service
- **THEN** the contribution is rejected in review, unless the transfer
  only happens after an explicit user action

#### Scenario: Contribution disables or bypasses DB encryption
- **WHEN** a contribution changes code related to `PRAGMA key`/database
  encryption and thereby disables or bypasses encryption by default
- **THEN** the contribution is rejected in review

#### Scenario: Export writes to a world-readable directory
- **WHEN** an export script writes a file containing health data to a
  directory with world-readable permissions
- **THEN** this counts as a finding that MUST be fixed before merge

### Requirement: Authenticated API access
If the FastAPI backend (`pwa/backend/`) is deployed, it SHALL require
authentication; unauthenticated endpoints that return health data SHALL
count as a critical vulnerability.

#### Scenario: New endpoint returns health data without an auth check
- **WHEN** a new or changed FastAPI endpoint returns health data without
  going through the existing authentication/authorization
  (`pwa/backend/authz.py`)
- **THEN** this counts as a critical security vulnerability that MUST be
  fixed before merge

### Requirement: No credentials in code or logs
API tokens, database keys, and credentials SHALL never appear in source
code, logs, or error output — only `~/.config/kyoro/health_config.json`
SHALL be used for this.

#### Scenario: Contributor commits an API key
- **WHEN** a commit contains an API token, database key, or other
  credential string in plaintext in source code
- **THEN** this counts as a finding that MUST be fixed before merge
  (credentials belong exclusively in
  `~/.config/kyoro/health_config.json`)

### Requirement: Data minimization on import
Importers SHALL only import the fields needed for the respective
analysis; surplus fields SHALL be dropped or ignored on import. Staging
files in `data/staging/` SHALL be treated as transient — retention
periods SHALL be documented and deletion after import SHALL be
recommended.

#### Scenario: New importer picks up unneeded raw data fields
- **WHEN** a new importer writes a raw data field to the database that
  is not used by any existing or planned analysis
- **THEN** the field is flagged as unnecessary in review and removed
  from the import path

### Requirement: Logging and audit trails
`import_log` SHALL document what was imported when — this SHALL NOT be
suppressed. Raw health values SHALL NOT be logged in application output;
only counts and status SHALL be logged.

#### Scenario: New importer doesn't write to import_log
- **WHEN** a new importer writes data to the database without creating
  an entry via `log_import()` in `import_log`
- **THEN** this counts as a convention violation that MUST be fixed
  before merge

#### Scenario: Log output contains raw health values
- **WHEN** a script writes raw measurements (e.g. specific lab values,
  HRV time series) instead of counts/status to application output during
  normal operation
- **THEN** this counts as a finding that MUST be fixed before merge

### Requirement: Review of new dependencies for data behavior
New dependencies SHALL be checked for their own data behavior; libraries
that "phone home" or collect telemetry SHALL NOT be accepted.

#### Scenario: New dependency collects telemetry
- **WHEN** a new dependency is added to `requirements.txt` that sends
  telemetry to the vendor by default or "phones home"
- **THEN** the dependency is rejected in review, unless the behavior can
  be reliably disabled by default

### Requirement: Confidential reporting of security vulnerabilities
Security issues SHALL be reported privately to the maintainer before
being publicly disclosed. A public issue SHALL NOT be opened for an
unpatched vulnerability.

#### Scenario: Someone discovers an unpatched security vulnerability
- **WHEN** a person discovers a security vulnerability in
  Kyoro-HealthHub that has not yet been fixed
- **THEN** they report it privately to the maintainer instead of opening
  a public GitHub issue

### Requirement: Labeling of AI-generated output
LLM output SHALL be clearly labeled as AI-generated everywhere it is
displayed.

#### Scenario: New UI surface shows LLM output without labeling
- **WHEN** a new or changed interface (CLI output, export, web UI)
  displays an LLM-generated analysis or comment
- **THEN** the output is visibly labeled as AI-generated before the
  contribution is merged
