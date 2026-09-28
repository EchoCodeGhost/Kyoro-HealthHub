## Context

Serial numbers are already pseudonymized before they reach `health.db`
(`scrub_polar_json.py` scrubs raw export files in place; `identity.db`
holds the real-serial↔pseudonym mapping; `registry.json` holds only the
pseudonym once scrubbing has run — see this session's device-tagging
cleanup for the full mechanics). `device_id` (e.g. `polar_v3`) and
`person` (`self`/`partner`) are the two remaining human-readable
identifiers that still land in `health.db`/`medicine.db` in the clear.

Both are used pervasively, not just as inert labels:
- `device_id` drives algorithm selection (`ALGO_ROUTING` in
  `compute_arrhythmia.py` picks a chest-strap vs. optical-PPG algorithm
  based on the device_id string), device-timeline lookups
  (`_polar_device_for_date`), and `source_priority` resolution.
- `person` drives every per-person filter across the pipeline
  (`OWN_PERSON_ID`, `resolve_person()`), and multi-person households
  (self + partner) need it to stay meaningful locally.

Both need to keep working *semantically* for local processing while never
storing the semantic string itself in `health.db`.

## Goals / Non-Goals

**Goals:**
- No `health.db`/`medicine.db` row ever contains a human-readable device
  model name or a person/relationship label — only opaque pseudonyms.
- Device-type-specific algorithm routing and per-person filtering keep
  working exactly as before, functionally — only the identifier's
  *representation* changes, not the logic.
- Local-only reports (analysis output, doctor exports) remain
  human-readable for the maintainer, resolved just-in-time, never
  round-tripped through the database.
- Migration is safe for existing data: no silent data loss, verifiable
  row counts before/after (same discipline as this session's
  `pseudonymize_polar_device_serials.py` cleanup).

**Non-Goals:**
- Not re-designing the EAV schema itself (measurements/ppi_raw shape stays).
- Not pseudonymizing metric *values* (heart rate numbers, symptom text) —
  only the device/person identifier columns.
- Not addressing `medicine.db`'s clinical text tables' broader PII handling
  beyond the `person` column (out of scope; separate concern).
- Not tackling the git-history/backup-file angle (old `.bak` files, this
  session's `data/health.db.bak.19072026`, etc. keep whatever they had —
  covered by normal repo/backup hygiene, not by this change).

## Decisions

### 1. Pseudonym format and generation: extend the existing serial pattern
Use the same deterministic SHA-256-derived approach already implemented
in `utils/anonymize.py` (`pseudonymize_device_serial`), with distinct
prefixes so a pseudonym's *kind* is still locally inferable without
decoding it: `DEV-XXXXXXXX` for device_id, `PER-XXXXXXXX` for person.
Rationale: proven pattern already in production for serials; deterministic
means re-running import/migration code is idempotent (same real value
always maps to the same pseudonym, so `INSERT OR IGNORE` dedup still
works); reusing the mechanism means one identity store, not three.

Alternative considered: random (non-deterministic) pseudonyms with an
explicit mapping table only. Rejected — breaks idempotent re-import
(`INSERT OR IGNORE` on `(datetime, pulse_ms, device, person)` needs the
same device pseudonym every time the same real device is seen again).

### 2. Where the real↔pseudonym mapping lives: one module, extend `identity.db`
Add `device_id_map(pseudo_id, device_id_real, created_at)` and
`person_map(pseudo_id, person_real, created_at)` tables to the existing
`~/.config/kyoro/identity.db` (already used for `device_serial_map` and
`account_pseudo_map`) — never in `health.db`. `registry.json`'s
`device_registry` entries gain a `device_id` that *is* the pseudonym from
the start (mirroring how `serial` already works after `scrub_polar_json.py`).

All lookups (device→pseudonym, person→pseudonym, and the reverse
resolution for reports, Decision 5) go through one new module —
`scripts/modules/identity_resolver.py` — the same "single access point"
pattern `modules/db.py` already establishes for DB connections. No script
reads `identity.db`/`registry.json` directly for identity resolution;
everything calls this module. This is also where the scope widens beyond
device/person: per the maintainer's explicit framing, the underlying
principle is broader than these two columns — *no locally-identifying
value should be inferable from stored data*, which also covers the Home
Assistant instance identifier, weather-station identifier, and any future
"which specific piece of my home setup was this" value. `identity_resolver`
is designed as a generic pseudonym-registry module (`resolve(kind, real) ->
pseudo`, `reverse(pseudo) -> real`) with `device`/`person` as the first two
`kind`s, not a device/person-specific one-off, so extending it to
`home_assistant_instance` or `weather_station` later is additive, not a
redesign.

