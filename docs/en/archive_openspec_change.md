# archive_openspec_change.py — Archive completed OpenSpec change

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/archive_openspec_change.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Moves a completed OpenSpec change directory to the archive/ folder and documents the completion.

## Relevance

Provides health data functions, essential for medical data processing

## Method

1. Validates that all tasks.md checkboxes are checked 2. Moves directory from changes/ to changes/archive/ 3. Creates archive metadata with completion date

## Data flow

- **Reads:** `openspec/changes/<change_name>/`
- **Writes:** `openspec/changes/archive/<change_name>/`

## Limitations

No automatic validation of task checkboxes — manual review required. No rollback after archiving.

## Usage

```bash
python3 scripts/archive_openspec_change.py pseudonymize-device-person-identifiers
python3 scripts/archive_openspec_change.py --list-pending
```
