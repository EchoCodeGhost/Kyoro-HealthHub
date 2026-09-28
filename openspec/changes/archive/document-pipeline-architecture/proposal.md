## Why

Kyoro-HealthHub is a public repo on GitHub. So far,
knowledge of the pipeline order (imports → import_all.py → compute_all.py
→ analyse_all.py) only lives in CLAUDE.md and in the header comment of
`scripts/compute_all.py`. External contributors otherwise have no
structured entry point to understand why the order is fixed and what
happens on a violation (e.g. compute before import, analysis before
compute). This spec makes existing, already-implemented behavior
explicit — no new functionality.

## What Changes

- New spec `pipeline-architecture` documenting the three pipeline
  stages (import → compute → analysis) and their dependency order as
  requirements/scenarios.
- No code change; purely documenting existing behavior.

## Capabilities

### New Capabilities
- `pipeline-architecture`: order and dependencies of the three pipeline
  stages (imports/ → import_all.py → compute_all.py → analyse_all.py),
  including the fixed dependency order among the compute scripts
  themselves and behavior on skipped stages.

### Modified Capabilities
(none — purely new documentation of existing behavior)

## Impact

- Affects no code files directly.
- References: `scripts/import_all.py`, `scripts/compute_all.py`,
  `scripts/analyse_all.py`, as well as the dependency header in
  `scripts/compute_all.py`.
- Serves future contributors as an onboarding reference alongside
  CLAUDE.md.
