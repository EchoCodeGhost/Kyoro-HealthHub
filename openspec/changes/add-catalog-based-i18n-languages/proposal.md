## Why

`modules/i18n.py`'s `t(de: str, en: str)` is called at roughly 4,964 sites
across `scripts/`, with both translated strings inline as literal arguments
at every call site — there is no central translation catalog; the
translations *are* the source code. This has served German/English fine,
but it doesn't scale to a third language: the only way to add one today
would be a full codebase sweep touching every one of those ~5000 sites, and
repeating that sweep for every future language. Even a lighter-weight
option considered during scoping — keep `t(de, en)` inline and only route
new languages through an external catalog keyed by the literal German
string — has a sharper problem: the German string would then double as
both UI text and a lookup key, so a routine wording fix to the German text
(clarity, typo) would silently break every other language's translation
for that string (silent fallback, no error, nothing flags the break).

## What Changes

- **BREAKING** (internal convention, not a public API): `t(de, en)` is
  replaced by a key-based `t(key: str) -> str`. All ~4,964 existing call
  sites are converted by an automated codemod — not by hand — to
  `t("<generated.key>")`, with the original German and English strings
  extracted into `scripts/modules/locales/de.json` and
  `scripts/modules/locales/en.json`. German and English become ordinary
  catalog languages, with no special inline-string status.
- A key-generation strategy is defined (see design.md) that produces
  stable, human-legible keys from the existing call sites in one pass —
  this is the trickiest part of the codemod and needs a concrete, tested
  approach before it touches 5000 call sites.
- A coverage-check tool (matching this project's existing `check_*.py`
  QA-tool pattern) reports, per locale file, how many/which catalog keys
  are missing a translation — so an incompletely translated language is
  visible to a maintainer instead of silently and permanently falling back
  to English forever for the gaps.
- A catalog-regeneration tool that can be re-run as new `t()` calls are
  added over time: adds new keys to every locale file (untranslated) and
  flags keys that no longer appear in the source (candidates for removal),
  without discarding existing translations — this is not a one-time
  snapshot, the codebase keeps growing.
- A generic, parameterized "add language X" task template (the target
  language name as its only variable) — the actual deliverable the user
  is after — that can be handed to a collaborator (e.g. Mistral, per this
  project's established multi-AI workflow) to execute the repeatable half
  of adding a new language: run the catalog tool, translate the resulting
  key list, save the locale file, verify via the coverage-check tool.
- `add_lang_arg()`/`--lang` moves from a fixed `choices=["de", "en"]` to
  dynamic discovery of whatever locale files exist under
  `scripts/modules/locales/`.

## Capabilities

### New Capabilities
- `catalog-based-i18n`: defines the key-based `t()` mechanism, the locale
  catalog file format and location, the codemod that migrates existing
  call sites, the coverage-check and catalog-regeneration tooling, and the
  parameterized process for adding a new language.

### Modified Capabilities
- `cross-cutting-conventions`: the "No hardcoded single-language
  user-facing output" requirement's scenario currently cites the literal
  `t("DE text", "EN text")` call pattern as the correct form — this needs
  updating to the key-based `t("key")` form now that it's the actual
  convention new code must follow.

## Impact

- `scripts/modules/i18n.py` — rewritten around key-based lookup instead of
  positional DE/EN arguments.
- All ~4,964 `t()` call sites across `scripts/` — mechanically converted by
  a codemod, not hand-edited.
- New: `scripts/modules/locales/{de,en}.json` (and future language files),
  a codemod/migration tool, a coverage-check tool, a catalog-regeneration
  tool.
- `scripts/health_config.py` / CLI scripts using `add_lang_arg()` — dynamic
  language-choice discovery instead of the hardcoded `["de", "en"]` list.
- `openspec/specs/cross-cutting-conventions/spec.md` — scenario update for
  the new `t()` call form.
- Every script's docstring `@usage` block that shows a `t("DE", "EN")`
  example needs no change (docstrings are developer documentation, not the
  runtime mechanism) unless it also shows actual `t()` call examples from
  the body — to be confirmed during implementation which docstrings, if
  any, quote real call syntax rather than just describing behavior.
