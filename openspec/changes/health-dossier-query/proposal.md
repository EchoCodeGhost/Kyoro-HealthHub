## Why

Kyoro-HealthHub already stores wearable/sensor data, lab values, symptoms, context notes, environmental data (weather, air quality, pollen, home sensors) and GPS stays across health.db, medicine.db and location.db, but each lives behind its own query tool (`context_query.py`, exporter profiles, `location_store.py`) or no query tool at all. There is no single place to ask "what happened on day X (or across weeks Y–Z)?" and get everything the pipeline knows back in one view — forcing manual cross-referencing across databases and scripts, and today's hand-picked table list is already incomplete (the schema has dozens of date-keyed tables: `weather_station`, `air_quality`, `pollen_dwd`, `home_environment`, `self_care`, `nutrition_daily`, `cognitive_tests`, `orthostatic_tests`, and more — new ones get added by importers regularly).

## What Changes

- Add a new `scripts/query/health_dossier.py` script that, given a date (and optional ±N-day window) or a range, assembles everything the pipeline knows for that window. The source list is **data-agnostic by design**, not a hand-maintained enumeration: the script introspects the health.db/medicine.db schemas (`sqlite_master`) for tables carrying a date/`ts` column (and, where present, a `person` column), and queries every matching table for rows in the window — automatically picking up weather, air quality, pollen, home-environment, cosmetics/self-care, nutrition, cognitive/functional tests, and any future table a new importer adds, without a code change to this script. Known non-agnostic special cases stay explicit because they need dedicated logic, not a generic per-table scan:
  - Blood/lab values nearest to the date, not just exact matches (`lab_results`, `lab_manual` in medicine.db) — nearest-value lookup is new logic, not currently exposed anywhere
  - Context notes/tags already aggregated in `user_context` (Oura tags, Garmin GDPR, symptom diaries, Bearable, Apple Health, app outputs generally, etc. — reuses `context_query.py`'s existing same-day join, extended with a date-window parameter)
  - GPS stays/tracks for the day from `location.db` (new thin read wrapper around `location_store.py`; must go through the existing privacy-zone redaction, never bypass it — location rows are explicitly excluded from the generic table scan so redaction can't accidentally be skipped)
  - A best-effort pointer to raw doctor-letter/lab documents (`medicine/arztbriefe/`, `medicine/laborbefunde/`, `medicine/krankenakte/`) whose filename or file-modified date falls in the window — these are unstructured files with no DB linkage today, so this is a heuristic filename/date match, explicitly labeled as "possibly relevant" rather than authoritative
  - Everything else — weather, air quality, pollen, home sensors, cosmetics/self-care, nutrition, cognitive/functional tests, and any later addition — goes through the generic table-scan path above
- Output as structured text (CLI) and optionally JSON, following the existing exporter-profile parameter convention (`:person`, `:date_from`, `:date_to`)
- Support not just a single target date but a date range: an explicit `--from A --to B` range, or relative shorthand `--last <N><unit>` with an **arbitrary** integer `N` and unit `d`/`w`/`m`/`y` (days/weeks/months/years) — e.g. `--last 4w`, `--last 17w`, `--last 4d`, `--last 2y` are all the same code path with a different number/unit, not a fixed list of supported periods — the dossier then covers every day in that span, distinct from the small ±N-day lookaround window used to catch midnight-spanning sessions around a single target date
- Add an opt-in `--llm` flag that sends the assembled dossier (single day or range) to the already-configured LLM provider for a pattern/trend analysis — following the exact same opt-in model as `health_query.py`/`analyse_all.py --llm` (never a silent default, provider configured per `health_config.json`, no remote call unless explicitly requested). Before anything is sent, the data is minimized: GPS stays are reduced to region-level (`location_store.py`'s existing `region_of()`/`stored_region()`, never raw coordinates), the unverified-document section is excluded unless its filenames alone are judged non-identifying, and no diagnosis-name identifiers are introduced into the prompt beyond what already exists in config-driven form.
- **Not in this change**: a calendar-event data source. No importer for calendar data (Apple/Google) exists yet; if the user wants calendar events in the dossier, that requires a separate importer change first. The dossier script will accept calendar data later without redesign (it already groups "by source"), but ships without it.

## Capabilities

### New Capabilities
- `health-dossier`: cross-source lookup that assembles everything the pipeline holds about a given date or date range — measurements, sessions, symptoms, lab values (nearest-date fallback), user-context notes/tags, location stays, and a best-effort pointer to unstructured documents — into one read-only view, respecting all existing privacy/pseudonymization rules of the source data.

### Modified Capabilities
_(none — this reads existing tables through existing or newly-added thin accessor functions; no existing capability's requirements change)_

## Impact

- New file: `scripts/query/health_dossier.py`
- New module function(s) in `scripts/modules/location_store.py` (or a small new helper) to expose a date-window stay/track lookup without duplicating the privacy-zone logic
- Possibly a small extension to `context_query.py`'s query function to accept a day-window instead of only exact-day joins (reuse, not fork)
- Read-only across health.db, medicine.db, location.db — no schema changes, no new tables, no writes
- Filesystem read (not DB) of `medicine/arztbriefe/`, `medicine/laborbefunde/`, `medicine/krankenakte/` for the heuristic document pointer
- No impact on import/compute pipeline order; this is a pure query-side addition
