# Allergen-Analyse der getrackten Nahrungsmittel (FDDB → nutrition_entries)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/immunology/analyse_allergens.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Classifies food products from FDDB entries by EU-14 allergens via keyword matching and analyses daily allergen load as well as allergen-symptom correlations.

## Relevance

Enables identification and analysis of allergen exposures and allergic reactions, essential for the clinical work-up and treatment of allergies and immune-mediated diseases

## Method

Substring matching on normalised product names against predefined keyword lists (not NLP/ML). Spearman correlation allergen × symptom category. Results are stored in nutrition_allergens (DB write).

## Scoring

```
Allergen categories: EU-14 allergens + oats (gluten-free classification)
Daily load: number of distinct allergens per day
Correlation strength: |r| <0.2 weak | 0.2-0.4 moderate | 0.4-0.7 strong | >0.7 very strong
```

## Data flow

- **Reads:** `nutrition_entries`, `symptoms`
- **Writes:** `nutrition_allergens (DB-Write), Konsolenausgabe (kein analyses/-Datei-Output)`

## Limitations

Heuristic method: Keyword matching is error-prone (false positives/negatives). No blood or skin prick test. No clinical validation of the keyword set. n=1, self-reported data.

## References

- Sampson HA, Aceves S, Bock SA, et al. (2014). Food allergy: a practice parameter update-2014. Journal of Allergy and Clinical Immunology, 134(5), 1016-1025.e43. doi:10.1016/j.jaci.2014.05.013
- Maintz L, Novak N (2007). Histamine and histamine intolerance. American Journal of Clinical Nutrition, 85(5), 1185-1196. doi:10.1093/ajcn/85.5.1185

## Usage

```bash
python analyse_allergens.py
python analyse_allergens.py --help
python analyse_allergens.py --from 2024-01-01 --to 2024-12-31
```
