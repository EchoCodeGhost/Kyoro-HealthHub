# manage_solo_nights.py — Nächte ohne Partner (Bett geteilt ja/nein) verwalten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/personal/manage_solo_nights.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Tracks nights slept alone. Sleep Cycle snoring and Somneo ambient noise are not person-specific (microphone also picks up partner snoring/noise) — this registry lets analysis scripts flag nights with guaranteed unambiguous attribution.

## Relevance

Enables person-specific attribution of microphone/ambient data, important for snoring/noise analyses

## Method

Stores in ~/.config/kyoro/solo_nights.json (local only, not in repo). Each entry: date_from, date_to (same value for a single night), notes. is_solo_night(date) in modules/solo_nights.py checks a date against the list.

## Data flow

- **Reads:** `~/.config/kyoro/solo_nights.json`
- **Writes:** `~/.config/kyoro/solo_nights.json`

## Limitations

Purely manual entry, no automatic derivation from sensor data.

## Usage

```bash
python3 scripts/utils/manage/personal/manage_solo_nights.py list
python3 scripts/utils/manage/personal/manage_solo_nights.py add
python3 scripts/utils/manage/personal/manage_solo_nights.py add YYYY-MM-DD [YYYY-MM-DD]
python3 scripts/utils/manage/personal/manage_solo_nights.py delete 3
python3 scripts/utils/manage/personal/manage_solo_nights.py edit 2
```
