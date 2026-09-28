# manage_allergies.py — Allergien und Unverträglichkeiten verwalten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/personal/manage_allergies.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Documents known allergies and intolerances (drug, insect venom, inhalation, contact, food, autoimmune) for doctor's letters and AI-assisted history taking.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Stores in ~/.config/kyoro/allergies.json (local only, not in repo). Each entry: allergen, type, reaction, severity, diagnosed, notes. Ctrl+C aborts at any time without data loss.

## Data flow

- **Reads:** `~/.config/kyoro/allergies.json`
- **Writes:** `~/.config/kyoro/allergies.json`

## Limitations

No clinical validation — documentation only. Always note cross-reactivity and alternatives for drug allergies in the notes field.

## Usage

```bash
python3 scripts/utils/manage/personal/manage_allergies.py list
python3 scripts/utils/manage/personal/manage_allergies.py add
python3 scripts/utils/manage/personal/manage_allergies.py edit 3
python3 scripts/utils/manage/personal/manage_allergies.py delete 3
python3 scripts/utils/manage/personal/manage_allergies.py export
```
