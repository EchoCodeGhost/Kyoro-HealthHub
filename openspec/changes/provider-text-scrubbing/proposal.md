## Why

The `calendar-ics-importer` change (proposed, not yet implemented) already designed a complete algorithm for stripping doctor/practice names and addresses out of free text before it is ever written to a table — but it wrote that algorithm inline, scoped only to `import_calendar_ics.py`. The same risk exists everywhere else free text from a scanned medical document reaches a table or an intermediate review file: `import_lab_results.py` (already running) writes a lab company's name into `lab_manual.labor`; the planned `import_diagnosis_history.py` (`intern/plan_import_diagnosis_history_2026-10.md`) currently discards the "Leistungserbringer" (treating provider) field entirely rather than keeping a pseudonymized reference to it; and the export path (`export_health.py`) has never been audited for whether any export profile surfaces a provider name from a table that could carry one. Building the same scrubbing logic four separate times would drift; this change extracts it once.

## What Changes

- New module `scripts/modules/provider_scrubbing.py` exposing `scrub_provider_text(text: str) -> ProviderScrubResult`, where `ProviderScrubResult` carries `clean_text`, `provider_category`, `provider_city`, `provider_country`, `provider_region`, `provider_pseudonym`, `needs_review`. This is the exact five-step algorithm already fully specified in the `calendar-ics-importer` proposal's "What Changes" section 1-5 (registry exact match → German postal-code reduction → title+name pattern stripping → safety net flag), lifted out verbatim and generalized to take arbitrary free text instead of being embedded in `.ics` field handling.
- `scripts/modules/identity_resolver.py`: add `kind="provider"` to `_generate_pseudonym()` and `resolve()` (both currently raise `ValueError` for anything other than `"device"`/`"person"` — ``openspec/specs/identifier-pseudonymization/spec.md` needs a delta here, this is a real requirement change, not just an additive one).
- New local-only config: `~/.config/kyoro/provider_registry.json` (never committed), with `templates/provider_registry.example.json` (dummy values) added to the repo as the documented schema.
- `intern/plan_import_diagnosis_history_2026-10.md` updated: the plan currently has the `diagnoses` importer discard the Leistungserbringer field outright ("wird nicht in diagnoses übernommen"). With this module available, the plan should instead pseudonymize it via `scrub_provider_text()` and keep a `provider_pseudonym` column on `diagnoses` — a planning-document change only, no importer exists yet to migrate.
- Research task (no guaranteed code change): audit `scripts/export_health.py` and `scripts/exporters/profiles/*.json` for any query that could surface a raw provider name from a table this module could clean.
- Explicitly NOT part of this change: rewriting `calendar-ics-importer` to consume this module instead of its own inline copy (that proposal predates this one; swapping it over is a follow-up once this module exists — recorded here as a dependency, not implemented by it), and NOT modifying `import_lab_results.py` itself in this change if that turns out to be more than a small call-site change (tracked as a task, escalate to a follow-up change if it grows).

## Capabilities

### New Capabilities
- `provider-text-scrubbing`: a reusable, import/export-agnostic module that detects and pseudonymizes doctor/practice names and addresses in free text via a local, never-committed registry plus two documented heuristics (German postal-code pattern, professional-title-plus-name pattern), flagging anything it cannot confidently resolve for human review instead of silently passing it through or discarding it.

### Modified Capabilities
- `identifier-pseudonymization`: `identity_resolver.resolve()`/`_generate_pseudonym()` must accept `kind="provider"` in addition to the existing `"device"`/`"person"` kinds, producing a stable, salted pseudonym for a canonical provider-registry key the same way the existing kinds do.

## Impact

- New file: `scripts/modules/provider_scrubbing.py`
- New file: `templates/provider_registry.example.json`
- New local-only file (not committed): `~/.config/kyoro/provider_registry.json`
- Modified: `scripts/modules/identity_resolver.py` (new `kind="provider"` branch in two places)
- Modified: `intern/plan_import_diagnosis_history_2026-10.md` (planning document only — Leistungserbringer handling changes from "discard" to "pseudonymize + keep column")
- Research-only, no guaranteed change: `scripts/export_health.py`, `scripts/exporters/profiles/*.json`
- Out of scope for this change (dependency, not deliverable): updating `calendar-ics-importer`'s own proposal/design to consume this module instead of its inline copy; touching `import_lab_results.py`'s actual code (tracked as a task, may spin out into its own change if non-trivial)
- No new third-party dependencies (pure Python regex + the existing local registry/resolver pattern — this is deliberately the non-ML tier; the separate, independent `llm-entity-redaction` proposal is where NER/spaCy comes in, for different text that has no registry to match against)
