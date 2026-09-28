## Context

CLAUDE.md's Configuration section states "No personal values are hardcoded
in the repo. Every date, device ID, and person identifier comes from
config" as a single sentence covering three distinct things. Two of the
three are already formal, scenario-backed requirements in `privacy-rules`
("No hardcoded timezones" covers timezone strings specifically, not
dates/timestamps in general; "No fallback dicts with hardcoded entity IDs"
covers device/entity IDs; "Person identifiers exclusively via
`OWN_PERSON_ID`" covers person identifiers). The date/timestamp part has no
corresponding requirement — it was raised as a gap while comparing
`cross-cutting-conventions` against a related, but distinct, question
(device/app import coverage) and turned out to be a real, separate gap
worth closing on its own.

## Goals / Non-Goals

**Goals:**
- State "no hardcoded personal date/timestamp literal" as a formal,
  scenario-backed requirement in `privacy-rules`, following the same
  SHALL/SHALL NOT + Given/When/Then style as its sibling requirements.
- Scope the rule to personal/clinical dates specifically (birth date,
  clinical event dates, device install/registry dates), not every date
  literal in the codebase, so it doesn't overreach into legitimate
  non-personal uses of date/timestamp values.

**Non-Goals:**
- Not building new automated tooling in this change. Whether
  `check_source_privacy.py` gets extended to detect hardcoded date
  literals is left as a documented open question, not implemented here —
  same approach the `document-cross-cutting-conventions` change took for
  its device-agnosticism rule, since reliably distinguishing "a personal
  date literal" from "a legitimate non-personal date literal" via static
  analysis is non-trivial (unlike the timezone rule, which matches a closed
  set of IANA strings).
- Not touching the existing, separate documentation rule in CLAUDE.md about
  not hardcoding dates/version numbers/line numbers *in docs* to mark
  *when* something changed (git history is the changelog) — that rule is
  about changelog hygiene in documentation content, this one is about
  personal data leaking into source code logic. Different concern, no
  overlap in scope.

## Decisions

**Add to `privacy-rules`, not `cross-cutting-conventions`.** The date
rule is about the same failure mode as the two sibling requirements
already in `privacy-rules` (device IDs, person identifiers) — a personal
value hardcoded into public source code instead of routed through config
— and shares the same enforcement path (`check_source_privacy.py`).
`cross-cutting-conventions` covers control-flow/output conventions
(timezone *handling*, device-agnostic *loading*, bilingual *output*), not
privacy/data-leakage rules. Alternative considered: add it to
`cross-cutting-conventions` since that capability was the one under
discussion when the gap was found — rejected, because the rule's actual
nature (personal data leakage) matches `privacy-rules`'s existing scope
and its two closest sibling requirements, not `cross-cutting-conventions`'s
scope.

**Scope: personal/clinical dates, not all date literals.** The
requirement targets dates that identify something about a real person
(birth date, clinical event dates, device ownership timelines) — the
same class of value CLAUDE.md's prose already names. Non-personal date
literals (algorithm constants, epoch/calendar arithmetic, externally
cited publication years for medical guidelines) are explicitly carved
out, mirroring the existing carve-out scenario pattern used for
device-agnosticism ("Data source is legitimately single-device by
design").

**Document-only, no new automated check in this change.** Same rationale
as the device-agnosticism and i18n rules in `cross-cutting-conventions`:
documenting the requirement first makes a future automated check
specifiable, without blocking this change on building one.

## Risks / Trade-offs

[Risk: "personal date" is a judgment call a reviewer has to make, unlike
the closed-set timezone-string check] → Mitigation: the requirement text
and scenarios give concrete examples (birth date, clinical event dates,
device install dates) plus an explicit non-personal carve-out, so a
reviewer has a checkable boundary even without automation.

[Risk: overreach — a contributor reads "no hardcoded dates" too broadly
and starts routing every incidental date literal (e.g. a fixed reference
date in a unit test, a schema migration version date) through config] →
Mitigation: the carve-out scenario explicitly limits the requirement to
personal/clinical data, and non-goals section states this is not a
changelog-hygiene rule.

## Open Questions

- Should a future automated check for hardcoded personal dates live in
  `check_source_privacy.py` (extending its scope) or as a separate
  `check_*.py` script? Left open — no automation is built in this change,
  same as the still-open device-agnosticism automation question.
