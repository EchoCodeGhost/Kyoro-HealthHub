# Prompt-Definitionen aus scripts/analysis/manual/*.py

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/prompts/analysis_manual.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Contains the LLM system prompts from the manual analysis scripts, moved verbatim from their original definition site (Phase 2 of the prompt-library migration) and registered in the central registry (modules.prompts).

## Relevance

Makes all manual analysis prompts discoverable in one place.

## Method

Each constant remains importable under its original name (e.g. SYSTEM_DE, SYSTEM_EN); it is additionally registered via register(Prompt(...)) with an owner path and classification.

## Data flow

- **Reads:** `keine`
- **Writes:** `keine`

## Limitations

Pure data holder — no logic of its own.

## Usage

```bash
from modules.prompts.analysis_manual import SYSTEM_PROMPT_ANALYSE_LAB_VERLAUF_DE
from modules.prompts.analysis_manual import SYSTEM_PROMPT_ANALYSE_URINE_DE
```