### 3. Algorithm/routing lookup: pseudonym → sensor_type, resolved once per process
Code that currently branches on semantic device_id strings (`ALGO_ROUTING`,
`DEVICE_H10`/`DEVICE_V3` constants, `_polar_device_for_date`) switches to
branching on **`sensor_type`** (already a `device_registry` field:
`chest_strap`, `optical_wrist`, `optical_wrist_gps`, etc.) instead of the
device_id string itself. A single lookup (`registry.json` → pseudonym →
sensor_type, cached per process) replaces every place that currently does
`if device_id == "polar_v3"`-style matching. This is strictly better even
independent of pseudonymization: routing on `sensor_type` is what these
places actually mean semantically ("this is a chest-strap ECG device"),
not "this is specifically a Vantage V3" — the current code conflates the
two. Where genuinely device-specific behavior is needed (not just sensor
class), the lookup table can carry a device-specific config field instead
of relying on string identity.

Alternative considered: keep device_id semantic, only pseudonymize
`person`. Rejected per explicit requirement — the maintainer wants device
model hidden too (a specific premium-watch model can itself be
identifying/profiling information).

### 4. Person resolution: same pattern, `OWN_PERSON_ID` becomes a pseudonym
`health_config.get_own_person_id()` returns the pseudonym (`PER-...`)
instead of resolving `'self'`/`'own'` to a semantic string. `resolve_person()`
keeps its interface (`'self'`/`'partner'` as *config-time* convenience
inputs, per `templates/health_config.example.json`'s existing "max"
placeholder pattern) but resolves to the pseudonym before anything touches
the database — exactly the boundary that already exists today for
`OWN_PERSON_ID`, just pointing at a pseudonym instead of a literal.

### 5. Reporting stays readable: resolve at render time, not at storage time
Analysis scripts and doctor exports call a new
`resolve_display_name(pseudo_id)` helper (reads `identity.db` locally,
never touches the network) exactly at the point of writing a report/plot
title — the resolved name never gets written back into any table.

## Risks / Trade-offs

- [Massive one-time migration across tens of millions of rows] →
  Mitigate with the same verify-before/after-counts discipline used for
  the Polar device-tagging cleanup this session; run in a transaction per
  table; keep a `.bak` copy of `health.db`/`medicine.db` before starting
  (established convention already used in this repo, e.g.
  `health.db.bak.19072026`).
- [Every compute/analysis script that currently does semantic string
  matching needs to be found and migrated — easy to miss one] →
  Mitigate with `grep -rn` audit for `device_id ==`/`person ==`/`'self'`
  literal comparisons as a pre-migration inventory step (tasks.md), and
  `check_source_privacy.py`-style compliance check extended to flag any
  remaining semantic device/person literal in source.
- [`sensor_type`-based routing loses genuinely per-device nuance for a few
  edge cases (e.g. calibration thresholds tuned to one specific watch
  model, not just its sensor class)] → Where that's真 needed, the
  device_registry lookup carries an explicit per-device config field
  (already the pattern for `regulatory` metadata) rather than
  reintroducing string identity checks.
- [Existing exports/backups/reports created before this change still have
  human-readable identifiers] → Out of scope (Non-Goals); document as a
  known gap in the new `docs/PRIVACY_ARCHITECTURE.md` section.

## Migration Plan

1. Schema: add pseudonym columns/tables (`identity.db` extensions), keep
   old semantic columns temporarily alongside for verification.
2. Backfill: generate pseudonyms for every existing `device_id`/`person`
   value seen in `health.db`/`medicine.db` + `registry.json`.
3. Code migration: switch routing logic to `sensor_type`-based lookup
   (Decision 3) — this can and should land *before* the data migration,
   verified against the still-semantic data, to de-risk the two changes.
4. Data migration: `UPDATE` existing rows old→pseudonym (mirroring this
   session's `pseudonymize_polar_device_serials.py` UPDATE/dedup pattern),
   table by table, with row-count verification.
5. Cut over `registry.json`/`OWN_PERSON_ID` to emit pseudonyms for all
   *future* imports.
6. Remove the temporary semantic columns once verified.
7. Document the principle in `CLAUDE.md` + new
   `docs/PRIVACY_ARCHITECTURE.md`, extend `check_source_privacy.py`.

Rollback: restore from the pre-migration `.bak` copy; the pseudonym
generation is deterministic and additive up to step 6, so most of the
migration is reversible until the old columns are actually dropped.

## Open Questions

- Should `sensor_type`-based routing fully replace `ALGO_ROUTING`'s current
  keying, or does the arrhythmia routing need a finer-grained
  "device class" distinct from `sensor_type` (e.g. two `optical_wrist_gps`
  devices with different validated algorithms)? Needs a closer read of
  `compute_arrhythmia.py`'s `ALGO_ROUTING` before finalizing Decision 3.
- Exact scope of `medicine.db`'s `person`-equivalent columns (does the
  clinical side use the same `OWN_PERSON_ID` convention throughout, or are
  there additional identifier columns to inventory there too?).
- Whether report/export resolution (Decision 5) needs a config toggle
  (some doctor exports may *want* the device model named for clinical
  context, e.g. "measured via chest-strap ECG" — needs the maintainer's
  input on which exports keep semantic device mentions vs. generic
  "chest-strap" phrasing).
