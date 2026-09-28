# Luftdruckveränderung × Migraine-Risiko

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/neurology/analyse_migraine_pressure.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Examines the relationship between atmospheric pressure changes and migraine events using a ±1-day window analysis and non-parametric group comparison.

## Relevance

Enables neurological analysis, essential for nervous system diagnostics

## Method

Intraday variability (pressure_max − pressure_min) and previous-day delta; Personen-Whitney U test for pressure values on migraine days vs. migraine-free days.

## Scoring

```
Pressure variability: (pressure_max - pressure_min) + Δ to previous day
Statistical test: Personen-Whitney U (non-parametric group comparison)
Minimum events: >=20 migraine events required for valid analysis
```

## Data flow

- **Reads:** `weather_station`, `sessions`, `session_metrics`
- **Writes:** `analyses/neurology/migraine_pressure_*.{md,png}`

## Limitations

Heuristic method: Exploratory analysis; minimum 20 migraine events required for valid conclusions; no multivariate exclusion of confounding triggers; no directional causality derivable; Hoffmann 2011 cited as background reference — no validated threshold implemented in code.

## References

- Hoffmann J, Lo H, Neeb L, Martus P, Reuter U (2011). Weather sensitivity in migraineurs. Journal of Neurology, 258(4):596-602. doi:10.1007/s00415-010-5798-7 (beobachtet: Luftdruckabfall <755 mmHg als möglicher Auslöser; kein RCT-Nachweis der Kausalität; im Skript kein strikter Schwellenwert implementiert — nur explorative Gruppenanalyse)

## Usage

```bash
python analyse_migraine_pressure.py
python analyse_migraine_pressure.py --help
python analyse_migraine_pressure.py --from 2024-01-01 --to 2024-12-31
```
