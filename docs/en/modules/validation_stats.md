# validation_stats.py — Statistische Funktionen für Gerätevalidierung

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/modules/validation_stats.py`

**Evidence tier:** infrastructure (no clinical claim)

## Purpose

Provides statistical functions for cross-device validation: Intraclass Correlation Coefficient (ICC), Mean Absolute Error (MAE), Root Mean Square Error (RMSE), and Bland-Altman analysis.

## Relevance

Provides validation functions, essential for data quality

## Method

ICC(2,1) per Shrout & Fleiss 1979 (Two-Way Random, Single Measures). MAE/RMSE as simple difference measures. Bland-Altman with 95% limits of agreement.

## Data flow

- **Reads:** `Keine`, `Tabellen`, `(reine`, `Mathematik)`
- **Writes:** `Keine Tabellen (gibt Berechnungsergebnisse zurück)`

## Limitations

Pure mathematics without clinical validation. No diagnostic function.

## References

- Shrout PE, Fleiss JL (1979). Intraclass correlations: Uses in assessing rater reliability. Psychological Bulletin, 86(2):420-428. doi:10.1037/0033-2909.86.2.420

## Usage

```bash
from modules.validation_stats import icc_two_way_random, mae, rmse, bland_altman
icc_val = icc_two_way_random(ratings)
mae_val = mae(a, b)
rmse_val = rmse(a, b)
ba_result = bland_altman(a, b)
```
