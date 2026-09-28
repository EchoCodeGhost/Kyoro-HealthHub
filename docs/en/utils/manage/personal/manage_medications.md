# manage_medications.py — Medikamente und Ergänzungsmittel verwalten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/personal/manage_medications.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Manages medications, supplements, and herbal preparations in a local JSON file. Enables tracking of intake periods and dosages for correlation with health data.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Stores in KYORO_CONFIG_DIR/medication_history.json (local only, not in repo). Supports various categories and dosage specifications.

## Data flow

- **Reads:** `KYORO_CONFIG_DIR/medication_history.json`
- **Writes:** `KYORO_CONFIG_DIR/medication_history.json`

## Limitations

Local file only. No automatic validation.

## Usage

```bash
python3 scripts/utils/manage/personal/manage_medications.py list [--active]
python3 scripts/utils/manage/personal/manage_medications.py add
python3 scripts/utils/manage/personal/manage_medications.py edit 3
python3 scripts/utils/manage/personal/manage_medications.py stop 3
python3 scripts/utils/manage/personal/manage_medications.py delete 3
python3 scripts/utils/manage/personal/manage_medications.py export [--active]
```
