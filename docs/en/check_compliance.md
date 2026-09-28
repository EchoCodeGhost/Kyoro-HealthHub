# Compliance-Prüfskript für Docstrings im Kyoro-HealthHub

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/check_compliance.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Checks all docstrings for compliance violations (medical diagnoses, demographic data, age data, geographic locations)

## Relevance

Provides health data functions, essential for medical data processing

## Method

Recursively scans Python files, extracts module docstrings via AST, checks for forbidden content: medical diagnoses (ME/CFS, POTS, etc.), demographic data, age data, geographic locations. Known false positives can be manually approved via --review into a baseline (compliance_baseline.json, bound to a hash of that docstring — if the docstring changes, the approval automatically expires).

## Data flow

- **Reads:** `Alle`, `Python-Dateien`, `in`, `den`, `angegebenen`, `Verzeichnissen`, `compliance_baseline.json`
- **Writes:** `STDERR/STDOUT (Fehlermeldungen und Statistik), compliance_baseline.json (nur bei --review)`

## Limitations

Only detects obvious violations. False positives possible. No semantic analysis, only pattern matching. The baseline prevents false failures but does not replace actually improving the patterns — it only records that a human reviewed that specific match.

## Usage

```bash
python scripts/check_compliance.py
python scripts/check_compliance.py --path scripts/
python scripts/check_compliance.py --stats
python scripts/check_compliance.py --review
```
