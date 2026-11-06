## ADDED Requirements

### Requirement: Single reusable provider-scrubbing function
Any importer or exporter that processes free text which may contain a
doctor/practice name or address SHALL call
`scripts/modules/provider_scrubbing.py::scrub_provider_text(text)`
instead of implementing its own matching/stripping logic. The function
SHALL return a result carrying `clean_text`, `provider_category`,
`provider_city`, `provider_country`, `provider_region`,
`provider_pseudonym`, and `needs_review`.

#### Scenario: A new importer needs to handle provider-identifying text
- **WHEN** a script (existing or new) is about to write free text that
  may contain a doctor/practice name or address into a table or an
  intermediate review file
- **THEN** it calls `scrub_provider_text()` and uses the returned
  `clean_text`/`provider_*` fields instead of writing the raw text

#### Scenario: Code review finds a second, independent scrubbing implementation
- **WHEN** a code review finds an importer or exporter with its own
  registry-match/postal-code/title-pattern logic instead of calling
  `scrub_provider_text()`
- **THEN** this counts as a convention violation that MUST be fixed
  before merge, unless that caller predates this module and migrating
  it is tracked as its own follow-up (e.g. `calendar-ics-importer`)

### Requirement: Registry-based exact match takes priority
A local, never-committed registry (`~/.config/kyoro/provider_registry.json`,
documented via `templates/provider_registry.example.json` with dummy
values) of known doctors/practices/addresses SHALL be checked first.
Each entry has a `match` list (case-insensitive substrings), `category`,
`city`, `country` (ISO 3166-1 alpha-2, required), and an optional
`region` (for a city name that recurs more than once within one
country).

#### Scenario: Text matches a registry entry
- **WHEN** the input text contains a substring listed in a registry
  entry's `match` list
- **THEN** that substring is stripped from `clean_text`,
  `provider_category`/`provider_city`/`provider_country`/`provider_region`
  are set from the entry, `provider_pseudonym` is set via
  `identity_resolver.resolve("provider", <canonical registry key>)`,
  and `needs_review` stays `False` for that match

### Requirement: German postal-code pattern reduces to city level
When no registry entry matches but the text contains a German postal
code followed by a capitalized place name (`\d{5}\s+[A-ZÄÖÜ][a-zäöüß]+`),
the street and house number SHALL be removed and the text reduced to the
city name, with `provider_country` set to `"DE"`.

#### Scenario: Unregistered German address with postal code
- **WHEN** the input text contains a 5-digit German postal code
  immediately followed by a capitalized place name, and no registry
  entry matched
- **THEN** the street/house number are removed, `clean_text` retains at
  most the city name, and `provider_country` is set to `"DE"`

### Requirement: Professional-title-plus-name pattern is stripped independently
A German professional or academic title (`Dr.`, `Dr. med.`, `Prof.`,
`Prof. Dr.`, `Facharzt/Fachärztin für ...`, `Zahnarzt/Zahnärztin`, etc.)
followed by one or two capitalized words SHALL be treated as a name
match and removed from `clean_text`, independently of whether a registry
or postal-code match also fired.

#### Scenario: Title-pattern name with no registry or address match
- **WHEN** the input text contains a recognized professional/academic
  title followed by one or two capitalized words, and this name is not
  in the registry and no postal code is present
- **THEN** the title+name is removed from `clean_text` and `needs_review`
  is set to `True`

#### Scenario: Title-pattern name that is also in the registry
- **WHEN** a title+name match also matches a registry entry
- **THEN** the registry-based result (category/city/country/pseudonym,
  `needs_review=False`) takes precedence over the bare title-pattern
  removal

### Requirement: Safety net flags remaining suspicious text instead of discarding it
If, after the registry/postal-code/title-pattern steps, the remaining
text still contains street-type suffixes, a leftover 5-digit number, or
multiple consecutive capitalized words, `needs_review` SHALL be set to
`True` and the (partially cleaned) text SHALL still be returned — never
silently dropped and never passed through unscrubbed without the flag.

#### Scenario: Suspicious leftover text with no clean match
- **WHEN** none of the registry/postal-code/title-pattern steps fully
  resolve the text, but a street-suffix word, a leftover 5-digit number,
  or several consecutive capitalized words remain
- **THEN** `needs_review` is `True` and `clean_text` contains the
  partially-processed text (not discarded, not silently passed through
  as if clean)

#### Scenario: A bare name with no title and no address
- **WHEN** the input text contains a personal name with neither a
  professional title nor an address/postal-code pattern (e.g. "mit
  Michael treffen")
- **THEN** this is a documented, accepted gap — the function is not
  required to detect it, and this limitation SHALL be stated in the
  module's `@limits` docstring
