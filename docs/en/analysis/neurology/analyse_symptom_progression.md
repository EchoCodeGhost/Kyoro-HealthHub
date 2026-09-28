# Symptomverlauf & Correlationen

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/neurology/analyse_symptom_progression.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses symptom progression over time: trends per category, good/bad-day profiles and correlation with objective biomarkers (HRV, sleep, stress).

## Relevance

Enables neurological analysis, essential for nervous system diagnostics

## Method

30/90-day moving averages per symptom category; good/bad-day split by energy budget quartile; Spearman rank correlation with HRV/sleep/stress.

## Scoring

```
Trend analysis: 30/90-day moving averages per symptom category
Good/bad day profiles: top vs bottom quartile by energy budget
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Data flow

- **Reads:** `symptoms`, `daily_stress`
- **Writes:** `analyses/neurology/*.{md,png}`

## Limitations

Heuristic method: Subjective symptom scaling; no clinically validated symptom scores; diary completeness determines interpretability. No adjustment for seasonal influences.

## References

- Fukuda K, Straus SE, Hickie I, Sharpe MC, Dobbins JG, Komaroff A (1994). The Chronic Fatigue Syndrome: A Comprehensive Approach to Its Definition and Study. Annals of Internal Medicine, 121(12):953-959. doi:10.7326/0003-4819-121-12-199412150-00009
- Carruthers BM, van de Sande MI, De Meirleir KL et al. (2011). Myalgic encephalomyelitis: International Consensus Criteria. Journal of Internal Medicine, 270(4):327-338. doi:10.1111/j.1365-2796.2011.02428.x

## Usage

```bash
python analyse_symptom_progression.py
python analyse_symptom_progression.py --help
python analyse_symptom_progression.py --from 2024-01-01 --to 2024-12-31
```
