## Context

Sun-a-ware is a body-worn UV/sun-exposure tracking device. Neither the
file format (CSV? JSON? proprietary app export file?) nor field
names/units are currently known — no sample file exists in the repo or
in `imports/`. This change is deliberately incomplete: it documents the
planned structure following the established importer pattern, without
making assumptions about the actual data format that could later turn
out to be wrong.

## Goals / Non-Goals

**Goals:**
- Demonstrate the importer-pattern workflow (`/opsx:propose` → spec
  delta → tasks) on a real, currently open backlog item.
- Record the blocker (missing format) as an explicit, non-skippable
  first task.

**Non-Goals:**
- No implementation of parser logic before the format is known — any
  attempt to guess the format would rest on assumptions that are highly
  likely to be wrong.
- No commitment to concrete `metric` names or units in this change —
  that follows only after reviewing the sample file.

## Decisions

- This change deliberately stays at the proposal/design/tasks level
  without spec-delta implementation details for field mappings, since
  these cannot be responsibly determined without a sample file. The spec
  file (`specs/sun-a-ware-import/spec.md`) therefore only describes the
  structural requirements that apply regardless of the concrete format
  (importer-pattern conformance), not the data fields themselves.

## Risks / Trade-offs

- [Risk] Without a sample file, any assumption about the export format
  remains speculative → Mitigation: task 1 explicitly requires obtaining
  a real export file before task 2 (parser implementation) may begin.
