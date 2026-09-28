# Umfassender Privacy- und Anonymisierungs-Check

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/check_all.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Performs comprehensive privacy and anonymisation checks

## Relevance

Provides health data functions, essential for medical data processing

## Method

Sequentially executes three checks: 1. Source code and doc check with check_source_privacy.py (.py/.md/.json, whole repo) 2. Database anonymisation check with check_anonymization.py 3. PII scan with scrub_pii.py --dry-run By default, only shows results. With --fix, PII is actually cleaned (with backup).

## Data flow

- **Reads:** `Alle`, `Quellcode-Dateien`, `und`, `Datenbanktabellen`
- **Writes:** `PII-Bereinigte Dateien (nur mit --fix)`

## Limitations

No direct validation. Dependent on individual check scripts.

## Usage

```bash
python3 scripts/check_all.py
python3 scripts/check_all.py --skip-db       # nur Quellcode
python3 scripts/check_all.py --skip-source   # nur DB + PII
python3 scripts/check_all.py --fix           # PII tatsächlich bereinigen (mit Backup)
```
