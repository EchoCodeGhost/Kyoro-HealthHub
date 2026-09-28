# manage_family_history.py — Familienanamnese und genetische Vorbelastungen erfassen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/personal/manage_family_history.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Documents conditions and findings in blood relatives to reveal genetic predispositions and inheritance patterns. Supports two views: by relative or by condition (cluster view).

## Relevance

Provides health data functions, essential for medical data processing

## Method

Stores in ~/.config/kyoro/family_history.json (local only, not in repo). Each entry: relative, condition, status (confirmed/suspected), side (maternal/paternal), age at onset, notes. Ctrl+C aborts without data loss.

## Data flow

- **Reads:** `~/.config/kyoro/family_history.json`
- **Writes:** `~/.config/kyoro/family_history.json`

## Limitations

No genetic database — purely anamnetic documentation. Not committed; never treat as confirmed diagnosis in others.

## Usage

```bash
python3 scripts/utils/manage/personal/manage_family_history.py list
python3 scripts/utils/manage/personal/manage_family_history.py list --by-condition
python3 scripts/utils/manage/personal/manage_family_history.py add
python3 scripts/utils/manage/personal/manage_family_history.py delete 3
python3 scripts/utils/manage/personal/manage_family_history.py edit 3
python3 scripts/utils/manage/personal/manage_family_history.py export
```
