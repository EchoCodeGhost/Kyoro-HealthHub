## ADDED Requirements

### Requirement: Key-based translation lookup
`t()` SHALL accept a single stable string key and return the translated
string for the active language by looking it up in that language's locale
catalog, instead of accepting literal per-language strings as positional
arguments.

#### Scenario: Call site requests a translation
- **WHEN** code calls `t("orthostatic_test.supine_label")` with the active
  language set to `"en"`
- **THEN** `t()` returns the English string stored under that key in
  `scripts/modules/locales/en.json`

#### Scenario: Key missing from the active language's catalog
- **WHEN** the active language's locale file has no entry for the
  requested key
- **THEN** `t()` falls back to the English catalog entry for that key, and
  this fallback is visible to the coverage-check tool (not silently
  invisible to a maintainer)

#### Scenario: Key missing from every catalog, including English
- **WHEN** a key is requested that exists in no locale file at all (e.g. a
  typo in the key, or a call site added without running the catalog
  tooling)
- **THEN** `t()` raises a clear error identifying the missing key, rather
  than returning a placeholder or empty string — a silently blank UI
  string is worse than a loud failure during development

### Requirement: Locale catalog file format
Each supported language SHALL have one flat JSON file at
`scripts/modules/locales/<lang>.json` mapping every known translation key
to that language's string. German and English SHALL use this same format
and location as every other language — neither has special inline-string
status.

#### Scenario: Adding a translation for an existing key
- **WHEN** a maintainer or collaborator wants to supply a Russian
  translation for an existing key
- **THEN** they add or edit a single `"<key>": "<Russian text>"` entry in
  `scripts/modules/locales/ru.json` — no source code changes anywhere else
  are needed

### Requirement: Automated call-site migration
The ~4,964 existing `t(de, en)` call sites SHALL be converted to
`t("<key>")` by an automated codemod, not by hand-editing, with the
original German and English strings preserved verbatim into
`de.json`/`en.json` under the generated keys.

#### Scenario: Codemod run against the current codebase
- **WHEN** the migration codemod is run once against `scripts/`
- **THEN** every `t(de, en)` call site becomes `t("<key>")`, `de.json` and
  `en.json` contain every original string pair under matching keys, and
  the pre-migration and post-migration behavior of every script is
  identical for German and English output

#### Scenario: Duplicate DE/EN string pairs across unrelated call sites
- **WHEN** two unrelated call sites happen to share the exact same German
  and English strings (e.g. a common status word used in several scripts)
- **THEN** the codemod either assigns them the same key deliberately (one
  shared catalog entry, acceptable since the text is identical) or
  distinguishes them with separate keys — this SHALL be a documented,
  deliberate choice in the migration tool, not an accidental side effect
  of whatever key-generation happens to produce

### Requirement: Catalog coverage check
A coverage-check tool, following this project's existing `check_*.py`
QA-tool pattern, SHALL report per locale file how many and which catalog
keys are missing a translation.

#### Scenario: Running the coverage check for a partially translated language
- **WHEN** a maintainer runs the coverage-check tool against a locale file
  that only covers some of the known keys
- **THEN** the tool reports the count and list of missing keys for that
  language, distinguishing it from a fully covered language

#### Scenario: Coverage check integrated into the QA gate
- **WHEN** `tools/qa_check.py` runs
- **THEN** it includes the coverage-check tool's result for at least
  German and English (both must stay at 100% coverage, since they are the
  canonical source languages) — partial coverage of a newly added
  third-plus language SHALL NOT fail the QA gate, only be reported

### Requirement: Catalog regeneration stays in sync with the codebase
A catalog-regeneration tool SHALL be re-runnable as new `t()` calls are
added over time: it adds newly discovered keys to every locale file
(untranslated, ready to fill in) and flags keys that no longer appear in
any call site as removal candidates, without discarding existing
translations for keys still in use.

#### Scenario: A new t() call is added to the codebase
- **WHEN** a contributor adds a new `t("some.new.key")` call and a matching
  `de.json`/`en.json` entry, then runs the regeneration tool
- **THEN** every other language's locale file gains a placeholder entry
  for the new key (or is flagged as missing it), and no existing
  translated entries in any locale file are altered or removed

#### Scenario: A t() call is removed from the codebase
- **WHEN** a call site using a given key is deleted and the regeneration
  tool is run
- **THEN** the tool flags that key as an unused/removal candidate in every
  locale file rather than silently deleting translated content

### Requirement: Dynamic language selection
`add_lang_arg()` and `set_lang()` SHALL discover available languages from
the set of locale files present under `scripts/modules/locales/`, instead
of a hardcoded `["de", "en"]` choice list.

#### Scenario: A new locale file is added
- **WHEN** `scripts/modules/locales/ru.json` exists with at least a
  partial translation
- **THEN** `--lang ru` becomes a valid, discoverable choice on every CLI
  script without any script-by-script code change

### Requirement: Parameterized process for adding a language
The project SHALL document a single, reusable process for adding a new UI
language, parameterized only by the target language, suitable for handing
to a collaborator (human or AI) to execute without redesigning the
approach per language.

#### Scenario: Handing off "add Spanish" to a collaborator
- **WHEN** a maintainer wants Spanish added as a supported language
- **THEN** the handoff consists of: run the catalog-regeneration tool to
  get the current key list, translate the keys into
  `scripts/modules/locales/es.json`, run the coverage-check tool to
  confirm completeness — the same three steps apply verbatim for any other
  target language, with only the language name/code changing
