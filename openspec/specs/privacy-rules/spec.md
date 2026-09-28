# privacy-rules Specification

## Purpose
Documents the source-code privacy conventions that keep personal
identifiers, diagnoses, and hardcoded config values out of this public
repository — no diagnosis/entity names in identifiers or filenames, no
hardcoded IANA timezones, no fallback dicts with real entity IDs.
Enforced by `scripts/utils/check_source_privacy.py`; exists so
contributors (and the maintainer) don't accidentally leak personal data
into the public code, even without prior knowledge of its sensitivity.
## Requirements
### Requirement: No diagnosis or entity identifiers in source code
Variables, constants, function names, and filenames SHALL NOT name a
diagnosis, a person-specific entity ID, or a condition-specific
identifier. Generic names (e.g. `EVENT_DATES`, `OI_HR_THRESHOLD`,
`postinfectious`) SHALL be used instead; the actual meaning SHALL live
exclusively in config values.

#### Scenario: New constant for a clinical threshold
- **WHEN** a contributor introduces a constant for a disease-specific
  threshold
- **THEN** the constant has a generic name (e.g. `OI_HR_THRESHOLD`
  instead of a name that names the underlying diagnosis), and the actual
  value comes from config

#### Scenario: Compliance check finds a forbidden identifier
- **WHEN** `python3 scripts/utils/check_source_privacy.py` runs
- **THEN** the script reports every occurrence of a fragment listed in
  `privacy_check.forbidden_identifiers` (local, non-committed config)
  found in source code, and exits with a non-zero exit code

### Requirement: Person identifiers exclusively via `OWN_PERSON_ID`
Code SHALL never use the string literal `'self'` as a person identifier
in source code or SQL. `OWN_PERSON_ID` from `scripts/health_config.py`
SHALL always be used instead.

#### Scenario: New SQL query with a person filter
- **WHEN** a contributor writes a SQL query filtering on the primary
  person
- **THEN** the parameter is passed from `OWN_PERSON_ID`, not the literal
  `'self'` written directly into the query

### Requirement: No hardcoded timezones
Source code SHALL never hardcode an IANA timezone string (e.g.
`"Europe/Berlin"`). DB-aware code SHALL use `resolve_timezone(conn,
person)`; code without DB access SHALL use `cfg.home_timezone` as a
fallback.

#### Scenario: New importer computes the local calendar day
- **WHEN** a new importer needs to derive the local calendar day from a
  UTC timestamp
- **THEN** it uses `resolve_timezone(conn, person)` instead of hardcoding
  a timezone as a string literal in code

### Requirement: No fallback dicts with hardcoded entity IDs
Code SHALL NOT contain `_FOO_DEFAULTS`-style dictionaries with hardcoded
entity IDs or sensor/device names as a fallback. If the corresponding
config is missing, the program SHALL abort with `sys.exit` and a clear
error message, instead of falling back to a default containing real
personal data.

#### Scenario: A config value is missing at runtime
- **WHEN** a script needs a config value (e.g. a device registry entry)
  that is missing from `~/.config/kyoro/health_config.json`
- **THEN** the script aborts with `sys.exit` and an understandable error
  message, instead of falling back to a default hardcoded in code with
  real entity data

### Requirement: No hardcoded personal dates/timestamps
Source code SHALL NOT hardcode a personal or clinical date/timestamp
literal (e.g. birth date, clinical event dates such as
infection/diagnosis/medication-start dates, device install/registry
dates). Every such date SHALL come from config instead (e.g.
`user.birthdate`, `clinical.events`, `device_registry[].date_from`) — the
same "every date... comes from config" principle CLAUDE.md already states
for device IDs and person identifiers, applied here to dates.

#### Scenario: New script needs a clinical event date
- **WHEN** a contributor writes code that needs a birth date, a clinical
  event date (infection, diagnosis, medication start/stop, etc.), or a
  device's ownership start date
- **THEN** the value is read from config (`user.birthdate`,
  `clinical.events`, `device_registry[].date_from`), never written as a
  date/datetime literal in source code

#### Scenario: Compliance check finds a hardcoded personal date
- **WHEN** `python3 scripts/utils/check_source_privacy.py` (or a future
  extension of it) finds a personal/clinical date literal in source code
- **THEN** this counts as a privacy violation that MUST be fixed before
  merge, the same way a hardcoded timezone string or entity ID is treated

#### Scenario: Date literal is not personal data
- **WHEN** a date or timestamp literal in source code is not personal or
  clinical data by nature (e.g. an algorithm constant, an epoch/calendar
  arithmetic boundary, or a publication year cited for an external medical
  guideline)
- **THEN** this is not a violation of this requirement — it applies to
  personal/clinical dates, not to every date/timestamp literal in the
  codebase

### Requirement: Mandatory compliance check before merge
Every contribution that introduces new source code SHALL pass
`python3 scripts/utils/check_source_privacy.py` with exit code 0 before
merge.

#### Scenario: Pull request with a new importer
- **WHEN** a contributor submits a pull request with a new importer or
  compute script
- **THEN** `check_source_privacy.py` (or `check_anonymization.py
  --source-only`) must pass cleanly before merge

### Requirement: No human-readable device or person identifiers in stored data
Beyond the existing source-code convention (no diagnosis/entity
identifiers in code), `health.db`/`medicine.db` itself SHALL also never
store a human-readable device (e.g. `polar_v3`) or person (e.g.
`self`/`partner`) identifier — only pseudonyms generated by
`identity_resolver`. This applies regardless of whether access is local
or through an external tool (including an externally connected AI).

#### Scenario: An external AI reads the database
- **WHEN** an external tool (e.g. a remotely connected AI) inspects
  `health.db` or `medicine.db` directly
- **THEN** no column allows inferring which concrete device model or
  which real person/relationship is behind a data point

#### Scenario: Compliance check extended to identifier pseudonymization
- **WHEN** a compliance check (analogous to
  `scripts/utils/check_source_privacy.py`) runs against
  `health.db`/`medicine.db`
- **THEN** it reports every occurrence of a non-pseudonymized,
  human-readable device or person identifier in `device_id`, `device`,
  or `person` columns

### Requirement: Developer anonymity in project artifacts
Planning and documentation artifacts (e.g. OpenSpec changes, commit
history) SHALL NOT allow inferring working hours, patterns, or the
identity of the maintaining person, beyond what is necessary to
contribute to the project.

#### Scenario: A new OpenSpec change is created
- **WHEN** a new OpenSpec change is created
- **THEN** its content references the maintaining person only
  generically (e.g. "the maintainer"), never by name or other
  identifying detail

### Requirement: No hardcoded host or user values in deployment artifacts
Deployment artifacts (systemd units, Caddyfiles, and comparable infra
configs) SHALL NOT hardcode a real Linux username or absolute home path.
A generic placeholder token (`CHANGEME`) SHALL be used instead, replaced
at deployment time via a documented one-liner (e.g. `sed
's/CHANGEME/YOURUSER/g'`).

#### Scenario: New systemd unit for a local service
- **WHEN** a contributor adds a new systemd unit file for a project-owned
  service
- **THEN** `User=`, `WorkingDirectory=`, `ExecStart=`, and
  `Environment=HOME=` contain the placeholder `CHANGEME` instead of a
  real username or absolute path, and a comment in the file header
  documents the replacement command for deployment

#### Scenario: Review of an existing deployment file
- **WHEN** an existing deployment file (e.g. `*.service`, `Caddyfile`)
  contains a real username or absolute home path instead of a
  placeholder
- **THEN** this counts as a violation of this requirement and is
  switched to `CHANGEME` before the next merge
