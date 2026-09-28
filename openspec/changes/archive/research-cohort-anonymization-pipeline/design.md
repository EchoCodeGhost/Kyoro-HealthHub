## Context

Each patient/participant already has a fully isolated instance
(`KYORO_ACTIVE_PATIENT_DIR` → own `health.db` + `db_key`), registered in
`master.db`'s `patient_number_map` (`patient_pseudo`, `patient_number`,
`practice_id`, `instance_dir`, `active`). `scripts/export_health.py`
already has `load_profile(name)` and `export_profile(profile, args, out_dir)`
that run a profile's SQL queries against one `health.db` and return
per-query row lists (see `scripts/export_health.py`). The
`research` profile (`scripts/exporters/profiles/research.json`) already
selects the full research column set (measurements, sessions, ppi_raw, ECG,
HRV, device firmware history, etc.) per person. None of this currently
combines across instances or de-identifies beyond the source pseudonym.

## Goals / Non-Goals

**Goals:**
- Produce one merged, de-identified dataset from N patient instances with
  a single command, gated on recorded consent.
- Reuse `export_health.py`'s existing profile/query machinery unchanged —
  this change adds a layer around it, not a competing exporter.
- Make the k-anonymity check a real gate (rows/groups below k are
  suppressed/generalized), not just a report that gets ignored.
- Every de-identification step (date shift offset, age band width, k
  threshold) is deterministic and logged in the run manifest so a study
  can describe its own methodology.

**Non-Goals:**
- No statistical disclosure control beyond k-anonymity (no l-diversity,
  no differential privacy) — out of scope for v1; note as a limitation
  in `@limits.de/@limits.en`.
- No automatic IRB/Ethikkommission workflow — `research_consent` records
  a **local** consent flag; obtaining that consent legitimately is a
  human/organizational process outside this codebase's scope.
- No network upload of the cohort dataset — this change only produces a
  local directory. Any transfer to an external research partner is a
  manual, separate step (and a separate risk decision) not automated here.
- No changes to the multi-tenant broker/authz layer itself — see the
  caveat in `proposal.md` about that layer's current test coverage.

## Decisions

**D1 — Cohort assembly runs client-side over instance directories, not
inside the broker.** `export_research_cohort.py` reads `master.db` for the
list of active `(patient_pseudo, instance_dir)` pairs directly (it is an
operator-run CLI tool, not a per-request web endpoint like the Kyoro SymptomTrack
broker) — same trust model as `manage_patients.py`, which already reads
`master.db` directly. Alternative considered: route cohort export through
the Kyoro SymptomTrack web broker's authz — rejected because cohort export is a
practice-admin/researcher batch operation run from a terminal, not a
clinician's per-patient web session; forcing it through the web broker
would add a dependency on the PWA being deployed and running, which
today's CLI tools do not require.

**D2 — Consent is a separate table (`research_consent`), not a column on
`patient_number_map`.** A patient can have multiple consent scopes over
time (e.g. consent for one study, not another; consent revoked later but
prior exports already delivered stay valid per their own scope) — a
single active/inactive column can't represent that history. Mirrors why
`access_log` is a separate append-only table rather than a status flag.

**D3 — De-identification is a pure post-processing step over query result
rows (`deidentify_cohort.py`), not a change to the SQL queries.**
`export_profile()` already returns `list[dict]` per query name; the new
module transforms those in memory before `write_output()`-equivalent
writes the merged file. This means `research.json` (and any future
profile someone wants to use for cohort work) needs zero changes, and the
transform logic has one place to be tested independently of DB access.

**D4 — Date shift is derived deterministically per patient, not randomly
re-rolled per run.** Shift offset = a stable hash of `patient_pseudo`
(e.g. `int(hashlib.sha256(patient_pseudo.encode()).hexdigest()[:8], 16) %
730 - 365`, giving a ±365 day offset), not `random.randint()`. This means
two exports of the same cohort (e.g. a re-export after fixing a bug) shift
dates identically, so relative comparisons across export runs still line
up, while the mapping from pseudonym to shift is not stored anywhere
retrievable-in-plaintext (it's a one-way hash, same non-reversibility
property as `pseudonymize_device_serial`).

**D5 — k-anonymity is checked over the profile's own output columns, not
a fixed hardcoded quasi-identifier list.** The checker takes an explicit
`--quasi-identifiers` argument (default: `age_band,gender`) rather than
guessing which columns are identifying — profiles vary, and guessing
wrong (checking too few → real re-identification risk; too many → most
rows suppressed for no reason) is worse than requiring the operator to
state the columns explicitly. `research.json`'s existing `persons` query
already exposes `timezone` which is itself a coarse location signal and
SHALL be included in the default quasi-identifier set discussion in
tasks.md.

## Risks / Trade-offs

- **[Risk]** Small cohorts (few active patients) will suppress most or
  all rows under k=5 — the tool becomes useless below a certain N.
  → **Mitigation:** `export_research_cohort.py` prints the pre-suppression
  group-size histogram before writing anything, so the operator sees "this
  cohort is too small for k=5" immediately rather than getting a near-empty
  file with no explanation.
- **[Risk]** Date-shifting breaks cross-patient temporal correlation
  analysis that some research questions genuinely need (e.g. "did
  everyone's HRV drop the same week during a regional infection wave?").
  → **Mitigation:** documented explicitly as a known limitation in
  `docs/CLINIC_DEPLOYMENT.md`'s new section — this tool trades that
  capability for date-based re-identification resistance; a study needing
  cross-patient date alignment needs a different, more carefully
  consent-scoped export path (out of scope here).
- **[Risk]** `research_consent` living in `master.db` (operator-controlled)
  means a compromised operator machine can see/forge consent records.
  → **Mitigation:** no stronger claim is made than for the rest of
  `master.db` (already holds the patient registry) — same trust boundary,
  not a new one. Documented, not "solved."
- **[Trade-off]** Reusing `export_health.py`'s `export_profile()` as-is
  means cohort export inherits any future profile changes automatically —
  good for consistency, but means a profile author who doesn't realize
  their profile might be used for cohort export could add a
  highly-identifying column without thinking about k-anonymity.
  → Documented in `research.json`'s description field as a note for
  profile authors (task in tasks.md), not solved structurally in v1.

## Migration Plan

No migration of existing data — this is new, additive functionality.
1. `create_master_schema.py` extended with `research_consent` (idempotent
   `CREATE TABLE IF NOT EXISTS`, safe against existing installations).
2. `manage_consent.py` and `export_research_cohort.py` are new entry
   points; nothing existing calls them, so no rollback risk for current
   users. Rollback = delete the two new files and drop the new table.

## Open Questions

- Should `--quasi-identifiers` have a project-wide recommended default
  beyond `age_band,gender` (e.g. always include `timezone` per D5)? Left
  for tasks.md to decide concretely rather than leaving it open at
  implementation time.
- Should suppressed rows be dropped silently from the merged file or kept
  in a separate `suppressed_<query>.csv` for audit purposes (never
  delivered to the researcher, but kept locally for the operator to see
  what was withheld)? Resolved in tasks.md: keep them locally,
  clearly marked, not included in the deliverable.
