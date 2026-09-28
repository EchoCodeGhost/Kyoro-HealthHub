## Context

The schema conventions already exist in full in the code
(`scripts/utils/create_schema.py`, `scripts/utils/base.py`) and in
CLAUDE.md ("Database design", "Conventions"). This change transfers that
knowledge into a spec, but does not change behavior.

## Goals / Non-Goals

**Goals:**
- Record existing schema conventions as requirements/scenarios, so
  they're checkable in code reviews and contributor PRs.

**Non-Goals:**
- No change to `create_schema.py` or existing tables.
- No new validation tooling (e.g. an automatic schema linter) — that
  would be a separate, later change.

## Decisions

- One `db-schema-conventions` spec instead of separate specs per table,
  since this is about recurring patterns that apply across tables.
- Requirements follow CLAUDE.md's "Database design" and "Conventions"
  sections 1:1, no new rules invented.

## Risks / Trade-offs

- [Risk] Conventions might have exceptions in practice (e.g. individual
  tables without a `person` column for historical reasons) → Mitigation:
  requirements are phrased as SHALL for new code, not as a claim that
  every existing table is already conformant.
