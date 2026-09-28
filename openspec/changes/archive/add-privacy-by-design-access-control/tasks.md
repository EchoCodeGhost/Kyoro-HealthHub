## 1. Prerequisite (needs explicit user confirmation — git history operation)

- [x] 1.1 Diff both stale worktree branches' `pwa/` state, confirm which is more current (done — only one of the two branches had `pwa/` at all, no divergence to resolve)
- [x] 1.2 Restore `pwa/` onto `main` via `git checkout <branch> -- pwa/` + new commit (done, commit "Restore pwa/ (Kyoro SymptomTrack) onto squashed main")

## 2. Patient registry & instance isolation (Kyoro-HealthHub)

- [x] 2.1 `patient_number_map` table added to `scripts/utils/create_identity_schema.py` (Mistral)
- [x] 2.2 `KYORO_ACTIVE_PATIENT_DIR` wired into `scripts/health_config.py`, all `Path.home()` defaults updated (Mistral; 2 stale fallbacks in `medicine_db_path`/`medicine_imaging_db_path` fixed by Claude)
- [x] 2.3 Regression check: behavior unchanged without the env var set — verified via `tests/manual/test_regression_no_env.py` (Claude)
- [x] 2.4 `scripts/utils/manage_patients.py` (`add`/`list`/`activate`/`deactivate`) implemented (Mistral)

## 2a. CRITICAL — instance-isolation gap in 34 existing files (highest priority, blocks 2.5/2.6 and any Track B verification)

- [x] 2a.1 `KYORO_MASTER_DIR` constant added to `scripts/health_config.py` (always real operator home, never follows `KYORO_ACTIVE_PATIENT_DIR`) (Mistral, verified by Claude)
- [x] 2a.2 `patient_number_map` removed from `identity.db` schema (`create_identity_schema.py`); new `scripts/utils/create_master_schema.py` creates `master.db` under `KYORO_MASTER_DIR` with `patient_number_map` + `practice_devices` tables (Mistral)
- [x] 2a.3 `scripts/utils/manage_patients.py` repointed from `identity.db`/`~/kyoro-patients/` to `master.db`/`KYORO_MASTER_DIR/patients/` (Mistral)
- [x] 2a.4 `pwa/backend/auth.py`'s `AUTH_FILE` explicitly repointed to `KYORO_MASTER_DIR` (Mistral)
- [x] 2a.5 All ~32 remaining files switched to import `KYORO_CONFIG_DIR` from `health_config.py` (Mistral; verified by Claude — `_KEY_FILE` in `modules/db.py` now confirmed to follow `KYORO_ACTIVE_PATIENT_DIR`; one leftover duplicate import in `manage_medications.py` cleaned up)
- [x] 2a.6 Exception confirmed: `scripts/utils/create_identity_schema.py` correctly stays on `KYORO_CONFIG_DIR` (instance-scoped pseudonym maps)
- [x] 2a.7 Regression check added in `check_source_privacy.py` — verified it actually flags a reintroduced `Path.home()/.config/kyoro` violation (Mistral implementation, Claude verification)
- [x] 2.5a `scripts/utils/manage_practice_devices.py` writes to `master.db`'s `practice_devices` table (Mistral, verified by Claude)
- [x] 2.5b `manage_patients.py cmd_add` interactive device-copy prompt (Mistral — was already implemented but missed during that review; found and end-to-end verified by Claude: added a device to the catalog, created a patient, confirmed the prompt, confirmed the device landed in the new instance's `device_registry`). One real bug fixed alongside: `manage_practice_devices.py cmd_add` used `INSERT OR REPLACE`, which the project's own `db-schema-conventions` spec explicitly forbids — replaced with a proper `ON CONFLICT ... DO UPDATE` upsert.

## 3. Authorization broker (Kyoro SymptomTrack backend, after restore)

- [x] 3.1 `patient_assignments` table added (default-deny) (Mistral)
- [x] 3.2 `access_log` table added (reads, writes, denied attempts) (Mistral)
- [x] 3.3 Authorization check added before instance activation (`authz.py`, Mistral)
- [x] 3.4 `pwa/backend/db.py`'s global `_PERSON` constant replaced with request-scoped resolution (Mistral; Claude fixed 2 follow-on bugs this surfaced — stale table names `pwa_migraine_live`/`pwa_afib_live` renamed consistently from `pwa_pwa_*`, and a missing `patient_pseudo` binding in `get_afib_history`'s SQL params)
- [x] 3.5 TOTP setup tested end-to-end (QR code → authenticator app → login) — verified via `tests/manual/test_totp_setup.py` (Claude); real QR-code-scan-by-human step still recommended before go-live as a final sanity check, but the code path (secret generation → TOTP verification → JWT issuance → JWT verification) is now proven correct

