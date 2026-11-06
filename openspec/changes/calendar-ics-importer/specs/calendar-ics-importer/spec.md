## ADDED Requirements

### Requirement: Source-agnostic multi-file .ics import
The system SHALL import calendar events from one or more RFC 5545 (.ics) files in a single run, regardless of which calendar application produced them (Apple Calendar/iCloud, Google Calendar, or any other standard-compliant export), via an explicit file list or an inbox-folder scan.

#### Scenario: Multiple files in one run
- **WHEN** the user runs `import_calendar_ics.py --file apple_export.ics google_export.ics`
- **THEN** events from both files are imported into `calendar_events` in the same run, without requiring separate invocations

#### Scenario: Inbox scan
- **WHEN** the user runs `import_calendar_ics.py --inbox` with one or more `.ics` files present in `imports/_inbox/`
- **THEN** each file is imported and then moved to `imports/_inbox/processed/`, in that order (import before move)

### Requirement: Recurring events expanded to concrete occurrences
The system SHALL expand `RRULE`/`EXDATE`/`RDATE` recurring event definitions into individual dated occurrences at import time, bounded by a fixed past/future window, rather than storing the recurrence rule itself.

#### Scenario: Weekly recurring event
- **WHEN** a `VEVENT` has `RRULE:FREQ=WEEKLY` with no `UNTIL`/`COUNT`
- **THEN** the importer creates one row per weekly occurrence falling within the configured `RECURRENCE_PAST_DAYS`/`RECURRENCE_FUTURE_DAYS` window, and none outside it

#### Scenario: Exception date
- **WHEN** a recurring event has an `EXDATE` matching one of its would-be occurrences
- **THEN** no row is created for that specific date

#### Scenario: Cancelled event skipped
- **WHEN** a `VEVENT` (recurring occurrence or single event) has `STATUS:CANCELLED`
- **THEN** no row is created for it

### Requirement: No doctor/practice name or complete address is ever persisted
The system SHALL NOT write a doctor name, practice name, or complete address (street name plus house number) to `health.db` under any circumstance, including for the user's own home/work addresses — not even as part of an unprocessed free-text field — regardless of whether the value is pseudonymized elsewhere.

#### Scenario: Registered doctor appointment
- **WHEN** an event's `LOCATION` or `DESCRIPTION` contains a string matching an entry in the local provider registry (e.g. a specific doctor's name and practice address)
- **THEN** the stored `title`/`location_text`/`description` no longer contain that matched string, and `provider_category`/`provider_city`/`provider_country`/`provider_pseudonym` are populated instead, plus `provider_region` if the registry entry provides one

#### Scenario: Unregistered address with a recognizable postal code
- **WHEN** an event's free text contains a German postal-code-shaped address not present in the registry (e.g. "Musterstraße 5, 12345 Musterstadt")
- **THEN** the stored text contains only the city name ("Musterstadt") — the postal code itself is also stripped, not just the street name and house number

#### Scenario: Large city with multiple postal codes
- **WHEN** the recognized address falls within a large city that spans many distinct postal codes (e.g. "80331 München")
- **THEN** the stored text contains only "München", without the postal code — city-name-only is deliberately coarser than postal-code-level precision, since a single large city's postal codes already distinguish between its districts

#### Scenario: Optional region for a same-named city within the country
- **WHEN** a registry entry for a provider explicitly sets a `region` value (e.g. "Oberbayern", to distinguish from another place of the same city name elsewhere in Germany)
- **THEN** `provider_region` is populated from that value; when a registry entry omits `region`, `provider_region` stays NULL rather than being guessed or derived from the postal code

#### Scenario: User's own address
- **WHEN** an event's `LOCATION` matches the user's own home or work address as registered in the provider registry
- **THEN** it is replaced the same way as a third-party provider match (e.g. reduced to a category like "Zuhause"/"Arbeitsplatz" plus city), never left as a complete address

### Requirement: Titled doctor names are stripped even without an address
The system SHALL detect a German professional/academic title (e.g. `Dr.`, `Dr. med.`, `Prof.`, `Prof. Dr.`, `Facharzt/Fachärztin für ...`, `Zahnarzt/Zahnärztin`) immediately followed by one or two capitalized words as a name match, and SHALL strip that matched text from `title`/`location_text`/`description`, regardless of whether any address or postal code is present in the same event.

#### Scenario: Titled name with no address at all
- **WHEN** an event's free text contains "Termin bei Dr. Müller" with no accompanying address or postal code
- **THEN** "Dr. Müller" is stripped from the stored text, and the row is still imported (with `needs_review = 1` if "Dr. Müller" is not in the provider registry)

#### Scenario: Titled name that is also a registry match
- **WHEN** a titled name matches both the title pattern and an entry in the provider registry
- **THEN** the registry match takes precedence — `provider_category`/`provider_city`/`provider_pseudonym` (and `provider_region` if set) are populated as in the registry-match requirement, and the row is not additionally flagged `needs_review` solely because of the title pattern

#### Scenario: Known residual gap — name with no title and no address
- **WHEN** an event's free text contains a bare personal name with neither a professional title nor any address/postal-code cue (e.g. "mit Michael treffen")
- **THEN** the system is not required to detect or strip it — this is a documented, accepted limitation, not a defect

### Requirement: Provider pseudonymization via the existing central resolver
The system SHALL obtain the opaque pseudonym for a matched provider/location exclusively through `identity_resolver.resolve()`, and SHALL NOT implement a separate pseudonymization mechanism for calendar data.

#### Scenario: Pseudonym for a registry match
- **WHEN** a provider registry match occurs during import
- **THEN** `provider_pseudonym` is set via `identity_resolver.resolve("provider", <canonical registry key>)`, and no alternate hashing/pseudonymization code path is used

#### Scenario: Deterministic repeat resolution
- **WHEN** the same provider is matched again in a later import run
- **THEN** `identity_resolver.resolve()` returns the same pseudonym as before, keeping `INSERT OR IGNORE` deduplication consistent

### Requirement: Unscrubbed-content safety net
The system SHALL flag an occurrence with `needs_review = 1` when address- or name-shaped text remains in its free-text fields after registry matching, postal-code reduction, and title-pattern name stripping, SHALL still import that occurrence rather than discarding it, and SHALL report the count of flagged occurrences at the end of a run.

#### Scenario: Leftover street-type suffix
- **WHEN** after scrubbing, an event's free text still contains a street-type suffix (e.g. "...weg", "...straße", "...platz", "...allee") or a leftover 5-digit number
- **THEN** the row is imported with `needs_review = 1` set, and the event is not discarded

#### Scenario: Run summary reports review count
- **WHEN** an import run completes with one or more `needs_review = 1` rows written
- **THEN** the script's output states how many occurrences need manual review

### Requirement: Dossier LLM contract
The system SHALL document, as a binding contract for the (separately implemented) health-dossier `--llm` pattern-analysis feature, that only `provider_category`, `provider_city`, `provider_region`, `provider_country`, `provider_pseudonym`, `date`, and `all_day` from `calendar_events` may ever be included in a payload sent to an LLM, and that `title`/`location_text`/`description` (scrubbed or not) and any row with `needs_review = 1` must never be included.

#### Scenario: Documented in importer limits
- **WHEN** the importer's docstring/`@limits` section is read
- **THEN** it states explicitly which `calendar_events` columns are safe for a future LLM payload and which are not, so a later implementer of the dossier's `--llm` allow-list has an unambiguous reference
