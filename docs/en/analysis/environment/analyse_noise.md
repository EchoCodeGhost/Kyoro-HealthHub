# Lärmbelastung & Symptom-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/environment/analyse_noise.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses ambient noise exposure (Apple Watch dBASPL) for daily averages, high-noise days, time-of-day patterns and correlation with migraine and neurological symptoms.

## Relevance

Examines the effects of noise exposure on stress levels, sleep quality, and cardiovascular health, essential for identifying environment-related stress factors

## Method

Daily and hourly aggregation of audio_exposure_env; WHO Environmental Noise 2018 Lden >55 dB(A) as orientation threshold; own critical threshold 70 dB; correlation with symptoms and sessions (migraine).

## Scoring

```
Noise level: <55 dB acceptable | 55-70 dB elevated | >70 dB critical (WHO guideline approximation)
High-noise day: >70 dB for >=1 hour
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Data flow

- **Reads:** `measurements`, `symptoms`, `sessions`
- **Writes:** `analyses/environment/noise_*.{md,png}`

## Limitations

Heuristic method: Apple Watch microphone measures instantaneous ambient sound level (dBSPL), not the time-weighted Lden of WHO 2018; own critical threshold 70 dB is project-internal; 55 dB used as dBSPL approximation of Lden guideline (not methodologically equivalent); correlation is exploratory without significance tests.

## References

- WHO Regional Office for Europe. Environmental Noise Guidelines for the European Region. Copenhagen: WHO/Europe; 2018. doi:https://iris.who.int/handle/10665/279952

## Usage

```bash
python analyse_noise.py
python analyse_noise.py --help
python analyse_noise.py --from 2024-01-01 --to 2024-12-31
```
