## Context

`docs/ETHICS.md`/`ETHICS_DE.md` already exist and were recently revised
to soften several claims that read as absolute guarantees the
project can't back (mosaic framing, accessibility, energy awareness) —
those stay as aspirational prose, deliberately not spec material. A
different subset of ETHICS.md was never meant to be aspirational: Section 4
(Prohibited Uses) and Section 7 (Security and Privacy by Design) are
already written as hard rules ("must", "SHALL"-equivalent), and one bullet
in Section 6 (AI-output labelling) is a concrete, checkable UI requirement.
The existing `privacy-rules` spec already demonstrates the pattern this
project uses for turning prose conventions into a reviewable OpenSpec
capability (see `openspec/changes/archive/document-privacy-rules/`).

## Goals / Non-Goals

**Goals:**
- Give contributors and reviewers a structured, scenario-based checklist
  for the subset of ETHICS.md rules that are actually testable/reviewable,
  matching the `privacy-rules` spec's format.
- Cross-link ETHICS.md/_DE.md to the new spec at the three affected
  sections so a reader lands on the formal version without duplicating
  full requirement text in prose.

**Non-Goals:**
- No change to ETHICS.md's/_DE.md's existing wording or content — this is
  additive documentation, not a rewrite of the values document.
- No new enforcement tooling (e.g. a pre-commit hook or CI check for these
  rules) — that would be a separate, later change if desired.
- Does not cover Sections 1–3, 5, or most of Section 6 — those remain
  normative/narrative only, per the user's explicit scoping (dignity,
  autonomy, chronic-illness rights, LGBTQ+ protections, research-consent
  process, and the AI-risk disclosure list are not being converted).

## Decisions

- **One capability, not three.** All three sources (prohibited uses,
  security minimums, AI labelling) go into a single `ethics-enforcement`
  spec rather than separate specs per section, because they share the
  same audience (contributors/reviewers) and the same purpose (a
  pre-merge checklist), mirroring how `privacy-rules` bundles several
  distinct rule types under one capability for the same reason.
- **Cross-reference, don't duplicate.** ETHICS.md/_DE.md keep their
  existing prose unchanged; a short pointer sentence is added at Sections
  4, 6, and 7 directing readers to `openspec/specs/ethics-enforcement/`
  for the formal requirement/scenario version. The spec's Purpose section
  points back to ETHICS.md/_DE.md as the narrative source, so neither
  document tries to be authoritative for both audiences at once.
- **Requirements phrased from ETHICS.md's existing wording**, not
  reinterpreted or expanded — this change transcribes agreed rules into
  spec format, it does not introduce new rules.

## Risks / Trade-offs

- [Risk] Two documents describing overlapping rules could drift apart over
  time (someone edits ETHICS.md's Section 7 without updating the spec, or
  vice versa) → Mitigation: the cross-reference sentences make the
  relationship explicit, and both documents are small enough that a
  future editor is likely to see both; no automated sync is attempted in
  this change.
- [Risk] Some Section 7 items (e.g. "API tokens must never appear in
  logs") are hard to verify by an automated check today and rely on
  reviewer diligence → Mitigation: scenarios describe the reviewable
  condition (what a PR/reviewer should look for), not a specific tool;
  automating any of them is out of scope here.
