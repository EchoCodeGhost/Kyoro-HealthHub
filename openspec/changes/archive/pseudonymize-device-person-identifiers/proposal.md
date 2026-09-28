## Why

Kyoro-HealthHub already pseudonymizes raw hardware serial numbers before
they reach `health.db` (see `scripts/utils/anonymize.py`,
`scrub_polar_json.py`, `pseudonymize_existing_devices.py`) — but the
`device_id` (e.g. `polar_v3`, `polar_m430`) and `person` (`self`/`partner`)
values that remain in `ppi_raw`, `measurements`, `devices`, and
`source_priority` are still human-readable. Anyone reading the database
directly — including an external/remote AI assistant working in this
repository, per the maintainer's explicit requirement — can currently see
which specific device model was worn (revealing e.g. premium sports-watch
ownership) and infer relationship structure (a `partner` person exists).
This was meant to be a foundational privacy principle of this project from
the start, not an afterthought; it has never been documented or enforced.
The underlying principle is broader than these two columns: nothing stored
should allow even a remote inference about the user, their specific
devices, or their home setup (Home Assistant instance, weather station,
etc.) — `device_id`/`person` are the first and highest-impact instances of
this, not the only ones; the resolver module this change introduces
(design.md, Decision 2) is deliberately generic so later identifiers can
be folded in without a redesign.

## What Changes

- Establish "no human-readable device model or person/relationship
  identifier leaves local-only config, ever — not even into `health.db`"
  as a documented architecture principle (new `docs/PRIVACY_ARCHITECTURE.md`
  section + cross-reference from `CLAUDE.md`).
- Introduce opaque pseudonyms for `device_id` (e.g. `DEV-8f3a21`) and
  `person` (e.g. `PER-4c11a0`), generated and stored the same way serial
  pseudonyms already are (`identity.db`, SHA-256-derived, deterministic).
- **BREAKING**: `ppi_raw.device`, `measurements.device_id`, `devices.device_id`
  (currently the table's PRIMARY KEY), and every `person` column across
  health.db switch from semantic strings to opaque pseudonyms.
- Add a local-only, non-exported lookup layer (`~/.config/kyoro/registry.json`
  + `identity.db`, extending the existing serial-pseudonym split) mapping
  pseudonym → `sensor_type`/algorithm-class and pseudonym → real person, so
  device-type-specific code (arrhythmia algorithm routing, wrist-device
  timeline lookup, source priority resolution) keeps working without ever
  needing the semantic name inside the database.
- Migrate every script that currently pattern-matches on semantic
  `device_id`/`person` strings to resolve through this lookup layer instead
  (see Impact).
- Analysis/export scripts that currently print human-readable device/person
  names in reports gain a resolution step (local-only) to keep doctor
  exports and personal reports readable, while the stored data itself stays
  opaque.

## Capabilities

### New Capabilities
- `identifier-pseudonymization`: local-only pseudonym generation, storage,
  and resolution for device and person identifiers, extending the existing
  serial-pseudonymization pattern to cover `device_id` and `person` as well.

### Modified Capabilities
- `db-schema-conventions`: `devices.device_id` primary key and every
  `person` column's meaning changes from a semantic string to an opaque,
  locally-resolvable pseudonym.
- `privacy-rules`: extends the existing "no hardcoded personal identifiers
  in source code" principle to a new, stronger requirement — "no
  human-readable device/person identifiers in stored data either."

## Impact

- **Schema**: `devices` (PK), `ppi_raw.device`, `measurements.device_id`,
  every `person` column in health.db and medicine.db, `source_priority`.
- **Config**: `~/.config/kyoro/registry.json`, `~/.config/kyoro/identity.db`
  (new tables/fields for device/person pseudonyms, alongside the existing
  `device_serial_map`).
- **Device-type-specific routing** (needs the new lookup layer instead of
  string matching): `scripts/compute/compute_arrhythmia.py` (`ALGO_ROUTING`),
  `scripts/importers/import_polar.py` (`_polar_device_for_date`,
  `_POLAR_SERIAL_TO_DEVICE_ID`, `DEVICE_H10`/`DEVICE_V3`/etc.),
  `scripts/compute/compute_canonical.py` (`CONFIDENCE`), `source_priority`
  resolution wherever it's read.
- **Person resolution**: `scripts/health_config.py` (`OWN_PERSON_ID`,
  `resolve_person()`), every importer/compute script that filters by person.
- **Reporting**: `scripts/analysis/*.py` and `scripts/exporters/*` that
  currently print device model / person names need a local-only
  pseudonym→real resolution step to stay human-readable for the maintainer
  without that resolution ever touching the database.
- **Existing data**: one-time migration for all already-imported rows in
  `health.db`/`medicine.db` (large — `ppi_raw`/`measurements` are in the
  tens of millions of rows, per the recent Polar device-tagging cleanup in
  this same session).
