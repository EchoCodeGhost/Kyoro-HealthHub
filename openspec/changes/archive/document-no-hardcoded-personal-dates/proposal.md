## Why

CLAUDE.md already states, as prose, "No personal values are hardcoded in the
repo. Every date, device ID, and person identifier comes from config." Two of
the three parts of that sentence are already formalized as checkable
requirements in `privacy-rules` — device IDs via "No fallback dicts with
hardcoded entity IDs" and person identifiers via "Person identifiers
exclusively via `OWN_PERSON_ID`". The date/timestamp part was never turned
into its own requirement with scenarios a reviewer (human or AI) can check a
PR against — it only exists as unstructured prose, the same gap that
motivated formalizing the timezone and device-agnosticism rules into
`cross-cutting-conventions`.

## What Changes

- New requirement in the existing `privacy-rules` capability: source code
  SHALL NOT hardcode a personal/clinical date or timestamp literal (e.g.
  birth date, clinical event dates such as infection/diagnosis dates, device
  install dates) — such values SHALL come from config instead (e.g.
  `user.birthdate`, `clinical.events`, `device_registry[].date_from`).
- An explicit carve-out scenario for date/timestamp literals that are not
  privacy-sensitive (algorithm constants, epoch/calendar arithmetic,
  externally cited publication years for medical guidelines — already
  permitted elsewhere as citations), so the rule targets personal data
  leakage and not every literal date in the codebase.
- Documentation-only change; no code changes required by this proposal
  itself. Whether `check_source_privacy.py` should be extended to detect
  this pattern automatically, or left as a future automation step, is
  decided in design.md (the same open-question pattern used for the
  device-agnosticism rule in `document-cross-cutting-conventions`).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `privacy-rules`: adds a new requirement, "No hardcoded personal
  dates/timestamps", alongside the existing "No hardcoded timezones" and "No
  fallback dicts with hardcoded entity IDs" requirements.

## Impact

- No code changes required by this proposal itself (documentation-only).
- Establishes a checkable convention for future PRs/reviews (human or AI),
  cross-referenced from CLAUDE.md's existing "No personal values are
  hardcoded in the repo" line rather than replacing it.
- Affected review surface: `scripts/importers/`, `scripts/compute/`,
  `scripts/analysis/`, `scripts/query/` — anywhere a new script defines a
  default parameter value, a fallback, or a comparison threshold involving a
  specific date or timestamp.
