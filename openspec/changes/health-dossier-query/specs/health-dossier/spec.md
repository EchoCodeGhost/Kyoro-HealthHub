## ADDED Requirements

### Requirement: Data-agnostic table discovery
The system SHALL discover which database tables to include in the dossier by introspecting the health.db and medicine.db schemas for tables with a `date` or `ts` column, rather than from a hardcoded enumeration of table names, SHALL filter by `person = OWN_PERSON_ID` for any discovered table that has a `person` column and include it unconditionally otherwise, and SHALL exclude only tables on an explicit, documented exclusion list (handled elsewhere via dedicated logic, administrative, population-level/non-individual, or not day-keyed) — so a table added by a future importer appears in the dossier without a code change to this script.

#### Scenario: New table appears automatically
- **WHEN** a new date/person-keyed table is added to health.db by a future importer and is not on the exclusion list
- **THEN** rows from that table falling within the requested window appear in the dossier without any change to `health_dossier.py`

#### Scenario: Excluded table stays excluded
- **WHEN** the schema scan encounters a table on the exclusion list (e.g. `schema_version`, `genetic_variants`, `outbreak_events`)
- **THEN** that table's rows are never included via the generic scan (tables needing dedicated handling, like `lab_manual` or `user_context`, are still covered through their own dedicated requirement, not omitted from the dossier entirely)

#### Scenario: Table without a person column is not filtered by person
- **WHEN** a discovered table (e.g. `home_environment`) has a date column but no `person` column
- **THEN** its rows for the window are included without a person filter, since the data is not individually attributed

### Requirement: Single-command cross-source day lookup
The system SHALL provide a script (`scripts/query/health_dossier.py`) that, given a target date and an optional day-window, returns all data the pipeline holds for that window across health.db and medicine.db — measurements, sessions, symptoms, user_context notes/tags, lab values, and every other date-keyed table discovered per the data-agnostic table discovery requirement (weather, air quality, pollen, home environment, self-care/cosmetics, nutrition, cognitive/functional tests, and any future addition) — without requiring the user to query multiple scripts or databases separately.

#### Scenario: Basic single-day lookup
- **WHEN** the user runs `health_dossier.py 2026-10-15`
- **THEN** the output includes any health.db measurements/sessions/symptoms, any medicine.db lab values, and any other matching date-keyed table's rows (e.g. weather, pollen, self-care) dated 2026-10-15, grouped by source/category, for `OWN_PERSON_ID`

#### Scenario: Multi-day window
- **WHEN** the user runs `health_dossier.py 2026-10-15 --days 1`
- **THEN** the output includes matching data from 2026-10-14 through 2026-10-16 inclusive, with each entry's own date shown (not collapsed into the target date)

#### Scenario: No data found
- **WHEN** the target date/window has no matching rows in any source
- **THEN** the script reports clearly that no data was found for that window, per source, rather than printing an empty or ambiguous result

### Requirement: Date-range and relative-period dossiers
The system SHALL support generating a dossier for a range of days, either via an explicit `--from A --to B` range or a relative shorthand `--last <N><unit>` with an arbitrary non-negative integer `N` and unit `d`/`w`/`m`/`y` (not a fixed list of preset periods), producing one dated section per day in the range rather than a single aggregated blob, and SHALL NOT compute range-level statistics (averages, trends) as part of this output.

#### Scenario: Explicit date range
- **WHEN** the user runs `health_dossier.py --from 2026-09-01 --to 2026-09-07`
- **THEN** the output contains one section per calendar day from 2026-09-01 through 2026-09-07, each built the same way a single-day lookup would be

