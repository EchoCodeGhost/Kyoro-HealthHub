# anamnese_interview.py — LLM-geführtes Anamnese-Interview

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/query/anamnese_interview.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Conducts an open-ended, LLM-driven interview across six tracks: exposure/travel history, animal contact, family history, occupational history & exposures, leisure & hobbies, social history (smoking/e-cigarettes/substance use/sexual history). The model asks associative follow-up questions when a statement has a known epidemiological/genetic connection. Sessions are resumable across multiple sittings.

## Relevance

Enables anamnesis interviews, essential for clinical data collection

## Method

1) Track selection or session resumption, 2) Initialize LLM provider (local or remote), 3) Conversation flow with incremental extraction of structured findings, 4) Persist session status and transcript, 5) Review export as Markdown.

## Data flow

- **Reads:** `health.db`, `(anamnese_sessions`, `anamnese_findings)`
- **Writes:** `health.db (anamnese_sessions, anamnese_findings)`

## Limitations

Requires Python 3.10+. Sessions with remote provider show a warning (data transmission). Extraction is unverified and must be manually reviewed.

## Usage

```bash
python3 scripts/query/anamnese_interview.py --track exposure
python3 scripts/query/anamnese_interview.py --track social --lang en
python3 scripts/query/anamnese_interview.py --resume <session_id>
python3 scripts/query/anamnese_interview.py --export <session_id>
```
