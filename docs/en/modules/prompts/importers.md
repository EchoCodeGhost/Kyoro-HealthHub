# Prompt-Definitionen aus scripts/importers/*.py

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/prompts/importers.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Contains the LLM prompt from import_medical_history.py, moved verbatim from its original definition site (Phase 2 of the prompt-library migration) and registered in the central registry (modules.prompts).

## Relevance

Makes the importer prompt discoverable in one place.

## Method

The constants remain importable under their original name (PROMPT_DE, PROMPT_EN); language selection deliberately stays at the call site in import_medical_history.py (`PROMPT_DE if lang == "de" else PROMPT_EN`), not here — otherwise the language would be fixed at module-import time instead of at call time.

## Data flow

- **Reads:** `keine`
- **Writes:** `keine`

## Limitations

Pure data holder — no logic of its own.

## Usage

```bash
from modules.prompts.importers import PROMPT_DE
from modules.prompts.importers import PROMPT_EN
```
