# Status der Pipeline und Personenliste für die TUI, nur lesend.

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/tui/status.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Determines the state of import, compute and analysis for the dashboard, and the persons for the person selection, without writing anything.

## Relevance

Shows whether analyses rest on current data

## Method

Reads import_log, compute_log and analysis_log through modules.db.open_readonly. Timestamps are converted to UTC and never compared as text; without a time zone they count as UTC, like datetime('now'). Neither post_import_* nor compute_* rows count as imports. Compute is outdated when an import with new rows is newer than the script with the oldest success. On-demand runs do not count.

## Data flow

- **Reads:** `import_log`, `compute_log`, `analysis_log`, `alle`, `Tabellen`, `mit`, `person-Spalte`, `identity.db`
- **Writes:** `Nichts`

## Limitations

read_person_choices can take long with a cold disk cache and belongs in a background worker. Unreadable data counts as unknown. Accessing OWN_PERSON_ID already loads identity_resolver, which ensures the schema of identity.db.

## Usage

```bash
status = read_pipeline_status()
status.compute_outdated
choices = read_person_choices()
```
