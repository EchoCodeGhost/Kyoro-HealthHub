# import_medical_history.py — Extracts dated events from free-text medical history

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/importers/import_medical_history.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Extracts dated events from free-text medical history

## Relevance

Enables import of health data, essential for comprehensive data analysis

## Method

Reads imports/manual/timeline_symptome.txt and uses a LOCAL LLM to extract dated events into imports/manual/life_events.json for user review and import. IMPORTANT: This script processes sensitive personal health data. It will refuse to run with any external/cloud LLM provider. Only local providers are permitted: openvino, ovms, ollama, lmstudio.

## Data flow

- **Reads:** `imports/manual/timeline_symptome.txt`
- **Writes:** `imports/manual/life_events.json`

## Limitations

Only local LLM providers. No cloud integration.

## Usage

```bash
python3 scripts/importers/import_medical_history.py
python3 scripts/importers/import_medical_history.py --timeline path/to/file.txt
python3 scripts/importers/import_medical_history.py --lang en
```
