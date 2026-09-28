# cross-cutting-conventions Specification

## Purpose
Documents coding conventions that apply to every new script regardless of
pipeline stage (importer, compute, analysis) — timezone handling,
device-agnostic data loading, and bilingual output. Exists so these rules,
previously scattered across `CLAUDE.md` prose and individual docstrings,
are checkable against reviewable scenarios instead of relying on a
reviewer remembering them. Complements `db-schema-conventions`, which
covers schema-shape rules (EAV, person column, pseudonyms) rather than
control-flow/output conventions.
## Requirements
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

### Requirement: Structural change to positionally-read data
A change that inserts, removes or reorders a field in a data structure read by
position — a result tuple consumed via `row[i]`, a fixed-length row unpacked into
variables, an `INSERT` column list paired with a value tuple — SHALL be treated as
a global change. Every reader of that structure SHALL be located and updated in
the same change, in the same way `db-schema-conventions` treats a table or column
rename as global rather than local.

This applies to positional access only. Structures read by key name (`dict`,
`sqlite3.Row`, named tuple field access) are unaffected, because inserting a field
there does not shift the meaning of the others.

#### Scenario: Field inserted into a result tuple
- **WHEN** a contributor adds a field in the middle of a tuple that is built in
  one place and consumed by index elsewhere (console output, plot, export,
  downstream aggregation)
- **THEN** the change locates every positional reader of that tuple and updates
  the indices, and the contributor states in the PR where those readers are —
  updating only the database column list is not sufficient

#### Scenario: Structure is read by key rather than position
- **WHEN** the affected structure is a dict, a `sqlite3.Row`, or a named tuple
  accessed by field name
- **THEN** inserting a field is not a global change and this requirement does not
  apply

### Requirement: Impossible values in a script's own output are defects
A value that cannot occur by construction — a loop variable outside its declared
range, a float where an integer is assembled, a per-day count exceeding the days
in the period — SHALL be treated as evidence of a defect and investigated before
any result derived from that run is reported or merged.

#### Scenario: Console summary prints an out-of-range value
- **WHEN** a script's output contains a value that its own control flow cannot
  produce (e.g. `lag+18d` where the lag loop is `range(1, 4)`)
- **THEN** the run is treated as failed and the cause is found, rather than the
  surrounding numbers being reported as valid

#### Scenario: Value is unusual but constructible
- **WHEN** a value is merely surprising — a high but reachable measurement, an
  unexpected but possible count
- **THEN** this requirement does not apply; it covers values ruled out by the
  code's own structure, not values ruled out by expectation

### Requirement: Concurrent multi-device readings default to priority selection
When a script combines a metric (e.g. heart rate, HRV) from more than one
device for the same moment, the DEFAULT SHALL be a single per-minute winner
chosen by `modules/device_registry.py::hr_priority()`/`collapse_concurrent()`
(sensor-type ranking: ECG > handheld ECG > chest strap > ring > optical
wrist > smartphone), never an unweighted average across the devices worn at
that moment. Averaging silently overweights periods where more devices were
worn against periods with only one, without the underlying physiology having
changed. This is the standard; deviating from it is permitted only under one
of the named conditions below, not as a free per-script choice.

Named conditions under which a script MAY deviate from priority-selection:
1. **Exact duplicate artifact** (same `ts`, `value`/`value_text`, `source_app`,
   only `device_id` differs): not a multi-device case at all — clean up via a
   one-time DB migration (s. `migrations/dedupe_measurements_multi_device.py`),
   not runtime logic.
2. **Gap-filling** (the priority-ranked device has no data for a given day/
   window): a lower-priority source MAY fill in, but only where the preferred
   device is genuinely silent — never blended on days the preferred device
   already has data (s. `compute_pem.py`'s `resolve_reference_device()`
   pattern).
3. **Session-type data** (training, sleep — not a scalar value): priority
   selection does not apply; use time-window clustering + a dedup key instead
   (s. `migrations/dedupe_polar_training_sessions.py`,
   `analyse_sleep_day_hr.py::_derive_apple_sleep_nights()`).
4. **Demonstrated insufficiency of hardware ranking**: when a plain
   sensor-type ranking is shown not to hold for a given metric/source pair
   (e.g. via `compute_calibrate_sources.py`'s bias/Pearson-r analysis against
   an anchor device), an empirically calibrated `source_confidence` value
   (s. `compute_canonical.py`) MAY override the static priority — this
   requires the calibration evidence, not just a preference.

#### Scenario: Two devices report different HR values for the same minute
- **WHEN** a script aggregates `heart_rate` (or another HR/HRV-adjacent
  metric) across sources and finds more than one `device_id` with a value
  for the same minute
- **THEN** the script keeps only the highest-`hr_priority()` device's row for
  that minute (tie-break: lexicographically smallest `device_id`) before
  computing any average — it does not fold every device's value into one mean

#### Scenario: A script wants to average across simultaneously worn devices
- **WHEN** a contributor is tempted to average HR/HRV across all sources
  active in a window as a way to "use all the data"
- **THEN** this counts as a convention violation unless one of the four named
  conditions above applies and is stated in the PR — "more data is better" is
  not itself a valid reason to deviate from priority selection

#### Scenario: Preferred device has no reading for the day
- **WHEN** the priority-ranked device (e.g. a chest strap) was not worn on a
  given day and only a lower-priority device (e.g. a smartwatch) recorded
  anything
- **THEN** the lower-priority device's value is used for that day (condition
  2, gap-filling) — this is not a violation, but the fallback must be scoped
  to days where the preferred device is genuinely absent, not applied broadly

#### Scenario: Combining training or sleep sessions from multiple sources
- **WHEN** a script needs to avoid double-counting the same real-world
  training session or sleep period recorded by more than one device
- **THEN** condition 3 applies — resolve via time-window clustering and a
  dedup key, not via `hr_priority()`, since sessions are not scalar readings
