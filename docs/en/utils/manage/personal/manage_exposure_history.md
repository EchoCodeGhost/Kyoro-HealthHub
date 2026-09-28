# manage_exposure_history.py — Expositionsanamnese verwalten (Zoonosen, Beruf, Sexualanamnese)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/utils/manage/personal/manage_exposure_history.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Documents animal contacts, occupational exposures, childhood environment and sexual history — relevant context when working up unexplained symptoms (zoonoses such as Q fever, Brucella, Leptospira, Echinococcus, Toxoplasma; STI screening history).

## Relevance

Provides health data functions, essential for medical data processing

## Method

Stores in ~/.config/kyoro/exposure_history.json (local only, not in repo). A single nested object rather than a list: {{childhood_environment, animal_contacts[], occupational_exposures[], sexual_history{{multiple_partners, hpv_vaccination, sti_screening[], known_stis[]}}}}. Ctrl+C aborts at any time without data loss.

## Data flow

- **Reads:** `~/.config/kyoro/exposure_history.json`
- **Writes:** `~/.config/kyoro/exposure_history.json`

## Limitations

No automatic risk calculation for ongoing/regular contacts — documentation only, for physicians to use during differential workup. Exception: for a one-time animal contact (`exposure == "einmalig"`), an immediate, lightweight heuristic pathogen hint (ANIMAL_SYNDROME_MAP matched against scripts/analysis/syndromes/*.json) is printed right after saving — not a replacement for the full geo-/time-matched analyse_pathogen_exposure.py, just an instant first pointer for acute single events (e.g. an animal accident) that would otherwise sit unnoticed until the next manual analysis run.

## Usage

```bash
python3 scripts/utils/manage/personal/manage_exposure_history.py show
python3 scripts/utils/manage/personal/manage_exposure_history.py childhood
python3 scripts/utils/manage/personal/manage_exposure_history.py animal add
python3 scripts/utils/manage/personal/manage_exposure_history.py animal delete 2
python3 scripts/utils/manage/personal/manage_exposure_history.py occupation add
python3 scripts/utils/manage/personal/manage_exposure_history.py occupation delete 1
python3 scripts/utils/manage/personal/manage_exposure_history.py sexual set
python3 scripts/utils/manage/personal/manage_exposure_history.py sti add
python3 scripts/utils/manage/personal/manage_exposure_history.py sti delete 1
```
