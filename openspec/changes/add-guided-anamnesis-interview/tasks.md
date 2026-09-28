## 1. Schema

- [x] 1.1 Add `anamnese_sessions` table (`id, track, started_at, last_updated_at, transcript_json, status`) to `utils/create_schema.py`, `CREATE TABLE IF NOT EXISTS`, following the existing schema-file convention.
- [x] 1.2 Add `anamnese_findings` table (`id, session_id, track, date_or_period, place_or_subject, event_text, relevance_note, person, created_at`) with a schema-comment flagging `event_text` as the highest-sensitivity free-text field in the project (per design.md risk notes). `track` values: `exposure`, `animal`, `family`, `occupational`, `leisure`, `social`. No special handling needed for the `person` column's pseudonymization — the project-wide `AFTER INSERT` trigger (`scripts/modules/db.py`) covers any table with a column literally named `person` automatically (design.md decision 4 update).
- [x] 1.3 Add appropriate indexes (`session_id`, `track`, `person`) mirroring the pattern used for other high-write tables (e.g. `measurements`).

## 2. Track prompts

- [x] 2.1 Write the exposure/travel-history track system prompt: opening question, instruction to actively cross-reference stated facts against epidemiological knowledge, instruction to phrase connections as hypotheses/questions rather than assertions (design.md decision 3).
- [x] 2.2 Write the animal-contact-history track system prompt (may overlap significantly with 2.1 — decide whether to merge into one "exposure" track or keep separate; record the decision in this file once made).
  - **Decision**: Keep separate tracks. Animal contact has distinct epidemiological patterns and follow-up questions compared to general exposure/travel history. The leisure track redirects animal mentions to the animal track to avoid duplication.
