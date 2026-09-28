## Context

`add-guided-anamnesis-interview` introduces `anamnese_findings`, a resumable, unverified staging table for structured facts extracted during an LLM-driven interview (five tracks: exposure/travel, animal contact, family history, occupational history, leisure & hobbies). Separately, this project already has four mature local JSON stores for the same categories of information, each with its own interactive `manage_*.py` script and each already consumed by real downstream tooling:

- `family_history.json` (`manage_family_history.py`) — read by doctor-letter material and the family-anamnesis section of `intern/` documents.
- `travel_history.json` (`manage_travel_history.py`) — read by `analyse_outbreak_exposure.py`, `import_travel_environment.py`, `geocode_stays.py`, `export_arzt_komplett.py`.
- `exposure_history.json` (`manage_exposure_history.py`) — single nested object (`childhood_environment`, `animal_contacts[]`, `occupational_exposures[]`, `sexual_history`), read by `analyse_pathogen_exposure.py`.
- `known_risk_exposures.json` (`manage_known_risk_exposures.py`) — chronic/cumulative risk factors keyed by a `syndrome_slug` that must match the slugs `analyse_outbreak_exposure.py` knows about; explicitly scoped to include animal husbandry, occupation, residence, and hobbies.

Without a bridge between the two, the interview's core value proposition — surfacing leads that matter for diagnosis — is structurally cut off from where this project actually consumes that kind of data.

## Goals / Non-Goals

**Goals:**
- Let a human, after reviewing extracted interview findings, promote selected ones into the correct existing JSON store(s) without re-typing them by hand.
- Reuse each target script's own schema/validation/I-O logic (`load()`/`save()`, field choice lists, slug constraints) as the single source of truth — this change adds an entry point into that logic, it does not duplicate the logic itself.
- Give the leisure & hobbies track (which has no dedicated event-history file) a real target: `known_risk_exposures.json`, using its already-documented scope.
- Preserve the human review gate `add-guided-anamnesis-interview` decision 7 establishes: promotion is per-finding, explicit, and never automatic.

**Non-Goals:**
- Not building a new, fifth JSON store — every finding maps to one of the four existing ones, or stays unpromoted.
- Not refactoring the existing interactive `cmd_add` flows in the four target scripts — they remain exactly as they are for manual/direct use; this change adds a parallel, non-interactive entry point alongside them.
- Not attempting to auto-select a `known_risk_exposures.json` slug the interview itself didn't already suggest — if the interview's associative questioning didn't surface a plausible pathogen-relevant slug for a hobby/exposure finding, that finding simply isn't offered for promotion to that store (see Risks).
- Not changing what `export_arzt_komplett.py`/`analyse_outbreak_exposure.py`/`analyse_pathogen_exposure.py` do with the data once it's in the JSON stores — they already work, this change only gets more real data to them.

## Decisions

**1. Add a non-interactive append function per target script, do not call the existing interactive `cmd_add` functions.**
Inspected all four scripts: `manage_family_history.py`'s and `manage_travel_history.py`'s `cmd_add()` are built entirely around `_prompt()` calls reading from the terminal (`input()`), not designed to accept a pre-built dict programmatically. `manage_exposure_history.py` already separates cleanly (`load()`/`save()` as pure I/O, `cmd_animal_add()`/`cmd_occupation_add()` as the interactive layer on top). Alternatives considered: refactor all four scripts to separate interactive-prompt logic from data-writing logic, so a single "write" path serves both interactive and programmatic callers. Rejected for this change — riskier (touches working, hand-tuned interactive UX in scripts the maintainer relies on directly) and larger in scope than necessary; a small new function per script (e.g. `add_entry_noninteractive(data: dict) -> None`) that calls the same `load()`/`save()` and re-runs the same field validation is a much smaller, additive footprint. Revisit consolidation later only if the duplication between the interactive and non-interactive paths becomes a real maintenance problem.

**2. Promotion is a `--promote` mode on the interview's existing review/export helper, not a separate script.**
The review/export helper (`add-guided-anamnesis-interview` task 4.1) already reads a session's `anamnese_findings` and needs the same "which track, which fields" knowledge that promotion needs. Alternatives considered: a standalone `scripts/utils/manage/personal/promote_anamnese_findings.py`. Rejected — would duplicate the session-loading and track-dispatch logic the export helper already has; keeping promotion as a mode of the same tool means one code path reads `anamnese_findings`, not two.

