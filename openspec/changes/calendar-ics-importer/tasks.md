## 1. Dependencies and schema

- [ ] 1.1 Add `icalendar` and `recurring-ical-events` to `requirements.txt` with a short comment explaining why (no stdlib module parses RFC 5545 reliably)
- [ ] 1.2 Create `templates/provider_registry.example.json` with dummy entries (one doctor/practice example, one "Zuhause" example) documenting the registry shape — `match`/`category`/`city`/`country` (required) plus `region` (optional, e.g. "Oberbayern", only for the rare case where city name alone is ambiguous even within one country)
- [ ] 1.3 Define `_SCHEMA_SQL` in `scripts/importers/import_calendar_ics.py` with `CREATE TABLE IF NOT EXISTS calendar_events` (all columns from design.md) plus `idx_calendar_events_date` and `idx_calendar_events_review` indexes
- [ ] 1.4 Check whether `scripts/modules/identity_resolver.py` already accepts an arbitrary `kind` string; if it has an explicit allow-list of kinds, add `"provider"` to it

## 2. .ics parsing and recurrence expansion

- [ ] 2.1 Implement `parse_ics_file(path) -> list[dict]`: parse with `icalendar.Calendar.from_ical()`, expand occurrences with `recurring_ical_events.of(calendar, keep_recurrence_attributes=True).between(horizon_start, horizon_end)` using `RECURRENCE_PAST_DAYS=3650`/`RECURRENCE_FUTURE_DAYS=400` module constants
- [ ] 2.2 Distinguish all-day (`date` object) vs. timed (`datetime` object) occurrences; for all-day, store `YYYY-MM-DD` directly as both `occurrence_start`/`occurrence_end` and `date`
- [ ] 2.3 For timed occurrences: tz-aware → convert to UTC ISO 8601; "floating" (naive) → localize with `ZoneInfo(_cfg.home_timezone)` first, then convert to UTC; resolve `date` via `local_date(ts_utc)` from `modules/base.py`
- [ ] 2.4 Skip occurrences with `STATUS == 'CANCELLED'`
- [ ] 2.5 Unit tests: a single non-recurring event, a weekly recurring event with `COUNT`, a recurring event with an `EXDATE`, an all-day event, a cancelled event (confirm it's skipped), a floating-time event

## 3. Scrubbing pipeline

- [ ] 3.1 Implement provider registry loading from `~/.config/kyoro/provider_registry.json` (empty/missing file → empty registry, not an error)
- [ ] 3.2 Implement `scrub_text(title, location, description, registry) -> dict` returning cleaned `title`/`location_text`/`description` plus `provider_category`/`provider_city`/`provider_region`/`provider_country`/`provider_pseudonym`/`needs_review`:
  - [ ] 3.2a Registry match (case-insensitive substring) → strip matched string from text, set category/city/country from the entry, set `provider_region` from the entry if present (else NULL — never derived), set `provider_pseudonym = identity_resolver.resolve("provider", <first match string as canonical key>)`
  - [ ] 3.2b No registry match, German postal-code pattern found (`\d{5}\s+[A-ZÄÖÜ][a-zäöüß]+`) → keep only the captured city-name group from that match; discard the postal-code digits themselves as well as everything before the match (street/house number) — result is the bare city name, never "PLZ Ort"; set `provider_country = "DE"` (follows directly from the pattern matched); `provider_region` stays NULL on this path (no postal-code-to-region lookup table added)
  - [ ] 3.2c Title-pattern name stripping (runs regardless of 3.2a/3.2b outcome): regex for German professional/academic titles (`Dr\.`, `Dr\. med\.`, `Prof\.`, `Prof\. Dr\.`, `Facharzt(?:in)?\s+für\s+\w+`, `Zahnarzt(?:in)?`, etc.) followed by one or two capitalized words → strip the matched "title + name" substring from the text; if not already resolved via a registry hit (3.2a), set `needs_review = 1`
  - [ ] 3.2d Residual-suspicion check (street-type suffixes, leftover 5-digit number, runs of capitalized words) → set `needs_review = 1`, keep the row
- [ ] 3.3 Unit tests for `scrub_text`: registry hit (doctor), registry hit (own address → "Zuhause"-style category), unregistered postal-code address (result is bare city name, postal code digits also gone — not "PLZ Ort"), unregistered address in a large multi-postal-code city like Munich (confirm result is just "München", not "80331 München" or any other district-identifying PLZ), titled name with no address at all (e.g. "Dr. Müller" stripped, `needs_review=1`), titled name that is also a registry hit (registry wins, no spurious `needs_review`), clean text with no match (passes through unflagged), suspicious leftover text (flags `needs_review`), bare untitled name with no address (documented as NOT caught — negative test confirming the accepted gap, not an oversight)
- [ ] 3.4 Confirm via test that no complete address (street + house number), no postal code, and no titled doctor name ever survives in any of the four `scrub_text` output paths

## 4. Core import logic and CLI

- [ ] 4.1 Implement `import_file(conn, path, person) -> int`: parse (2.1), scrub (3.2) before building the insert row, `INSERT OR IGNORE` into `calendar_events`
- [ ] 4.2 SPDX header, structured docstring (per design.md's documented contract for the dossier `--llm` path), `t("DE","EN")` i18n
- [ ] 4.3 CLI: `--file <path> [<path2> ...]` (`nargs='+'`), `--inbox`, `--update`, `--person`, `--lang` (`add_lang_arg`/`apply_lang_from_args`)
- [ ] 4.4 `--inbox`: import first, then move processed files to `imports/_inbox/processed/`
- [ ] 4.5 `log_import(conn, 'calendar_ics', str(path), n)` after each file's commit
- [ ] 4.6 End-of-run summary: total occurrences imported, count with `needs_review = 1`
- [ ] 4.7 Register in `scripts/import_all.py`'s `IMPORTERS` list

## 5. Compliance and verification

- [ ] 5.1 `person` is always `OWN_PERSON_ID`, never the literal `'self'`, anywhere in the new code
- [ ] 5.2 No hardcoded IANA timezone string anywhere (floating-time localization uses `_cfg.home_timezone`)
- [ ] 5.3 `python3 tools/gen_docs.py scripts/importers/import_calendar_ics.py` → `OK`
- [ ] 5.4 `python3 scripts/utils/check_source_privacy.py` → exit 0
- [ ] 5.5 Manual test: build a small real-ish `.ics` with one registered-provider event, one unregistered postal-code address, one titled-name-no-address event (e.g. "Termin bei Dr. Müller"), one deliberately ambiguous leftover-text event, one all-day event, one weekly-recurring event with `EXDATE` — run the importer and manually inspect `calendar_events` to confirm every row matches the expected scrubbing outcome from the spec's scenarios
- [ ] 5.6 Manual test: re-run the same file a second time and confirm row counts don't change (idempotent `INSERT OR IGNORE`)
