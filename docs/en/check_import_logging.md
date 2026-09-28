# Import-Logging-Compliance-Check

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/check_import_logging.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Automatically checks that every importer which writes data to a database also logs the run via log_import() — the CLAUDE.md convention "Log the run to import_log" was previously enforced only by code review, not by a technical check.

## Relevance

Technical enforcement of the audit-trail claim (see docs/ETHICS.md, "treated as if it could end up in court") — without complete import_log entries, the provenance of database rows is no longer forensically traceable.

## Method

Scans scripts/importers/*.py. A script that contains INSERT statements (INSERT INTO / INSERT OR) must also call log_import(. Scripts without INSERT statements (pure fetch scripts, delegation wrappers, helper modules) are implicitly exempt, since they write nothing to the DB that would need logging. Since add-provenance- logging, an additional soft, non-build-breaking warning category: files that call log_import( without a recognizable person= kwarg (file-level, not call-site-precise) — surfaces the gradual rollout of the new person parameter without immediately breaking the ~30 not-yet-migrated callers.

## Data flow

- **Reads:** `scripts/importers/*.py`
- **Writes:** `STDOUT/STDERR (Fehlermeldungen)`

## Limitations

Source-text heuristic (no AST/data-flow tracking) — does not detect INSERT statements assembled dynamically from strings, nor logging calls via aliases/re-exports of log_import.

## Usage

```bash
python3 scripts/check_import_logging.py
python3 scripts/check_import_logging.py --path scripts/importers
```
