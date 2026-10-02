# Contributing

> **Deutsche Version:** [CONTRIBUTING_DE.md](CONTRIBUTING_DE.md)

Kyoro-HealthHub uses a modular plugin architecture. Adding a new data source, export profile, or device requires no changes to core code.

Before starting, check [OPENSPEC.md](OPENSPEC.md) — the project's architectural
requirements (pipeline order, DB schema conventions, privacy rules, importer
pattern) are kept as versioned specs in `openspec/specs/`, alongside this guide.

---

## License and sign-off

By contributing to this project you agree that your contribution is released
under the [GNU General Public License v3.0 or later](../LICENSE) (the
same license as the project itself).

This project uses the **Developer Certificate of Origin (DCO)** instead of a
Contributor License Agreement. Every commit must be signed off:

```bash
git commit --signoff -m "your message"
```

This adds a `Signed-off-by: Your Name <you@example.com>` line and certifies
that you wrote the contribution (or have the right to submit it under GPL).
See [developercertificate.org](https://developercertificate.org/) for the full
DCO text.

New source files should carry an SPDX header:

```python
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Kyoro-HealthHub contributors
```

## Upstream-first policy

If you improve or extend Kyoro-HealthHub for your own personal or private
household use, we ask that you contribute your changes back to this
repository via a pull request.

This is not a legal requirement under GPL-3.0, but a community expectation.
Keeping a private fork helps no one; a PR benefits everyone who uses this
tool privately.

Note the scope statement in [README.md](../README.md) ("Release status —
deferred / no certification planned"): this project does not pursue
certification for research, institutional, or commercial deployment. If
you are extending it for a research project, a clinical study, or another
institutional context, you are responsible for independently satisfying
the EU AI Act, MDR, and GDPR obligations that apply to that use — this
project's upstream-first policy does not imply that such use is
supported or endorsed. If your institution's ethics board or
data-protection policy prevents you from opening a PR, please consider
filing an issue describing the improvement so others can implement it
independently for their own private use.

---

**Please do not** include personal data, real names, locations, dates of birth,
or real API tokens in commits, issues, or pull requests. Use placeholder
fixtures instead.

**This software is not a medical device.** Contributions that present output as
diagnostic, that imply clinical validation that does not exist, or that
recommend specific medical actions to end users will be rejected. See
[NOTICE](../NOTICE).

By contributing you also agree to the project's [Ethical Principles](ETHICS.md),
which cover human dignity, rights of people with chronic illness and disability,
LGBTQ+ protections, prohibited uses, and security requirements.

---

## Git workflow

This repo has two branches:

- **`dev`** (the default branch) — where all normal work happens. Open your
  PR against `dev`.
- **`main`** — the stable release line. Only updated by a maintainer
  squash-merging `dev` into it when a batch of changes is ready to be "the"
  released version, tagged as a [GitHub Release](../../releases). Don't
  target `main` directly with a PR.

Both branches are protected: direct pushes are rejected, for every
contributor — human or AI-assisted, including repo admins. All changes go
through a branch and a pull request:

```bash
git checkout -b <short-descriptive-branch-name> dev
# make your changes, commit
git push -u origin <branch-name>
gh pr create --base dev   # or open the PR on github.com
```

A PR against `dev` becomes mergeable once its **"Quality gate"** check
(`ci.yml`, runs `tools/qa_check.py`) is green, the branch is up to date
with `dev`, **and it has at least one approving review** from someone
other than the PR's author — GitHub rejects self-approval outright,
regardless of write access. Repo admins are exempt from the review
requirement for their own PRs (not from the Quality gate) so the project
maintainer isn't blocked waiting on a second reviewer for routine work;
everyone else's PRs need that second pair of eyes before merge.

An AI assistant working in this repo cannot approve its own pull request on
someone's behalf — GitHub rejects an approval submitted by the same account
that opened the PR — so review and merge both stay human actions even when
an assistant authored the branch.

## Checks before a pull request

Run the CI gate locally first — it is what `ci.yml` actually runs, and matching
it locally avoids a red PR:

```bash
python3 tools/qa_check.py
```

This runs 11 checks: docs-in-sync (`tools/gen_docs.py --check`), prompts-docs-sync
(`scripts/generate_prompts_docs.py --check`), SPDX headers, syntax, source
privacy, no embedded dates, no memory links, AI labeling, ruff (a restricted,
bug-only rule set), docstrings, and syndrome-endemic-regions sync. See the
module docstring of `tools/qa_check.py` for what each one covers.

`tests/smoke.sh` is **not** part of that gate — of the check scripts it only
covers `check_sql_columns.py`. The binding requirement for source privacy
lives in [`openspec/specs/privacy-rules`](../openspec/specs/privacy-rules/spec.md):

> Every contribution introducing new source code SHALL pass
> `python3 scripts/utils/check_source_privacy.py` with exit code 0 before merge.

A few checks are not part of `qa_check.py` and need to be run separately:

```bash
python3 scripts/check_all.py                    # privacy + anonymisation + PII
python3 scripts/check_compliance.py             # review queue, see compliance_baseline.json
python3 scripts/check_import_logging.py         # only for new/changed importers
./tests/smoke.sh                                # pipeline runs clean
```

Read [`openspec/specs/`](../openspec/specs/) first — it holds the requirements a
review will point at, among them no hardcoded IANA timezone, device-agnostic loading
via a preference chain rather than a single `device_id`, bilingual output via `t()`,
and finding confidence via `modules/confidence.py` instead of local vocabularies.

### Checking `@refs` citations

Two separate tools check the DOIs/PMC IDs declared in a module's `@refs` —
they ask different questions and are run at different times:

| | `tools/check_doi_resolves.py` | `tools/verify_refs.py` |
|---|---|---|
| Question asked | Does this identifier **exist**? | Does this identifier point to **exactly this paper**? |
| Method | Queries Crossref, falling back to DataCite (the two DOI registration agencies covering journal articles vs. datasets/software like Zenodo records) | Asks an LLM (Perplexity) to compare the citation text against what the identifier actually resolves to |
| Needs an API key | No | Yes (`llm.perplexity_api_key`) |
| Cost | Free, no rate limit concern | API cost per citation |
| When to run | Anytime — cheap enough for CI or a habit | Pre-release gate only; citations change rarely |
| A clean run means | The identifier isn't dead/typo'd | Human review still required — the model can err too |

Run `check_doi_resolves.py` first: a DOI that doesn't resolve at all is a
strictly cheaper class of error to catch than a DOI that resolves to the
*wrong* paper, and there's no reason to spend API calls verifying a
citation whose identifier is already known to be dead.

## Versioning and changelogs

Don't hardcode dates, version numbers, source-line numbers, or other
ephemeral/machine-generated identifiers in file content (docstrings,
comments, docs, OpenSpec proposals/designs/tasks) to record *when*
something changed, *which* revision introduced it, or *exactly where* in a
file to find it:

- Dates/versions — e.g. "Fixed 2026-07-18", "Version 3.1", "As of
  2026-07-22", a changelog table with a date column, a dated filename like
  `plan_x_2026-07-14.md`.
- Commit hashes and auto-generated branch names cited as narrative context
  — e.g. "(Done, commit `4238986`)", "only `worktree-agent-<hash>` had
  this". These identify a point in history the reader can't meaningfully
  act on without already having `git log` open, and they don't survive a
  rebase/squash.
- Line numbers — e.g. "`check_patient_access()` (line 30)". A function or
  file name is a stable reference; a line number drifts out of sync on the
  very next unrelated edit to that file, silently pointing at the wrong
  code.

Git already carries the "when"/"which revision" information: commit
history for the day-to-day "what changed and why," and — once the project
has a stable release history — tags/GitHub Releases for "which version
introduced this." Baking the same fact into file content just duplicates
it somewhere that goes stale (nobody updates a changelog table, a cited
line number, or a cited commit hash when they later touch that code
again), and pre-release it adds no value at all, since the commit history
it implicitly points to gets squashed away before the first public
release anyway.

Describe *what* changed and *why*, and *by name* (function/file/table),
not *when*, *at which commit*, or *at which line* — let the commit message
or PR carry that, and let a name survive edits that a line number can't.

**Exception:** citations to external sources — medical guideline versions
(e.g. "AWMF S3 guideline, version 6.0"), publication years, DOIs — are
domain content, not project changelog, and should stay.

---

## Personal case examples

Don't narrate real personal health events as motivating examples or
rationale in docs, comments, or docstrings — not even generalized or
anonymized ("a documented case showed...", "in one instance, a finding
turned out to be..."). This repo describes the pipeline and its rationale
in generic terms; the actual health data — including anecdotes about what
happened with it — stays local, in the gitignored `intern/` directory or
the person's own private notes, never in tracked files.

This is different from the dates/versions rule above: there's no
mechanical check for it (unlike a fixed list of forbidden identifiers,
recognizing "this is a real personal anecdote dressed as a generic
example" takes judgment, not string matching). Before writing a "why this
matters" / motivating paragraph, ask: *is this a general fact about the
domain, or a specific thing that happened to a specific person's data?*
If the latter, generalize it or drop it.

The same applies to personal device-ownership history: a comment
explaining *why* a script needs two device-era branches ("first unit was
lost, second unit bought on <date>") narrates a specific real event, not
a general architectural fact — even though the underlying mechanism
(multiple device_ids for the same device class, disambiguated by
`date_from`/`date_to`) genuinely is architecture and belongs in the
comment. Keep the mechanism, drop the story: state which device_ids
exist and that their applicable date range lives in local config
(`registry.json`), not the specific real dates or why there's more than
one unit. This applies to comments and echoed/printed strings in any
tracked file, not just `.py` docstrings — a `.sh` script's comments carry
the same risk and get no automated check at all (`check_no_dates.py` and
`check_compliance.py` only scan `.py`/`.md`).

The same judgment applies to referencing `intern/` from tracked files:
pointing to it as an architectural fact ("private notes live locally
under `intern/`, see the backup docs") is fine and used elsewhere in this
repo; pointing to a *specific* private file or backlog item from unrelated
content isn't — it gives an external reader nothing (they can't open it)
and only signals that private notes exist about that specific topic.

---

## Adding a New Importer

Create one file in `scripts/importers/import_<source>.py` and implement the `run()` function:

```python
from modules.base import ImportResult, resolve_person, resolve_timezone, local_date

def run(conn, data_path, lang='de', person=None) -> ImportResult:
    result = ImportResult()
    # ...
    return result
```

### ImportResult

```python
from dataclasses import dataclass, field

@dataclass
class ImportResult:
    rows_inserted: int = 0
    rows_skipped:  int = 0
    errors:        list[str] = field(default_factory=list)
```

### Utility functions

| Function | Purpose |
|---|---|
| `resolve_person(conn, device_id, device_user_id, explicit)` | Returns `person_id` string — looks up device owner or scale slot |
| `resolve_timezone(conn, ts_utc, person, device_id, session_id, embedded_offset)` | Returns `ZoneInfo` — 6-level fallback from GPS to home timezone |
| `local_date(ts_utc, tz)` | Returns `YYYY-MM-DD` string for the local calendar day |

### Duplicate handling

Use `INSERT OR IGNORE` for all inserts — the primary key silently drops exact duplicates:

```python
conn.execute("""
    INSERT OR IGNORE INTO measurements (ts, date, metric, value, unit, device_id, person)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", (ts, date, metric, value, unit, device_id, person))
result.rows_inserted += conn.execute("SELECT changes()").fetchone()[0]
```

### Person resolution

```python
person = resolve_person(conn,
    device_id=device_id,         # looks up devices.person
    device_user_id=slot,         # looks up persons.device_user_id (e.g. 'u1', 'u2')
    explicit=person_param)       # overrides everything if provided
```

### Timezone resolution

```python
tz = resolve_timezone(conn,
    ts_utc=ts_utc,
    person=person,
    device_id=device_id,         # tries devices.timezone (level 5)
    session_id=session_id,       # tries session_tracks GPS (level 1)
    embedded_offset='+02:00')    # Polar GDPR embedded offset (level 3)
date = local_date(ts_utc, tz)
```

### Log the import

```python
log_import(conn, "import_mysource", data_path, result.rows_inserted, result.rows_skipped,
          person=person)
```

`person` should be the same resolved value used for the actual writes above — pass it explicitly, don't rely on the default. If a migration or importer genuinely acts across all persons rather than one (rare — most importers write one source's data for one person), pass `person=None` explicitly rather than omitting the argument: omitting it defaults to the configured `OWN_PERSON_ID`, which would misattribute a cross-person operation to a single person. `git_commit` is captured automatically; no parameter needed.

### Register in import_all.py

Add one line to `scripts/import_all.py`:

```python
from importers import import_mysource
results['mysource'] = import_mysource.run(conn, cfg['mysource_path'], person=args.person)
```

### Analysis scripts get logging automatically

Unlike importers, `analyse_*.py` scripts don't call anything themselves to get logged — every script run through `analyse_all.py` is recorded in `analysis_log` (script, git commit, exit code, duration) automatically. Nothing to add when writing a new analysis script.

---

## Adding a New Export Profile

Create a JSON file in `scripts/exporters/profiles/<profile_name>.json`:

```json
{
  "name": "cardiology",
  "description": "Datenpaket für Kardiologen: HR, HRV, SpO2, AFib-Burden, EKGs, Blutdruck",
  "description_en": "Data package for cardiologists: HR, HRV, SpO2, AFib burden, ECG, blood pressure",
  "aliases": [],
  "queries": {
    "daily_heart": "SELECT date, person, resting_hr, hrv_rmssd_ms, spo2_avg FROM daily_summary WHERE person = :person AND date BETWEEN :date_from AND :date_to ORDER BY date",
    "ecg_sessions": "SELECT datetime, classification, symptoms, device_id FROM ecg_sessions WHERE person = :person AND date(datetime) BETWEEN :date_from AND :date_to ORDER BY datetime"
  }
}
```

- Each entry in `queries` is a named, full SQL `SELECT` statement — the name becomes the output file/sheet name.
- Named parameters `:person`, `:date_from`, `:date_to` are injected automatically from the CLI flags. `--person all` rewrites `person = :person` to `1=1` via regex, so write the filter as a literal `person = :person` comparison if you want `all` to work.
- Optional `aliases` list lets the profile be invoked under additional names (e.g. `metabolic` is also reachable as `diabetology`/`endocrinology`).
- Optional `algorithm_note` (string) documents non-clinically-validated detection logic used in a query, shown alongside the export.

No Python required — `export_health.py` loads all profiles from this directory at startup.

---

## Adding a New Device

Insert a row into the `devices` table:

```sql
INSERT INTO devices (device_id, brand, model, serial, sensor_type, person, date_from, date_to, timezone)
VALUES ('polar_h10_3', 'Polar', 'H10', 'XXXXXXXX', 'chest_strap', 'self', '2026-06-01', NULL, NULL);
```

`sensor_type` values:

| Value | Description |
|---|---|
| `optical_wrist_gps` | Optical wrist sensor with built-in GPS |
| `optical_wrist` | Optical wrist sensor without GPS |
| `chest_strap` | Chest strap (beat-to-beat RR) |
| `ring` | Smart ring (optical, finger) |
| `handheld_gps` | Handheld GPS device |
| `scale` | Body composition scale (bioimpedance) |
| `bp_monitor` | Blood pressure monitor (oscillometric) |
| `glucometer` | Blood glucose meter (capillary, manual) |
| `thermometer` | Thermometer (clinical) |
| `smartphone` | Smartphone (GPS source, HA companion) |
| `cgm` | Continuous glucose monitor |
| `hub` | Smart home hub (e.g. Home Assistant) |
| `weather_station` | Local weather station |

For shared devices (scale, blood pressure monitor, thermometer), set `person = NULL` and use `device_user_id` in the `persons` table to assign scale slots.

---

## Adding a New Metric

The `measurements` table is EAV — no schema change needed. Just insert rows:

```sql
INSERT OR IGNORE INTO measurements (ts, date, metric, value, unit, device_id, person)
VALUES ('2026-06-01T07:00:00Z', '2026-06-01', 'my_new_metric', 42.0, 'unit', 'my_device', 'self');
```

For categorical metrics (text values), use `value_text` and leave `value` as `NULL`:

```sql
INSERT OR IGNORE INTO measurements (ts, date, metric, value, value_text, device_id, person)
VALUES ('2026-06-01T07:00:00Z', '2026-06-01', 'resilience_level', NULL, 'strong', 'oura_4', 'self');
```

---

## Adding a New Person

Insert a row into `persons`:

```sql
INSERT INTO persons (person_id, display_name, device_user_id, timezone)
VALUES ('partner', NULL, 'u2', 'Europe/Berlin');
```

- `person_id` is used in all health data tables (`person` column).
- `display_name` is optional — for clinical use, leave `NULL` and use an anonymised hash as `person_id`.
- `device_user_id` maps scale slot identifiers (`u1`, `u2`) to persons automatically.
- `timezone` is the home timezone fallback (IANA name, e.g. `Europe/Berlin`).

---

## Folder Structure

```
scripts/
├── importers/
│   ├── import_polar.py         — Polar GDPR export
│   ├── import_apple.py         — Apple Health export.zip
│   ├── import_oura.py          — Oura API
│   ├── import_garmin.py        — Garmin Connect
│   ├── import_beurer.py        — Beurer Health Manager Pro
│   ├── import_omron.py         — Omron Connect
│   ├── import_ecowitt_csv.py   — EcoWitt weather station
│   ├── import_homeassistant.py — Home Assistant
│   └── ...                     — one file per source
├── compute/
│   └── compute_*.py            — derived-table scripts, run in order by compute_all.py
├── analysis/
│   └── <specialty>/analyse_*.py — plots and reports, one subdirectory per specialty
├── exporters/
│   └── profiles/
│       ├── cardiology.json
│       ├── sleep.json
│       └── ...                 — one JSON file per profile
├── modules/
│   ├── base.py                 — ImportResult, resolve_person(), resolve_timezone(), local_date()
│   ├── i18n.py                 — bilingual helper: t("DE text", "EN text")
│   └── db.py                   — open_db() / open_medicine_db() connection helpers
├── utils/
│   └── create_schema.py        — schema definition (single source of truth)
├── export_health.py             — main export runner
├── import_all.py                — runs all importers
└── compute_all.py               — runs compute/ scripts in dependency order
```
