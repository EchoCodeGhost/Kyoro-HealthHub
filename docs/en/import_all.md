# Master Health Data Import

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/import_all.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Calls all available importers as subprocesses and coordinates the import of health data from various sources into the health.db database.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Execution order: 0) sync registry.json → health.db.devices (sync_registry_to_devices.run(), non-blocking), 1) process_inbox.py for inbox files, 2) File-based importers, 3) API importers. Each importer is called as a subprocess. Errors are collected and displayed summarily at the end. After import, post_import_sanitize is automatically executed. --person is forwarded ONLY to importers with a verified --person flag (_PERSON_AWARE allowlist) — important for shared devices (e.g. a sensor also used by another person), where the device id alone says nothing about the person. Blindly forwarding to every importer is deliberately NOT implemented: most don't know --person and would crash with "unrecognized arguments". A full switch to in-process run() calls (instead of forwarding a subprocess flag) is planned as a larger follow-up change, see openspec/changes/switch-import-all-to-inprocess-run/.

## Data flow

- **Reads:** `imports/_inbox/`, `(Dateien)`, `verschiedene`, `API-Datenquellen`
- **Writes:** `health.db (alle Tabellen basierend auf importierten Daten)`

## Limitations

Dependent on the availability and correctness of individual importers. No central data validation. Errors in subprocesses are not necessarily treated as errors of the main script. No medical interpretation.

## Usage

```bash
python import_all.py
python import_all.py --update
python import_all.py --update --person PER-xxxxxxxx
```
