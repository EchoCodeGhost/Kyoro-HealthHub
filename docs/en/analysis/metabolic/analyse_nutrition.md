# Nutritions-Analyse (FDDB)

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/metabolic/analyse_nutrition.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Analyses FDDB nutrition data for macronutrient distribution, calorie trend and meal timing, as well as Spearman correlation with next-day HRV and energy.

## Relevance

Enables metabolic analysis, essential for metabolic health

## Method

Daily aggregate from nutrition_daily; Spearman rank correlation (pure Python) between nutrition variables and next-day HRV/energy; own calorie target (KCAL_ZIEL=2000 kcal) as reference.

## Scoring

```
Kalorie-Klassifikation (heuristisch, projektintern):
<1500 kcal = Unterversorgung, 1500–2500 kcal = Normal, >2500 kcal = Erhöht
Referenz: KCAL_ZIEL = 2000 kcal (eigener Zielwert, nicht DGE-kalibriert)
Späte Mahlzeiten: Stunden-Stempel ≥21:00 Uhr = "spät" (heuristisch)
Basis: projektintern; DGE/EFSA-Referenzwerte für Makronährstoffe existieren, aber im Skript nicht umgesetzt.
```

## Data flow

- **Reads:** `nutrition_daily`, `measurements`, `symptoms`
- **Writes:** `analyses/metabolic/nutrition_*.{md,png}`

## Limitations

Heuristic method: Own calorie target (2000 kcal) not individually calibrated; calorie bands (1500/2500 kcal) heuristic without DGE/WHO reference value comparison; late meal threshold 21:00 without published validation; FDDB data dependent on manual logging; lag correlation exploratory without multiple testing correction.

## References

- FAO/WHO/UNU 2001, Energy requirements — Human energy requirements; ISBN:92-5-105212-5
- Almoosawi S, Vingeliene S, Karagounis LG, Pot GK (2016). Chrono-nutrition: a review of current evidence from observational studies on global trends in time-of-day of energy intake and its association with obesity. Proceedings of the Nutrition Society, 75(4):487-500. doi:10.1017/S0029665116000306

## Usage

```bash
python analyse_nutrition.py
python analyse_nutrition.py --help
python analyse_nutrition.py --from 2024-01-01 --to 2024-12-31
```
