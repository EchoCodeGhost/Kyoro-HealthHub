## Ultrareview pass

Cloud multi-agent review of the feature commit found 8 real bugs beyond
what the manual end-to-end test caught (see the tasks below for the
original manual-test findings — this is a second, independent pass):
import path broke outside repo root, `--person all` silently dropped
rows for `ecg_samples`/`persons`, the date-column heuristic missed most
real timestamp columns (re-identification risk via unshifted
`ts_start`/`ts_end` etc.), the worker used raw `sqlite3.connect` instead
of `open_db()` (breaks on SQLCipher-encrypted instances), k-anonymity
silently no-op'd when a quasi-identifier column didn't exist on a table,
a failed instance export was swallowed instead of aborting, consent
grant couldn't be re-issued after revocation, plus i18n/doc-translation
nits. All fixed and verified (unit tests extended, manual test re-run,
import fix verified from `/tmp` with no `PYTHONPATH`). Details in the
commit message for this review pass (see git history).

## 1. `master.db` schema: consent table

- [x] 1.1 Extend `scripts/utils/create_master_schema.py`'s `_DDL` string
  with:
  ```sql
  CREATE TABLE IF NOT EXISTS research_consent (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      patient_pseudo  TEXT NOT NULL,
      consent_scope   TEXT NOT NULL,
      consent_given_at TEXT NOT NULL,
      revoked_at      TEXT,
      notes           TEXT,
      FOREIGN KEY (patient_pseudo) REFERENCES patient_number_map(patient_pseudo)
  );
  CREATE INDEX IF NOT EXISTS idx_research_consent_lookup
      ON research_consent(patient_pseudo, consent_scope);
  ```
  `consent_scope` is a free-text label the operator defines per study
  (e.g. `"study-2026-hrv-cohort-a"`) — no fixed enum, mirrors how
  `practice_id` is free text in `patient_number_map`.
- [x] 1.2 Regression check: run `create_or_upgrade()` against an existing
  `master.db` fixture that already has data in `patient_number_map` —
  confirm existing rows survive untouched (idempotent `CREATE TABLE IF
  NOT EXISTS`, no data loss).

## 2. Consent management CLI

- [x] 2.1 New `scripts/utils/manage_consent.py`, same argparse/subcommand
  style as `scripts/utils/manage_patients.py`:
  - `grant --patient <patient_pseudo> --scope <scope> [--notes <text>]`
    → `INSERT INTO research_consent (patient_pseudo, consent_scope,
    consent_given_at) VALUES (?, ?, ?)` with `datetime.now().isoformat()`.
    Refuses (prints error, exit 1) if `patient_pseudo` is not found in
    `patient_number_map`.
  - `list [--patient <patient_pseudo>]` → prints all consent rows
    (optionally filtered), showing scope, given_at, revoked_at (or
    "active").
  - `revoke --patient <patient_pseudo> --scope <scope>` → `UPDATE
    research_consent SET revoked_at = ? WHERE patient_pseudo = ? AND
    consent_scope = ? AND revoked_at IS NULL`. Use `UPDATE`, not `INSERT
    OR REPLACE` (this is a state transition on an existing row, not a
    fresh insert — this is the one legitimate case in this change where
    `UPDATE` is correct and `INSERT OR IGNORE` would be wrong; do not
    "fix" it to INSERT OR IGNORE).
  - SPDX header, `@tier infrastructure`, full `@purpose.de/@purpose.en`,
    `@method.de/@method.en`, `@reads`/`@writes` (`master.db`),
    `@limits.de/@limits.en`, `@usage` docstring block matching the style
    in `scripts/utils/anonymize.py` and `scripts/utils/manage_patients.py`.
- [x] 2.2 Manual test: grant consent for a dummy patient/scope, list it,
  revoke it, list again and confirm `revoked_at` is now set and a second
  `revoke` call on the same row is a no-op (0 rows affected, no crash).

## 3. De-identification helpers

