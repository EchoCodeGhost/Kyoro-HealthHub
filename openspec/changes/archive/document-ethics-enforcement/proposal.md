## Why

`docs/ETHICS.md`/`ETHICS_DE.md` mixes narrative values prose (mission,
dignity, aspirational goals) with a subset of rules that are actually
testable/reviewable — prohibited uses, security/privacy minimums, and one
AI-output labelling requirement. Right now those testable rules only exist
as prose inside a values document, so a contributor or reviewer has no
structured requirement/scenario to check a PR against, unlike the existing
`privacy-rules` spec. This change documents only the enforceable subset as
a new OpenSpec capability, mirroring the already-archived
`document-privacy-rules` change. No code changes, no change to ETHICS.md's
content — pure documentation of existing, already-agreed rules.

## What Changes

- New spec `ethics-enforcement` documenting, as SHALL/scenario
  requirements: the prohibited-uses list (Section 4), the security/privacy
  minimums (Section 7), and the AI-output labelling requirement (one point
  from Section 6).
- Short cross-reference added in `docs/ETHICS.md`/`ETHICS_DE.md` at
  Sections 4, 6, and 7 pointing to the new spec as the formal,
  reviewable counterpart of that prose.
- No behavioural change; this documents rules the project already commits
  to in ETHICS.md.

## Capabilities

### New Capabilities
- `ethics-enforcement`: prohibited uses (profiling for
  insurance/employment/credit/law-enforcement, non-consensual surveillance,
  training commercial AI on personal health data without consent, exposing
  identity data to unauthorised parties, discrimination on protected
  characteristics), security/privacy-by-design minimums (local-only DB
  storage by default, DB encryption not bypassed, no world-readable export
  locations, authenticated API access, no secrets in source/logs/error
  output, data minimisation at import, `import_log` not suppressed, no raw
  health values in logs, new dependencies reviewed for telemetry/phone-home
  behaviour, private vulnerability disclosure before public disclosure),
  and AI-output labelling (LLM output must be clearly labelled as
  AI-generated wherever displayed).

### Modified Capabilities
(none — this only adds a new capability; no existing spec's requirements
change)

## Impact

- No code files affected directly.
- References: `docs/ETHICS.md`, `docs/ETHICS_DE.md` (narrative source of
  these rules), `scripts/utils/check_source_privacy.py` (existing
  compliance tooling, unrelated scope), `pwa/backend/` (auth requirement),
  `scripts/modules/db.py` / `health_config.py` (local storage, encryption).
- Serves as a PR-review checklist for contributor-facing rules that were
  previously only stated as prose in an ethics document, not as a spec.
