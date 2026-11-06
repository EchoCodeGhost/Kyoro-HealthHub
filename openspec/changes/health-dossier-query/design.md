## Context

Three separate query surfaces already know how to reconstruct part of a day:

- `scripts/query/context_query.py` joins `user_context` (notes/tags from Oura, Garmin GDPR, symptom diaries, Bearable, Apple Health, etc.) with "canonical" measurement tables for a single exact day (`--with-context`).
- `scripts/modules/location_store.py` has all the stay/track storage and privacy-zone redaction logic, but no public "give me everything for date X" accessor — callers currently write their own date-range SQL per importer/exporter.
- `medicine.db`'s `lab_results` / `lab_manual` have `date` columns but no "nearest value to date X" lookup anywhere; every existing consumer (exporters) filters by exact `:date_from`/`:date_to` range, not proximity.

None of these three talk to each other. Reconstructing a single day today means running three different scripts against three different databases and manually lining up the output. The `symptoms` table (health.db) is its own first-class table, separate from `user_context`, and currently has no dedicated query helper either.

Raw clinical documents (`medicine/arztbriefe/`, `medicine/laborbefunde/`, `medicine/krankenakte/`) are stored as files on disk, created by a human dropping PDFs in after an appointment. There is no DB table linking a document to the date of the appointment/lab draw it covers — `import_lab_results.py`-style importers read the PDF once and only persist the extracted values, not a reference back to the source file.

## Goals / Non-Goals

