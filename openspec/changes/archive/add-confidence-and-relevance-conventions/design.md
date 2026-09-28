## Context

The user explicitly asked for two firm, project-wide enforced
principles:

1. A clear distinction between confirmed statements, suspected
   associations, and open leads.
2. Always document why a data type is relevant in the first place.

Research done before this change confirmed: point 1 exists only as
local ad-hoc vocabulary in a single script
(`analyse_postinfectious_diagnose.py`, levels marked with emoji),
point 2 practically doesn't exist as a required field at all — only
occasional comments in schema code. Both are so far **lived
case-by-case practice, not an enforced convention.**

## Goals / Non-Goals

**Goals:**
- Create a reusable, central code module for confidence labels that
  every analysis script can import, instead of inventing its own
  strings.
- Introduce a new required docstring field (`@relevance`), enforced by
  `check_docstrings.py` — exactly like `@limits` is already enforced
  today, but **without a tier exception** (explicit user requirement:
  should cover everything).
- Take the existing, already-proven three-level logic from
  `analyse_postinfectious_diagnose.py` as the template, not reinvent it.
- **Full migration of all existing scripts with `@tier`** to
  `@relevance.de/en`, organized in batches by subdirectory (see
  `tasks.md`) — explicitly **no** pilot-with-remaining-backlog approach
  anymore (correction of the original plan after explicit user feedback:
  "No. This should cover everything").

**Non-Goals:**
- No new compliance checker/linter beyond `check_docstrings.py` — the
  existing pre-commit QA chain covers enforcement.
- No change to the database (no new column schema) — confidence
  labeling only affects text/report output, not stored values.
- Confidence labeling (confirmed/suspected/lead) is not enforced in
  every migrated script, only `@relevance` — confidence labels
  only apply to scripts that actually communicate uncertain/
  interpretive findings (mainly `scripts/analysis/`, possibly
  `scripts/compute/`); an importer or a pure utility script generally
  has no "finding" to label.

## Decisions

### 1. Three confidence levels, no more

Exactly three levels, following the already-proven practice:

| Level | German | English | Emoji | Meaning |
|---|---|---|---|---|
| 1 | bestätigt | confirmed | ✅ | Backed by a validated method/reference or direct measurement (corresponds to `@tier: validated`/`calibrated` level for this individual finding) |
| 2 | vermutet | suspected | ⚠️ | Plausible hypothesis with supporting but not conclusive evidence |
| 3 | offener Hinweis | open lead | ❓ | Weak pattern/coincidental-finding candidate, explicitly marked as a starting point for further workup, not a conclusion |

More than three levels (e.g. an intermediate one) would make the
decision harder for authors without real added benefit — the three
levels directly mirror the language already used in existing local
case documents.

### 2. Central module instead of a copy-paste dict per script

`scripts/modules/confidence.py` with one public function:

```python
def label_finding(text_de: str, text_en: str, level: str) -> tuple[str, str]:
    """Formats a finding with a confidence prefix.

    level: "confirmed" | "suspected" | "lead"
    Returns (German string, English string), each with an
    emoji prefix, e.g. ("✅ Bestätigt: ...", "✅ Confirmed: ...").
    """
```

Reasoning for a dedicated module instead of extending `modules/base.py`:
`base.py` is already very broad (ImportResult, resolve_person,
resolve_timezone, local_date) — a thematically self-contained, narrow
module is easier to find and test (its own
`tests/unit/test_confidence.py`).

### 3. `@relevance` complements `@purpose`, does not replace it

`@purpose.de/en` stays "what does this script compute".
`@relevance.de/en` explicitly answers "why is the underlying data type/
this metric relevant at all, what clinical or scientific question does
it answer". Separate fields instead of an extended `@purpose`, because
otherwise the existing field would have to be rewritten retroactively
for all 846+ scripts, instead of just adding one new field.

### 4. Required-field level: stricter than `@limits` — for ALL tiers

`@relevance.de/en` becomes mandatory in `check_docstrings.py`'s
`REQUIRED_TAGS` for **every** `@tier` value, including `heuristic`
(which is currently exempt for `@limits`, see the existing
`TIER_SPECIFIC_TAGS` logic in `check_docstrings.py`). Deliberate
deviation from `@limits` symmetry: the reasoning for why a data type is
relevant makes sense independent of the script's validation level — even
a purely heuristic script should be able to justify why its input data
type is collected/used at all.

### 5. Full migration instead of a pilot batch

Following explicit user correction ("No. This should cover
everything"), the full retrofit of all existing scripts with
`@tier` is part of this change, not deferred. `check_docstrings.py`
enforces the new field **repo-wide** after the migration completes, not
just for new/changed docstrings. The migration itself is batched by
subdirectory in `tasks.md` (`scripts/analysis/`,
`scripts/importers/`, `scripts/utils/`, `scripts/compute/`,
`scripts/modules/`, `scripts/query/`, `scripts/calibration/`,
`scripts/exporters/`, remainder scattered), so the scope stays manageable
and progress stays visible — realistically several work sessions, but
as one coherent, fully tracked task, not a vague "someday".

## Risks / Trade-offs

- **Risk:** With so many scripts to migrate, `@relevance` risks degrading
  into pure boilerplate ("relevant for the analysis") if the migration
  is pushed through too mechanically. → Mitigation: every batch task in
  `tasks.md` requires content-specific justifications, no template
  phrases; Claude reviews samples from every batch, not just whether the
  field is syntactically present.
- **Risk:** `check_docstrings.py` runs red while the migration is in
  progress (intermediate state: some scripts have `@relevance`, others
  don't yet). → Mitigation: enforcement only becomes strict repo-wide
  (hard requirement without exception for unchanged files) once all
  batches in `tasks.md` are checked off — until then only required for
  new/changed docstrings, as originally planned.
- **Trade-off:** Three confidence levels are a simplification — the real
  evidence landscape is often a continuum. Deliberately accepted, since
  a finer scale (e.g. percentages, as already used in some local case
  documents) remains possible per
  individual case; the three levels are a minimum requirement for
  consistency, not a ban on more precise figures in addition to the
  label.

## Migration Plan

1. Build + test `scripts/modules/confidence.py`.
2. Extend `check_docstrings.py` + `docs/docstring_template.md`/
   `docstring_faq.md` with `@relevance` (initially only required for
   new/changed docstrings, see Risks).
3. Full migration of all scripts in batches by subdirectory (see
   `tasks.md`), including switching
   `analyse_postinfectious_diagnose.py`'s ad-hoc dict over to
   `scripts/modules/confidence.py` and checking other analysis scripts
   for places worth confidence-labeling.
4. After all batches complete: switch `check_docstrings.py` enforcement
   to repo-wide strict (no more exception for unchanged files).
5. Confirm `python3 scripts/check_docstrings.py` +
   `tools/gen_docs.py --check` green, then archive the change.

## Open Questions

None — `heuristic` is explicitly included after the correction (see
Decision 4), full migration is explicitly included (see Decision 5).
