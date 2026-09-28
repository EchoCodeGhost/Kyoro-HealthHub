## ADDED Requirements

### Requirement: No hardcoded IANA timezone
Code that converts between UTC timestamps and local calendar dates/times
SHALL NOT hardcode an IANA timezone string (e.g. `"Europe/Berlin"`). It
SHALL use `resolve_timezone(conn, person)` from `modules/base.py` when a DB
connection and person are available, or `cfg.home_timezone` as a fallback
when they are not.

#### Scenario: New compute script needs local-time bucketing
- **WHEN** a contributor writes a function that groups timestamps into
  local-time windows (e.g. daytime rest-period detection)
- **THEN** the function resolves the timezone via `resolve_timezone()` or
  `cfg.home_timezone`, never a string literal, even as a documented default
  parameter value

#### Scenario: Code review finds a hardcoded timezone string
- **WHEN** a code review or `check_source_privacy.py` finds an IANA
  timezone string literal in source code
- **THEN** this counts as a convention violation that MUST be fixed before
  merge, regardless of whether the literal happens to match the
  maintainer's actual timezone

### Requirement: Device-agnostic data loading
A script reading a data source (e.g. nightly HRV, continuous heart rate)
that could plausibly be recorded by more than one configured device brand
SHALL NOT filter exclusively by one specific device's `device_id`. It
SHALL use a preference-ordered fallback chain (a preferred device first,
then any device recording that metric) so the script still returns data
when the preferred device is not configured or not the one actually
recording that data type.

#### Scenario: Script filters HRV by a specific device only
- **WHEN** a script loads nightly RMSSD and filters by
  `device_id = cfg.oura_device_id` (or any other single-brand device id)
  without a fallback
- **THEN** this counts as a convention violation, because the script
  silently returns nothing for contributors or time periods where that
  specific brand is not the one recording the data

#### Scenario: Data source is legitimately single-device by design
- **WHEN** a script reads data that can only ever come from one specific
  device by construction (e.g. a device-specific raw export format with no
  equivalent metric from other brands)
- **THEN** filtering by that device's id alone is not a violation — the
  requirement applies to data sources that could plausibly come from
  multiple devices, not to inherently single-source data

### Requirement: Bilingual user-facing output
User-facing text (console output, report text, error messages intended for
the user rather than a stack trace) SHALL use `t("<German text>", "<English
text>")` from `modules/i18n.py` instead of a hardcoded single-language
string.

#### Scenario: New script prints a status message
- **WHEN** a contributor adds a `print()` call with user-facing text (e.g.
  a progress message or a computed summary)
- **THEN** the text is wrapped in `t("DE text", "EN text")` so it respects
  the project's `KYORO_LANG` / `--lang` language selection

#### Scenario: Internal log line, not user-facing
- **WHEN** a message is a developer-facing debug/log statement never shown
  to the end user in normal operation
- **THEN** this requirement does not apply — it covers user-facing output
  only, not internal logging
