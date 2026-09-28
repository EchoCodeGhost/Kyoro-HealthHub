## 1. New module `scripts/modules/confidence.py`

- [x] 1.1 SPDX header + full bilingual docstring
      (`@tier infrastructure`, `@purpose.de/en`, `@relevance.de/en` —
      this module itself must serve as the first reference example for
      the new required field, `@method.de/en`, `@reads: none`,
      `@writes: none`, `@usage`).
- [x] 1.2 Function `label_finding(text_de: str, text_en: str, level: str) -> tuple[str, str]`:
      `level` ∈ `{"confirmed", "suspected", "lead"}`, raises `ValueError`
      on an invalid value. Return: `(German string with
      emoji prefix, English string with emoji prefix)`.
      Prefixes: `✅ Bestätigt`/`✅ Confirmed`,
      `⚠️ Vermutet`/`⚠️ Suspected`,
      `❓ Offener Hinweis`/`❓ Open lead`.
- [x] 1.3 `tests/unit/test_confidence.py`: all three levels, invalid
      `level` value raises `ValueError`, return format checked exactly
      (not just "contains an emoji").

## 2. Extend docstring tooling

- [x] 2.1 `scripts/check_docstrings.py`: add `@relevance.de`/
      `@relevance.en` to `REQUIRED_TAGS` for **all** tier values,
      including `heuristic` (deliberately no exception, unlike
      `@limits` — see design.md Decision 4).
- [x] 2.2 `docs/docstring_template.md` + `docs/docstring_faq.md`:
      document the new `@relevance.de/en` field (definition, 2-3
      examples, distinction from `@purpose`), plus a new section on
      confidence labeling (`scripts/modules/confidence.py`, when to use
      which of the three levels). Done: new sections "@relevance" and
      "confidence labeling" in `docstring_template.md`, required-tags
      table + checklist updated; FAQ entries 2.03 (@purpose vs.
      @relevance) and 2.10 (`confidence.py`) added, numbering corrected
      throughout. `gen_docs.py --check` still green.
- [x] 2.3 Check `tools/gen_docs.py`: renders `@relevance` correctly in
      `docs/de/`/`docs/en/` (alongside `@purpose`, analogous to
      `@limits`).

## 3. Full migration — batches by subdirectory

**For every batch:** write `@relevance.de/en` with content specific to
each script (no boilerplate phrase like "relevant for the analysis").
Where a script communicates an uncertain/interpretive result (mainly in
`scripts/analysis/`, possibly `scripts/compute/`), also switch it over
to `scripts/modules/confidence.py` if it doesn't already use a
consistent vocabulary. After every batch:
`python3 -m compileall -q <changed files>` +
`ruff check <changed files> --select F` green, otherwise unchanged
behavior.

- [x] 3.1 **`scripts/analysis/`** — largest and most
      important batch, since confidence labeling also applies here.
      Recommended to further split by sub-specialty (cardiovascular 21,
      sleep 14, neurology 11, infectious 9, activity 9, manual 7,
      metabolic 6, internal_medicine 6, immunology 5, environment 5,
      cycle 4, psychology 2, ophthalmology 2, longevity 2, syndromes 1,
      psychiatry 1, plus `analyse_overview.py`/`analyse_health_timeline.py`).
      Replace `analyse_postinfectious_diagnose.py`'s local `tier_prefix`
      dict with `label_finding()`
      (`confirmed`→`"confirmed"`, `exposure`→`"suspected"`,
      `suspected`→`"lead"`, see design.md Decision 1 table) — serves as
      the reference example for the rest of this batch's scripts.
- [x] 3.2 **`scripts/importers/`** — `@relevance` here
      mostly explains why the imported data source is relevant to the
      overall record (e.g. why lab values, why a particular wearable).
- [x] 3.3 **`scripts/utils/`** — including `manage_*`
      scripts; `@relevance` here often justifies structural/privacy
      purpose rather than a clinical question — both are valid, as long
      as it's concrete, not generic.
- [x] 3.4 **`scripts/compute/`** — here check whether
      computed scores (e.g. AFES, PEM score) need confidence labeling,
      not just `@relevance`.
- [x] 3.5 **`scripts/modules/`** — including the new
      `confidence.py` itself (from task 1.1).
- [x] 3.6 **`scripts/query/`**.
- [x] 3.7 **`scripts/calibration/`**.
- [x] 3.8 **`scripts/exporters/`**.
- [x] 3.9 **Remaining scattered scripts with `@tier`** (e.g.
      directly under `scripts/`, `scripts/migrations/`) — cross-check
      beforehand via `grep -rl "@tier" --include="*.py" scripts/`
      against the sum of batches 3.1-3.8, to make sure nothing is
      missed. Verified: all scripts with `@tier` in `scripts/` have
      `@relevance.de/en` (`grep -rl "@relevance"
      scripts/ | wc -l` == `find scripts -name "*.py" | wc -l`).

## 4. Switch on repo-wide enforcement

- [x] 4.1 After all batches (3.1-3.9) complete: adjust
      `check_docstrings.py` so `@relevance` is checked **without an
      exception for unchanged existing scripts** (remove the transition
      exception from task 2.1). Done: `should_enforce_relevance_tags()`
      and the dead helper function `is_recently_modified_or_new()`
      removed, `@relevance` is now unconditionally checked for all
      tiers.
- [x] 4.2 `python3 scripts/check_docstrings.py` green across the
      **entire** repo — confirms complete coverage, no missed scripts.
      (all valid, 0 errors, a handful of files with warnings
      — warnings are pre-existing findings unrelated to `@relevance`,
      see the completion report.)

## 5. Verification

- [x] 5.1 `python3 tools/gen_docs.py --check` green.
- [x] 5.2 `python3 -m pytest tests/unit/test_confidence.py -q` green.
- [x] 5.3 `python3 scripts/utils/check_source_privacy.py` green.
- [x] 5.4 Full smoke test (`tests/smoke.sh`) green — in particular
      `analyse_all`, output of the changed analysis scripts manually
      spot-checked against the state before the change (confidence
      labels must look identical in content, only sourced from the new
      module, no behavior change). Done against the real production DB
      (not dummy/synthetic): `SMOKE OK`, `analyse_all` all scripts
      without errors, all unit tests green including
      `test_confidence.py`. Spot check in the reference script
      `analyse_postinfectious_diagnose.py` confirms: new labels
      `✅ Bestätigt:` / `⚠️ Vermutet:` appear correctly and
      meaningfully in today's analysis outputs.

- [x] 6.1 `openspec validate add-confidence-and-relevance-conventions --strict`
      green.
- [x] 6.2 Review: `proposal.md`, `design.md`, `specs/documentation-
      conventions/spec.md` and this `tasks.md` are consistent with each
      other. Done: no real contradiction. The script count in
      proposal/design (state before the change) is one lower than in
      tasks.md 3.9 (after adding `confidence.py`, which is itself one of
      the newly-tiered scripts) — consistent, not contradictory. ADDED
      instead of MODIFIED spec for
      `documentation-conventions` is correct, since the sibling change
      `document-deployment-and-docstring-conventions` is still
      unarchived — both changes use the same capability
      name for the planned merge on archiving. **Open coordination
      point for 6.3:** this sibling change is still completely
      unimplemented and targets the same capability — check before
      archiving whether two time-offset ADDED deltas onto the same new
      capability merge cleanly.
- [ ] 6.3 Archive the change once tasks 1-5 are fully complete (no
      remaining backlog item — full migration is this change's
      completion criterion).