- [x] 2.3 Write the family-history track system prompt: per-relative walkthrough style, same cross-referencing instruction, adapted for genetic/hereditary pattern-spotting instead of infectious exposure.
- [x] 2.3a Write the occupational-history-&-exposures track system prompt: jobs/industries chronologically, chemical/solvent/dust/biological workplace exposure, shift-work patterns, workplace environment (mold, sick-building issues), same cross-referencing instruction (design.md decision 3).
- [x] 2.3b Write the leisure-&-hobbies track system prompt: sports, crafts, substances, hobby-related environmental exposure; SHALL redirect animal-contact mentions to the animal-contact track rather than duplicate extraction logic (design.md decision 3, spec "Track selection").
- [x] 2.3c Write the social-history track system prompt: tobacco (incl. cannabis/THC smoking, filtered/unfiltered), e-cigarettes/vaping (nicotine or nicotine-free), other substance use (route of administration, injection-equipment sharing), sexual history (partner gender, known-infected partners, protection use) — framed strictly as factual, non-judgmental risk-factor screening, never counseling (design.md decision 3 update, spec "Track selection").
- [x] 2.4 Write the shared incremental-extraction prompt/parsing logic that turns a user turn into zero or more structured `anamnese_findings` rows (JSON contract between the extraction call and the Python code that writes rows).
- [x] 2.5 Write the shared memory-anchor prompting logic (design.md decision 8, spec "Memory-anchor prompting"): per-track guidance on which physical memory aids are typically relevant for which period/topic (e.g. vaccination record for childhood-immunization questions, photo album for early-life physical-appearance questions, old lab reports/doctor's letters for exposure/occupational tracks), surfaced contextually during the conversation, not just as a generic opener.
- [x] 2.6 Build the explicit per-call language directive (design.md decision 9, spec "Interview language consistency"): a short, session-language-naming instruction injected into EVERY LLM call for a session — both the main turn-loop call (3.4) and the separate incremental-extraction call (2.4) — not stated once in the opening system prompt and assumed to hold. Wire the session's configured language (from `--lang`/`KYORO_LANG`, default German) into this directive.

## 3. Core script

- [x] 3.1 New `scripts/query/anamnese_interview.py`: SPDX header + full bilingual docstring block (`@tier infrastructure`, `@purpose.de/en`, `@method.de/en`, `@reads`, `@writes`, `@limits.de/en`, `@usage`) per project convention.
- [x] 3.2 CLI: track selection (new session) or session resumption (list existing in-progress sessions, load transcript).
- [x] 3.3 Wire into existing `llm_provider.py` dispatch (reuse `medical`-keyword routing already in place — no new backend config; works with local backend by default and with a configured remote provider such as OpenRouter, same as `health_query.py`).
- [x] 3.3a Detect whether the active backend for this session is local vs. remote (`is_local` flag already present on `LLMProvider`, see `llm_backends.md`) and show the one-time remote-provider warning before the first request of a session if remote (spec requirement "Configurable LLM provider with remote-provider warning").
- [x] 3.4 Turn loop: send transcript + user input to LLM, print response, run incremental extraction, persist finding rows + updated transcript after every turn (not just at session end).
- [x] 3.5 Graceful handling of an interrupted session (crash/Ctrl-C) — verify on restart that the last completed turn's transcript and findings are intact (ties to spec scenario "Session interrupted mid-conversation").
- [x] 3.6 `add_lang_arg`/`apply_lang_from_args` for `--lang`, consistent with rest of project.

## 4. Review/export helper

- [x] 4.1 Small helper (CLI flag or separate function) to render a session's `anamnese_findings` as a human-readable Markdown table (same shape as the hand-built tables used elsewhere for lab checklists), for copy-paste into a doctor's letter draft. MUST resolve the `person` column back to a readable label via `identity_resolver.resolve_display_name()` before rendering (design.md decision 4 update) — otherwise the export shows raw `PER-...` pseudonyms instead of e.g. "Mutter".
- [x] 4.2 Ensure every rendered finding is visibly labeled as self-reported/unverified interview output (spec requirement "Unverified-provenance labeling").

## 5. Privacy & compliance

- [x] 5.1 `OWN_PERSON_ID` used for the user; family-history track uses a free-text subject label resolved via `identity_resolver.resolve_person()`, never a hardcoded `'self'` literal anywhere in the new code.
- [x] 5.2 `python3 scripts/utils/check_source_privacy.py` exits 0 against the new file(s).
- [x] 5.3 `python3 scripts/check_compliance.py` reviewed for the new file(s); any new findings resolved or approved via baseline with justification.

## 6. Tests & dogfooding

- [x] 6.1 Unit tests for the extraction-parsing logic (JSON-contract → `anamnese_findings` row mapping), using synthetic conversation turns — no real personal data in test fixtures.
- [x] 6.2 Unit test for session resumption: start a session, simulate interruption, reload, confirm transcript + findings are intact.
- [ ] 6.3 Manual dogfooding: run each of the six tracks (exposure/travel, animal, family, occupational, leisure, social) against the author's own already-documented history and compare the tool's follow-up questions against what's already known from `intern/` case documents — record whether the tool's associative questioning actually surfaces (or would have surfaced) the same leads. This is the real acceptance check for the feature's core value proposition, not just "does it run." For the social track specifically, also confirm the tone stays factual/non-judgmental throughout (spec "Track selection" scenario).
- [ ] 6.4 Manual dogfooding of the memory-anchor prompting specifically (design.md decision 8): run a session where the author describes an old photo/document from memory, and record whether the system (a) proactively suggested consulting a memory aid at a contextually sensible point, and (b) correctly extracted a structured finding from the description. Acceptance reference: the childhood-photo-album session that surfaced a diagnostically relevant lead — the tool should plausibly have prompted for and captured a comparable observation.
- [ ] 6.5 Language-consistency dogfooding (design.md decision 9, spec "Interview language consistency"): run at least one LONG multi-turn session (not a short smoke test) in the default language and confirm every question, follow-up, and memory-anchor suggestion stays in that language throughout — including after turns containing long English-adjacent content (e.g. a pasted lab value with English terminology). A short session passing is not sufficient evidence; language drift is more likely to surface over length, per the observed real-world failure mode this requirement is based on.

## 7. Documentation

- [ ] 7.1 `docs/DATA_COLLECTION_GUIDE_DE.md` (and EN counterpart once that exists): add a section pointing to this tool as the "aufwendigere" alternative to the manual checklist approach.
- [x] 7.2 `python3 tools/gen_docs.py scripts/query/anamnese_interview.py` → `OK`.
- [ ] 7.3 `openspec validate add-guided-anamnesis-interview --strict` green before archiving.
