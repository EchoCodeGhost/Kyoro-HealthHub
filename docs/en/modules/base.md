# base.py — Gemeinsame Hilfsfunktionen für Importer

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/base.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides common utility functions and primitives for importers. Documented in CLAUDE.md.

## Relevance

Provides base functions for module structure, essential for system architecture

## Method

Contains: ImportResult (standardized return value), resolve_person() (person ID from argument or default), resolve_timezone() (IANA timezone), local_date() (UTC → local date), log_import() (forensic-safe logging).

## Data flow

- **Reads:** `persons`, `Tabelle`, `(für`, `resolve_timezone)`
- **Writes:** `import_log Tabelle (über log_import)`

## Limitations

Internal helper module. Signature changes break all importers.

## Usage

```bash
python base.py
python base.py --help
python base.py --from 2024-01-01 --to 2024-12-31
```
