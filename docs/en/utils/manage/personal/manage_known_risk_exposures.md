# manage_known_risk_exposures.py — Persönliche Dauerrisiko-Expositionen verwalten

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/personal/manage_known_risk_exposures.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Records chronic or cumulative personal risk exposures (animal husbandry, occupation, residence, hobbies) that raise the probability of specific infectious diseases above population average. Used by analyse_outbreak_exposure.py to adjust LLM weightings.

## Relevance

Provides health data functions, essential for medical data processing

## Method

Stores in ~/.config/kyoro/known_risk_exposures.json (local only, not in repo). Each entry has: slug (pathogen key), description, level (high/medium/low), notes. Ctrl+C aborts at any time without data loss.

## Data flow

- **Reads:** `~/.config/kyoro/known_risk_exposures.json`
- **Writes:** `~/.config/kyoro/known_risk_exposures.json`

## Limitations

Slugs must match the syndrome slugs used in analyse_outbreak_exposure.py.

## Usage

```bash
python3 scripts/utils/manage/personal/manage_known_risk_exposures.py list
python3 scripts/utils/manage/personal/manage_known_risk_exposures.py add
python3 scripts/utils/manage/personal/manage_known_risk_exposures.py delete 2
python3 scripts/utils/manage/personal/manage_known_risk_exposures.py edit 2
```
