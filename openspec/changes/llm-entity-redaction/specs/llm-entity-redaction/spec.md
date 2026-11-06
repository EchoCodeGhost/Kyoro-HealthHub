## ADDED Requirements

### Requirement: Person-name filter applied centrally for every remote LLM call
The system SHALL apply a person-name redaction filter to `prompt` and `system` text inside `modules/llm.py::call_llm()` whenever the configured provider is remote (`is_local` false or unknown), under the same gate already used for the existing location-text filter, so that no caller needs to apply it itself.

#### Scenario: Remote provider configured
- **WHEN** `call_llm()` is invoked with a remote provider configured (e.g. OpenRouter, Anthropic, Mistral) and the prompt contains a detectable person name
- **THEN** the name is replaced with a pseudonym before the request is sent

#### Scenario: Local provider configured
- **WHEN** `call_llm()` is invoked with a local provider configured (e.g. Ollama, llama.cpp, OpenVINO)
- **THEN** the prompt and system text are sent unchanged — this filter does not run, matching the existing location-filter precedent that local providers are never filtered

#### Scenario: Any existing caller is covered without modification
- **WHEN** any script that already calls `modules.llm.call_llm()` (e.g. an `analyse_*.py` script, `health_query.py`) runs with a remote provider configured
- **THEN** the person-name filter applies to its prompt automatically, with no change required in that script

### Requirement: Two-tier detection — registry exact match, then local NER
The system SHALL first check prompt/system text against the local provider registry (`provider_registry.json`, shared with the `calendar-ics-importer` capability when present) for an exact match, and SHALL then run a local NER model against the remaining text to detect `PERSON` entities not already matched, replacing each detected name with a pseudonym via `identity_resolver.resolve()`.

#### Scenario: Name already in the provider registry
- **WHEN** the prompt text contains a name that exactly matches an entry in `provider_registry.json`
- **THEN** it is replaced via the registry match (same pseudonym as elsewhere in the system for that entry), without relying on NER for that occurrence

#### Scenario: Name not in the registry, detected by NER
- **WHEN** the prompt text contains a person name not present in the registry
- **THEN** the local NER model detects it as a `PERSON` entity and it is replaced with a pseudonym obtained via `identity_resolver.resolve("llm_mention", <normalized name>)`

#### Scenario: Registry absent
- **WHEN** no `provider_registry.json` exists (e.g. the calendar importer hasn't been set up)
- **THEN** the registry tier is simply skipped and NER-based detection still runs

### Requirement: Language-appropriate NER model selection
The system SHALL detect the language of the text (German or English) before running NER, SHALL use a dedicated per-language spaCy pipeline for the detected language rather than a single multilingual model, and SHALL fall back to the pipeline for the session's configured language (via `modules.i18n.get_lang()`) — not a hardcoded language — when detection is uncertain or the language is neither German nor English, rather than skipping NER entirely.

#### Scenario: German text
- **WHEN** the prompt text is detected as German
- **THEN** the German spaCy pipeline (e.g. `de_core_news_md`) is used for `PERSON` detection

#### Scenario: English text
- **WHEN** the prompt text is detected as English (e.g. an imported note from an English-language app export)
- **THEN** the English spaCy pipeline (e.g. `en_core_web_md`) is used for `PERSON` detection

#### Scenario: Detection uncertain or unsupported language
- **WHEN** language detection fails, is low-confidence, or returns a language that is neither German nor English
- **THEN** the pipeline for `modules.i18n.get_lang()`'s current value is used as the fallback, rather than skipping entity detection for that text or hardcoding German regardless of session language

#### Scenario: Session running with KYORO_LANG=en
- **WHEN** the session's configured language is English (`KYORO_LANG=en` or `set_lang("en")`) and language detection on a given text is uncertain
- **THEN** the English pipeline is used as the fallback for that text, not German

#### Scenario: Per-process model caching
- **WHEN** multiple calls in the same process need the same language's model
- **THEN** that language's pipeline is loaded once and reused, not reloaded per call; a language whose model is never needed in a given run is never loaded

### Requirement: NER runs entirely locally
The system SHALL run the NER model entirely on the local machine, and SHALL NOT send any text to an external service to perform entity detection.

#### Scenario: NER inference
- **WHEN** the redaction filter scans prompt text for person names
- **THEN** the detection itself happens via a local spaCy model, with no network request made for that purpose

### Requirement: Logging reveals counts only, never matched text
The system SHALL log only the number of entities redacted per call, and SHALL NOT log the detected name or any other content of the matched text.

#### Scenario: Redaction occurs during a call
- **WHEN** one or more names are redacted from a prompt
- **THEN** the log records a count (e.g. "2 entities redacted"), and does not record what those entities were

### Requirement: Single configurable on/off switch, no per-caller policy
The system SHALL control this filter via one configuration key (`llm.redact_entities`, default `true`), SHALL NOT implement a per-caller allow-list or graduated precision policy for it (unlike the location filter), and the default SHALL be the restrictive (filtering-enabled) choice.

#### Scenario: Default configuration
- **WHEN** `llm.redact_entities` is not set in `health_config.json`
- **THEN** the filter runs (default `true`), consistent with "restrictive by default"

#### Scenario: Explicitly disabled
- **WHEN** `llm.redact_entities` is explicitly set to `false`
- **THEN** the filter does not run for any caller — there is no per-caller override in either direction

### Requirement: Documented as risk reduction, not a guarantee
The system's documentation (module docstring, `@limits`) SHALL state plainly that NER-based detection can miss names (false negatives) and misflag ordinary text (false positives), and SHALL NOT present this filter as a complete or certified anonymization.

#### Scenario: Docstring review
- **WHEN** `scripts/modules/entity_redaction.py`'s docstring is read
- **THEN** it states the false-negative/false-positive limitation explicitly, without an unqualified claim of completeness
