# Cyclephase × Sleepqualität × Body temperature

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cycle/analyse_cycle_sleep.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Investigates the association between cycle phase, sleep quality and body temperature using Kruskal-Wallis test and group comparison across 4 cycle phases.

## Relevance

Examines the influence of the menstrual cycle on sleep quality and circadian rhythms, essential for identifying cycle-related sleep disorders and optimizing sleep hygiene

## Method

Phase assignment from oura_cycle_insights (preferred) or WomanLog estimation (fixed day boundaries). Kruskal-Wallis test (non-parametric) for group differences. No clinically validated thresholds for phase-specific sleep differences.

## Scoring

```
Phase assignment: menstruation day 1-5 | follicular day 6-13 | ovulation day 14 | luteal day 15-28
Statistical test: Kruskal-Wallis (non-parametric group comparison)
```

## Data flow

- **Reads:** `oura_cycle_insights`, `womanlog_cycles`, `sleep_cycle_full`, `oura_sleep`, `oura_readiness`
- **Writes:** `analyses/cycle/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: Phase assignment from wearable is approximate. Sleep source varies by data availability. No hormone measurements to confirm phases. n=1.

## References

- Shechter A, Boivin DB (2010). Sleep, Hormones, and Circadian Rhythms throughout the Menstrual Cycle in Healthy Women and Women with Premenstrual Dysphoric Disorder. International Journal of Endocrinology, 2010:259345. doi:10.1155/2010/259345
- de Zambotti M, Baker FC, Colrain IM (2015). Validation of Sleep-Tracking Technology Compared with Polysomnography in Adolescents. Sleep, 38(9):1461-1468. doi:10.5665/sleep.4990

## Usage

```bash
python analyse_cycle_sleep.py
python analyse_cycle_sleep.py --help
python analyse_cycle_sleep.py --from 2024-01-01 --to 2024-12-31
```
