## 1. Dependencies and configuration

- [ ] 1.1 Add `spacy` and `langdetect` to `requirements.txt` with comments explaining their purpose (local NER + language detection for pre-LLM redaction)
- [ ] 1.2 Document the model download steps (e.g. `python3 -m spacy download de_core_news_md` and `python3 -m spacy download en_core_web_md`) in `onboard.py`/README, same as other post-install steps (`playwright install chromium`)
- [ ] 1.3 Add `llm.redact_entities` (default `true`) and `llm.ner_models` (default `{"de": "de_core_news_md", "en": "en_core_web_md"}`) to `templates/health_config.example.json` with explanatory comments
- [ ] 1.4 Confirm `identity_resolver.py` accepts `kind="llm_mention"` (it should already, per the `calendar-ics-importer` change's task 1.4 check — if that change hasn't landed yet, do the same check/extension here)

## 2. Core redaction module

- [ ] 2.1 Create `scripts/modules/entity_redaction.py` with SPDX header and a docstring that states the false-negative/false-positive limitation plainly (per spec's "Documented as risk reduction" requirement)
- [ ] 2.2 Implement `redact_entities_for_llm(text: str) -> tuple[str, int]`:
  - [ ] 2.2a Load `provider_registry.json` if present (reuse the loader from `calendar-ics-importer` if that change has landed; otherwise a local fallback that simply returns an empty registry)
  - [ ] 2.2b Exact-match tier: replace any registry match in `text`, count replacements
  - [ ] 2.2c Language detection: run `langdetect` on the remaining text; map result to `"de"`/`"en"`; on failure/low confidence or any other language, default to `modules.i18n.get_lang()` (the session's configured language), not a hardcoded `"de"`
  - [ ] 2.2d NER tier: run the spaCy pipeline for the detected language on the remaining text, find `PERSON` entities, replace each with `identity_resolver.resolve("llm_mention", <normalized text>)`, count replacements
  - [ ] 2.2e Return `(redacted_text, total_count)`
- [ ] 2.3 Lazy-load each language's spaCy pipeline once per process, cached per language code (module-level dict) — never reload per call, never load a language's model that was never needed in that run
- [ ] 2.4 Unit tests: registry-only match, German-NER-only match (no registry present), English-NER-only match, both tiers matching different names in the same text, no match (text unchanged, count 0), language-detection-failure fallback to `i18n.get_lang()`'s value tested with both `set_lang("de")` and `set_lang("en")` active (confirm the fallback follows the session language, not a hardcoded one), confirm no network call occurs during NER or language detection (mock/assert no `requests`/`urllib` call from within the redaction path)

## 3. Integration into `call_llm()`

- [ ] 3.1 In `scripts/modules/llm.py::call_llm()`, add the `redact_entities_for_llm()` call alongside the existing `filter_prompt_text()` call, under the same `is_remote` gate, for both `prompt` and `system`
- [ ] 3.2 Respect `llm.redact_entities` config: skip the call entirely when `false`
- [ ] 3.3 Log only the count (reuse or mirror the existing location-filter log-count pattern) — no matched text in logs
- [ ] 3.4 Update `call_llm()`'s docstring to mention the new filter, consistent with how it already documents the location filter's behavior

## 4. Compliance and verification

- [ ] 4.1 `python3 scripts/utils/check_source_privacy.py` → exit 0
- [ ] 4.2 Manual test: construct a short German prompt and a short English prompt, each containing a fabricated person name with no other context, run both through `call_llm()` with a remote provider configured (or a mocked remote provider for the test), confirm the name is replaced in both before the (mocked) send
- [ ] 4.3 Manual test: same prompts, local provider configured, confirm both are sent unchanged
- [ ] 4.4 Manual test: confirm a name that matches a `provider_registry.json` entry is caught by the registry tier even if NER alone might miss it (e.g. construct a deliberately NER-unfriendly name string)
- [ ] 4.5 Spot-check latency: measure NER inference time (including language detection and first-load of each model) on a handful of realistic prompt lengths in both languages, confirm it's not a noticeable addition relative to the remote round-trip; adjust the default model choices (Open Questions in design.md) if it is
