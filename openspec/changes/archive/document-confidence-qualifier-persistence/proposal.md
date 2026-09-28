## Why

The `documentation-conventions` capability already requires every analysis
script's *generated* output (report text, plot title, LLM prompt context) to
label findings as confirmed/suspected/open lead via
`scripts/modules/confidence.py`. That requirement worked as intended: one
such pipeline (a compute script, its corresponding analysis script, and a
DB column pair named with an explicit `_possible`/`_suspected` suffix)
consistently hedged its finding as suspected/possible, never as confirmed.
The gap was one layer further out: a hand-authored narrative synthesis
document under `intern/` that restates and cross-references findings
from these scripts across many sections, had the "wearable-detected, not
clinically confirmed" qualifier correctly attached in one section (added
in an earlier correction) but silently dropped in roughly a dozen other
sections that had each independently copied/expanded the same underlying
finding over months. An AI assistant later read one of the unqualified
copies and reported a wearable-suspected finding as confirmed — a
defect caught only because the actual result on file said otherwise.
The existing requirement doesn't cover
this failure mode because it's scoped to script-generated output, not to
manually maintained prose that summarizes script output over time.

## What Changes

- New requirement in the existing `documentation-conventions` capability:
  when a hand-authored narrative synthesis document restates a finding that
  originates from a confidence-labeled source (a `confidence.py`-labeled
  script output, or a hedged DB column/table such as a
  `<finding>_possible`/`<finding>_suspected` pair), the
  restatement SHALL preserve the same confidence qualifier — it SHALL NOT
  silently upgrade a suspected/possible finding to unqualified fact during
  summarization or copying into a new section.
- Scoped narrowly to the concrete failure mode (confidence-qualifier loss
  during narrative copying), not a general "review all documentation"
  mandate — this is a targeted extension of the existing confidence-
  labeling requirement, not a new capability.
- Documentation-only change; no code changes required by this proposal
  itself. Whether tooling could ever check this automatically (matching a
  restated finding against its confidence-labeled source) is left as an
  open question in design.md, not implemented here.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `documentation-conventions`: adds a requirement extending the existing
  finding-confidence labeling principle to hand-authored narrative
  synthesis documents, alongside the existing script-output requirement.

## Impact

- No code changes required by this proposal itself (documentation-only).
- Establishes a checkable convention for future edits to narrative
  synthesis documents under `intern/`, cross-referenced from the
  existing confidence-labeling requirement.
- Affected review surface: any hand-authored Markdown document that
  restates findings sourced from confidence-labeled scripts or hedged DB
  columns — primarily the case-synthesis document, potentially comparable
  synthesis documents (e.g. doctor letters under `intern/`)
  if they independently restate the same findings rather than being
  generated from the synthesis document.
