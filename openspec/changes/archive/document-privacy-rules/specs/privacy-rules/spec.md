## ADDED Requirements

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

### Requirement: Mandatory compliance check before merge
Every contribution that introduces new source code SHALL pass
`python3 scripts/utils/check_source_privacy.py` with exit code 0 before
merge.

#### Scenario: Pull request with a new importer
- **WHEN** a contributor submits a pull request with a new importer or
  compute script
- **THEN** `check_source_privacy.py` (or `check_anonymization.py
  --source-only`) must pass cleanly before merge
