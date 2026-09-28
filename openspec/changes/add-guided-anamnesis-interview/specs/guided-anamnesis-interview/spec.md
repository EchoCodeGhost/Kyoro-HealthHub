## ADDED Requirements

### Requirement: Track selection
The system SHALL let the user start an interview against one of six tracks: exposure/travel history, animal contact history, family history, occupational history & exposures, leisure & hobbies, or social history (tobacco/e-cigarette/other substance use and sexual history). Each track SHALL use its own opening prompt and structured-extraction schema, sharing the same underlying interview engine. The leisure & hobbies track's system prompt SHALL redirect animal-contact-related statements to the animal contact track's extraction schema rather than duplicating that extraction logic. The social history track SHALL frame all questions as routine clinical risk-factor screening (relevant to hepatitis B/C, HIV, endocarditis, and cardiovascular risk) and SHALL NOT moralize or counsel.

#### Scenario: User starts a new interview
- **WHEN** the user runs the interview script and selects a track (e.g. "family history")
- **THEN** the system creates a new session record for that track and begins with the track's opening question

#### Scenario: User discloses a substance-use or sexual-history risk factor
- **WHEN** the user states a fact in the social history track that carries a known infection or health risk (e.g. shared injection equipment, unprotected sex with a partner of unknown or known-positive status)
- **THEN** the system's next response asks a targeted follow-up phrased as a hypothesis to verify, in the same factual, non-judgmental register used for every other track — never as moral commentary or health advice

### Requirement: Associative follow-up questioning
The system SHALL instruct the LLM to actively cross-reference user statements against its general medical/epidemiological/genetic knowledge and ask a targeted follow-up question when a plausible connection exists, rather than only progressing through a fixed list of questions.

#### Scenario: User mentions an exposure with a known but non-obvious disease association
- **WHEN** the user states a fact that the model's background knowledge associates with a specific risk (e.g. a specific animal contact)
- **THEN** the system's next response SHALL include a follow-up question referencing that association, phrased as a hypothesis to verify (e.g. "X is a known reservoir for Y — did you also have contact with...") rather than an assertion of fact

### Requirement: Multi-session persistence and resumption
The system SHALL persist the full conversation transcript and session status locally so that an interview can be paused and resumed in a later run without losing prior context.

#### Scenario: User resumes an interrupted interview
- **WHEN** the user restarts the interview script and selects an existing in-progress session
- **THEN** the system loads the stored transcript, reconstructs context for the LLM, and continues the conversation from where it left off

#### Scenario: Session interrupted mid-conversation
- **WHEN** the interview process is terminated unexpectedly (e.g. crash, closed terminal) after at least one exchange
- **THEN** the transcript and any findings extracted up to that point remain present in local storage on the next run

### Requirement: Incremental structured extraction
The system SHALL extract structured findings (date/period, place or subject, event description, relevance note, person) from the conversation incrementally, after each user turn, and persist each finding immediately rather than only at the end of the session.

#### Scenario: User states a new fact mid-conversation
- **WHEN** the user's response contains an extractable fact (e.g. a date, place, or exposure detail)
- **THEN** the system SHALL write a corresponding row to local storage before prompting the next question, so the fact is retained even if the session ends immediately afterward

### Requirement: Configurable LLM provider with remote-provider warning
The system SHALL dispatch interview requests through the project's existing multi-provider LLM configuration (as used by `scripts/query/health_query.py`), defaulting to the local backend. A remote/cloud provider (e.g. OpenRouter) SHALL also be usable if configured. Before starting a session against a non-local provider, the system SHALL display an explicit one-time warning that interview content (unstructured personal/family health narrative) will be transmitted to that provider, referencing this project's existing external-AI-provider privacy guidance.

#### Scenario: Interview session runs against the default local backend
- **WHEN** any interview turn is processed and no remote provider is configured for the active backend
- **THEN** the LLM request is dispatched through the local backend configuration and no warning is shown

