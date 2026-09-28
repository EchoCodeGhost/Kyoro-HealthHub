# Prompt-Definitionen aus scripts/analysis/longevity/*.py

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/prompts/analysis_longevity.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Contains the LLM system prompts from the longevity analysis scripts, moved verbatim from their original definition site (Phase 2 of the prompt-library migration) and registered in the central registry (modules.prompts).

## Relevance

Makes all longevity analysis prompts discoverable in one place.

## Method

Each constant remains importable under its original name (e.g. SYSTEM_PROMPT_DE, SYSTEM_PROMPT_EN); it is additionally registered via register(Prompt(...)) with an owner path and classification.

## Data flow

- **Reads:** `keine`
- **Writes:** `keine`

## Limitations

Pure data holder — no logic of its own.

## Usage

```bash
from modules.prompts.analysis_longevity import SYSTEM_PROMPT_DE_ANALYSE_LONGEVITY
from modules.prompts.analysis_longevity import SYSTEM_PROMPT_EN_ANALYSE_LONGEVITY
```
