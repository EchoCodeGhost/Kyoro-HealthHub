# generate_prompts_docs.py — Automatische Generierung von docs/prompts.md

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/generate_prompts_docs.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Automatically generates docs/prompts.md from the central prompt registry (modules.prompts). Replaces manual maintenance of the documentation.

## Relevance

Keeps the prompt catalog in sync with the registry, preventing documentation and code from drifting apart again.

## Method

1) Imports all prompt modules, 2) Reads all registered prompts via all_prompts(), 3) Generates markdown with overview table and detailed prompt information, 4) Preserves explanatory sections from the template, 5) Adds version history.

## Data flow

- **Reads:** `Alle`, `Dateien`, `in`, `scripts/modules/prompts/`
- **Writes:** `docs/prompts.md`

## Limitations

Only generates the table parts automatically; explanatory sections are taken from a template.

## Usage

```bash
python scripts/generate_prompts_docs.py
python scripts/generate_prompts_docs.py --check
```
