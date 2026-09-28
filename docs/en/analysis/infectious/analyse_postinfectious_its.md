# Interrupted Time Series (ITS) Analysis

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/infectious/analyse_postinfectious_its.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Compares HRV (RMSSD), resting heart rate and sleep quality before and after a configurable cut-off date using segmented linear regression (interrupted time series).

## Relevance

Supports infection-related data analysis and decision-making through systematic processing of wearable and symptom data

## Method

Segmented linear regression Y = β₀ + β₁·t + β₂·D + β₃·(t−t_c)·D; OLS in Pure-Python. Cohen's d for effect size. No confounder adjustment.

## Scoring

```
Model: Y = β₀ + β₁·t + β₂·D + β₃·(t−t_c)·D where D=1 if t>=t_c (cutoff date)
Effect size: Cohen's d 0.2 small | 0.5 medium | 0.8 large
Segment trend: β₁ pre-interruption | β₃ post-interruption change
```

## Data flow

- **Reads:** `polar_nightly_hrv`, `measurements`, `sessions`, `session_metrics`
- **Writes:** `analyses/infectious/*.{md,png}`

## Limitations

Heuristic method: No causal inference; confounders (seasonality, device changes) not controlled. Minimum data requirement: ≥30 days per segment recommended.

## References

- Penfold RB, Zhang F (2013). Use of Interrupted Time Series Analysis in Evaluating Health Care Quality Improvements. Academic Pediatrics, 13(6 Suppl):S38-S44. doi:10.1016/j.acap.2013.08.002 (ITS-Methode)
- Cohen J (1988). Statistical Power Analysis for the Behavioral Sciences (2nd ed.). Lawrence Erlbaum Associates. (Cohen's d: 0.2 small, 0.5 medium, 0.8 large)

## Usage

```bash
python analyse_postinfectious_its.py
python analyse_postinfectious_its.py --help
python analyse_postinfectious_its.py --from 2024-01-01 --to 2024-12-31
```
