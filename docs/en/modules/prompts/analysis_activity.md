# Prompt-Definitionen aus scripts/analysis/activity/*.py

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/prompts/analysis_activity.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Contains the LLM system prompts from the activity analysis scripts, moved verbatim from their original definition site (Phase 2 of the prompt-library migration) and registered in the central registry (modules.prompts).

## Relevance

Makes all activity analysis prompts discoverable in one place.

## Method

Each constant remains importable under its original name (e.g. SYSTEM_PROMPT); it is additionally registered via register(Prompt(...)) with an owner path and classification.

## Data flow

- **Reads:** `keine`
- **Writes:** `keine`

## Limitations

Pure data holder — no logic of its own.

## Usage

```bash
from modules.prompts.analysis_activity import SYSTEM_PROMPT_ANALYSE_FUNCTIONAL_CAPACITY_DE
from modules.prompts.analysis_activity import SYSTEM_PROMPT_ANALYSE_SPORT_ENVIRONMENT_DE
```
