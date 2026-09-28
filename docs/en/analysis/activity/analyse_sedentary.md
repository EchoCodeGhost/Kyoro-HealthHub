# Sitzverhalten & Bewegungsunterbrechungen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/activity/analyse_sedentary.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses daily standing and sitting behaviour from Apple Watch (stand hours, standing time) and Polar activity levels and their correlation with next-day HRV.

## Relevance

Enables activity data analysis, essential for movement and fitness analysis

## Method

Aggregation of stand_hour (Apple Health) and stand_time_min; Spearman rank correlation with HRV; custom target: ≥12 stand hours/day (Apple Watch criterion).

## Scoring

```
Stand goal: >=12 stand-hours/day (Apple Watch criterion). Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Data flow

- **Reads:** `measurements`
- **Writes:** `analyses/activity/*.{md,png}`

## Limitations

Heuristic method: Threshold of 12 stand hours follows Apple Watch product definition, not clinical studies. No adjusted targets for persons with exercise intolerance.

## References

- Biswas A, Oh PI, Faulkner GE et al. (2015). Sedentary Time and Its Association With Risk for Disease Incidence, Mortality, and Hospitalization in Adults. Annals of Internal Medicine, 162(2):123-132. doi:10.7326/M14-1651
- Healy GN, Dunstan DW, Salmon J, Cerin E, Shaw JE, Zimmet PZ, Owen N (2008). Breaks in Sedentary Time: Beneficial Associations With Metabolic Risk. Diabetes Care, 31(4):661-666. doi:10.2337/dc07-2046

## Usage

```bash
python analyse_sedentary.py
python analyse_sedentary.py --help
python analyse_sedentary.py --from 2024-01-01 --to 2024-12-31
```
