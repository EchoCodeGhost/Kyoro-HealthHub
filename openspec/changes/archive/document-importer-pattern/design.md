## Context

The importer pattern already exists in full in the code
(`scripts/modules/base.py`, `scripts/import_all.py`) and in CLAUDE.md
("Adding a new importer"). This change transfers that knowledge into a
spec, but does not change behavior.

## Goals / Non-Goals

**Goals:**
- Record the structural and behavioral requirements for new importers as
  requirements/scenarios, checkable via the `review-importer` skill and
  human reviews.

**Non-Goals:**
- No changes to existing importers or to `import_all.py`.
- No duplication of rules already documented in `db-schema-conventions`
  (EAV, `INSERT OR IGNORE`, the `person` column) — this spec references
  them instead of repeating them.

## Decisions

- An `importer-pattern` spec focuses on what is specific to importers
  (function signature, `log_import()` timing, registration), not on
  general schema rules already covered in `db-schema-conventions`.
- Requirements follow CLAUDE.md's "Adding a new importer" section and
  the actual code in `scripts/modules/base.py` 1:1 — no new rules
  invented.

## Risks / Trade-offs

- [Risk] Overlap with `db-schema-conventions` could lead to
  contradictory documentation if one of the two specs is later changed
  without checking the other → Mitigation: explicit references instead
  of duplicating requirement text.
