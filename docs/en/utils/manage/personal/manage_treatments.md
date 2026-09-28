# manage_treatments.py — Therapie-Einträge verwalten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/personal/manage_treatments.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Manages session entries (physiotherapy, osteopathy, massage, etc.). Supports single appointments with time or ongoing courses over days/weeks. Data can be correlated with HRV/symptoms.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Single appointments (e.g., osteopathy 15:00-16:00) and ongoing courses are captured via date_from/date_to fields. Time is optional. Stores in ~/.config/kyoro/treatment_history.json (local only, not in repo).

## Data flow

- **Reads:** `~/.config/kyoro/treatment_history.json`
- **Writes:** `~/.config/kyoro/treatment_history.json`

## Limitations

Local file only. No automatic validation.

## Usage

```bash
python3 scripts/utils/manage/personal/manage_treatments.py list [--active]
python3 scripts/utils/manage/personal/manage_treatments.py add
python3 scripts/utils/manage/personal/manage_treatments.py edit 3
python3 scripts/utils/manage/personal/manage_treatments.py stop 3
python3 scripts/utils/manage/personal/manage_treatments.py delete 3
python3 scripts/utils/manage/personal/manage_treatments.py export [--active]
```
