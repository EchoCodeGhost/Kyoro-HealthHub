## Why

Every script that calls a remote LLM provider already goes through one shared function, `modules/llm.py::call_llm()`, which already filters *location* text before sending it to a remote provider (`location_store.filter_prompt_text()`, per `openspec/specs/location-privacy/spec.md`'s "Location text in prompts to remote providers" requirement). There is no equivalent filter for *person/entity names*. Many tables already hold free text that can contain third-party names — `symptoms.value_text`, `self_care.notes`, `user_context` notes (fed by Oura tags, Garmin GDPR, symptom diaries, Bearable, etc.) — none of it scrubbed today. Dozens of `analyse_*.py` scripts, `health_query.py`, `anamnese_interview.py`, and others read this text into a prompt and pass it to `call_llm()`; if the configured provider is remote (OpenRouter, Anthropic, Mistral, etc.), that free text — and any name within it — goes out as-is.

This surfaced while designing the `calendar-ics-importer` change's import-time scrubbing: a calendar event's title/location/description get cleaned before they're even written to health.db, but every *other* table's free text has no equivalent protection at the one point that actually matters for this risk — the moment text leaves the machine toward a remote model.

## What Changes

- Add a new local, offline Named Entity Recognition (NER) pass that detects person names (and, where the model's labels allow, organizations) in prompt/system text, as a second filter run alongside the existing location filter — in the same place (`call_llm()`), under the same `is_remote` gate (local providers are never filtered, same precedent as the location filter).
- New module `scripts/modules/entity_redaction.py` (naming mirrors the existing `location_redaction.py`) exposing `redact_entities_for_llm(text: str) -> tuple[str, int]` — same `(filtered_text, count)` return shape as `location_store.filter_prompt_text()`, logging only a count, never the matched text.
- Detection order, reusing existing infrastructure rather than building two separate systems:
  1. First, an exact match against the local `provider_registry.json` registry introduced by the `calendar-ics-importer` change (if that change has landed) — zero false-positive risk, reuses `identity_resolver.resolve("provider", ...)` for a consistent pseudonym.
  2. Then, a local language-detection step (`langdetect`) picks German or English, and the matching local NER pipeline (new dependency: `spacy` + per-language pipelines, defaults `de_core_news_md`/`en_core_web_md`, both configurable) scans the remaining text for `PERSON` entities not already handled by step 1 — a dedicated per-language model instead of one weaker multilingual model, since this project is bilingual (`KYORO_LANG`) and several sources already produce English free text. Each detected name is replaced with a pseudonym via `identity_resolver.resolve("llm_mention", <normalized name>)` — the existing central resolver (`openspec/specs/identifier-pseudonymization/spec.md`), not a new pseudonymization scheme.
  3. Local providers are never filtered (nothing leaves the machine); this matches the existing location-filter precedent exactly.
- New config section (`llm.redact_entities`, default `true`) in `health_config.json` to allow disabling this specific filter if the user judges the risk acceptable for her own setup — default stays the safe, restrictive choice, same pattern as the location filter's default `"none"`.
- **Not a replacement** for the calendar importer's import-time scrubbing (that still runs independently, before data is even written to disk) — this is a second, independent layer at the LLM-call boundary, catching the same kind of risk everywhere else in the codebase that already-stored free text could reach a remote model.
- **Explicitly not a guarantee**: NER is probabilistic (false negatives and false positives both occur). This reduces risk; it does not eliminate it. Documented plainly, not oversold — consistent with `feedback_local_first_framing` conventions never to claim an absolute.

## Capabilities

### New Capabilities
- `llm-entity-redaction`: a local NER-based filter that strips/pseudonymizes detected person names from any prompt or system text before it reaches a remote LLM provider, applied centrally inside `call_llm()` so every existing and future caller is covered without per-script changes.

### Modified Capabilities
_(none — this is additive, parallel to the existing location-text filter in `location-privacy`; that capability's own requirements are unchanged.)_

## Impact

- New file: `scripts/modules/entity_redaction.py`
- Modified: `scripts/modules/llm.py::call_llm()` — add the new filter call alongside the existing `filter_prompt_text()` call, under the same `is_remote` gate
- New dependencies: `spacy` plus German and English NER pipelines (model names configurable; default recommendations `de_core_news_md`/`en_core_web_md`), and `langdetect` for the language-detection step that picks between them
- New config key: `llm.redact_entities` (default `true`) in `health_config.json` / `templates/health_config.example.json`
- Soft dependency on `calendar-ics-importer`'s `provider_registry.json`/`identity_resolver` `kind="provider"` extension (reused as the first, exact-match detection tier) — this change works even if that one hasn't landed yet (NER alone still runs), but is strictly more precise once both exist
- Affects every script that calls `modules.llm.call_llm()` with a remote provider configured — no changes needed in those scripts themselves, the filter is centralized