#### Scenario: Interview session runs against a configured remote provider
- **WHEN** the user starts or resumes an interview session and the active backend is configured as a remote provider
- **THEN** the system displays the remote-provider warning before the first request of that session is sent, and the request is dispatched through the configured remote provider

### Requirement: Unverified-provenance labeling
The system SHALL mark every extracted finding as originating from a self-reported interview, not as a verified fact, so downstream consumers (human review, future exports) cannot mistake it for confirmed clinical data.

#### Scenario: A finding is written to storage
- **WHEN** a structured finding row is created
- **THEN** the row is associated with its source track/session and is not written into any table or config that this project treats as verified clinical fact (e.g. `clinical.events`)

### Requirement: Person-scoped storage without hardcoded identifiers
The system SHALL store findings and sessions using the project's existing person-identification convention (`OWN_PERSON_ID` for the user, a free-text subject label resolved via `identity_resolver.resolve_person()` for other individuals such as family members) and SHALL NOT use a hardcoded literal such as `'self'` in source code. A free-text subject label SHALL NOT be assumed to remain in plaintext in storage — the project's central pseudonymization safeguard (`scripts/modules/db.py`) automatically rewrites any `person` column value to a pseudonym on insert; human-readable rendering (e.g. the review export) SHALL resolve pseudonyms back via `identity_resolver.resolve_display_name()`.

#### Scenario: Family-history finding is recorded
- **WHEN** a finding concerns a family member rather than the user themselves
- **THEN** the stored row identifies the subject via a free-text label distinct from `OWN_PERSON_ID`, no source code path references a literal person string, and the value persisted in `health.db` is a pseudonym, not the plaintext label

### Requirement: Memory-anchor prompting
The system SHALL, where contextually appropriate for the period or topic under discussion, proactively suggest that the user consult a physical memory aid — old photo albums, diaries/calendars, or historical medical paperwork (doctor's letters, lab reports, childhood examination booklets, vaccination records, allergy passports) — and describe what it shows, as a text-only conversational turn. The system SHALL NOT require, request, or process an uploaded image or document.

#### Scenario: Conversation reaches a period/topic where a memory aid is commonly useful
- **WHEN** the interview reaches a point where a physical memory aid (e.g. a vaccination record for a childhood-immunization question, an old photo album for an early-life physical-appearance question) is plausibly relevant
- **THEN** the system's response SHALL include a suggestion to consult that type of memory aid and describe its contents in the next turn

#### Scenario: User describes a photo or document from memory
- **WHEN** the user's response describes the contents of a photo or document they consulted
- **THEN** the system extracts any structured facts from that description the same way as from any other conversational turn (per the Incremental structured extraction requirement), with the same unverified-provenance labeling

### Requirement: Interview language consistency
The system SHALL conduct the entire interview — every LLM-generated question, follow-up, and memory-anchor suggestion — in the session's configured language (default German, switchable via the project's existing `--lang`/`KYORO_LANG` mechanism), and SHALL NOT drift into another language mid-session. This applies regardless of what language the system prompt scaffolding, code, or surrounding documentation happen to be written in — the language directive to the model SHALL be explicit and SHALL be included in every LLM call for a session (main turn and incremental-extraction call alike), not stated once and assumed to hold for the rest of the conversation.

#### Scenario: Interview session starts in the default language
- **WHEN** a new interview session starts without an explicit `--lang` override
- **THEN** every question, follow-up, and memory-anchor suggestion is generated in German, even though the system prompt itself and the codebase are written in English

#### Scenario: Long or memory-anchor-heavy session
- **WHEN** a session runs many turns, or the user's turns include long descriptions of old documents/photos
- **THEN** the interview language remains consistent with the session's configured language throughout — a long or content-heavy conversation is not, by itself, a justification for a language drift

#### Scenario: User writes a turn in a different language than the session's configured language
- **WHEN** the user's own input for a turn happens to be in a language other than the session's configured language
- **THEN** the system's next response is still generated in the session's configured language, not mirrored to the user's turn language
