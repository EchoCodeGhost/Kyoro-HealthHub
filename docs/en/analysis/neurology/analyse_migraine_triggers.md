# Migraine — Multi-Trigger-Analyse

> GENERATED FROM DOCSTRING — DO NOT EDIT BY HAND.  
> Source: `scripts/analysis/neurology/analyse_migraine_triggers.py`

**Evidence tier:** heuristic (deliberate design from domain knowledge, no formal literature or validation basis)

## Purpose

Identifies migraine triggers from sleep, HRV, weather and cycle data via lag correlation (±3 days) and non-parametric group comparison.

## Relevance

Enables neurological analysis, essential for nervous system diagnostics

## Method

Lag correlation per trigger variable; Personen-Whitney U test (migraine day vs. non-migraine day); relative risk in worst trigger quartile; own combined risk score.

## Scoring

```
Kombinierter Trigger-Risiko-Score (heuristisch, projektintern):
Signifikante Trigger (p<0.05) → gewichteter Komposit-Score
Schwere-Klassifikation: ≥3 = "schwer" (heuristisch, kein validierter Schwellenwert)
Quartil-Risiko: relatives Risiko im schlechtesten Trigger-Quartil
Basis: projektintern, keine klinische Validierung.
```

## Data flow

- **Reads:** `sessions`, `session_metrics`, `measurements`, `weather_station`, `oura_cycle_insights`, `reproductive_health`, `symptoms`
- **Writes:** `analyses/neurology/migraine_triggers_*.{md,png}`

## Limitations

Heuristic method: Exploratory analysis without multiple testing correction; causal trigger identification not possible; severity threshold ≥3 for "severe migraine" is heuristic without guideline basis; cycle data only if Oura cycle insights or reproductive health present; migraine events required in sessions table.

## References

- Goadsby PJ, Holland PR, Martins-Oliveira M, Hoffmann J, Schankin C, Akerman S (2017). Pathophysiology of Migraine: A Disorder of Sensory Processing. Physiological Reviews, 97(2):553-622. doi:10.1152/physrev.00034.2015
- Scher AI, Stewart WF, Liberman J, Lipton RB (1998). Prevalence of Frequent Headache in a Population Sample. Headache: The Journal of Head and Face Pain, 38(7):497-506. doi:10.1046/j.1526-4610.1998.3807497.x

## Usage

```bash
python analyse_migraine_triggers.py
python analyse_migraine_triggers.py --help
python analyse_migraine_triggers.py --from 2024-01-01 --to 2024-12-31
```
