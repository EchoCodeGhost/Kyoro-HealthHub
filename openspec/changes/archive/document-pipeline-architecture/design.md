## Context

The pipeline order already exists in full in the code
(`scripts/import_all.py`, `scripts/compute_all.py`, `scripts/analyse_all.py`)
and is documented as a fixed dependency order in the header comment of
`compute_all.py`. This change transfers that knowledge into a spec, but
does not change behavior.

## Goals / Non-Goals

**Goals:**
- Record existing pipeline behavior as spec requirements/scenarios.
- Give contributors a reliable reference for why the order is mandatory
  (rather than just convention).

**Non-Goals:**
- No change to `import_all.py`, `compute_all.py`, or `analyse_all.py`.
- No automation/enforcement of the order via code (e.g. locking,
  dependency checks) — that would be a separate, later change.

## Decisions

- One `pipeline-architecture` spec instead of three separate specs per
  stage, since the three stages only make sense together (the order
  itself is the core requirement, not each stage in isolation).
- Requirements follow CLAUDE.md's "Pipeline stages" section 1:1, no new
  rules invented.

## Risks / Trade-offs

- [Risk] The fixed compute dependency order only lives in the header
  comment of `compute_all.py`, not in structured form (no list in the
  spec itself, since it changes with new compute scripts) → Mitigation:
  the spec references the source instead of duplicating the order, to
  avoid drift.
