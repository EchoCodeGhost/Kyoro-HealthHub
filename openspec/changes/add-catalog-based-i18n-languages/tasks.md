## 1. Core mechanism

- [ ] 1.1 Rewrite `scripts/modules/i18n.py`: `t(key: str, **kwargs) -> str`
      looks up `key` in the active language's locale catalog, applies
      `.format(**kwargs)` if kwargs given, falls back requested-language →
      English → raises a clear error if the key exists in no catalog.
- [ ] 1.2 `set_lang()`/`get_lang()`: accept any language code discovered
      under `scripts/modules/locales/`, not a fixed `Literal["de", "en"]`.
- [ ] 1.3 `add_lang_arg()`: build `choices` dynamically from the locale
      files present, instead of the hardcoded `["de", "en"]` list.
- [ ] 1.4 Create `scripts/modules/locales/` with empty/seed
      `de.json`/`en.json` (populated for real by the migration in group 3).

## 2. Migration tooling (build + pilot)

- [ ] 2.1 Build the AST-based migration codemod: locate every `t(...)`
      call, extract the two string arguments (literal or simple f-string),
      generate a key (`<dotted.module.path>.<slug_of_english_text>`,
      numeric suffix on same-prefix collision), rewrite the call site to
      `t("<key>")` or `t("<key>", **kwargs)` for f-string cases, and emit
      the extracted DE/EN pairs keyed the same way.
- [ ] 2.2 Handle the f-string interpolation case specifically: bare
      name/attribute/subscript expressions become template placeholders +
      kwargs automatically; anything more complex (operators, function
      calls, format specs) is left untouched and reported in a "needs
      manual handling" list instead of guessed at.
- [ ] 2.3 Handle non-literal `t()` arguments (a call site passing a
      variable instead of a string literal, if any exist) the same way —
      report for manual handling, don't attempt to infer.
- [ ] 2.4 Build the byte-identical validation pass: for every rewritten
      call site, re-render both languages from the new catalog + generated
      key and diff against the originally captured DE/EN strings.
- [ ] 2.5 Run the codemod against one pilot module first; run the
      validation pass; fix the codemod until the pilot module round-trips
      cleanly (including at least one f-string call site, to prove
      criterion 2.2 works before scaling up).

## 3. Full migration

- [ ] 3.1 Run the codemod repo-wide across `scripts/`.
- [ ] 3.2 Run the byte-identical validation pass repo-wide; resolve every
      flagged call site (manual f-string handling, non-literal arguments)
      by hand, re-validating after each fix.
- [ ] 3.3 Manually spot-check the collision report (task 2.1) for any
      accidental key reuse that should have been distinct keys.
- [ ] 3.4 Run the full existing test suite (`python -m pytest`) — no
      script's behavior should differ, since every t() call still returns
      the same DE/EN string it did before.

## 4. Coverage tooling & QA gate

- [ ] 4.1 Build `scripts/utils/check_i18n_coverage.py` (follows the
      `check_no_dates.py`/`check_source_privacy.py` pattern): reports
      missing-key count/list per locale file.
- [ ] 4.2 Build the catalog-regeneration tool: adds newly-discovered keys
      (from a fresh codebase scan) to every locale file as untranslated
      placeholders, flags keys no longer referenced anywhere as removal
      candidates, never touches existing translated entries for keys still
      in use.
- [ ] 4.3 Wire `check_i18n_coverage.py` into `tools/qa_check.py`: DE/EN
      <100% coverage fails the gate; any other language's coverage is
      reported only, does not fail the gate.

## 5. Spec & documentation updates

- [ ] 5.1 Apply the `cross-cutting-conventions` delta spec (already
      drafted in this change) to `openspec/specs/cross-cutting-conventions/spec.md`
      once this change is archived (standard OpenSpec archive step, not a
      manual edit now).
- [ ] 5.2 Find and update any docstring `@usage`/`@method` text that
      quotes the literal old `t("DE", "EN")` call form as an example,
      across affected scripts (likely many — the migration itself doesn't
      touch docstring prose, only code).
- [ ] 5.3 Update `CLAUDE.md`'s "Language" section (currently describes
      `t("DE", "EN")`) to describe the key-based mechanism.

## 6. The actual deliverable: parameterized "add language X" template

- [ ] 6.1 Write a standalone, reusable task template (target language as
      its only variable) describing: run the catalog-regeneration tool →
      get the current key list → translate into
      `scripts/modules/locales/<lang>.json` → run the coverage-check tool
      to confirm completeness → (optional) spot-check a handful of screens/
      CLI outputs in the new language. Place it where it's easy to find
      and reuse (e.g. `docs/CONTRIBUTING.md` section, or
      `templates/add_language_task.md`) — confirm placement with the user
      before finalizing.
- [ ] 6.2 Dry-run the template once for a real target language (per the
      user's original examples — Russian, Spanish, or French) to confirm
      the instructions are actually sufficient without additional
      context, before considering the template done.

## 7. Tests

- [ ] 7.1 Unit test `t()`: key lookup, kwargs formatting, fallback
      chain (requested → English → error for a key missing everywhere),
      per the spec's scenarios.
- [ ] 7.2 Unit test the coverage-check tool against fixture locale files
      with known gaps.
- [ ] 7.3 Unit test the catalog-regeneration tool: new key added → appears
      as untranslated placeholder elsewhere; existing translation
      untouched; removed key → flagged, not deleted.
- [ ] 7.4 Run the full suite (`python -m pytest`) and confirm no
      regressions beyond what's already covered in group 3.

## 8. Final QA gate

- [ ] 8.1 Run `python3 tools/qa_check.py` (now including the new coverage
      check) and confirm all checks pass.
- [ ] 8.2 Run `python3 scripts/utils/check_source_privacy.py` and
      `python3 scripts/utils/check_no_dates.py` — confirm clean.
