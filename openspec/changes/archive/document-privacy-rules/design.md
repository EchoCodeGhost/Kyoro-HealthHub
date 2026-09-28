## Context

The privacy rules already exist in full in the code
(`scripts/utils/check_source_privacy.py`) and in CLAUDE.md ("Privacy
rules (this repo is public)"). This change transfers that knowledge into
a spec, but does not change behavior.

## Goals / Non-Goals

**Goals:**
- Record existing privacy conventions as checkable requirements/
  scenarios, so they're clearly traceable in contributor PRs.

**Non-Goals:**
- No change to `check_source_privacy.py` or the forbidden-identifier
  list.
- No new tooling extension (e.g. pre-commit hook) — that would be a
  separate, later change.

## Decisions

- One `privacy-rules` spec instead of splitting by rule type, since all
  rules serve the same goal (no personal data in public code) and should
  be read together as one review checklist.
- Requirements follow CLAUDE.md's "Privacy rules (this repo is public)"
  section 1:1, no new rules invented.

## Risks / Trade-offs

- [Risk] The concrete forbidden-identifier list lives in local,
  non-committed config (`privacy_check.forbidden_identifiers`) and is
  therefore not visible to contributors → Mitigation: the spec describes
  the pattern (generic names, config-only) instead of the list itself,
  so contributors can understand and apply the principle even without
  access to the local config.
