# Syndrom-Konfiguration Generator

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/syndromes/_generate.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Generates syndrome configuration files from source file

## Relevance

Enables health data analysis, essential for medical diagnostics

## Method

One-shot migration script: reads SYNDROME_CONFIG, SYNDROME_CODES, SYNDROME_SERO and _AFES_CONTEXT from the parent script (without importing it, to avoid side-effects), then writes one JSON file per syndrome plus _afes_context.txt.

## Data flow

- **Reads:** `analyse_postinfectious_diagnose.py`, `(Quelldatei)`
- **Writes:** `JSON-Dateien pro Syndrom in scripts/analysis/syndromes/`

## Limitations

One-time execution. No automatic updates. Already performed — the JSON files in this folder are the source of truth since the migration; `analyse_postinfectious_diagnose.py` loads them at runtime (`_load_syndromes()`) instead of hardcoding them. Running this again would try to read the (no longer present) literal dict assignment and therefore aborts deliberately with a clear error instead of silently overwriting or corrupting the JSON files.

## Usage

```bash
python3 scripts/analysis/syndromes/_generate.py
python3 _generate.py  # from scripts/analysis/syndromes/ directory
```
