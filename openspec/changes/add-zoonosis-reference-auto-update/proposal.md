## Why

Kyoro's animal-/zoonosis-reference data — the `endemic_regions` fields in
`scripts/analysis/syndromes/*.json` and the new `ANIMAL_SYNDROME_MAP` in
`scripts/utils/manage/personal/manage_exposure_history.py` — is static
and only updated when a maintainer manually notices something and edits
the file. Unusual or newly-described transmission pathways (e.g. a
single published case report of tularaemia transmitted via blood contact
from a roe deer in a car collision) never surface automatically, even
though the project already ingests continuous outbreak/surveillance feeds
for other purposes (`import_outbreak_data.py`: WHO, ECDC, ProMED, RKI,
LGL Bayern, WAHIS/WOAH, ...).

This gap was found while manually adding wildlife species (Reh, Hirsch,
Wildschwein, ...) to `ANIMAL_SYNDROME_MAP` after reading exactly such a
case report — the trigger for this change was noticing that the mapping
just built has the identical "static, needs a human to notice" limitation
already documented (and accepted) for `endemic_regions`.

## What Changes

- A new script that periodically (or on demand) scans a small set of
  **case-report-style sources** — primarily ProMED-mail (already an
  outbreak source in `import_outbreak_data.py`, well suited to unusual
  single-case reports) and optionally a narrow PubMed query — for items
  that describe a new or unusual animal-to-human pathogen transmission.
- LLM-assisted extraction of a structured candidate association (animal,
  syndrome slug, transmission mechanism, source citation) from each new
  item.
- A **local review queue** (JSON file, own CLI, same pattern as
  `manage_exposure_history.py`) — candidates are never auto-merged into
  `ANIMAL_SYNDROME_MAP` or `endemic_regions`; a human confirms or
  discards each one first.
- Only confirmed candidates get written into the existing reference
  files, with the source citation carried along.

## Capabilities

### New Capabilities
- `zoonosis-reference-update`: periodic discovery of candidate
  animal-pathogen associations from case-report sources, human-reviewed
  before merging into the existing static reference data
  (`ANIMAL_SYNDROME_MAP`, `endemic_regions`).

### Modified Capabilities
(none — this change only adds a discovery/review step in front of the
existing, unchanged reference-data files; it does not change how
`analyse_pathogen_exposure.py` or `manage_exposure_history.py` consume
that data)

## Impact

- Affects `scripts/utils/manage/personal/manage_exposure_history.py`
  (`ANIMAL_SYNDROME_MAP` becomes a target for reviewed updates, not just
  hand-edits) and `scripts/analysis/syndromes/*.json` (`endemic_regions`
  likewise).
- Reuses the ProMED source-fetching already present in
  `import_outbreak_data.py` rather than adding a parallel feed
  infrastructure — no new external dependency for that part.
- New: an LLM extraction step and a local review-queue file/CLI, both
  new code.
- No impact on existing importers, schema, or the person-override
  convention — this is reference-data tooling, not a data importer for
  personal health data.

**Status:** proposal/design/tasks only — **not started**. Deliberately
scoped as a plan for later, not an active implementation (see
`design.md` Non-Goals and `tasks.md` for the concrete, still-open work).