- [x] 3.1 New `scripts/utils/deidentify_cohort.py`:
  - `date_shift_offset_days(patient_pseudo: str) -> int`: deterministic
    per-patient offset, `int(hashlib.sha256(patient_pseudo.encode()).hexdigest()[:8], 16) % 730 - 365`
    (range ±365 days). Pure function, no I/O, easy to unit-test.
  - `shift_date(value: str, offset_days: int) -> str`: parses an ISO
    date or datetime string, adds `offset_days`, returns in the same
    format (date-only in → date-only out; datetime in → datetime out,
    preserving time-of-day and timezone suffix unchanged, only the
    calendar date component shifts).
  - `age_band(birthdate: str, reference_date: str, band_width: int = 5) -> str`:
    returns e.g. `"30-34"`. Never returns or accepts exact age in days/months.
  - `check_k_anonymity(rows: list[dict], quasi_identifiers: list[str], k: int = 5) -> tuple[list[dict], list[dict], dict]`:
    returns `(kept_rows, suppressed_rows, group_size_histogram)`. Groups
    by the tuple of `quasi_identifiers` column values; any group with
    `len(group) < k` goes entirely into `suppressed_rows`.
  - Full bilingual docstring block (SPDX + `@tier` + `@purpose.*` +
    `@method.*` + `@limits.de`: "Datums-Verschiebung ist deterministisch
    pro Patient-Pseudonym, aber nicht aus der Ausgabe rekonstruierbar
    (Einweg-Hash, analog zu `pseudonymize_device_serial`). k-Anonymität
    prüft nur die explizit übergebenen Spalten — keine automatische
    Erkennung identifizierender Felder." / matching `@limits.en`).
- [x] 3.2 Unit tests (new `tests/test_deidentify_cohort.py`, pytest,
  matching existing test conventions in `tests/`):
  - Same `patient_pseudo` → same offset across two calls.
  - Two different `patient_pseudo` values → offsets differ (assert
    inequality for at least a handful of sample pseudonyms — not a
    formal proof, just a smoke test against an accidental constant
    function).
  - `shift_date` round-trips a known date by a known offset and produces
    the exact expected result (fixed-offset test case).
  - `check_k_anonymity` with a synthetic 20-row fixture where one
    quasi-identifier combination appears 3 times (< k=5) and another
    appears 8 times (≥ k=5): assert the 3-row group is entirely in
    `suppressed_rows` and the 8-row group is entirely in `kept_rows`.

## 4. Cohort export orchestrator

**Verification addendum (Claude):** Mistral's original
submission had `[x]` on all tasks in this and section 5, but the
actual test run (not just diff review) failed. Bugs found and
fixed:
1. `_run_instance_export` set `KYORO_ACTIVE_PATIENT_DIR` repeatedly
   within the same process (looping over instances) — ineffective,
   because `scripts/health_config.py` computes `KYORO_CONFIG_DIR` as a
   module constant on first import (`sys.modules` caching). Fixed: a new
   worker subprocess `scripts/exporters/_export_instance_worker.py`,
   started once per instance with the env var in its own process
   environment (result returned as JSON over stdout to the
   orchestrator).
2. `args.person` was referenced but never defined via `argparse` —
   added `--person` with a default of `"all"`.
3. `export_root` (the date directory) was never created when no row was
   kept/suppressed (empty test instances) — `manifest.json` failed with
   `FileNotFoundError`. Fixed: `export_root.mkdir(...)` before writing
   the manifest.
4. Found and fixed a pre-existing, unrelated bug in
   `scripts/export_health.py`'s `run_query()`: when `person == "all"`,
   the bound parameter `:person` was unconditionally removed from
   `params`, even when the regex substitution (only for the pattern
   `person = :person`) didn't apply at all (e.g. for `person_id =
   :person` in `research.json`'s `persons` query) — leading to
   `sqlite3.ProgrammingError: You did not supply a value for binding
   parameter :person`. Fixed: only pop the parameter when `:person` was
   actually removed from the SQL text.
5. `tests/manual/test_research_cohort.py` never provisioned the dummy
   instances with a real schema/config — `scripts/utils/init_db.py` is
   NOT suited for this (see the separate bug finding below) and was not
   used; the test file now creates the schema directly via
   `create_schema.SCHEMA`. Additionally added a new Test 4 with real
   `measurements` rows that actually verifies date shifting AND
   k-anonymity suppression with real data (previously only tested with
   empty DBs — which proved nothing about the actual core
   functionality).

**Separate finding, also fixed in the meantime (at the
user's request to "look into it" / "fix it", outside the original scope
of this change, but directly blocking for any real patient
onboarding):** The complete onboarding of a new patient instance
(`onboard.py` with `KYORO_ACTIVE_PATIENT_DIR` set, as documented in
`docs/CLINIC_DEPLOYMENT.md`) was thoroughly broken — four related bugs,
all traceable to the same pattern (`Path.home()`/a hardcoded repo path
instead of `KYORO_CONFIG_DIR`/`Config().db_path`):
1. `onboard.py`: `CONFIG_DEST = Path.home() / ...` instead of
   `KYORO_CONFIG_DIR` — always wrote the config into the REAL operator
   config, never into the instance. Fixed: `KYORO_CONFIG_DIR` imported
   and used; additionally a new `DATA_ROOT` variable
   (= `KYORO_ACTIVE_PATIENT_DIR` if set, otherwise `REPO_ROOT`) for
   `REQUIRED_DIRS` (imports/, data/staging/, analyses/), and the copied
   config is now automatically rewritten in instance mode (prefix
   `~/Kyoro-HealthHub` → the actual instance path).
2. `scripts/utils/init_db.py`: `db_path = ROOT / "data" / "health.db"`
   hardcoded against the repo root — fixed to `Config().db_path`.
3. `scripts/utils/create_identity_schema.py`: `_IDENTITY_DB =
   Path.home() / ...` — the identical pattern, fixed to
   `KYORO_CONFIG_DIR / "identity.db"`. (Contradicts an earlier
   verification pass for task 2a.6, which had incorrectly classified
   this file as already correct.)
4. `scripts/health_config.py`: `Config`'s path properties never called
   `.expanduser()` — a literal `~` in a config value (as in the shipped
   template) would never have worked, instead creating a folder literally
   named `~`. Fixed defensively (`.expanduser()` on `db_path`,
   `medicine_db_path`, `medicine_imaging_db_path`, `data_root`,
   `analyses_dir`, `manual_dir`, `polar_dir`, `apple_xml`).
5. `docs/CLINIC_DEPLOYMENT.md`/`_DE.md`: consistently outdated path
   `kyoro-patients/PT-XXXX` (assuming a subfolder in the repo) instead
   of the actual `~/.config/kyoro-master/patients/PT-XXXX` (since the
   `KYORO_MASTER_DIR` refactor) — this also
   affected the documented onboarding command (`cd kyoro-patients/...;
   python3 ../../scripts/onboard.py`, which pointed nowhere) and the
   `manage_patients.py add` call syntax (the docs showed two positional
   arguments, the actual CLI requires `--practice-id`). All occurrences
   in both language versions corrected.

**Verified** (not just diff review): real onboarding of a new instance
played through end to end (registration → `onboard.py` with
`KYORO_ACTIVE_PATIENT_DIR` → config/health.db/identity.db/imports/
correctly scoped to the instance, real operator config/identity.db
unchanged), single-user regression without `KYORO_ACTIVE_PATIENT_DIR`
checked (behavior unchanged), full `pytest` suite (56 existing tests)
green, the new cohort-export test still green, `check_source_privacy.py`
green.

- [x] 4.1 New `scripts/exporters/export_research_cohort.py`, argparse CLI:
  ```
  python3 scripts/exporters/export_research_cohort.py \
      --scope study-2026-hrv-cohort-a \
      --profile research \
      --quasi-identifiers age_band,gender \
      --k 5 --age-band-width 5 \
      --date-from 2020-01-01 --date-to 2026-12-31
  ```
  Steps the script performs, in order:
  1. Open `master.db`, query all `active = 1` rows from
     `patient_number_map`.
  2. For each, query `research_consent` for a matching
     `(patient_pseudo, consent_scope=--scope)` row with `revoked_at IS
     NULL`. Partition instances into `consented` / `excluded`.
  3. **If `excluded` is non-empty: abort before any output is written.**
     Print the list of excluded `patient_pseudo` values and the reason
     (no consent row / revoked). Exit code 1. (Per spec requirement
     "Consent-gated instance inclusion" — this is a hard gate, not a
     warning-and-continue.)
  4. For each consented instance: set `KYORO_ACTIVE_PATIENT_DIR` to its
     `instance_dir` for the duration of that instance's export (subprocess
     or explicit env-var scoping — follow the same pattern
     `serve_instance_tools.py` uses for single-instance activation), call
     `load_profile(args.profile)` and `export_profile(...)` from
     `scripts.export_health` (import, don't shell out — reuse the Python
     functions directly) to get the per-instance rows.
  5. Apply `deidentify_cohort.shift_date` to every date/datetime field in
     every row (iterate profile query result columns; a field is treated
     as a date field if its column name ends in `_at`, `date`, or
     matches `^ts$`/`^datetime$` — reuse whatever date-column convention
     `export_health.py` already uses if one exists, otherwise this
     naming heuristic).
  6. Apply `deidentify_cohort.age_band` wherever a birthdate field is
     present in a query result (the `persons` query in `research.json`
     does not currently expose birthdate — confirm during implementation
     whether any profile query does; if none does, this step is a no-op
     today but the function must exist for when one does).
  7. Merge all instances' rows per query name into one combined
     `list[dict]` per query, tagging each row with its `patient_pseudo`
     (never the real `patient_number` or any real identifier).
  8. Run `deidentify_cohort.check_k_anonymity` on the merged rows using
     `--quasi-identifiers` and `--k`.
  9. Write kept rows to
     `KYORO_MASTER_DIR/research_exports/<today ISO date>/<query_name>.csv`
     (reuse `write_output`'s CSV logic from `export_health.py` if it's
     factored for reuse; otherwise a minimal equivalent — do not
     duplicate a second CSV-writing convention).
  10. Write suppressed rows to the same run directory under
      `suppressed/<query_name>.csv` (NOT part of the deliverable — document
      this distinction in the script's own `--help` text and in
      `docs/CLINIC_DEPLOYMENT.md`).
  11. Write `manifest.json` in the run directory: `scope`, `profile`,
      `k`, `age_band_width`, `quasi_identifiers`, `instances_included`
      (count only, not pseudonyms — the manifest ships with the
      deliverable), `instances_excluded_count`, `rows_suppressed` (per
      query name), timestamp. Per spec: **no date-shift offsets and no
      patient pseudonyms in this file.**
  12. Print the pre-suppression group-size histogram to stdout (per spec
      "Cohort too small overall" scenario) before step 9 writes anything.
- [x] 4.2 SPDX header + full bilingual docstring block (same tags as
  above) on `export_research_cohort.py`.
- [x] 4.3 (N/A — checked: `export_health.py` never logs to `import_log`
  either, so per this task's own instruction there is no existing
  pattern to follow for exporters.) Log the run in `import_log`-equivalent tracking if such a
  pattern exists for exporters (check whether `export_health.py` already
  logs runs anywhere; if it does, follow the same pattern for
  consistency; if it doesn't, do not invent one for this script alone).

## 5. Manual end-to-end verification (do this, not just code review — diff-review alone has missed real bugs in this project before)

- [x] 5.1 Create 3 dummy patient instances via `manage_patients.py`
  (reuse the existing test pattern from
  `tests/manual/test_verification.py`, with `$HOME` redirected to a temp
  dir before any `health_config` import, exactly like that file already
  does — do not run this against the operator's real
  `~/.config/kyoro-master/`).
- [x] 5.2 Grant consent for 2 of the 3, leave the third without consent.
  Run `export_research_cohort.py` and confirm it aborts, naming the third
  patient as excluded, and writes no output directory at all.
- [x] 5.3 (Covered by Test 4 in `tests/manual/test_research_cohort.py`,
  added during ultrareview follow-up; per-patient offset
  determinism additionally unit-tested in
  `test_date_shift_offset_days_deterministic`.) Grant consent for all 3. Seed each instance's `health.db` with a
  handful of rows across a few different dates. Run the export again;
  confirm: three instances' data present in the merged CSVs tagged by
  `patient_pseudo`; dates are shifted (not equal to the original seeded
  dates); a re-run produces identical shifted dates for the same patients
  (determinism check per spec).
- [x] 5.4 (Covered by Test 4c in the same manual test — steps/heart_rate
  split proves suppression on real seeded data.) Seed the 3-instance dummy cohort so exactly one age_band/gender
  combination has only 2 matching rows (< default k=5); confirm those
  rows land in `suppressed/` and not in the deliverable CSVs, and that
  the histogram is printed before any file is written.
- [x] 5.5 Revoke one of the 3 consents after data has already been
  exported once; confirm a second export run now excludes that patient
  (revocation takes effect going forward) while not attempting to alter
  or delete the prior run's already-written directory (revocation is not
  retroactive deletion — out of scope here, document this if not already
  obvious from the design).

## 6. Documentation & compliance

- [x] 6.1 (Done, both languages, includes the missing-QI
  warning behavior added during the ultrareview fix pass.) New section in `docs/CLINIC_DEPLOYMENT.md` (English) and
  `docs/CLINIC_DEPLOYMENT_DE.md` (German, written first or in parallel —
  follow whichever file-ordering convention the rest of this doc pair
  already uses) titled "Research cohort export" / "Forschungs-
  Kohortenexport": consent workflow (`manage_consent.py grant/list/
  revoke`), running the export, reading the manifest, what "suppressed"
  means and why those rows are kept locally but never delivered, and the
  known limitation that date-shifting removes cross-patient temporal
  alignment (link back to this change's `design.md` risk section for the
  full rationale, or inline a short version).
- [x] 6.2 `python3 scripts/utils/check_source_privacy.py` exits 0 against
  all new files.
- [x] 6.3 `openspec validate --changes` green for this change.
- [x] 6.4 Run `tools/gen_docs.py` (or whatever regenerates
  `docs/de/utils/*.md` / `docs/en/utils/*.md` from docstring tags) so the
  new scripts get their generated doc pages, matching how
  `serve_instance_tools.py` got `docs/de/utils/serve_instance_tools.md` /
  `docs/en/...` when it was added (see git history).
