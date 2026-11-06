## Why

Kyoro-HealthHub has no calendar data source yet. Reconstructing what happened on a given day (e.g. "was there a doctor's appointment that day?") currently requires the user to remember or manually cross-check an external calendar app — there's no way to correlate wearable/lab data with scheduled appointments. This was explicitly deferred as a Non-Goal/Phase-2 item in the `health-dossier-query` change (not yet implemented) specifically because no calendar importer existed; this change builds that importer first, ahead of the dossier feature.

Calendar entries are also the single most likely place in this pipeline for third-party personal data (doctor names, practice names, exact street addresses) to show up in free text, which none of the existing importers need to handle at this level — this change's privacy design is the main piece of new ground, not just the .ics parsing itself.

## What Changes

- Add `scripts/importers/import_calendar_ics.py`: reads one or more `.ics` files (source-agnostic — Apple Calendar/iCloud and Google Calendar both export standard RFC 5545 iCalendar) via `--file <path> [<path2> ...]` or `--inbox`.
- New dependencies: `icalendar` (parsing) and `recurring-ical-events` (RRULE/EXDATE/RDATE recurrence expansion within a fixed window: `RECURRENCE_PAST_DAYS=3650`, `RECURRENCE_FUTURE_DAYS=400`).
- New table `calendar_events` in health.db — one row per concrete occurrence (recurring series are expanded, not stored as a rule), with `date`/`person` columns that make it automatically compatible with the generic date/person table-discovery the (separately planned, not-yet-implemented) `health-dossier-query` change already specifies.
- **New mandatory pre-insert scrubbing step**, stricter than this repo's usual stance on local-only free text: doctor names, practice names, and complete addresses (street + house number) MUST NOT be stored, not even locally. Before any insert:
  1. Match `SUMMARY`/`LOCATION`/`DESCRIPTION` against a local, never-committed provider registry (`~/.config/kyoro/provider_registry.json`, template with dummy values at `templates/provider_registry.example.json`) of known doctors/practices/addresses (including the user's own home/work addresses).
  2. On a match: strip the raw matched string from the text; set `provider_category`/`provider_city`/`provider_country`/`provider_region` from the registry entry; set `provider_pseudonym` via the existing central `identity_resolver.resolve("provider", ...)` (no new pseudonymization mechanism). `provider_country` is a required field per registry entry (ISO 3166-1 alpha-2) because a bare city name is not globally unique across countries. `provider_region` is an **optional** registry field (e.g. a German `Regierungsbezirk`/state name like "Oberbayern") for when the same city name also exists more than once *within* a country (e.g. more than one German Musterstadt) — never auto-derived, only ever set when the registry entry explicitly provides it; identification itself still happens via the pseudonym regardless, so this is a display convenience, not a correctness requirement.
  3. No registry match but a German postal-code pattern is found: reduce to the city name only — the postal code is used to locate the city, then discarded along with the street/house number, since a postal code narrows a large city down to a specific district (e.g. Munich has dozens of distinct postal codes) and is therefore less private than the bare city name. `provider_country` is set to `"DE"` in this case, since the matched pattern is specifically the German postal-code format — this is a direct consequence of the pattern itself, not a guess. A documented heuristic, not NER/ML.
  4. **Title-pattern name stripping (independent of 2./3.):** a German professional/academic title (`Dr.`, `Dr. med.`, `Prof.`, `Prof. Dr.`, `Facharzt/Fachärztin für ...`, `Zahnarzt/Zahnärztin`, etc.) followed by one or two capitalized words is treated as a positive name match and stripped from the text, even when there is no address or postal code at all (e.g. "Termin bei Dr. Müller"). If that name is also in the registry, step 2 already handled it; if not, the title+name is still removed and `needs_review = 1` is set.
  5. Safety net: if suspicious text remains after 2./3./4. (street-type suffixes, a leftover 5-digit number, multiple consecutive capitalized words), flag the row `needs_review = 1` and still import it (no data loss) rather than silently passing unscrubbed text through. A bare name with neither a title nor an address (e.g. "mit Michael treffen") remains a documented, accepted gap — not reliably detectable without NER.
- Contract for the (separate, future) `health-dossier-query` `--llm` path: it MUST only ever use `provider_category`/`provider_city`/`provider_region`/`provider_country`/`provider_pseudonym`/`date`/`all_day` from `calendar_events`, never `title`/`location_text`/`description` (even scrubbed) and never a `needs_review = 1` row. Recorded here as a dependency/contract for that change, not implemented by it.

## Capabilities

### New Capabilities
- `calendar-ics-importer`: imports calendar events from `.ics` files into health.db, expanding recurring events into concrete occurrences, with a mandatory privacy-scrubbing step that prevents doctor/practice names and complete addresses from ever being persisted, replacing them with a generic category+city+country label and an opaque pseudonym.

### Modified Capabilities
_(none — this is a new, standalone importer; it does not change any existing capability's requirements. It establishes a data contract that the not-yet-implemented `health-dossier-query` change will need to honor, but that change's own spec is not modified here.)_

## Impact

- New file: `scripts/importers/import_calendar_ics.py`
- New table: `calendar_events` (health.db), schema defined inline in the importer (`_SCHEMA_SQL`), no `create_schema.py` change needed per project convention
- New dependencies in `requirements.txt`: `icalendar`, `recurring-ical-events`
- New local-only config: `~/.config/kyoro/provider_registry.json` (never committed), plus `templates/provider_registry.example.json` in the repo
- Possible small extension to `scripts/modules/identity_resolver.py`: add `kind="provider"` if not already generic enough to accept a new kind
- New entry in `scripts/import_all.py`'s `IMPORTERS` list
- No impact on existing tables, importers, or compute/analysis scripts