## 3a. Bugs found during end-to-end verification (not caught by code review alone)

- [x] 3a.1 `pwa/backend/main.py`: SyntaxError in 6 routes (required `body` param placed after a defaulted `patient_pseudo` param) — file didn't compile. Fixed by reordering parameters.
- [x] 3a.2 `pwa/backend/main.py`: 17 routes had an invalid double `Depends()` declaration (`user: WritableUser = Depends(require_write)` when `WritableUser` is already `Annotated[..., Depends(require_write)]`) — FastAPI raises `AssertionError` at app-load time. Fixed by removing the redundant `= Depends(...)` defaults and re-ordering parameters again (no-default params must precede defaulted ones).
- [x] 3a.3 `pwa/backend/db.py`: `get_conn()`'s row_factory selection checked only whether `sqlcipher3` is importable, not whether the actual connection object is a sqlcipher3 connection — breaks `.fetchone()` whenever `sqlcipher3` is installed but no `db_key` is configured. Fixed to check `isinstance(conn, sqlite3.Connection)`.
- [x] 3a.4 `scripts/utils/manage_patients.py`: crashed with "no such table: patient_number_map" on a fresh install since nothing called `create_master_schema.create_or_upgrade()` before use. Fixed: self-heals on import.
- [x] 3a.5 `pwa/backend/requirements.txt`: missing `python-multipart`, required by the attachment-upload endpoint. Added.
- [x] 3a.6 Mistral's own verification scripts had left real test patients/users in the operator's real `~/.config/kyoro-master/` from a prior run — cleaned up, and all three scripts moved to `tests/manual/` with `$HOME` redirected to a temp dir before any `health_config`/`auth`/`db` import for future isolation.

## 4. Tool gating

