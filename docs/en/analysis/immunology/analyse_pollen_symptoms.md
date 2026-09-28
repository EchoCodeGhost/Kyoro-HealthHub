# Pollen × Symptom-Korrelation

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/immunology/analyse_pollen_symptoms.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Investigates the association between pollen concentrations and symptom categories using Spearman correlation, lag analysis and Person-Whitney U.

## Relevance

Enables correlation of pollen flight data with individual symptoms, essential for distinguishing pollen-induced allergic reactions from other triggers and personalized allergy therapy

## Method

Spearman rank correlation per pollen type × symptom category with lag -2..+2 days; Person-Whitney U for high vs. low pollen days. No multiple-comparison adjustment.

## Scoring

```
Pollen types: birch | alder | grasses | mugwort | ragweed | olive | hazel | ash | rye (Open-Meteo/DWD)
Pollen load: low | moderate | high | very high (provider-specific)
Lag analysis: -2 to +2 days (pollen to symptom correlation)
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Data flow

- **Reads:** `pollen`, `pollen_dwd`, `symptoms`
- **Writes:** `analyses/immunology/*.{md,png}`

## Limitations

Heuristic method: Observational correlations only; no clinically validated allergy thresholds; p<0.2 reporting threshold is considerably more liberal than standard p<0.05 (increased false-positive rate); sensitivity depends on diary completeness; no multiple testing correction.

## References

- D'Amato G, Cecchi L, Bonini S, Nunes C, Annesi-Maesano I, Behrendt H, Liccardi G, Popov T, Van Cauwenberge P (2007). Allergenic pollen and pollen allergy in Europe. Allergy, 62(9):976-990. doi:10.1111/j.1398-9995.2007.01393.x
- Luyten A, Bürgler A, Glick S, Kwiatkowski M, Gehrig R, Beigi M, Hartmann K, Eeftens M (2024). Ambient pollen exposure and pollen allergy symptom severity in the EPOCHAL study. Allergy, 79(7), 1908-1920. doi:10.1111/all.16130

## Usage

```bash
python analyse_pollen_symptoms.py
python analyse_pollen_symptoms.py --help
python analyse_pollen_symptoms.py --from 2024-01-01 --to 2024-12-31
```
