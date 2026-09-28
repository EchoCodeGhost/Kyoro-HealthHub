# Prompt Library CLI — `python3 -m modules.prompts`

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/prompts/__main__.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Allows invoking the prompt library as a module (`python3 -m modules.prompts`), so all prompt modules are imported (and thus registered) before `--list`/`--check` run.

## Relevance

Pure CLI entry point, no logic of its own.

## Method

Imports all known prompt submodules (currently only `query`), then calls `modules.prompts.main()`.

## Data flow

- **Reads:** `keine`
- **Writes:** `keine`

## Limitations

Must be manually extended for every new prompt submodule (e.g. `analysis_*`), otherwise its prompts won't be picked up by `--list`/`--check`.

## Usage

```bash
python3 -m modules.prompts --list
python3 -m modules.prompts --check
```
