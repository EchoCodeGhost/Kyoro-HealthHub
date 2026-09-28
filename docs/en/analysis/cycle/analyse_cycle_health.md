# Menstrual Cycle Health Analysis

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cycle/analyse_cycle_health.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses cycle length statistics, phase-specific HRV (follicular vs. luteal), symptom burden per phase, temperature curve from Oura skin temperature and correlations.

## Relevance

Enables comprehensive analysis of cycle-related health patterns, including hormone patterns, symptom correlations, and physiological changes, essential for personalized gynecological care

## Method

Phase assignment from reproductive_health events (period_start / ovulation) with configurable day boundaries; Pearson correlation HRV × symptoms per phase. No formally validated thresholds for phase-specific HRV.

## Scoring

```
Cycle length: short <24 days | normal 21-35 days | long >38 days (FIGO 2018)
Phase assignment: menstruation day 1-5 | follicular day 6-12 | ovulation day 13-15 | luteal day 16+
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Data flow

- **Reads:** `reproductive_health`, `oura_temperature_raw`, `oura_cycle_insights`, `polar_nightly_hrv`, `symptoms`, `measurements`
- **Writes:** `analyses/cycle/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: Phase assignment is an estimate, not a hormonally confirmed measurement. Cycle length variation affects phase boundaries. n=1, no control group. Regular cycle: 21–35 days per WHO/ACOG consensus (Munster et al. 2012,

## References

- Munster K, Schmidt L, Helm P (1992). Length and variation in the menstrual cycle - a cross-sectional study from a Danish county. BJOG, 99(5):422-429. doi:10.1111/j.1471-0528.1992.tb13762.x
- ACOG Practice Bulletin No. 150 (2015). Early Pregnancy Loss. Obstet Gynecol 125(5):1258-1267.

## Usage

```bash
python analyse_cycle_health.py
python analyse_cycle_health.py --help
python analyse_cycle_health.py --from 2024-01-01 --to 2024-12-31
```
