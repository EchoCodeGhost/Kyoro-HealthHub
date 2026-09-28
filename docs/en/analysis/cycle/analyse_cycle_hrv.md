# Cycle- & HRV-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/cycle/analyse_cycle_hrv.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses cycle length trends from WomanLog, phase-specific HRV / energy / PEM risk, cycle symptoms and Oura cycle insights.

## Relevance

Analyzes cycle-related changes in heart rate variability, essential for understanding the autonomic nervous system and identifying hormonal influences on cardiovascular health

## Method

Rough 4-phase assignment from cycle start date (fixed day boundaries); group comparison HRV/stress by phase. Oura cycle insights are used directly without cross-validation. No formally validated thresholds.

## Scoring

```
Cycle length: short <24 days | normal 21-35 days | long >38 days (FIGO 2018)
Phase assignment: menstruation day 1-5 | follicular day 6-12 | ovulation day 13-15 | luteal day 16+
```

## Data flow

- **Reads:** `reproductive_health`, `symptoms`, `oura_cycle_insights`, `daily_stress`
- **Writes:** `analyses/cycle/*.{md,png} (kein DB-Write)`

## Limitations

Heuristic method: Fixed phase boundaries (day 1–5, 6–12, 13–15, 16+) ignore individual variability. Oura phase assignment is proprietary and not published-validated. n=1, exploratory. Cycle length boundaries: short < 24 days / long > 38 days per FIGO 2018 (Munro et al., Int J Gynaecol Obstet 2018, doi:10.1002/ijgo.12666). All phase boundaries (days 1–5, 6–12, 13–15) are heuristic, not hormonally confirmed.

## References

- Munro MG et al. (2018). FIGO classification system for causes of abnormal
- Munro MG, Critchley HOD, Fraser IS (2018). The two FIGO systems for normal and abnormal uterine bleeding symptoms and classification of causes of abnormal uterine bleeding in the reproductive years: 2018 revisions. International Journal of Gynecology & Obstetrics, 143(3):393-408. doi:10.1002/ijgo.12666

## Usage

```bash
python analyse_cycle_hrv.py
python analyse_cycle_hrv.py --help
python analyse_cycle_hrv.py --from 2024-01-01 --to 2024-12-31
```
