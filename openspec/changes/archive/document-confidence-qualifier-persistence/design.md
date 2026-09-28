## Context

`documentation-conventions` already has a "Finding-confidence labeling via
a shared module" requirement, scoped to script-generated output
(`scripts/modules/confidence.py`, three levels: confirmed/suspected/open
lead). It worked exactly as designed for one such pipeline: the compute
script's docstring explicitly states the output is not a clinical
diagnosis, the generated report text consistently uses a hedged phrasing
rather than an unqualified statement, and the underlying DB columns are
named with an explicit `_possible`/`_suspected` suffix rather than an
unqualified name. Every layer of the automated pipeline correctly hedged
the finding.


## Goals / Non-Goals

**Goals:**
- Extend the existing confidence-labeling principle, in the same spirit
  and the same capability, to cover hand-authored narrative synthesis
  documents that restate script-sourced or DB-sourced findings — not just
  the scripts' own generated output.
- Keep the new requirement narrowly scoped to the actual failure mode
  (confidence qualifier lost during narrative restatement), so it's
  checkable in principle rather than a vague "keep documentation accurate"
  mandate.

**Non-Goals:**
- Not requiring `intern/` documents to use `confidence.py` programmatically
  — they are hand-authored Markdown, not Python scripts with structured
  docstrings. The requirement is about preserving the qualifier in prose,
  not about wiring `intern/` into the `@tier`/`confidence.py` machinery
  built for `scripts/`.
- Not building automated tooling to detect qualifier loss in this change.
  Matching a restated claim in a large narrative document back to its
  confidence-labeled source would require some form of semantic diffing —
  nontrivial, and explicitly left as a documented open question, same
  pattern as the still-open device-agnosticism and hardcoded-personal-
  dates automation questions in sibling changes.
- Not mandating a full audit of every existing `intern/` document in this
  change. The affected passages were already corrected in the
  conversation that motivated this proposal; this change documents the
  convention going forward, it does not re-scope past work.

## Decisions

**Extend `documentation-conventions`, not a new capability.** This is the
same underlying principle (confidence must travel with a finding) applied
to one more surface (narrative prose) rather than a conceptually new rule.
A new capability was considered and rejected: splitting "confidence
labeling in code" and "confidence labeling in narrative docs" into two
specs would let them drift out of sync with each other, when they are
meant to express one policy.

**Requirement framed as "restatement inherits the source's qualifier," not
"re-verify against the source every time."** The practical failure mode
was a qualifier silently dropped while copying/summarizing, not a stale
qualifier that needed re-checking against changed data. The requirement
targets the specific, observed defect.

**No automated check in this change.** Same rationale as sibling
conventions changes: documenting the requirement first makes a future
automated check specifiable (e.g. a script that greps `intern/` documents
for finding-adjacent keywords cross-referenced against known
confidence-labeled DB columns), without blocking this change on building
one that doesn't exist yet.

## Risks / Trade-offs

[Risk: requirement is unenforceable without tooling, so it depends on
manual discipline — exactly what already failed once] → Mitigation: same
honest framing as the sibling `cross-cutting-conventions` change — this
spec makes the rule reviewable and gives a concrete checklist item for the
next `/audit` pass over hand-authored case-synthesis documents, it does not
claim to prevent the failure by itself.

[Risk: overreach — contributor starts hedging every sentence in a
narrative document out of caution, making it unreadable] → Mitigation: the
requirement is scoped to findings that originate from a confidence-labeled
source (a script output or a hedged DB column); established, independently
confirmed clinical facts (lab-confirmed diagnoses, documented specialist
findings) are not affected.

## Open Questions

- Should a future automated check for this live as a new `check_*.py`
  script, or as an extension of the `/audit` skill's existing scope? Left
  open — no automation is built in this change.
