# manage_travel_history.py — Reiseverlauf verwalten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/personal/manage_travel_history.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Tracks visited regions and time periods for later analysis. Enables correlation of travel with health data.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Stores in ~/.config/kyoro/travel_history.json (local only, not in repo). Supports recording of region, country, start, end, and context.

## Data flow

- **Reads:** `~/.config/kyoro/travel_history.json`
- **Writes:** `~/.config/kyoro/travel_history.json`

## Limitations

No validation of region codes. File is stored outside the repository.

## Usage

```bash
python3 scripts/utils/manage/personal/manage_travel_history.py list
python3 scripts/utils/manage/personal/manage_travel_history.py add
python3 scripts/utils/manage/personal/manage_travel_history.py add "Region Name" YYYY-MM YYYY-MM-DD
python3 scripts/utils/manage/personal/manage_travel_history.py delete 3
python3 scripts/utils/manage/personal/manage_travel_history.py edit 3
```
