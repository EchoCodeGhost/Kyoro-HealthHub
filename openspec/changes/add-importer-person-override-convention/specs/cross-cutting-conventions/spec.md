## ADDED Requirements

### Requirement: Functional person override in importers
An importer that accepts a person override — a `--person` CLI flag, or a
`person` parameter on a `run(conn, data_path, lang, person)` function — SHALL
resolve it via `resolve_person()` (`modules/base.py`) and thread the resolved
value into every database write the importer performs. Accepting or declaring
the parameter without using it in the actual insert/save calls does not satisfy
this requirement. An importer with no person override at all SHALL NOT hardcode
`OWN_PERSON_ID` in a write path that could plausibly need to record a different
person's data.

#### Scenario: Person parameter declared but not threaded through
- **WHEN** a `run()` or CLI handler resolves a `person` value (e.g. via
  `resolve_person(args.person)`) but the function that performs the actual
  `INSERT`/save does not receive or use it
- **THEN** this counts as a convention violation — the parameter's presence
  gives the appearance of person-awareness without the substance, which is
  worse than not having it at all because it invites trusting a broken control

#### Scenario: Data source could come from a device shared across people
- **WHEN** an importer's data source is a device or app that could plausibly be
  shared between multiple people (e.g. a household sensor used across family
  members, a borrowed device) rather than being permanently owned by one person
- **THEN** the importer SHALL require an explicit person override for that run
  rather than inferring the person from device identity or falling back
  silently to the configured own person

#### Scenario: Importer only ever handles one person's own data by construction
- **WHEN** a data source is inherently single-person (e.g. a personal genetics
  file, a diary app tied to one account) with no plausible multi-person use
- **THEN** hardcoding the config's own person is acceptable and this
  requirement does not apply — the requirement targets sources that could
  plausibly need a different person, not all importers universally
