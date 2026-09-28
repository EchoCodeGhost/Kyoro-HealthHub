**Status correction (Claude review after Mistral's implementation):**
The checkboxes below reflect the actual state, not what Mistral
originally reported (which was completely 0/42, even though much of it
already existed — a known drift pattern in this repo). During the
review, several bugs in the migration itself were also fixed (see commit
notes / docstrings in the affected files):
- The migration scripts targeted a wrong, small test file
  (`data/health_v2.db`) instead of the real `data/health.db` —
  fixed, they now go through `modules.db.open_db()`/`open_medicine_db()`.
- `identity_resolver.py` generated pseudonyms unsalted
  (`sha256(kind:value)`) — given the low cardinality of `device_id`/
  `person`, these were reconstructible from `health.db` via a
  dictionary attack, exactly the threat this change is meant to
  prevent. Fixed: a locally, one-time generated salt in `identity.db`
  (`pseudonym_salt` table), never committed.
- The single large transaction across all tables, as well as the
  "row-count verification" (counted non-NULL values of a column — which
  can never change from an UPDATE), were replaced with a commit per
  table + real total-row-count verification; real collision detection
  (PK-aware, following the `pseudonymize_polar_device_serials.py`
  pattern) was added.
- Not yet **executed** against real data — only verified via
  `--dry-run` against `medicine.db`. The `health.db` migration needs 4.1
  (backup) first and the user's explicit go-ahead before `--execute`.

## 1. Resolver module (foundation)

- [x] 1.1 Create `scripts/modules/identity_resolver.py`: `resolve(kind, real_value) -> pseudo_id`, `reverse(pseudo_id) -> real_value`, `resolve_display_name(pseudo_id) -> str` (for reports)
- [x] 1.2 Extend `identity.db` schema: `device_id_map(pseudo_id, device_id_real, created_at)`, `person_map(pseudo_id, person_real, created_at)` — tables analogous to the existing `device_serial_map`
- [x] 1.3 `registry.json` schema: document `device_registry` entries so that `device_id` is henceforth a pseudonym generated via `identity_resolver` (`manage_registry.py`/`.md`)
- [x] 1.4 Unit tests for `identity_resolver`: determinism (same real value → same pseudonym), reverse resolution, behavior on an unknown pseudonym (`tests/test_identity_resolver.py`, 13/13 green)

## 2. Switch device-type routing to `sensor_type` (before data migration)

- [x] 2.1 Audit: `grep -rn` for semantic `device_id` string comparison in `scripts/compute/*.py`, `scripts/importers/*.py` as an inventory (`scripts/audit_device_id_usage.py`)
- [x] 2.2 `compute_arrhythmia.py`: switch `ALGO_ROUTING` from device-identifier keys to `sensor_type` keys (`SENSOR_TYPE_ROUTING`), resolved via `device_registry.sensor_type()`, with a legacy fallback
- [x] 2.3 `import_polar.py` checked: `_polar_device_for_date`, `DEVICE_H10`/`DEVICE_V3` etc. already read `device_id` dynamically from `_cfg.device_registry` (never hardcoded literal comparisons) — work automatically with pseudonyms after the `registry.json` update (4.6), empirically verified (`DEVICE_V3` → `DEV-394bbcad` etc.). No code changes needed. One exception: `polar_hrv_spot.source` column DEFAULT `'polar_v3'`/`'polar'` — not a target field of this migration (`source` ≠ `device_id`), low priority, to be addressed separately.
- [x] 2.4 `compute_canonical.py` checked: `CONFIDENCE` is keyed by `(canonical_metric, source_app)` — `source_app` values (`polar_connect`, `apple_health`, `garmin_connect`, …) are integration/pipeline names, not one of the pseudonymized target columns (`device_id`/`device`/`person`), and are not affected by this migration. No code changes needed.
- [x] 2.5 `source_priority` checked: no place in the code reads `source_priority.device_id` and compares it against a semantic string — only `seed_source_priority()`/`init_db.py` write to it. In the process, found and fixed a real regression bug: `init_db.py` (fresh DB initialization) wrote `device_id` unpseudonymized into `devices`/`source_priority`, and `_resolve_person()` returned any value other than `'self'`/`'own'` (e.g. `'partner'`) unchanged in plaintext — a repeated `onboard.py` run would have immediately reopened the gap just closed. Both places now go through `identity_resolver.resolve_device()`/`resolve_person()`, verified (`_resolve_person('partner', ...)` → `PER-e1bfd50f`).
- [x] 2.6 Run the existing tests for the modules above — `pytest tests/` green (except for 3 pre-existing, unrelated failures: missing optional deps `pyotp`/`fhir.resources`, one test-order-dependent env test)

## 3. Schema and config preparation

- [x] 3.1 Switch `OWN_PERSON_ID`/`resolve_person()` in `scripts/health_config.py` to pseudonym resolution via `identity_resolver` (the fallback path was removed during review — it would otherwise have produced a second, unsalted pseudonym value inconsistent with the salted resolver)
- [x] 3.2 Check all importer/compute scripts via `grep` audit for the string literal `'self'`/`'partner'` (`scripts/audit_device_id_usage.py`)
- [x] 3.3 Identify analysis/export scripts that currently print human-readable device/person names in reports; added a `resolve_display_name()` call (`analyse_ecg_session.py`) — **spot check, not exhaustively searched** (only one script switched over so far)

## 4. Data migration (existing data)

- [x] 4.1 Create a backup of `health.db`/`medicine.db` — already present and current: `health.db.bak` backup (MD5 identical to `health.db`, created after its last change), `medicine.db.bak` backup
- [x] 4.2 Generate pseudonyms for every `device_id`/`person` value actually present in `health.db`/`medicine.db` (backfill in `identity.db`) — script corrected (`generate_pseudonyms_for_existing_data.py`, previously targeted the wrong DB). Actually run against both DBs (after 4.5): 0 remaining plaintext identifiers found — the actual migration (4.3/4.5) had already pseudonymized all values and created the `identity.db` entries as a side effect, as predicted in the script's docstring. The backfill run merely confirms completeness, no new entries.
- [x] 4.3 Migration script `scripts/migrations/pseudonymize_device_person_identifiers.py` — rewritten during review: real DB via config, commit per table, PK-aware collision detection, real total-row-count verification
- [x] 4.4 `--dry-run` run verified against the real `medicine.db` AND fully against the real `health.db` (79 tables). In the process, found and fixed two real data issues:
      - An old, unsalted `person` value `P-F83C73A3` (from the pre-`identity_resolver` era of `OWN_PERSON_ID`) would, without normalization, have received a DIFFERENT pseudonym than the literal `'self'` — splitting the same person across two pseudonyms across tables. Normalization added (`normalize_person_value()`), verified in `pathogen_exposure_summary` (the only table with both spellings).
      - `'nonexistent'` in `daily_context.person` (several thousand rows since 2017, a legacy artifact from an older `compute_daily_context.py` version) — user confirmed: same person as `'self'`, now under the same normalization.
      - `'unknown'` (schema `DEFAULT`) is deliberately left untouched — no pseudonym, since there's no real person reference.
      - Performance fix: the collision check unnecessarily skipped full table scans when no pseudonyms exist yet (first run) + a temporary index for `UPDATE`/`COUNT` on columns that aren't a prefix of the primary key — previously > 10 min without progress on `measurements`, now < 1 min for all 79 tables.
- [x] 4.5 Migration actually run against `health.db` AND `medicine.db` (user go-ahead received): all 79 + 6 tables committed, 0 errors, 0 data loss. `measurements` (tens of millions of rows) + `ppi_raw` (tens of millions of rows) identical before/after. `daily_context` found several thousand real duplicates in the process (alias collision `'nonexistent'`/`'P-F83C73A3'` on the same day) and correctly cleaned them up. Spot check on `measurements`: no more plaintext `device_id`/`person` values present.
- [x] 4.6 `registry.json` switched to pseudonymized values: several `device_id` and `person` fields in `device_registry` updated, backed up under `registry.json.bak`. Verified: `device_registry.sensor_type()` lookup works with the new pseudonyms (`DEV-394bbcad` → `optical_wrist_gps`), full test suite still green (141/148, the same 7 pre-existing failures as before the migration — missing optional deps + one test-order-dependent test), privacy check green.

## 5. Cleanup & verification

- [x] 5.1 Full test suite (141/148 green, 7 pre-existing unrelated failures) + `tools/qa_check.py` green (all 6 check groups, `docs in sync` regenerated via `tools/gen_docs.py`)
- [x] 5.2 Automated spot check (not just manual): `devices`, `measurements`, `ppi_raw` checked via regex against `^(DEV|PER)-[0-9a-f]{8}$` — 0 plaintext hits after 4.5 **and** after the brand/model fix (see below)
- [x] 5.3 Compatibility check: `resolve_display_name(pseudonym)` still returns the real device name for local reports (verified: `DEV-06cebea0` → `garmin_fenix6`). While testing `analyse_ecg_session.py`, found a **pre-existing, unrelated bug** (wrong `sys.path` depth index in the top-level import, existed before this session/before Mistral's change) — not part of this change, deliberately not fixed alongside, to be reported to the user separately.

## 5b. Additionally found & fixed (not in the original 24 tasks, but a direct consequence of this change's goal)

- [x] **`devices.brand`/`devices.model` sat in plaintext right next to the now-opaque `device_id`** (e.g. `'Polar', 'Vantage V3'`) — would have completely undermined the purpose of the migration for this table (also relevant, among other things, for the `research.json` export profile's `SELECT * FROM devices`). User confirmed: fix this too. Implemented: columns removed from `create_schema.py`, migration `_migrate_devices_drop_brand_model()` in `init_db.py` (fresh-init + `--sync` path), the real `health.db` migrated (columns dropped, no data loss in the remaining columns), `import_cgm.py`/`pseudonymize_existing_devices.py`/`post_import_sanitize.py` adjusted (all three would otherwise have crashed or kept writing plaintext). brand/model remain exclusively local in `registry.json`.
- [x] **Systemic finding**: ~20-30 importer scripts still write `device_id` as a hardcoded literal directly into `measurements`/`ppi_raw`/`devices`, without going through `identity_resolver` (e.g. `import_cgm.py`'s `'libre3'`) — every future import run would have written plaintext again for new rows. The user chose a central fix over touching 20-30 individual files: a new, central safeguard mechanism in `modules/db.py` (`_install_pseudonymization_safeguard()`, called from `open_db()`/`open_medicine_db()`/`open_medicine_imaging_db()`) — registers SQL functions `pseudonymize_device()`/`pseudonymize_person()` and creates an `AFTER INSERT` trigger for every table with a `device_id`/`device`/`person` column that automatically rewrites any still-plaintext value to its pseudonym (idempotent, `CREATE TRIGGER IF NOT EXISTS`). Verified: inserting `'polar_v3'`/`'self'` is automatically turned into `DEV-.../PER-...`; already-pseudonymized values remain unchanged (passthrough). Performance cost measured: ~4× slower on bulk inserts (136k instead of 552k rows/s) — negligible for daily imports, only noticeable on a full historical re-import (minutes instead of seconds).
  - **Important caveat**: the trigger is persisted in the DB file, but the SQL functions are registered per connection — any code that uses `sqlite3.connect()` directly instead of `modules.db.open_db()` will crash on write with `no such function: pseudonymize_person`. Already found and fixed: `tests/manual/test_research_cohort.py` (used raw `sqlite3.connect()`, now switched to `open_db()`). **Not exhaustively checked against every raw `sqlite3.connect()` spot in the repo** — the production import/compute path (all importers, `compute_*.py`) already goes through `open_db()`, remaining risk lies with test/utility scripts outside that path.
  - The `_resolve_person()`/`device_id` write path in `init_db.py` was also fixed (see 2.5) — both mechanisms (trigger + explicit resolver call) now apply in parallel, defense-in-depth.

## 6. Documentation

- [x] 6.1 Create a new section in `docs/PRIVACY_ARCHITECTURE.md` (DE+EN): principle "no human-readable device/person identifier leaves local config"
- [x] 6.2 `CLAUDE.md` extended with a cross-reference to this principle (privacy section)
- [x] 6.3 `db-schema-conventions` and `privacy-rules` specs archived/synced on completion (user go-ahead received): all 3 spec deltas (db-schema-conventions modified, privacy-rules extended, new `identifier-pseudonymization` capability) merged into the main specs via `openspec-sync-specs`, `openspec validate --all --strict` green (14/14), change moved to `archive/pseudonymize-device-person-identifiers/` via `openspec archive --skip-specs -y`.
