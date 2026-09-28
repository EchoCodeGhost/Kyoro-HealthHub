# manage_clinical_events.py — Gesundheitsereignisse verwalten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/personal/manage_clinical_events.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Manages health events (e.g., infections, treatments, procedures) in a local JSON file. Allows adding, editing, deleting, and exporting events for documentation.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Stores events in ~/.config/kyoro/clinical_events.json (local only, not committed to repo). Supports various event types with date, description, and tags. Export as Markdown table available.

## Data flow

- **Reads:** `~/.config/kyoro/clinical_events.json`
- **Writes:** `~/.config/kyoro/clinical_events.json`

## Limitations

Local file only, not stored in database or version control. No automatic validation of inputs.

## Usage

```bash
python3 scripts/utils/manage/personal/manage_clinical_events.py list
python3 scripts/utils/manage/personal/manage_clinical_events.py add
python3 scripts/utils/manage/personal/manage_clinical_events.py edit 3
python3 scripts/utils/manage/personal/manage_clinical_events.py delete 3
python3 scripts/utils/manage/personal/manage_clinical_events.py export
```
