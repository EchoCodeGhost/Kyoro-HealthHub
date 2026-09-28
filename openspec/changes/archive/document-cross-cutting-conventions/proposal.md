## Why

A contributor's PR (merged, then corrected the same day) hardcoded an IANA
timezone string and relied exclusively on one specific device brand being
configured, instead of using the existing `resolve_timezone()` helper and a
device-agnostic fallback chain. Both violations passed code review and were
only caught afterward, one by the automated privacy check, one by manual
inspection against production data. The underlying rules already exist —
scattered across `CLAUDE.md` prose and individual docstrings — but were not
written down as an enforceable, example-backed convention a reviewer (human
or AI) can check a PR against. This proposal captures three such
cross-cutting rules as a formal spec, so they are checkable the same way
`db-schema-conventions` already makes the EAV/person-column/pseudonym rules
checkable.

## What Changes

- New spec capturing three coding conventions that apply to every new
  script, independent of which pipeline stage it belongs to:
  1. No hardcoded IANA timezone strings — use `resolve_timezone(conn,
     person)` in DB-aware code, or `cfg.home_timezone` as a fallback.
  2. No exclusive reliance on one specific configured device/brand for a
     data source that could plausibly come from multiple devices — use a
     preference-ordered, device-agnostic fallback chain instead.
  3. No hardcoded single-language user-facing output — use `t("DE", "EN")`
     from `modules/i18n.py`.
- Does **not** re-cover the existing multi-user (`person` column /
  `OWN_PERSON_ID`) requirement — that is already a formal requirement in
  `db-schema-conventions` and is only cross-referenced here, not duplicated.

## Capabilities

### New Capabilities
- `cross-cutting-conventions`: coding conventions (timezone handling,
  device-agnostic data loading, bilingual output) that apply across
  importers, compute scripts, and analysis scripts alike, independent of
  pipeline stage.

### Modified Capabilities
(none — `db-schema-conventions` is referenced, not changed)

## Impact

- No code changes required by this proposal itself (documentation-only).
- Establishes a checkable convention for future PRs/reviews (human or AI),
  referenced from `CLAUDE.md`'s existing privacy-rules section rather than
  replacing it.
- Affected review surface: `scripts/importers/`, `scripts/compute/`,
  `scripts/analysis/` — anywhere a new script reads a timestamp, a specific
  device's data, or prints user-facing text.