#### Scenario: Relative period shorthand with arbitrary N and unit
- **WHEN** the user runs `health_dossier.py --last 4w`, or `--last 17w`, or `--last 4d`, or `--last 2y`
- **THEN** in each case the system resolves the corresponding number of days ending today (using the person's resolved timezone, never a hardcoded one) and produces the same per-day sections as the equivalent explicit `--from`/`--to` call — the parser is generic over `N` and unit, not a lookup table of supported periods

#### Scenario: Range with no aggregation
- **WHEN** a multi-day dossier is generated
- **THEN** the output does not include computed averages, trends, or other range-level statistics — only the per-day sections

### Requirement: Optional, minimized, opt-in LLM pattern analysis
The system SHALL support an opt-in `--llm` flag that sends the already-assembled dossier (single day or range) to the configured LLM provider for a pattern/trend analysis, SHALL NOT make any remote call unless `--llm` is explicitly passed and a provider is configured, SHALL build the LLM payload from an explicit allow-list of sections rather than the full dossier, SHALL reduce any location data in that payload to region-level only, and SHALL exclude the unverified-document section from the payload by default.

#### Scenario: No LLM call without the flag
- **WHEN** `health_dossier.py` is run without `--llm`
- **THEN** no network request to any LLM provider is made, and the dossier is fully produced from local data alone

#### Scenario: LLM call requires a configured provider
- **WHEN** `--llm` is passed but no LLM provider is configured in `health_config.json`
- **THEN** the script reports that no provider is configured and does not silently fall back to a default remote provider

#### Scenario: Location data minimized before the LLM call
- **WHEN** a dossier containing location stays is sent to the LLM with `--llm`
- **THEN** the payload contains only region-level location information (via `location_store.py`'s existing region resolution), never raw coordinates or place names

#### Scenario: Unverified documents excluded from LLM payload
- **WHEN** a dossier with candidate documents in the unverified-documents section is sent to the LLM with `--llm`
- **THEN** that section is not included in the payload sent to the provider

#### Scenario: LLM analysis works across a range
- **WHEN** `--llm` is combined with `--from`/`--to` or `--last`
- **THEN** the pattern analysis considers the whole range's per-day sections, not just a single day

### Requirement: Nearest-date lab value matching
The system SHALL, for lab/blood values, fall back to the nearest available value per parameter when no value exists exactly on the target date, SHALL display the actual date of the matched value alongside it, and SHALL omit values further than a configurable maximum distance (default 90 days) from the target date rather than presenting a stale value as current.

#### Scenario: Exact-date lab value exists
- **WHEN** a lab parameter has a recorded value exactly on the target date
- **THEN** that exact value is shown, with its date matching the target date

#### Scenario: Nearest-date fallback within cutoff
- **WHEN** a lab parameter has no value on the target date but has one 12 days earlier, and the cutoff is 90 days
- **THEN** that 12-days-earlier value is shown, labeled with its actual date (not the target date)

#### Scenario: Nearest value beyond cutoff is omitted
- **WHEN** the closest available value for a lab parameter is 200 days from the target date and the cutoff is 90 days
- **THEN** that parameter is omitted from the dossier for this date, not shown with a distant date

### Requirement: Location data via existing privacy controls only
The system SHALL include GPS stays/tracks for the requested window by calling an accessor function inside `scripts/modules/location_store.py`, and SHALL NOT query `location.db` directly with ad-hoc SQL from outside that module, so that privacy-zone redaction and pseudonymization already implemented there cannot be bypassed.

#### Scenario: Location data respects privacy zones
- **WHEN** the day dossier includes a stay that falls inside a configured privacy zone
- **THEN** the dossier shows the same redacted/zone-level representation that `location_store.py` would return to any other caller, not raw coordinates

#### Scenario: No direct SQL access to location.db
- **WHEN** `health_dossier.py` needs location data for the window
- **THEN** it calls a function in `location_store.py` rather than opening `location.db` and writing its own SELECT

### Requirement: Unverified document pointer, clearly separated
The system SHALL list files from `medicine/arztbriefe/`, `medicine/laborbefunde/`, and `medicine/krankenakte/` whose filename or filesystem modification date falls within the requested window, in a section visually and textually separated from verified structured data, labeled as an unverified heuristic match.

#### Scenario: Candidate document found
- **WHEN** a file in `medicine/arztbriefe/` has a modification date inside the requested window
- **THEN** it appears in a separate "possibly relevant documents (unverified)" section, not mixed into the structured lab/measurement data

#### Scenario: No heuristic match
- **WHEN** no file in the watched directories falls within the window
- **THEN** the document section states that no candidate documents were found, rather than being silently omitted

### Requirement: Machine-readable output option
The system SHALL support a `--json` flag that emits the same dossier content as structured JSON instead of formatted text, for downstream scripting.

#### Scenario: JSON output requested
- **WHEN** the user runs `health_dossier.py 2026-10-15 --json`
- **THEN** the script prints a single valid JSON document containing the same sources/sections as the text output, with no extra human-readable text interleaved
