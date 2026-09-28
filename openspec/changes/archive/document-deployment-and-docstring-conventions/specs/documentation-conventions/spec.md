## ADDED Requirements

### Requirement: Bilingual text (German before English) in user- and contributor-facing content
All user- and contributor-facing text SHALL be bilingual (German first,
then English). In Python code this SHALL be implemented via the
`t("DE", "EN")` helper from `scripts/modules/i18n.py`, with runtime
language selection via `KYORO_LANG`/`--lang`. In non-Python files without
runtime language switching (e.g. systemd units, Caddyfiles, other infra
configs), both languages SHALL appear as consecutive comment lines in the
same content block (German first, then English). Freely-named Markdown
documentation MAY instead exist as two separate files (`<NAME>.md`
English, `<NAME>_DE.md` German) when the filename is not dictated by an
external tool.

#### Scenario: New docstring in a Python script
- **WHEN** a contributor adds a new script with `@purpose`/`@method`/
  `@limits` fields
- **THEN** each of these fields exists in both a `.de` and an `.en`
  variant

#### Scenario: New systemd unit or config file with a fixed filename
- **WHEN** a contributor adds a new deployment file whose filename is
  dictated by the target system (e.g. `symptom-pwa.service`)
- **THEN** German and English comment lines appear paired side by side
  in the same comment block, not as two separate files

#### Scenario: New freely-named Markdown documentation
- **WHEN** a contributor adds a new Markdown documentation file without
  an externally dictated filename (e.g. a deployment guide)
- **THEN** either an inline-bilingual format or the two-file pattern
  (`<NAME>.md` + `<NAME>_DE.md`) SHALL be used, consistent with existing
  examples in the same directory

### Requirement: Structured docstring field schema as the single source of truth
The module docstring of every Python script under `scripts/` with a
`@tier` field SHALL contain the required fields defined in
`docs/docstring_template.md`: `@tier`, `@purpose.de`/`@purpose.en`,
`@method.de`/`@method.en`, `@limits.de`/`@limits.en`, `@reads`,
`@writes`, `@usage`. Optional fields (`@thresholds`, `@scoring`,
`@refs`) SHALL be used when the script contains clinical thresholds, a
scoring formula, or citable references. The docstring SHALL be the sole
source for the generated files under `docs/de/`/`docs/en/` — generated
by `tools/gen_docs.py`, validated by `scripts/check_docstrings.py`.

#### Scenario: New script with a @tier field missing required fields
- **WHEN** `python3 scripts/check_docstrings.py` runs against a script
  whose docstring has a `@tier` field but not all required fields
- **THEN** the script reports the missing required fields and exits with
  a non-zero exit code

#### Scenario: Docstring change without documentation regeneration
- **WHEN** a contributor changes a `@method.de`/`@method.en` field in a
  script without re-running `python3 tools/gen_docs.py`
- **THEN** `tools/gen_docs.py --check` reports a mismatch between the
  committed generated documentation and the current docstring content

#### Scenario: Script is moved or deleted
- **WHEN** a script with existing generated documentation under
  `docs/de/`/`docs/en/` is moved or deleted
- **THEN** `tools/gen_docs.py` reports the corresponding generated
  documentation file as orphaned, until it is manually removed or
  regenerated at the new path
