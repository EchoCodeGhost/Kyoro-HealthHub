## Context

Triggered while manually extending `ANIMAL_SYNDROME_MAP` (roe deer,
red deer, wild boar, fox, rodents, bats, wild birds, ticks) after reading
a published case report of tularaemia transmitted by blood contact from
a roe deer during a car collision — an association nobody would think to
add proactively, and that the existing static mapping structurally
cannot surface on its own.

The project already has continuous outbreak/surveillance ingestion
(`import_outbreak_data.py`: WHO all 6 regions, ECDC, ProMED, RKI
SurvStat/GrippeWeb/ARE, LGL Bayern, WAHIS/WOAH, CDC Travel, HealthMap,
Eurosurveillance, ReliefWeb, CRM) and an LLM-assisted analysis layer
(the `system_prompt` fields in `scripts/analysis/syndromes/*.json`,
consumed by `analyse_postinfectious_diagnose.py`). This change combines
both existing capabilities for a new purpose rather than introducing
new infrastructure.

## Goals / Non-Goals

**Goals:**
- Surface unusual/newly-described animal→human transmission pathways
  from a small set of case-report-style sources, on a cadence a human
  can realistically review (not real-time).
- Keep the human in the loop for every reference-data change — this is
  clinical-adjacent data, not a domain where automated best-guess merges
  are acceptable.
- Reuse existing source-fetching (ProMED via `import_outbreak_data.py`)
  instead of building a parallel feed layer.

**Non-Goals:**
- No fully autonomous updates to `ANIMAL_SYNDROME_MAP` or
  `endemic_regions` — every candidate requires explicit human
  confirmation before merge, no exceptions.
- Not a diagnostic system and not a replacement for
  `analyse_pathogen_exposure.py`'s geo-/time-matched analysis — this
  change only keeps the *reference data* that other tools already
  consume more current.
- No new external feed infrastructure duplicate of
  `import_outbreak_data.py` — if ProMED/PubMed access needs new
  plumbing, that plumbing belongs in that importer, not duplicated here.
- No commitment yet to real-time or even daily cadence — likely a
  manually-triggered or infrequent (e.g. monthly) run, given the low
  rate of genuinely new transmission-pathway case reports.

## Decisions

- **Source scope, deliberately narrow at first:** ProMED-mail only for
  the first iteration (already integrated, well-suited to unusual
  single-case reports, does not require a new API integration). A
  PubMed case-report query is a plausible later addition, not part of
  the first cut.
- **Extraction:** LLM-assisted structured extraction (animal, syndrome
  slug from the existing `scripts/analysis/syndromes/` set, transmission
  mechanism, source citation/URL) from each new ProMED item since the
  last run. Items that don't clearly map to an existing syndrome slug
  are surfaced as "no matching syndrome — needs a new syndrome file
  first, out of scope for auto-merge" rather than forced into an
  approximate match.
- **Review queue:** a local JSON file (same local-first, no-new-infra
  pattern as `manage_exposure_history.py`), with its own small CLI
  (`show` / `confirm <n>` / `discard <n>`) — confirmed entries get
  written into `ANIMAL_SYNDROME_MAP` and, where relevant, an
  `endemic_regions` entry; discarded ones are logged but not retried.
- **Provenance:** every merged entry carries its source citation
  (ProMED post ID/URL, publication date) so a future reader can see
  *why* an association exists, not just that it does — matches the
  project's existing `@refs` convention on syndrome files.

## Risks / Trade-offs

- [Risk] LLM extraction could hallucinate an association or misread a
  case report → Mitigation: mandatory human confirmation before any
  merge; source citation always carried along for verification.
- [Risk] ProMED includes unconfirmed/preliminary reports → Mitigation:
  confirmed entries are still flagged as "single case report" provenance
  in the merged data, not elevated to the same confidence level as
  well-established associations (e.g. Q-Fieber↔Rind).
- [Risk] Scope creep toward a general-purpose medical-literature-scanning
  system → Mitigation: explicitly out of scope per Non-Goals above; this
  change only feeds two specific, already-existing static structures.