**Goals:**
- One script, one command, one date (or date range, explicit or relative like "last 4 weeks") in → everything the pipeline currently knows about that window, out.
- Data-agnostic coverage: new tables added by future importers (weather, environment, apps, anything date-keyed) show up in the dossier automatically, without a code change to this script — see decision 0.
- Reuse existing storage/redaction/query logic; add only the missing glue (date-window support, nearest-date lab lookup, a thin location accessor, generic table discovery).
- Keep every privacy guarantee the underlying data already has (location privacy zones, pseudonymized device/person IDs) — the dossier is a new *view*, not a new *exemption*.
- Make the "nearest lab value" semantics explicit and visible in the output (show the actual date of the matched value, not just the value, so a value from 9 days away isn't mistaken for same-day).

**Non-Goals:**
- No calendar-event integration in this change (no importer exists yet; tracked as a possible follow-up change).
- No new DB tables, no schema migration, no writes of any kind — purely read/aggregate.
- No automatic OCR/parsing of the raw document files to find their "true" date — filename/mtime heuristic only, explicitly flagged as unverified in the output.
- No range-level *numeric* aggregation/statistics (averages, trend lines) computed in Python — that stays `analyse_all.py`'s territory. The optional `--llm` pattern analysis (decision 9) is qualitative interpretation on request, not a replacement for that.
- The dossier itself (without `--llm`) must remain independently correct and complete without any model in the loop — `--llm` is an additive interpretation layer, never a dependency for the core output.

## Decisions

**0. Table coverage is schema-driven ("data-agnostic"), not a hand-maintained list.**
health.db and medicine.db already have dozens of date-keyed tables beyond the "obvious" ones (`weather_station`, `weather_remote`, `air_quality`, `pollen_dwd`/`pollen_google`/`pollen`, `biometeo`, `indoor_air_quality`, `home_environment`, `home_environment_ts`, `home_presence`, `self_care` (covers cosmetics/skincare via its `category` field), `nutrition_daily`/`nutrition_entries`, `cognitive_tests`, `functional_tests`, `orthostatic_tests`, `food_triggers`, `fluid_intake`, `body_composition`, `blood_pressure`, `blood_glucose`, and more) — and new importers add new tables regularly. Hand-listing every table in `day_dossier.py`/`health_dossier.py` would mean the dossier silently misses whatever table was added last and nobody remembered to wire in. Instead:
  - At startup, introspect `sqlite_master` for both databases to find tables with a column named `date` or `ts` (the two naming conventions already used consistently across the schema).
  - For each such table, if it also has a `person` column, filter `WHERE person = :person AND <date_col> BETWEEN :from AND :to`. If it has no `person` column (e.g. `home_environment`, `home_environment_ts`, `home_presence` — household-level, not individually attributed), include it unconditionally for the window, since there's nothing to filter by and the data isn't person-specific to begin with.
  - A short, explicit exclusion list keeps out tables that are date-keyed but not meaningfully "about this day" or need special handling done elsewhere in this design: `measurements`/`session_metrics`/`sessions` (handled explicitly, not generically, since they need the existing device-priority/EAV logic — see cross-cutting-conventions, not a flat per-table dump), `lab_results`/`lab_manual` (handled via nearest-date matching, decision 3, not exact-window), `user_context` (handled via the `context_query.py` join, decision 2), any table representing location (excluded entirely from the generic scan — always decision 4's dedicated accessor), administrative/non-clinical tables (`schema_version`, `import_log`, `import_file_hashes`, `compute_log`, `devices`, `device_firmware_history`, `persons`, `source_priority`, `data_quality_flags`), population-level surveillance tables with no `person` column and no individual relevance (`outbreak_events`, `wastewater_amelag`, `ed_syndromic_surveillance`, `outbreak_exposure` — these are about disease surveillance in the population/region, not "what happened to me on day X"), and non-day-keyed reference tables (`genetic_variants`, `genetic_risk_markers` — these don't vary by day).
  - This list lives as a small `EXCLUDED_TABLES` set in `health_dossier.py` itself with a one-line reason each — explicit opt-out, not implicit opt-in, so a reviewer can see exactly what's deliberately not generically scanned and why, while everything else (present now or added later) is included automatically.
  - This directly satisfies "komplett agnostisch von den Daten" without needing day_dossier.py to be touched every time a new importer/table is added — new tables matching the `date`/`ts` + optional `person` pattern show up automatically.

**1. New script `scripts/query/health_dossier.py`, not a new exporter profile.**
Exporter profiles (`scripts/exporters/profiles/*.json`) are SQL-only and designed for one database at a time via `:person`/`:date_from`/`:date_to`. The dossier spans three databases (health.db, medicine.db, location.db) plus a filesystem scan, which the exporter mechanism doesn't support. A dedicated script under `scripts/query/` (where `context_query.py` and `health_query.py` already live) matches the existing layout convention better than stretching the exporter format.

**2. Reuse `context_query.py`'s query function via import, don't duplicate its SQL.**
`context_query.py` already has the `user_context` + canonical-table join logic; extend its underlying function to accept `date_from`/`date_to` (it currently supports this for the general listing path already — confirm and reuse, only add the window param where it's single-day-only) and import it from `health_dossier.py` rather than re-implementing the join.

**3. Nearest-date lab lookup is a new, explicit function, not implicit in the main query.**
For `lab_manual`/`lab_results`, "nearest to date X" means: for each `parameter`, find the row with the smallest `ABS(julianday(date) - julianday(:target))`, independently per parameter (a CBC panel and a vitamin D test may legitimately come from different draws). Implemented as `nearest_lab_values(conn, target_date, max_distance_days, person)` in a shared module (`scripts/modules/` — exact file TBD during implementation, e.g. `modules/lab_lookup.py`) so it's independently testable and reusable outside the dossier. `max_distance_days` defaults to something conservative (e.g. 90) so a stale value from a year ago doesn't get silently presented as "the" value for this day — rows beyond the cutoff are omitted, not included with a bigger disclaimer.

**4. Location access goes through a new read-only wrapper, never a raw SQL query against location.db from `health_dossier.py`.**
Add `stays_and_tracks_for_window(person, date_from, date_to)` to `location_store.py` itself (same module that owns the privacy-zone logic), so the redaction/zone rules stay in one place and the dossier script never has the chance to accidentally read an un-redacted column.

**5. Document pointer is filename/mtime matching, clearly labeled "ungeprüft".**
Scan the three `medicine/` subdirectories for files whose name contains a date-like token near the target window, or whose filesystem mtime falls in the window, and list them as "possibly relevant documents (unverified, filename/date heuristic)" — never merged into the structured data, always a visually separate section, so a wrong match can't be mistaken for a verified data point.

**6. Output: structured text by default, `--json` for machine consumption.**
Matches `health_query.py`/`context_query.py` precedent. No HTML/PDF rendering in this change.

**7. Date window, not just single date.**
The user's request ("Blutwerte in der Nähe von einem bestimmten Tag") implies a tolerance is already baked into decision 3 for labs specifically; separately, the CLI also accepts a `--days N` window (default 0 = exact day) so sessions spanning midnight (e.g. sleep) and nearby symptom entries aren't missed by an overly strict exact-day filter.

**8. Two distinct range concepts — do not conflate them.**
- `--days N`: a *lookaround* tolerance on a single target date (catches a sleep session that started the evening before, or a lab value a few days off). Still produces one dossier "about" one target date.
- `--from A --to B` / `--last <N><unit>`: a *multi-day report* — every calendar day in the span gets its own dated section, each built the same way a single-day dossier would be (same per-day functions, called in a loop), not a single flattened/aggregated blob. This is what makes "letzte 4 Wochen", "letzte 17 Wochen" or "letzte 4 Tage" possible without inventing new aggregation logic or a per-period special case — it's N single-day dossiers concatenated, grouped by day in the output, for whatever N and unit the user passes.
- `--last` shorthand parses `<number><unit>` generically — `N` is an arbitrary non-negative integer (not a fixed set of presets like "4 weeks" or "7 weeks"; those are just examples), `unit` ∈ {`d` days, `w` weeks, `m` calendar months, `y` calendar years} — relative to today (resolved via `resolve_timezone()`/`cfg.home_timezone`, never a hardcoded timezone), computing `date_from`/`date_to` and then behaving exactly like an explicit `--from`/`--to` call — no separate code path, and no allow-list of "supported" periods to maintain.
- Nearest-date lab fallback (decision 3) still applies **per day** inside a range: each day in the range independently gets its nearest lab value (subject to the cutoff), so a 4-week report doesn't repeat the same nearest value for all 28 days without saying so — if a value's nearest match is the same source row for several consecutive days, that's shown explicitly (same date shown each time) rather than hidden.
- For a multi-day range, the per-day sections are the primary output; a range-level summary/rollup is explicitly out of scope for this change (see Non-Goals) to avoid scope creep into analysis/statistics territory that `analyse_all.py` already owns.

**9. Optional LLM pattern analysis is opt-in, minimized, and reuses existing provider plumbing.**
`--llm` triggers a second pass after the dossier is assembled: the already-built structured dossier (single day or range) is handed to the configured LLM provider (same resolution path as `health_query.py`: `health_config.json`, opt-in, no silent default, local/remote choice stays the user's) with a prompt asking for pattern/trend observations across the window. Before the call:
- Location: only region-level (`location_store.py::region_of()`/`stored_region()`), never raw lat/lon or place names, regardless of what the non-LLM dossier output shows the user locally.
- Unverified documents section: excluded from the LLM payload by default (a flag could opt it back in later, but filenames can be identifying and the match is unverified anyway — not worth the risk for an optional feature).
- No new diagnosis-specific wording is introduced in the prompt template itself — any condition-specific framing comes only from config values already flowing through the rest of the pipeline (same rule as everywhere else in the repo), not from a hardcoded prompt string naming a diagnosis.
- Device/person IDs stay pseudonymized exactly as already stored; the LLM call changes nothing about that.
This mirrors the project's standing stance ("local-first, remote LLM opt-in and configurable per tool, never a silent default") rather than inventing a new consent model for this one script.

## Risks / Trade-offs

- **[Risk]** Nearest-date lab matching could mislead if `max_distance_days` is too generous → **Mitigation:** show the matched date explicitly next to every value; keep the default cutoff conservative; make it a CLI flag, not a hardcoded silent default deep in the function.
- **[Risk]** Filename/mtime document heuristic produces false positives/negatives (e.g. a batch-scanned backlog of old letters all sharing one mtime) → **Mitigation:** label section explicitly as unverified; this is a pointer for the human to go look, not a parsed data source.
- **[Risk]** Aggregating across health.db + medicine.db + location.db in one script risks accidentally bypassing a privacy control present in one of them (e.g. location redaction) → **Mitigation:** decision 4 — all location access goes through `location_store.py`'s own accessor, never raw SQL from the new script; same pattern should apply if any future addition touches pseudonymized device/person IDs.
- **[Risk]** Scope creep toward calendar integration in the same change → **Mitigation:** explicitly listed as a Non-Goal; tracked as a separate follow-up change if wanted.
- **[Risk]** Generic schema scan (decision 0) automatically includes a future table that turns out to be sensitive in a way the exclusion list didn't anticipate (e.g. a new table storing something identity-adjacent) → **Mitigation:** the exclusion list is opt-out by design specifically so it's reviewable; adding a new importer/table is already a reviewed PR in this repo, and the convention should be to add genuinely non-day/administrative/population-level tables to `EXCLUDED_TABLES` as part of that same PR, same as any other new-table checklist item.
- **[Risk]** Generic scan touches many tables per call → **Mitigation:** this is a local SQLite query tool run interactively, not a hot path; a schema-driven `PRAGMA table_info`/`sqlite_master` scan plus one indexed lookup per table is not a performance concern at this data scale (see existing `analyse_all.py` which already does comparably broad scans).
- **[Risk]** `--llm` payload accidentally leaks more than intended (e.g. a future edit adds a new section to the dossier and forgets to exempt/minimize it before the LLM call) → **Mitigation:** build the LLM payload from an explicit allow-list of sections/fields, not by serializing the whole dossier object and subtracting — new sections are excluded by default until someone deliberately adds them to the allow-list.

## Migration Plan

Not applicable — no schema or data migration; purely additive read-side code. Rollback is simply not using/removing the new script.

## Open Questions

- Exact module path for `nearest_lab_values()` — new `modules/lab_lookup.py` vs. adding to an existing module (e.g. `modules/db.py`). Decide during implementation based on where it reads most naturally.
- Whether `symptoms` (health.db) needs its own helper or can be queried directly in `health_dossier.py` given its simple schema (date/symptom/value/category/person/source) — current lean is: query directly, no new module needed, since it's a single straightforward table unlike the multi-source `user_context` join.
- Default `--days` window value and default `max_distance_days` for labs — proposed defaults above (0 and 90) should be confirmed against what's actually useful in practice once tried on real data.
