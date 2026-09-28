## MODIFIED Requirements

### Requirement: Bilingual user-facing output
User-facing text (console output, report text, error messages intended for
the user rather than a stack trace) SHALL use `t("<key>")` from
`modules/i18n.py`, with the string itself defined in the German and
English locale catalogs (`scripts/modules/locales/de.json`,
`.../en.json`), instead of a hardcoded single-language string or an inline
literal string passed directly to `t()`.

#### Scenario: New script prints a status message
- **WHEN** a contributor adds a `print()` call with user-facing text (e.g.
  a progress message or a computed summary)
- **THEN** the text is wrapped in `t("<key>")`, with a German and English
  entry added under that key to the respective locale catalog files, so
  the output respects the project's `KYORO_LANG` / `--lang` language
  selection

#### Scenario: Internal log line, not user-facing
- **WHEN** a message is a developer-facing debug/log statement never shown
  to the end user in normal operation
- **THEN** this requirement does not apply — it covers user-facing output
  only, not internal logging
