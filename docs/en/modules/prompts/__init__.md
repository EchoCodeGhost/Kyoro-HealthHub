# Prompt Library — zentrales Register für LLM-System-Prompts

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/prompts/__init__.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Central registry for all LLM system prompts in the project, with each prompt explicitly attributed to its source file (owner). Solves the problem of prompts being scattered across ~70 files with no central overview.

## Method

`Prompt` dataclass (name, owner, classification, lang, text) + `register()` adds instances to the `PROMPTS` dict (keyed by owner path). `prompts_for(owner)`/`all_prompts()` query it. `python3 -m modules.prompts --list`/`--check` as CLI: `--check` verifies required fields and that no owner file still has an unregistered `SYSTEM_*`/`*_PROMPT` constant (drift protection, analogous to `tools/gen_docs.py --check`).

## Limitations

Only checks field presence and registration completeness, not the medical/factual correctness of prompt content.

## Usage

```bash
python3 -m modules.prompts --list
python3 -m modules.prompts --check
```
