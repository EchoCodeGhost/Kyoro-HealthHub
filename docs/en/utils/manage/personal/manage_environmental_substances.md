# manage_environmental_substances.py — Umweltsubstanzen verwalten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/personal/manage_environmental_substances.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Manages environmental substances (cosmetics, household products) for trigger tracking. Enables recording of substances and their usage for correlation with symptoms. Supports automatic INCI ingredient lookup via Open Beauty Facts.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Stores in ~/.config/kyoro/environmental_substances.json (local only, not in repo). Similar to manage_medications.py, but with custom fields for cosmetics and household products. Automatically looks up INCI ingredients when adding (can be skipped with --no-lookup). Existing entries can be updated with refresh-ingredients <nr>.

## Data flow

- **Reads:** `~/.config/kyoro/environmental_substances.json`, `Open`, `Beauty`, `Facts`, `API`
- **Writes:** `~/.config/kyoro/environmental_substances.json`

## Limitations

Local file only. No automatic validation. INCI lookup requires network access and may fail if the product is not known in Open Beauty Facts.

## Usage

```bash
python3 scripts/utils/manage/personal/manage_environmental_substances.py list [--active]
python3 scripts/utils/manage/personal/manage_environmental_substances.py add [--no-lookup]
python3 scripts/utils/manage/personal/manage_environmental_substances.py edit 3
python3 scripts/utils/manage/personal/manage_environmental_substances.py stop 3
python3 scripts/utils/manage/personal/manage_environmental_substances.py delete 3
python3 scripts/utils/manage/personal/manage_environmental_substances.py refresh-ingredients 3
python3 scripts/utils/manage/personal/manage_environmental_substances.py export [--active]
```
