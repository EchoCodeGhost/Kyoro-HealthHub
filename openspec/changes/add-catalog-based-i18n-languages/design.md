## Context

`modules/i18n.py`'s `t(de, en)` is called ~4,964 times across `scripts/`
with both language strings inline as literal arguments — no central
catalog, the translations are the source code. Many call sites use
f-strings with interpolated variables (e.g.
`t(f"{n} Tage", f"{n} days")`), evaluated *before* `t()` is called — `t()`
today just picks one already-substituted string. Adding a third language
under the current design means either sweeping all ~5000 sites again per
new language, or (a rejected lighter option) keying an external catalog by
the literal German string, which makes the German UI text double as a
lookup key — editing that text for clarity later would silently break
every other language's translation for it. The user confirmed the fuller
fix: convert every call site to a stable, opaque key, with German and
English becoming ordinary catalog languages like any other.

## Goals / Non-Goals

**Goals:**
- One-time, automated (not hand-edited) migration of all ~4,964 call
  sites to `t("<key>")`.
- German and English get no special treatment vs. a third language —
  same file format, same location, same tooling.
- f-string interpolation continues to work after the migration.
- A repeatable process for adding a language, parameterized only by the
  language itself.
- Byte-identical German/English output before and after migration.

**Non-Goals:**
- Translating any content into a third language as part of this change —
  this change only builds the mechanism and tooling; the "add language X"
  template document is the reusable artifact, not an actual Russian/
  Spanish/French catalog delivered here.
- A general-purpose i18n framework (pluralization rules, ICU message
  format, RTL layout, etc.) — this project's needs are simple
  string/template substitution; don't import that complexity speculatively.
- Changing `docs/de|en/*` per-script documentation or docstring
  `@purpose.de`/`@purpose.en` tags — those are a separate, existing
  bilingual-docstring convention (developer-facing documentation, not
  runtime UI text) and are out of scope here.

## Decisions

**Keys are generated from the English string, namespaced by module path,
not from the German string.** Format:
`<dotted.module.path>.<slug_of_english_text>`, e.g.
`compute.compute_pem.no_baseline_available`. English over German because
key names read as identifiers, and this project already has non-German
contributors/AI collaborators (Mistral) who benefit from English-legible
keys even though German is the default *output* language. A short numeric
suffix (`_2`, `_3`, ...) is appended only on a real collision within the
same module-path prefix — the codemod SHALL NOT silently reuse a key
across unrelated call sites in different files just because the text
happens to match; see the spec's "Duplicate DE/EN string pairs" scenario
for the one exception (deliberately shared, e.g. a common status word),
which the migration tool must call out for a human decision, not infer
silently.

**f-string call sites become template strings + format kwargs, not
pre-substituted text.** `t(f"{n} Tage", f"{n} days")` becomes
`t("steps.days_count", n=n)`, with the catalog storing
`"steps.days_count": "{n} Tage"` (a `str.format()`-style template) and
`t()` performing `catalog[key].format(**kwargs)` after lookup. The codemod
handles this automatically **only** for f-strings whose interpolated
expressions are bare names or simple attribute/subscript access (`{n}`,
`{obj.attr}`, `{d[key]}`) — anything with an operator, function call, or
format spec beyond simple ones (`{a + b}`, `{some_func(x)}`) is flagged
for manual review rather than guessed at, since silently mis-converting an
expression into a wrong kwarg reference would be a runtime bug, not just a
missed translation.

**Fallback chain on a missing key: requested language → English → error.**
Never German as the fallback for a third language — English is the more
neutral pivot language for someone who explicitly chose neither German nor
English. German and English themselves have no fallback between each
other: both must stay at 100% coverage (enforced by the QA gate), so a
missing DE or EN entry is a bug in the migration/regeneration tooling, not
a normal runtime condition.

**Migration is AST-based, not regex-based.** `t()` call sites include
multi-line calls, nested strings, and f-strings with braces — a regex
codemod risks mismatching call boundaries or string content. Use Python's
`ast` module (or `libcst` if precise formatting/comment preservation
across the ~365 files matters, which it does — this is a huge diff
already without also reformatting unrelated code) to locate every `t(...)`
call, extract both string arguments (or flag non-literal arguments for
manual handling — e.g. a call site that already passes a variable instead
of a literal string is a pre-existing edge case to find and resolve
first), and rewrite in place.

**Migration validation: byte-identical output check.** Before rewriting,
the migration tool captures, for every call site, the literal DE and EN
strings it extracted (pre-substitution templates). After rewriting and
regenerating catalogs, a validation pass re-renders every key in both
languages and diffs against the captured originals — any mismatch blocks
the migration from being considered complete. This is the closest thing to
a regression test for a 5000-site mechanical rewrite; per this project's
testing standard, "the codemod looked right" is not sufficient evidence
on its own.

**Coverage-check tool is a new `scripts/utils/check_i18n_coverage.py`**,
following the existing `check_*.py` pattern (`check_no_dates.py`,
`check_source_privacy.py`), wired into `tools/qa_check.py` alongside them.
German/English coverage <100% fails the gate (would indicate the
migration/regeneration tooling has a bug); any other language's coverage
is reported but does not fail the gate.

## Risks / Trade-offs

- **[Risk] A ~5000-site automated rewrite across ~365 files is a large,
  hard-to-fully-manually-review diff.** → Mitigation: the byte-identical
  output validation pass above is the primary safety net, not manual
  review of every hunk; manual review focuses on spot-checks and on every
  call site the codemod flagged as needing human handling (complex
  f-string expressions, non-literal arguments).
- **[Risk] Key collisions across similar strings in the same module.** →
  Mitigation: numeric disambiguation suffix, plus the migration tool
  prints a report of every collision it resolved so a maintainer can spot
  check for accidental key reuse vs. genuinely-intended sharing.
- **[Risk] Catalog files (~5000 entries across de.json/en.json) become a
  large, hard-to-review JSON diff on future changes.** → Accepted:
  alternative (keeping strings inline) is exactly the scalability problem
  this change exists to fix; a flat JSON catalog is still far more
  reviewable than a second full-codebase sweep per language.
- **[Trade-off] Namespacing keys by module path means moving a
  print/message to a different file changes its key.** → Accepted: this
  is visible in the catalog diff (a rename), which is more auditable than
  a key that silently stays put while meaning drifts, or a location-
  independent key scheme that loses the "where is this used" context
  entirely.

## Migration Plan

1. Build the migration codemod + catalog-regeneration tool + coverage
   checker (see tasks.md) against a small pilot subset first (e.g. one
   module) to validate the key-generation and f-string-handling approach
   before running it repo-wide.
2. Run the codemod once, repo-wide, producing `de.json`/`en.json` and the
   rewritten call sites in one commit-able change.
3. Run the byte-identical validation pass; fix any flagged call sites
   (manual f-string handling, non-literal arguments) before proceeding.
4. Wire `check_i18n_coverage.py` into `tools/qa_check.py`.
5. Update `cross-cutting-conventions`'s scenario text (per the spec delta)
   and any docstrings that quote the old `t("DE", "EN")` call form as a
   literal example.
6. Write the parameterized "add language X" task template as a standalone
   document (e.g. `docs/CONTRIBUTING.md` section or a template file under
   `templates/`) — the deliverable the user actually asked for.

Rollback: this is a source-only, no-DB-schema change. Reverting the
migration commit(s) fully restores the previous `t(de, en)` mechanism.