- [x] 4.1 (Done; bookkeeping fix — checkbox was never updated after implementation.) **Concretized (Claude) — ready for implementation.** New `scripts/utils/serve_instance_tools.py`: requires `KYORO_ACTIVE_PATIENT_DIR` to be set (aborts otherwise), starts `datasette serve <instance>/data/health.db` as a subprocess for `datasette` subcommand; prints the per-instance Grafana config path for `grafana-config` subcommand (no automatic Grafana start — installation-specific). Full working code in the local clinic multi-patient plan, section 2.1. Also update `docs/CLINIC_DEPLOYMENT_DE.md`'s "Tool-Integration" example commands to match.
      **Update:** the `grafana-config` subcommand was removed.
      It only ever printed a config path and never actually integrated
      Grafana (no bundled dashboard/datasource config, no automatic start),
      while `cmd_datasette` — the part that actually did something — never
      handled SQLCipher decryption, so it would have failed against a real
      encrypted instance DB (instances are encrypted by default, see
      `CLINIC_DEPLOYMENT.md`). Decision: drop the Grafana stub rather than
      finish it, and point to self-service setup in
      `CLINIC_DEPLOYMENT.md`/`CLINIC_DEPLOYMENT_DE.md` instead. The
      "gated at instance selection, not per-tool" principle (this
      change's core design decision, see `design.md`) still covers a
      self-configured Grafana exactly the same way. **Update:**
      the `datasette` subcommand's missing decryption handling was also
      fixed — `cmd_datasette()` now resolves `db_path`/`db_key` via
      `health_config.load()` (correctly relative to
      `KYORO_ACTIVE_PATIENT_DIR`) and decrypts through the new shared
      `scripts/modules/datasette_utils.py` before serving, with a
      per-instance-unique temp filename. Verified end to end against a
      real SQLCipher-encrypted test database.

## 5. Documentation

- [x] 5.1a `docs/CLINIC_DEPLOYMENT_DE.md` written (Mistral, originally as `docs/CLINIC_DEPLOYMENT.md` with no `_DE` suffix — renamed by Claude to match project convention); extensive "Nebenläufigkeit verstehen" section added by Claude explaining the CLI-env-var vs. web-per-request-parameter split with a concrete clinic-morning walkthrough.
- [x] 5.1b (Done — `docs/CLINIC_DEPLOYMENT.md` (EN) exists,
  links switched.) **Mistral's task:** write the English `docs/CLINIC_DEPLOYMENT.md` (faithful translation of `_DE.md`, same structure/sections/code examples including "Nebenläufigkeit verstehen"). Then: remove the "(noch ausstehend — siehe plan...)" qualifier from the German file's language banner; add a `> **German version:** [CLINIC_DEPLOYMENT_DE.md](CLINIC_DEPLOYMENT_DE.md)` banner to the new English file; and switch the three transitional links (in `README.md`'s "Multi-person support" bullet, `docs/ARCHITECTURE.md`'s design-principle #2, optionally `README_DE.md`) from `CLINIC_DEPLOYMENT_DE.md` back to `CLINIC_DEPLOYMENT.md` (EN).
- [x] 5.2 README/ARCHITECTURE wording finalized to reflect actually-achieved state (Mistral; Claude corrected stale "geplant, noch nicht gebaut" wording in README_DE.md/ARCHITECTURE_DE.md that Mistral's pass had missed, and fixed all `CLINIC_DEPLOYMENT.md` links to point at the file that actually exists)

## 6. Verification

- [x] 6.1 Two dummy patients, two test users (one authorized, one not) — unauthorized attempt denied and logged. Verified via `tests/manual/test_verification.py` (Claude, after fixing bugs in 3a that blocked this from ever passing)
- [x] 6.2 `openspec validate --changes` green
- [x] 6.3 `python3 tools/qa_check.py` + `python3 scripts/check_compliance.py` green (new compliance findings reviewed individually and approved as false positives — generic terms like "patient"/"Praxis"/"Klinik"/"Diagnose" in new docstrings, no real personal data)

## 7. Production hardening (closes the gap repeatedly flagged since 6.1: "code-complete, passed one dummy smoke test" is not the same claim as "tested"/"hardened")

Context: task 6.1's `tests/manual/test_verification.py` proves the broker
denies an unauthorized request in one narrow, synthetic, single-process
scenario (2 dummy patients, 1 authorized + 1 unauthorized user). It does
**not** establish that the system behaves correctly under real
concurrency, under adversarial input, or with a real human doing the
TOTP enrollment step. Do not mark this change fully hardened — or use it
for real patient data at clinic/research scale — until this section is
done and each item's actual observed result (not just "ran without
crashing") is recorded here.

- [x] 7.1 **Concurrency/load test.** (Claude, after 7.2a-d were
  fixed.) Ran an ad-hoc `asyncio`+`httpx` script (repo already depends on
  `httpx`, no new dependency added) from a fully isolated `$HOME`
  (`tempfile.mkdtemp`, same pattern as `tests/manual/`) so no real
  patient/user data touched the operator's `~/.config/kyoro-master/`;
  temp dir removed at the end of every run. For each run: created N
  dummy patients via `manage_patients.py add`, created 2 API users each
  assigned to a disjoint half of the patients (so any cross-contamination
  would be directly observable), started `uvicorn main:app` once, fired
  concurrent `GET /api/entries/{date}` requests with `Authorization:
  Bearer <api_key>` round-robining across (user, patient) pairs.
  Verified after each run: (a) every returned symptom entry's
  patient-tagged marker matched the `patient_pseudo` requested — **0
  cross-contamination in any run**; (b) every non-denied `access_log` row
  was attributed to a `(user_id, patient_pseudo)` pair that actually has
  an assignment — **0 misattributions in any run**; (c) latency/error
  behavior vs. N (see below — a real global-lock effect WAS found and is
  reported honestly, not hidden).
  **Results:**
  - N=20 patients, 200 fully-concurrent requests: 0.75s wall clock,
    **265 req/s**, **0 errors**, p50/p95 latency 457ms/572ms.
  - N=100 patients, 100 fully-concurrent requests (1 request/patient —
    a realistic "everyone hits refresh at the same instant" clinic
    morning-rush scenario): 0.71s wall clock, **140 req/s**, **0
    errors**, p50/p95 latency 264ms/400ms.
  - N=100 patients, 1000 fully-concurrent requests (10x oversubscription
    — a deliberately adversarial stress level, not a realistic clinic
    load): 14.1s wall clock, **71 req/s**, **0 errors after raising the
    test client's own timeout to 60s** (with a 10s client timeout, ~27%
    of requests hit a client-side read timeout — no server error, no
    wrong data, just genuine queuing), p50/p95 latency **9.9s/11.0s**.
    This confirms non-linear latency growth with N *is* present at this
    adversarial concurrency level, but it is the documented, deliberate
    `BEGIN IMMEDIATE` serialization from the 7.2a fix (see authz.py
    comments) — not a lock accidentally affecting unrelated patients'
    correctness, and not silent corruption. It reflects a real, inherent
    limit of this project's single-SQLite-file architecture (every
    request, including reads, now writes one `access_log` row per 7.2b;
    SQLite allows only one writer at a time). Two intermediate findings
    that shaped the final design, recorded for anyone revisiting this:
    a first implementation used `BEGIN IMMEDIATE` only for
    `require_write=True` routes and a plain deferred `BEGIN` for reads;
    that reintroduced the exact "global lock in the wrong place" failure
    mode this task warns about (39.6% error rate at N=100/1000, latency
    growing non-linearly) **and**, worse, a second attempt at the same
    idea surfaced `SQLITE_BUSY_SNAPSHOT` errors (deferred-BEGIN reads
    that later try to upgrade to a write via the access_log INSERT can
    have their WAL snapshot invalidated by a concurrent committer, and
    `busy_timeout` does **not** help — the snapshot is invalid, not just
    slow) — up to 99% `sqlite3.OperationalError: database is locked`
    under load. Universal `BEGIN IMMEDIATE` (current code) avoids both
    failure modes at the cost of full serialization under extreme
    concurrency, which is the safer tradeoff for a health-data system.
  **Not done / left for real-world validation:** true multi-process load
  (only one uvicorn process was tested, no `--workers`), and a run
  against SQLCipher-encrypted `health.db` (`db_key` set) rather than
  plain SQLite (this test's temp `$HOME` had no `db_key` configured, so
  it exercised the plain-`sqlite3` code path, not the `sqlcipher3` one —
  the locking semantics discussed above should be the same either way
  since both wrap the same SQLite core, but this was not empirically
  verified here).
- [x] 7.2 **Adversarial review of `pwa/backend/authz.py`.** Read
  `check_patient_access()` and `require_patient_access()`
  specifically hunting for: (a) a race between checking
  `patient_assignments` and actually reading/writing the patient's data
  — could a revoked assignment still let an in-flight request complete
  after revocation? (b) does `_log()` write the `access_log`
  entry *before or after* the actual data access — if after, a crashed
  request after a successful unauthorized read would leave no audit
  trail; (c) any code path where a missing/malformed `patient_pseudo`
  falls through to a default value instead of a hard deny. Write up
  findings as new tasks in this section (7.2a, 7.2b, ...), do not fix
  silently without recording what was found and why.

- [x] 7.2a **Race condition between authorization check and data access**
  (Claude.) A new `authz.authorized_connection()`
  context-manager variant keeps the `patient_assignments` check AND the
  caller's subsequent data access within ONE `BEGIN
  IMMEDIATE` transaction on the same connection — a concurrent
  revocation (a write to patient_assignments) must wait on the
  SQLite write lock until this transaction commits or rolls back. For
  this, ~16 functions in `pwa/backend/db.py`
  (`upsert_entries`, `get_entries_for_date`, `get_entries_for_range`,
  `delete_entry`, all migraine/AFib functions) got an optional
  `conn=None` parameter (default behavior for other callers
  unchanged), and all ~20 routes in `main.py` that previously ran
  `check_patient_access()` + exactly one `db.xxx()` call back to back
  were switched to `with authorized_connection(...) as conn:` +
  `conn=conn`. The one route with multiple data accesses
  after a single check (`GET /api/export`, three `db.xxx()` calls) keeps
  all three within the same `with` block. Not switched over: the three
  attachment routes (`/api/attachments/*`) — these never called
  `check_patient_access()` in the first place (no `patient_pseudo` query
  parameter, only `entry_id`/`attachment_id`); that is a pre-existing,
  separate scope gap outside these four findings and was left untouched.
  The load test (7.1) confirms: 0 cross-contamination across all three
  runs. Trade-off (found during the load test, see the 7.1 notes):
  `BEGIN IMMEDIATE` locks the ENTIRE file, not just the affected
  patient — under very high concurrency (N=100, 10x oversubscription)
  this also serializes requests for unrelated patients; not measurable
  at realistic load (N=20, N=100 with 1 request/patient).

- [x] 7.2b **Audit-log timing problem**
  (Claude.) `check_patient_access()`/`_check_on_conn()` and
  `authorized_connection()` now write the `access_log` entry on the
  SAME connection as the `patient_assignments` check and
  commit both together (`_log()` no longer commits itself, no longer
  opens its own connection). On every denial, a commit happens
  immediately (before the `HTTPException` is raised), so the
  log entry survives even if the caller crashes afterward.
  Verified via `tests/manual/test_verification.py` (a path typo
  in it was corrected in passing to the actual `manage_patients.py`
  location under `scripts/utils/manage/clinic/`) — the audit log still
  contains the expected entries after access/denial.

- [x] 7.2c **Missing validation of patient_pseudo**
  (Claude, together with 7.2d.) Adopted the real format from
  `scripts/utils/manage/clinic/manage_patients.py:_pseudo()`
  (not the guessed `PAT-[A-Z0-9]{4}` from the review, but the actually
  generated `PT-` + 8 hex uppercase characters): `_PSEUDO_RE =
  re.compile(r'^PT-[0-9A-F]{8}$')` in `authz.py`. Checked as the VERY
  FIRST thing in `_check_on_conn()`, before any DB query. Empty/malformed
  values are hard-rejected with 403 (no fallthrough to a
  default value) and still logged (action `denied`, detail `malformed
  patient_pseudo`).

- [x] 7.2d **Potential SQL-injection risk**
  (Claude, together with 7.2c — the same format check covers
  both.) The format check from 7.2c runs before every SQL query;
  a comment in `authz.py` notes that this is defense-in-depth —
  the queries were already parameterized (no actual
  injection risk), but an empty/unexpectedly-shaped value should
  still not be passed through to the database.
- [ ] 7.3 **Real TOTP QR-code-scan-by-human.** `tests/manual/test_totp_setup.py`
  (task 3.5) already proves the code path (secret generation → TOTP
  verification → JWT issuance/verification) works in isolation. This
  task is specifically the step that automation cannot cover: generate a
  real QR code via `pwa/backend/auth.py --setup`, scan it with an actual
  authenticator app (Google Authenticator, Aegis, or similar) on a real
  phone, log in with the generated 6-digit code, confirm a valid JWT
  comes back and a wrong code is rejected. This needs a human with a
  phone, not a script — flag it to the user/operator rather than trying
  to script around it. **Still outstanding** — no longer a release gate
  (see 7.4), but needed before clinic/research use is actually certified.
- [x] 7.4 Update `docs/CLINIC_DEPLOYMENT.md`/`_DE.md`'s status
  banner — done ahead of 7.3, per explicit user decision to descope
  clinic/research/practice multi-user certification from a release
  gate: it now ships as "implemented, not yet certified for this
  release" (individual/family use unaffected) rather than blocking the
  release on 7.3. Banner changed from "RELEASE-BLOCKER — target model"
  to "NOT YET CERTIFIED FOR THIS RELEASE"; same change made to
  `README.md`/`README_DE.md`'s multi-person-support line and a new
  "Release status" section. 7.3 remains open and should still be done
  before clinic/research use is actually certified.
