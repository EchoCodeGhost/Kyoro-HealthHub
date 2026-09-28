# Prompt-Definitionen aus scripts/analysis/ophthalmology/*.py

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/prompts/analysis_ophthalmology.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Contains the LLM system prompts from the ophthalmology analysis scripts, moved verbatim from their original definition site (Phase 2 of the prompt-library migration) and registered in the central registry (modules.prompts).

## Relevance

Makes all ophthalmology analysis prompts discoverable in one place.

## Method

Each constant remains importable under its original name (e.g. _SYSTEM_DE, _SYSTEM_EN); it is additionally registered via register(Prompt(...)) with an owner path and classification.

## Data flow

- **Reads:** `keine`
- **Writes:** `keine`

## Limitations

Pure data holder — no logic of its own.

## Usage

```bash
from modules.prompts.analysis_ophthalmology import SYSTEM_DE_ANALYSE_FUNDUS
from modules.prompts.analysis_ophthalmology import SYSTEM_EN_ANALYSE_FUNDUS
```
