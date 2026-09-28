## Context

`CLAUDE.md` already states "never hardcode an IANA timezone string" as a
privacy rule, and several docstrings (e.g. `compute_ppi_dfa.py`,
`compute_hr_zones.py`) document device-agnostic fallback behavior as a
`@method` detail. Neither is written as a checkable requirement with
scenarios a reviewer can walk through. The concrete trigger: a merged PR
hardcoded `"Europe/Berlin"` as a timezone default and a device-`id`-only
filter for a data source that in practice comes from whichever wearable
happens to be configured — both slipped past review because there was no
single place stating the rule in reviewable, example-backed form.

## Goals / Non-Goals

**Goals:**
- State the three conventions (timezone, device-agnosticism, i18n) as
  formal, scenario-backed requirements, following the existing
  `db-schema-conventions` style (SHALL/SHALL NOT + Given/When/Then
  scenarios).
- Make each requirement checkable against a specific, real example from
  today's PR review, so the spec is grounded rather than abstract.

**Non-Goals:**
- Not re-deriving the multi-user (`person` column) requirement — already
  covered by `db-schema-conventions`.
- Not building new automated tooling in this change. `check_source_privacy.py`
  already catches hardcoded timezones; device-agnosticism and i18n checks
  are left as a possible future automation, not implemented here.

## Decisions

**Separate capability, not an extension of `db-schema-conventions`.**
`db-schema-conventions` is specifically about the SQLite schema shape (EAV,
person column, pseudonyms). Timezone/device/language conventions apply to
control flow and output, not schema — bundling them would blur what each
spec is for. Alternative considered: extend `db-schema-conventions` with a
"general conventions" section — rejected, since two contributors looking
for "how do I handle timezones" and "how do I add a column" shouldn't have
to read the same document.

**Document-only, no new automated check in this change.** The timezone
rule already has automated enforcement (`check_source_privacy.py`).
Device-agnosticism and i18n do not, and building reliable static checks for
either (detecting "assumes exactly one device" or "hardcoded non-t()
string") is nontrivial and out of scope for a documentation change.
Documenting the requirement first makes a future automated check specifiable.

## Risks / Trade-offs

[Risk: documentation without enforcement gets ignored, same as the
`CLAUDE.md` prose version already was] → Mitigation: none automatic in this
change; the honest expectation is that this spec makes the rule reviewable
(a reviewer — human or AI — can point at a specific requirement/scenario),
not that it prevents the violation by itself. A future automated check
remains an open option, not promised here.

[Risk: device-agnosticism as a blanket rule could be over-applied to cases
where a script legitimately targets one specific device on purpose] →
Mitigation: the requirement is scoped to "a data source that could
plausibly come from multiple devices," with a scenario explicitly carving
out single-device-only cases.

## Open Questions

- Should a future automated check for device-agnosticism live in
  `check_source_privacy.py` (extending its scope beyond privacy) or as a
  separate `check_*.py` script? Left open — no automation is built in this
  change.
