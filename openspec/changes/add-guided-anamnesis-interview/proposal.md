## Why

Reconstructing a lifetime history — which animals over which years, which travels, which relatives had which conditions, but also occupational exposures and leisure/hobby activities — is where some of the highest-value diagnostic leads in this project actually came from, but only because an LLM with epidemiological/genetic background knowledge kept asking *associative* follow-up questions ("hamsters are the primary LCMV reservoir — did you have contact with other rodents too?") rather than working through a fixed checklist. A static list of questions (the lighter alternative already sketched in `docs/DATA_COLLECTION_GUIDE_DE.md`) cannot reproduce that — it requires the user to already know which follow-up matters. A second, distinct pattern produced a lead the same way: describing childhood photos in detail (from a baby photo album) surfaced a diagnostically relevant physical sign — visible in retrospect but never consciously registered as a symptom at the time, and that pure verbal recall without an external memory anchor would not have surfaced. This change makes both patterns — associative cross-referencing, and memory-anchored recall via old photos/documents — a reusable, local, multi-session tool that covers a comprehensive life review ("Gesamt-Nabelschau"), not just infectious/genetic exposure, instead of something that only happens inside an ad-hoc chat session.

## What Changes

- New guided interview CLI (`scripts/query/anamnese_interview.py`) that conducts an open-ended, LLM-driven conversation over one of six tracks (exposure/travel history, animal contact history, family history, occupational history & exposures, leisure & hobbies, social history — tobacco/e-cigarette/other substance use and sexual history), starting from a short topic menu but not constrained to it.
- The LLM actively cross-references stated facts against background epidemiological/genetic knowledge and asks targeted follow-ups (mirrors what happened organically in this project's own anamnesis work).
- The system proactively prompts the user to consult physical memory anchors relevant to the track and period being discussed — old photo albums, diaries/calendars, and historical medical paperwork (doctor's letters, lab reports, childhood examination booklets, vaccination records, allergy passports) — and to describe what they show, since this pattern has independently surfaced findings that pure verbal recall did not. Text-only for this iteration: the user describes the document/photo in their own words, no image upload or document parsing.
- Sessions are resumable across multiple sittings — partial transcripts and already-extracted structured rows persist locally between runs.
- Structured output (date/place/event/relevance rows, per person for family history) is written to a new local table (`anamnese_findings`, see design.md) as the conversation progresses, not only at the end — so a session that's interrupted still keeps what it extracted.
- Uses the project's existing multi-provider LLM configuration (`scripts/query/health_query.py`'s pattern) — works with a local backend by default, but a remote provider (e.g. OpenRouter) is also usable, consistent with how other query tools in this project already support both. Because interview content is unusually hard to pseudonymize (free-text exposure/family narratives, not a single metric value), the CLI SHALL show an explicit one-time warning before starting a session against a non-local provider, reusing this project's existing external-AI-provider guidance (README: prefer Zero Data Retention providers).
- **BREAKING**: none — purely additive, new script + new table.

## Capabilities

### New Capabilities
- `guided-anamnesis-interview`: an LLM-driven, multi-session, associative interview tool that reconstructs a comprehensive life/exposure/family history across six domains (exposure/travel, animal contact, family, occupational, leisure/hobbies, social history) — including memory-anchored recall via old photos and medical documents — and persists it as structured, resumable, locally-stored data.

### Modified Capabilities
(none — no existing spec's requirements change)

## Impact

- New file: `scripts/query/anamnese_interview.py`
- New schema addition: `anamnese_findings` table (and a session/transcript table) in `utils/create_schema.py`
- Reuses: existing LLM provider config/dispatch from `scripts/query/health_query.py` (no new LLM integration path)
- No impact on existing importers, compute scripts, or export profiles
- Follow-up documentation note in `docs/DATA_COLLECTION_GUIDE_DE.md` linking to this tool once built
