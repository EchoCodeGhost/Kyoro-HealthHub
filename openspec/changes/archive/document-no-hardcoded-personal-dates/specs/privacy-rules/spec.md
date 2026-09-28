## ADDED Requirements

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
