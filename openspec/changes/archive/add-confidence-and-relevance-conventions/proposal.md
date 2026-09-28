## Why

Research done at the user's request confirmed two gaps in
the existing documentation/output conventions that are central for a
project with a court-admissibility goal:

1. **No consistent separation of confirmed/suspected/open-lead at the
   finding level.** The existing `@tier` field
   (`validated|calibrated|research|heuristic|experimental`) only
   classifies whole scripts/methods, not the individual statements a
   script makes at runtime. Exactly one script
   (`analyse_postinfectious_diagnose.py`) already has a clean
   three-level vocabulary (✅ confirmed / ⚠ suspected with exposure / ❓
   pure suspicion) — but ad hoc, local, never recorded anywhere as a
   reusable convention or spec. Every other script phrases uncertainty
   differently or not explicitly at all.
2. **No requirement to document why a data type/metric is collected/
   computed at all.** The existing `@purpose` field only describes WHAT
   a script does, not WHY the underlying data type is clinically/
   scientifically relevant. This reasoning exists at best as an
   incidental comment in schema code, never as a required statement.

Both gaps contradict the project's goal of preparing findings so they
hold up before a specialist, an expert witness, or a court — a finding
without a recognizable confidence level and without justified relevance
is usable neither for a physician nor in court.

## What Changes

- New `documentation-conventions` capability (if the same-named
  capability from `document-deployment-and-docstring-conventions` is
  already archived: MODIFIED, otherwise kept as an independent ADDED
  spec in parallel and merged on archiving) with two new requirements:
  - **Required docstring field `@relevance.de`/`@relevance.en`**: every
    script with `@tier` SHALL, in addition to `@purpose`, justify why
    the collected/computed data type is clinically or scientifically
    relevant (not just what is computed, but why it's worth collecting).
  - **Reusable finding-confidence labeling**: every analysis output
    (report text, plot title, LLM prompt context) that communicates a
    concrete association/finding SHALL assign it one of three confidence
    levels — **confirmed**, **suspected**, **open lead** — via a new
    shared helper `scripts/modules/confidence.py`, not through ad-hoc
    strings per script.
- New module `scripts/modules/confidence.py`: provides
  `label_finding(text, level, lang)` (or equivalent) that returns
  consistently formatted, bilingual, emoji-prefixed strings for all
  three confidence levels — replaces the local ad-hoc vocabulary in
  `analyse_postinfectious_diagnose.py` as the reference implementation.
- Extension of `scripts/check_docstrings.py`: `@relevance.de`/
  `@relevance.en` become required fields for **all** `@tier` values
  (including `heuristic` — deliberately **no** exception, unlike
  `@limits`; the user wants complete coverage).
- Extension of `docs/docstring_template.md`/`docs/docstring_faq.md` with
  the new field and the confidence convention.
- **Full retrofit of all existing scripts with `@tier`** (see Impact)
  to `@relevance.de/en` — not a
  pilot batch with a remaining backlog, but the full migration is
  explicitly part of this change (see `tasks.md`, organized in batches
  by subdirectory). Confidence labeling via
  `scripts/modules/confidence.py` is retrofitted wherever a script
  communicates an uncertain/interpretive result (mainly
  `scripts/analysis/`, possibly also `scripts/compute/`).

## Capabilities

### New/Modified Capabilities
- `documentation-conventions`: two new requirements (`@relevance`
  required field for **all** tiers, finding-confidence labeling via
  `scripts/modules/confidence.py`) in addition to the requirements
  already proposed in `document-deployment-and-docstring-conventions`
  (bilingualism, docstring field schema).

## Impact

- New file: `scripts/modules/confidence.py`.
- Changed files: `scripts/check_docstrings.py` (new required fields, no
  tier exception), `docs/docstring_template.md`, `docs/docstring_faq.md`.
- **Full migration** (every script matching `grep -rl "@tier"
  --include="*.py" scripts/`), spanning `scripts/analysis/`,
  `scripts/importers/`, `scripts/utils/`, `scripts/compute/`,
  `scripts/modules/`, `scripts/query/`, `scripts/calibration/`,
  `scripts/exporters/`, and scattered elsewhere — all get
  `@relevance.de/en`. Batches by subdirectory in `tasks.md`.
- All future new/changed scripts with `@tier` MUST include
  `@relevance.de/en` starting at merge of this change — enforced by
  `check_docstrings.py` (part of the pre-commit QA gate).
- Realistically a multi-part effort (too many scripts to responsibly
  migrate in one pass, each field must be substantively correct, not
  just boilerplate) — tracked as batches within **this** change, not as
  a separate, unprioritized backlog item.
- No breaking changes to database schema or pipeline behavior.