**3. Track → target-store mapping, with `known_risk_exposures.json` as leisure & hobbies' primary (not secondary) target.**
| Track | Primary target | Secondary target (optional, if chronic/ongoing) |
|---|---|---|
| exposure/travel | `travel_history.json` | `known_risk_exposures.json` |
| animal contact | `exposure_history.json` (`animal_contacts[]`) | `known_risk_exposures.json` |
| occupational | `exposure_history.json` (`occupational_exposures[]`) | `known_risk_exposures.json` |
| family history | `family_history.json` | — (no pathogen-relevance shape fit) |
| leisure & hobbies | `known_risk_exposures.json` | — (no dedicated event-history file exists) |

`known_risk_exposures.json` entries require a `slug` matching `analyse_outbreak_exposure.py`'s known syndrome-slug set (`_KNOWN_INFECTION_SLUG_MAP` and related lookups) — the promotion step SHALL only offer this target when the interview's own associative extraction already attached a plausible slug candidate to the finding (this is the same cross-referencing judgment `add-guided-anamnesis-interview` decision 3 already asks the model to make), not invent one at promotion time. A finding without a plausible slug simply isn't offered for this target and remains reachable only via the plain-Markdown export.

**4. Multi-target promotion is offered per applicable store independently, not merged into one combined write.**
A single real-world fact (e.g. "kept chickens for 8 years") can legitimately belong in both a historical record (`exposure_history.json`) and a risk-weighting entry (`known_risk_exposures.json`). The promotion UI presents each applicable target as its own yes/no confirmation, so the human can accept one, both, or neither — never a single combined decision that silently writes to multiple files at once.

**5. No new schema, no changes to `health.db`/`medicine.db`.**
This change is entirely at the "read from one local store, write to another local store" level — `anamnese_findings` rows are read (not deleted or modified) and the four target `.json` files are appended to. A promoted finding SHOULD be marked (e.g. a `promoted_to` note or timestamp on the `anamnese_findings` row) so re-running `--promote` on the same session doesn't re-offer already-promoted findings — exact mechanism left to tasks.md/implementation, but idempotency (no duplicate entries on a second `--promote` run) is a hard requirement, not an optimization.

## Risks / Trade-offs

- **[Risk] A promoted entry silently mangles or loses nuance compared to the original interview finding** (e.g. a rich, hedged interview statement gets collapsed into a terse structured field). → Mitigation: the promotion step always shows a preview of the exact entry that would be written and requires explicit per-finding confirmation (decision 2, no auto-write); the original `anamnese_findings.event_text` remains in the SQLite table regardless of promotion, so nothing is destroyed even if a promoted entry is imperfect.
- **[Risk] `known_risk_exposures.json` slug mismatch** — if the interview suggests a slug that has since drifted from `analyse_outbreak_exposure.py`'s actual known set (or the set changes after the interview ran), a promoted entry could silently fail to match during analysis. → Mitigation: the promotion step validates the slug against the *current* known-slug set at promotion time (not at interview time), not just trusting whatever the interview extracted; a mismatch blocks that specific promotion with a clear message rather than writing an entry that will never be matched.
- **[Risk] Re-running `--promote` on a session promotes the same finding twice, creating duplicate entries across `.json` files.** → Mitigation: idempotency requirement (decision 5) — mark promoted findings, skip already-promoted ones on subsequent runs, mirroring this project's `INSERT OR IGNORE` durability convention used everywhere else.
- **[Risk] The four target scripts' schemas drift over time (new fields, renamed choices) and the new non-interactive append functions silently fall out of sync.** → Mitigation: the non-interactive functions reuse the same `load()`/`save()` and validation constants as the interactive commands (decision 1) rather than hardcoding a parallel schema, so a schema change in one place is visible in both paths; still worth a task-level reminder to keep the non-interactive path in the same file as the interactive one it mirrors, not extracted elsewhere where it could drift unnoticed.

## Migration Plan

Purely additive: four new functions (one per existing script), one new CLI mode on an already-planned helper. No data migration, no rollback complexity beyond removing the new functions/mode if abandoned. Sequenced strictly after `add-guided-anamnesis-interview`, since this change reads from the `anamnese_findings` table that one creates — that table exists now and this change's implementation is largely complete (see `tasks.md`).

## Open Questions

- Whether promoted-finding tracking (decision 5) should live as a column on `anamnese_findings` itself or a separate small mapping table — deferred to tasks.md/implementation, either is fine as long as idempotency holds.
- Whether a sixth track added to the interview later would need its own mapping-table row here, or could reuse `known_risk_exposures.json` as a catch-all default — deferred until a concrete sixth track is proposed.
