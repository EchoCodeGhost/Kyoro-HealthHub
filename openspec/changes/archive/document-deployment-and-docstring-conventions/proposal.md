## Why

While cleaning up the `manage_*` scripts, a real Linux
username and an absolute home path were found hardcoded in the
`[Service]` directives of `pwa/symptom-pwa.service` (and its duplicate
under `tools/KST-PWA/`) — a violation of the spirit of the existing
`privacy-rules` spec, which currently only covers source code (Python
identifiers, timezones, fallback dicts) and says nothing about
deployment artifacts (systemd units, Caddyfiles). Both files were
already switched to a `CHANGEME` placeholder ad hoc; but this rule
exists nowhere as a binding requirement, so the next contributor could
repeat the same mistake.

At the same time, the project has lived two further conventions since
the start that were never recorded as a spec anywhere: consistent
bilingualism (German first, then English) in all user-/
contributor-facing text, and a structured docstring field schema
(`@tier`, `@purpose.de/en`, `@method.de/en`, `@limits.de/en`, `@reads`,
`@writes`, `@usage`, optionally `@thresholds`/`@scoring`/`@refs`), which
via `tools/gen_docs.py` is the sole source for the generated docs under
`docs/de/`/`docs/en/` and is validated by
`scripts/check_docstrings.py`. Both are documented extensively in
`docs/docstring_template.md` and `docs/docstring_faq.md`, but (unlike
DB schema, importer pattern, and pipeline architecture) were never
formalized as a binding spec — analogous to the already-archived
`document-*-conventions` changes.

## What Changes

- New requirement in the existing `privacy-rules` spec: deployment
  artifacts (systemd units, Caddyfiles, similar infra configs) SHALL NOT
  hardcode real host/user names or absolute paths, but use a generic
  placeholder (`CHANGEME`) instead, replaced by a documented `sed`
  one-liner at deployment time.
- New spec capability `documentation-conventions` with two requirements:
  - Bilingualism (German before English) for all user-/
    contributor-facing text — in Python via `t("DE", "EN")`
    (`scripts/modules/i18n.py`) at runtime, in non-Python files (systemd
    units, configs) as side-by-side comment blocks, since there's no
    runtime language switching there.
  - The structured docstring field schema as a binding requirement
    (previously only documented in `docs/docstring_template.md`):
    required fields, validation via `check_docstrings.py`, the docstring
    as the sole source for generated docs via `tools/gen_docs.py`.

## Capabilities

### New Capabilities
- `documentation-conventions`: bilingualism convention (DE/EN) for all
  user-/contributor-facing text, plus the structured docstring field
  schema as the single source of truth for generated docs.

### Modified Capabilities
- `privacy-rules`: new requirement "No hardcoded host/user values in
  deployment artifacts" extends the existing scope (previously only
  source code) to infra/deployment files.

## Impact

- Affected files (already fixed, now retroactively specified):
  `pwa/symptom-pwa.service`, `tools/KST-PWA/symptom-pwa.service`.
- No code changes required by this change itself — it formalizes lived
  practice (docstring convention, bilingualism) and closes a gap in
  `privacy-rules`. Future deployment files and docstrings will be
  checked against the new requirements.
- No breaking changes.
