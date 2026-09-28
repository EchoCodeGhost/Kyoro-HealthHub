# Prompt-Definitionen aus scripts/query/*.py

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/prompts/query.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Contains the LLM system prompts from `health_query.py`, `health_report.py`, and `anamnese_interview.py`, moved verbatim from their original definition site (Phase 1 of the prompt-library migration) and registered in the central registry (`modules.prompts`).

## Relevance

Makes all query prompts discoverable in one place, instead of scattered across three files.

## Method

Each constant remains importable under its original name (e.g. `SYSTEM_SQL`); it is additionally registered via `register(Prompt(...))` with an owner path and classification. The source scripts import the constants from here instead of defining them themselves.

## Data flow

- **Reads:** `keine`
- **Writes:** `keine`

## Limitations

Pure data holder — no logic of its own, no runtime validation of the prompt content itself (only field presence via `modules.prompts --check`).

## Usage

```bash
from modules.prompts.query import SYSTEM_SQL, SYSTEM_INTERPRET
from modules.prompts.query import SYSTEM_HRV, SYSTEM_ARRHYTHMIA
```
