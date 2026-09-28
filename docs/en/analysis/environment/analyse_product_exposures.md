# Exposition × Symptom-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/environment/analyse_product_exposures.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Cross-analyses product exposures (medications, cosmetics, dental care, household products) against symptom entries: calendar, substance frequency, co-occurrence and time-lag analysis (0–2 days).

## Relevance

Analyzes exposures to household and consumer products, essential for identifying potential toxic exposures and allergic triggers

## Method

Co-occurrence exposure × symptom as ratio (days with/without); Spearman correlation for quantitative symptom scores. Time lag 0–2 days. No confounder control, no statistical test with correction level.

## Scoring

```
Exposure categories: medication | cosmetics | dental | household | food | other
Time lag: 0 days | +1 day | +2 days (exposure to symptom onset)
Co-occurrence: days with exposure AND symptoms vs days with exposure only
```

## Data flow

- **Reads:** `product_exposures`, `symptoms`, `weather_station`
- **Writes:** `Konsolenausgabe (kein analyses/-Verzeichnis, kein DB-Write)`

## Limitations

Heuristic method: Causality cannot be established. Exposure logging is incomplete (manual input). n=1, exploratory hypothesis generation.

## References

- Simons FER, Ebisawa M, Sanchez-Borges M, et al. (2015). 2015 update of the evidence base: World Allergy Organization anaphylaxis guidelines. World Allergy Organization Journal, 8:32. doi:10.1186/s40413-015-0080-1
- Worm M, Moneret-Vautrin A, Scherer K, et al. (2014). First European data from the network of severe allergic reactions (NORA). Allergy, 69(10):1397-1404. doi:10.1111/all.12475

## Usage

```bash
python analyse_product_exposures.py
python analyse_product_exposures.py --help
python analyse_product_exposures.py --from 2024-01-01 --to 2024-12-31
```
