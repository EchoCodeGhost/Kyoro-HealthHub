# Docstring Validierungstool für Kyoro-HealthHub

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/check_docstrings.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Validates all docstrings in the project against the structured schema

## Relevance

Provides health data functions, essential for medical data processing

## Method

Recursively scans Python files, extracts module docstrings via AST, checks for required tags based on @tier classification, validates bilingual tags and reference formatting

## Data flow

- **Reads:** `Alle`, `Python-Dateien`, `in`, `den`, `angegebenen`, `Verzeichnissen`
- **Writes:** `STDERR/STDOUT (Fehlermeldungen und Statistik)`

## Limitations

Only detects module docstrings, not function docstrings (planned for v2). Automatic fixes not yet implemented.

## Usage

```bash
python scripts/check_docstrings.py
python scripts/check_docstrings.py --path scripts/compute
python scripts/check_docstrings.py --stats
```
