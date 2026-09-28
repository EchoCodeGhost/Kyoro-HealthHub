# solo_nights.py — Lookup-Hilfsfunktion für Nächte ohne Partner

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/solo_nights.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides is_solo_night(date) for analysis scripts to detect nights with guaranteed unambiguous microphone/ambient-data attribution (Sleep Cycle snoring, Somneo ambient noise are otherwise not person-specific).

## Relevance

Enables person-specific attribution of microphone/ambient data, important for snoring/noise analyses

## Method

Reads ~/.config/kyoro/solo_nights.json (list of date_from/date_to/ notes), file maintained via manage_solo_nights.py.

## Data flow

- **Reads:** `~/.config/kyoro/solo_nights.json`
- **Writes:** `Keine Tabellen (statischer Lookup)`

## Limitations

Only as complete as the manually maintained config file.

## Usage

```bash
from modules.solo_nights import is_solo_night
if is_solo_night("2026-06-15"):
    ...
```
