# audit_device_id_usage.py — Semantische Identifier-Nutzung prüfen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/audit_device_id_usage.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Scans source code for direct semantic device_id and person comparisons that need to be updated for pseudonymization.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Regex-based search for patterns like device_id=="polar_v3", 'self', 'partner' in Python files. Reports findings with file/line.

## Data flow

- **Reads:** `scripts/compute/`, `scripts/importers/`, `scripts/analysis/`, `scripts/exporters/`
- **Writes:** `Keine (nur Konsolenausgabe)`

## Limitations

False positives possible in comments/documentation. No automatic fixes — reporting only.

## Usage

```bash
python3 scripts/audit_device_id_usage.py
python3 scripts/audit_device_id_usage.py > audit_results.txt
```
