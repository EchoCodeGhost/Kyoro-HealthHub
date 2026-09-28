# Schlafatmungs-Analyse — Atemstörungen, SpO₂ und Schlafapnoe-Risiko

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/sleep/analyse_sleep_respiration.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses nightly breathing disturbances from Apple Watch and Oura, SpO₂ and respiratory rate and their association with sleep stages as a heuristic sleep apnoea risk screening.

## Relevance

Enables sleep analysis, essential for sleep research and health monitoring

## Method

Correlates sleep_breathing_disturbances (Apple), breathing_disturbance_index (Oura, kept separate due to differing scale), SpO₂ and respiratory_rate with sleep stages; AHI reference values per AASM classification (5/15/30) as orientation only, not diagnosis. Sleep stage norms from the shared, cited modules/sleep_norms.py (deep 13-23%, REM 18-25%, same values as analyse_sleep_stages.py).

## Scoring

```
Breathing disturbances: frequency per night (Apple Watch count)
SpO2: >=95% normal | 90-94% notable | <90% critical (night average)
Sleep stages: N3/deep and REM normal ranges — see modules/sleep_norms.py
```

## Data flow

- **Reads:** `measurements`, `oura_sleep_model`, `sleep_hypnogram`
- **Writes:** `analyses/sleep/*.{md,png}`

## Limitations

Heuristic method: Apple Watch does not provide a validated AHI; AHI thresholds (5/15/30) are AASM reference values (Berry 2012) applied here to non-PSG data. Sleep stage norms (see modules/sleep_norms.py) are population-mean-based, not individually validated targets.

## References

- Berry RB, Budhiraja R, Gottlieb DJ et al. (2012). Rules for Scoring Respiratory Events in Sleep: Update of the 2007 AASM Manual for the Scoring of Sleep and Associated Events. Journal of Clinical Sleep Medicine, 8(5):597-619. doi:10.5664/jcsm.2172
- Boulos MG, Jairam T, Kendzerska T, Im J, Mekhael A, Murray BJ (2019). Normal polysomnography parameters in healthy adults: a systematic review and meta-analysis. Lancet Respiratory Medicine, 7(6):533-543. doi:10.1016/S2213-2600(19)30057-8 (Herleitung der Schlafstadien-Normbereiche siehe modules/sleep_norms.py)

## Usage

```bash
python analyse_sleep_respiration.py
python analyse_sleep_respiration.py --help
python analyse_sleep_respiration.py --from 2024-01-01 --to 2024-12-31
```
